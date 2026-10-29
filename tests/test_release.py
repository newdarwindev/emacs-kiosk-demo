import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('release', Path(__file__).resolve().parents[1] / 'scripts/release.py')
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)
SHA = 'a' * 40
ENV = {'GITHUB_REPOSITORY': release.REPO, 'GITHUB_REF': 'refs/heads/main',
       'GITHUB_EVENT_NAME': 'push', 'GITHUB_SHA': SHA, 'GITHUB_RUN_ID': '123',
       'BUILD_ATTEMPT': '1', 'RELEASE_TAG': 'build-123-1-' + SHA[:12]}


def fixture(root):
    source = root / 'input'
    evidence = source / 'evidence'
    evidence.mkdir(parents=True)
    (source / 'build').mkdir()
    iso = source / 'build/emacs-kiosk-x86_64.iso'
    iso.write_bytes(b'unit-test ISO placeholder; never boot evidence')
    for name in release.EVIDENCE_FILES:
        (evidence / name).write_text('synthetic unit fixture\n')
    report = {'source_commit': SHA, 'passed': True, 'network': 'none', 'architecture': 'x86_64',
              'checks': [{'name': n, 'passed': True} for n in release.SCREENSHOTS +
                         ['guest-boot-and-offline-integrations', '04-buffer-switch', '05-return-to-editor']]}
    (evidence / 'test-report.json').write_text(json.dumps(report))
    (evidence / 'build-metadata.txt').write_text(f'source_commit={SHA}\n')
    paths = {'emacs-kiosk-x86_64.iso': iso, **{n: evidence / n for n in ('packages-resolved.txt', 'packages-requested.txt')}}
    (evidence / 'SHA256SUMS').write_text(''.join(f'{release.sha256(p)}  {n}\n' for n, p in paths.items()))
    rehash(evidence)
    return source


