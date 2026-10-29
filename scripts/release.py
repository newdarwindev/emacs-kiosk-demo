#!/usr/bin/env python3
"""Prepare and reconcile immutable-by-workflow public demo releases. No overwrite API."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile

REPO = 'newdarwindev/emacs-kiosk-demo'
SCREENSHOTS = ['01-boot-emacs', '02-typed-marker', '03-cancel-recovery',
               '04-buffer-switch', '05-return-to-editor', '06-slack-fixture', '07-tmux-output']
EVIDENCE_FILES = {name + ext for name in SCREENSHOTS for ext in ('.png', '-ocr.txt')} | {
    'SHA256SUMS', 'EVIDENCE-SHA256SUMS', 'build-metadata.txt', 'packages-requested.txt',
    'packages-resolved.txt', 'qemu-command.json', 'qemu-serial.log', 'qemu.log', 'test-report.json'}
ASSETS = {'emacs-kiosk-x86_64.iso', 'boot-evidence.tar.gz', 'source-sha.txt',
          'build-metadata.json', 'SHA256SUMS'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(path):
    with path.open('rb') as file:
        return hashlib.file_digest(file, 'sha256').hexdigest()


def identity(env):
    require(env.get('GITHUB_REPOSITORY') == REPO, 'Unexpected repository')
    require(env.get('GITHUB_REF') == 'refs/heads/main', 'Releases require main')
    require(env.get('GITHUB_EVENT_NAME') in {'push', 'workflow_dispatch'}, 'Untrusted release event')
    sha, run, attempt = (env.get(k, '') for k in ('GITHUB_SHA', 'GITHUB_RUN_ID', 'BUILD_ATTEMPT'))
    require(re.fullmatch('[0-9a-f]{40}', sha), 'Invalid source SHA')
    require(run.isdecimal() and attempt.isdecimal(), 'Invalid build identity')
    tag = f'build-{run}-{attempt}-{sha[:12]}'
    require(env.get('RELEASE_TAG') == tag, 'Release tag/build identity mismatch')
    return {'source_sha': sha, 'run_id': run, 'build_attempt': attempt, 'tag': tag,
            'architecture': 'x86_64', 'repository': REPO,
            'workflow_url': f'https://github.com/{REPO}/actions/runs/{run}'}


def verify_checksums(file, paths):
    records = {}
    for line in file.read_text().splitlines():
        digest, name = line.split(None, 1)
        name = name.removeprefix('./')
        require(re.fullmatch('[0-9a-f]{64}', digest), 'Invalid checksum')
        require(name in paths and name not in records, f'Unexpected/duplicate checksum path: {name}')
        require(sha256(paths[name]) == digest, f'Checksum mismatch: {name}')
        records[name] = digest
    require(set(records) == set(paths), 'Incomplete checksum manifest')


def prepare(source, output, env):
    meta = identity(env)
    evidence = source / 'evidence'
    require({p.name for p in evidence.iterdir()} == EVIDENCE_FILES, 'Evidence allowlist mismatch')
    require(all(p.is_file() and not p.is_symlink() for p in evidence.iterdir()), 'Unsafe evidence entry')
    verify_checksums(evidence / 'EVIDENCE-SHA256SUMS',
                     {n: evidence / n for n in EVIDENCE_FILES - {'EVIDENCE-SHA256SUMS'}})
    iso = source / 'build/emacs-kiosk-x86_64.iso'
    require(iso.is_file() and not iso.is_symlink(), 'Missing/unsafe ISO')
    verify_checksums(evidence / 'SHA256SUMS', {'emacs-kiosk-x86_64.iso': iso,
                     **{n: evidence / n for n in ('packages-resolved.txt', 'packages-requested.txt')}})
    report = json.loads((evidence / 'test-report.json').read_text())
    require(report.get('passed') is True and report.get('source_commit') == meta['source_sha'],
            'Boot report must pass for the exact source SHA')
    expected = Counter(SCREENSHOTS + ['guest-boot-and-offline-integrations',
                                     '04-buffer-switch', '05-return-to-editor'])
    require(Counter(c.get('name') for c in report.get('checks', [])) == expected,
            'Missing required guest/UI checks')
    require(all(c.get('passed') is True for c in report['checks']), 'Failed guest/UI check')
    require(report.get('network') == 'none' and report.get('architecture') == 'x86_64',
            'Unexpected guest configuration')
    require(f"source_commit={meta['source_sha']}\n" in (evidence / 'build-metadata.txt').read_text(),
            'Image metadata/source mismatch')
    output.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(iso, output / iso.name)
    # Stable archive bytes make a retry verifiable without replacing published assets.
    with (output / 'boot-evidence.tar.gz').open('wb') as raw:
        with gzip.GzipFile(fileobj=raw, mode='wb', filename='', mtime=0) as zipped:
            with tarfile.open(fileobj=zipped, mode='w', format=tarfile.PAX_FORMAT) as archive:
                for name in sorted(EVIDENCE_FILES):
                    path = evidence / name
                    info = tarfile.TarInfo('evidence/' + name)
                    info.size, info.mode, info.mtime = path.stat().st_size, 0o644, 0
                    with path.open('rb') as file:
                        archive.addfile(info, file)
    (output / 'source-sha.txt').write_text(meta['source_sha'] + '\n')
    meta.update({'boot_and_visual_checks': len(report['checks']),
                 'image_sha256': sha256(iso), 'image_bytes': iso.stat().st_size,
                 'evidence_sha256': sha256(output / 'boot-evidence.tar.gz'),
                 'publication': 'passed trusted-main build; immutable-by-workflow prerelease'})
    (output / 'build-metadata.json').write_text(json.dumps(meta, sort_keys=True, indent=2) + '\n')
    (output / 'SHA256SUMS').write_text(''.join(f'{sha256(output / n)}  {n}\n' for n in sorted(ASSETS - {'SHA256SUMS'})))
    return meta


def gh(*args, payload=None):
    command = ['gh', *args]
    result = subprocess.run(command, input=None if payload is None else json.dumps(payload),
                            text=True, capture_output=True, check=True)
    return result.stdout


def api(endpoint, payload=None, method=None):
    args = ['api', endpoint]
    if method:
        args += ['--method', method]
    if payload is not None:
        args += ['--input', '-']
    return json.loads(gh(*args, payload=payload))


def matching_release(tag):
    pages = json.loads(gh('api', f'repos/{REPO}/releases?per_page=100', '--paginate', '--slurp'))
    matches = [r for page in pages for r in page if r['tag_name'] == tag]
    require(len(matches) <= 1, 'Duplicate release tag; refusing mutation')
    return matches[0] if matches else None


def verify_remote_asset(asset, local):
    require(asset['state'] == 'uploaded', f"Incomplete upload: {asset['name']}")
    require(asset['size'] == local.stat().st_size, f"Remote size mismatch: {asset['name']}")
    require(asset.get('digest') == 'sha256:' + sha256(local),
            f"Missing/mismatched server SHA256: {asset['name']}; refusing overwrite")


def publish(output, env):
    meta = identity(env)
    require({p.name for p in output.iterdir()} == ASSETS, 'Release asset allowlist mismatch')
    require(all(p.is_file() and not p.is_symlink() for p in output.iterdir()), 'Unsafe release asset')
    verify_checksums(output / 'SHA256SUMS', {n: output / n for n in ASSETS - {'SHA256SUMS'}})
    prepared = json.loads((output / 'build-metadata.json').read_text())
    require(all(prepared[k] == v for k, v in meta.items()), 'Prepared release identity mismatch')
    tag = meta['tag']
    refs = api(f'repos/{REPO}/git/matching-refs/tags/{tag}')
    for ref in refs:
        if ref['ref'] == 'refs/tags/' + tag:
            obj = ref['object']
            if obj['type'] == 'tag':
                obj = api(f"repos/{REPO}/git/tags/{obj['sha']}")['object']
            require(obj['type'] == 'commit' and obj['sha'] == meta['source_sha'], 'Existing tag points elsewhere')
    release = matching_release(tag)
    if release is None:
        body = (f"Verified successful main build `{meta['source_sha']}`.\n\n"
                f"[Passing image / real QEMU boot / keyboard-OCR run]({meta['workflow_url']}). "
                "All 10 guest checks passed before this release was prepared.\n\n"
                "x86_64 BIOS/QEMU only; RAM-only, no credentials or real accounts. "
                "Educational demo, not a hardened kiosk.\n\n"
                "Download the ISO, boot-evidence archive, source-sha.txt, build-metadata.json and SHA256SUMS. "
                "Run `sha256sum -c SHA256SUMS` with the files in one directory.\n\n"
                "Newest published build prerelease on the Releases page is the latest successful published build. "
                "Prereleases do not use GitHub's stable Latest badge. "
                "This workflow never moves tags, deletes releases or replaces assets. "
                "Release assets are not subject to the 14-day Actions artifact retention.\n")
        release = api(f'repos/{REPO}/releases', {'tag_name': tag, 'target_commitish': meta['source_sha'],
                      'name': f"Verified main build {meta['run_id']}.{meta['build_attempt']} ({meta['source_sha'][:12]})",
                      'body': body, 'draft': True, 'prerelease': True, 'make_latest': 'false'}, 'POST')
    require(release['target_commitish'] == meta['source_sha'] and release['prerelease'] is True,
            'Existing release identity mismatch')
    existing = {a['name']: a for a in release['assets']}
    require(set(existing) <= ASSETS and len(existing) == len(release['assets']), 'Unexpected remote release assets')
    for name, asset in existing.items():
        verify_remote_asset(asset, output / name)
    missing = ASSETS - set(existing)
    require(release['draft'] or not missing, 'Published release is incomplete; refusing mutation')
    for name in sorted(missing):
        # No --clobber, no automatic retry after an uncertain outcome.
        gh('release', 'upload', tag, str(output / name), '--repo', REPO)
    release = api(f"repos/{REPO}/releases/{release['id']}")
    require({a['name'] for a in release['assets']} == ASSETS, 'Asset upload incomplete')
    for asset in release['assets']:
        verify_remote_asset(asset, output / asset['name'])
    if release['draft']:
        release = api(f"repos/{REPO}/releases/{release['id']}", {'draft': False, 'make_latest': 'false'}, 'PATCH')
    require(release['draft'] is False, 'Release remains unpublished')
    print(release['html_url'])
    if env.get('GITHUB_STEP_SUMMARY'):
        with Path(env['GITHUB_STEP_SUMMARY']).open('a') as summary:
            summary.write(f"## Published verified build\n[Download ISO and evidence]({release['html_url']})\n\n"
                          f"Source: `{meta['source_sha']}`. All 5 asset sizes and server SHA-256 digests verified.\n")
    return release


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['prepare', 'publish'])
    parser.add_argument('--input', type=Path, default=Path('release-input'))
    parser.add_argument('--output', type=Path, default=Path('release-assets'))
    args = parser.parse_args()
    if args.action == 'prepare':
        prepare(args.input, args.output, os.environ)
    else:
        publish(args.output, os.environ)