def rehash(evidence):
    (evidence / 'EVIDENCE-SHA256SUMS').write_text(''.join(
        f'{release.sha256(evidence / n)}  ./{n}\n' for n in sorted(release.EVIDENCE_FILES - {'EVIDENCE-SHA256SUMS'})))


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.source = fixture(self.root)
        self.output = self.root / 'assets'

    def tearDown(self):
        self.tmp.cleanup()

    def prepare(self):
        return release.prepare(self.source, self.output, ENV)

    def asset(self, name):
        return {'name': name, 'state': 'uploaded', 'size': (self.output / name).stat().st_size,
                'digest': 'sha256:' + release.sha256(self.output / name)}

    def remote(self, draft=False, names=None):
        return {'id': 1, 'tag_name': ENV['RELEASE_TAG'], 'target_commitish': SHA, 'prerelease': True,
                'draft': draft, 'assets': [self.asset(n) for n in (release.ASSETS if names is None else names)],
                'html_url': 'https://github.com/' + release.REPO + '/releases/tag/' + ENV['RELEASE_TAG']}

    def test_rejects_untrusted_events_branches_and_repositories(self):
        for key, value in [('GITHUB_EVENT_NAME', 'pull_request'), ('GITHUB_REF', 'refs/heads/other'),
                           ('GITHUB_REPOSITORY', 'fork/demo'), ('RELEASE_TAG', 'latest')]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                release.identity({**ENV, key: value})

    def test_prepare_allowlist_checksums_and_determinism(self):
        self.prepare()
        other = self.root / 'other'
        release.prepare(self.source, other, ENV)
        self.assertEqual({p.name for p in self.output.iterdir()}, release.ASSETS)
        for name in release.ASSETS:
            self.assertEqual(release.sha256(self.output / name), release.sha256(other / name))

    def test_tampered_image_rejected(self):
        (self.source / 'build/emacs-kiosk-x86_64.iso').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'Checksum mismatch'):
            self.prepare()

    def test_extra_private_file_rejected(self):
        (self.source / 'evidence/.env').write_text('synthetic-placeholder')
        with self.assertRaisesRegex(ValueError, 'allowlist'):
            self.prepare()

    def test_failed_or_wrong_commit_report_rejected(self):
        for field, value in [('passed', False), ('source_commit', 'b' * 40)]:
            p = self.source / 'evidence/test-report.json'
            original = p.read_text()
            report = json.loads(original); report[field] = value
            p.write_text(json.dumps(report)); rehash(p.parent)
            with self.assertRaisesRegex(ValueError, 'Boot report'):
                self.prepare()
            p.write_text(original); rehash(p.parent)

    def test_missing_guest_assertion_rejected(self):
        p = self.source / 'evidence/test-report.json'
        report = json.loads(p.read_text()); report['checks'].pop()
        p.write_text(json.dumps(report)); rehash(p.parent)
        with self.assertRaisesRegex(ValueError, 'required guest'):
            self.prepare()

    def test_published_release_is_idempotent_and_nonmutating(self):
        self.prepare(); remote = self.remote()
        with patch.object(release, 'matching_release', return_value=remote), \
             patch.object(release, 'api', side_effect=[[], remote]) as api, \
             patch.object(release, 'gh') as gh:
            self.assertFalse(release.publish(self.output, ENV)['draft'])
            gh.assert_not_called()
            self.assertEqual(api.call_count, 2)

    def test_conflicting_existing_asset_never_overwritten(self):
        self.prepare(); remote = self.remote(draft=True)
        remote['assets'][0]['digest'] = 'sha256:' + '0' * 64
        with patch.object(release, 'matching_release', return_value=remote), \
             patch.object(release, 'api', return_value=[]), patch.object(release, 'gh') as gh:
            with self.assertRaisesRegex(ValueError, 'refusing overwrite'):
                release.publish(self.output, ENV)
            gh.assert_not_called()

    def test_partial_draft_resumes_only_missing_assets(self):
        self.prepare(); remote = self.remote(draft=True, names={'source-sha.txt'})
        complete = self.remote(draft=True)
        published = self.remote(draft=False)
        with patch.object(release, 'matching_release', return_value=remote), \
             patch.object(release, 'api', side_effect=[[], complete, published]), \
             patch.object(release, 'gh', return_value='') as gh:
            self.assertFalse(release.publish(self.output, ENV)['draft'])
            self.assertEqual(gh.call_count, 4)
            self.assertTrue(all('--clobber' not in c.args for c in gh.call_args_list))

    def test_incomplete_published_release_is_not_modified(self):
        self.prepare(); remote = self.remote(names={'source-sha.txt'})
        with patch.object(release, 'matching_release', return_value=remote), \
             patch.object(release, 'api', return_value=[]), patch.object(release, 'gh') as gh:
            with self.assertRaisesRegex(ValueError, 'Published release is incomplete'):
                release.publish(self.output, ENV)
            gh.assert_not_called()

    def test_existing_tag_wrong_commit_is_rejected(self):
        self.prepare()
        refs = [{'ref': 'refs/tags/' + ENV['RELEASE_TAG'], 'object': {'type': 'commit', 'sha': 'b' * 40}}]
        with patch.object(release, 'api', return_value=refs), patch.object(release, 'gh') as gh:
            with self.assertRaisesRegex(ValueError, 'tag points elsewhere'):
                release.publish(self.output, ENV)
            gh.assert_not_called()

    def test_write_permission_is_isolated_to_gated_release_job(self):
        workflow = (Path(__file__).resolve().parents[1] / '.github/workflows/linux-image.yml').read_text()
        build, publish = workflow.split('  release:\n')
        self.assertNotIn('contents: write', build)
        self.assertIn('contents: write', publish)
        for required in ["github.ref == 'refs/heads/main'", "github.event_name == 'push'",
                         "needs.boot-and-visual.result == 'success'", 'artifact-ids:',
                         'persist-credentials: false']:
            self.assertIn(required, publish)


if __name__ == '__main__':
    unittest.main()
