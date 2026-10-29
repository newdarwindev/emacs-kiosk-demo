# Emacs Kiosk Demo

A credential-free **Alpine Linux + Emacs + tmux** live demo. It boots a real Linux kernel from an ISO, starts Xorg and a full-screen Emacs session, and keeps changes only in RAM. No installer, host disk, network interface, Slack account, AI account, or credential is attached to the test VM.

**Implemented target: x86_64 BIOS/QEMU only.** ARM/aarch64, UEFI, physical hardware support, persistence, and a hardened kiosk escape policy are not implemented or claimed. The previous draft's dual-architecture claim was removed rather than represented as tested.

## Download continuous builds

Every successful trusted `main` push (or manual run on `main`) now publishes a
[verified build prerelease](https://github.com/newdarwindev/emacs-kiosk-demo/releases).
**The newest published build prerelease is the latest successful published build.**
Prereleases cannot use GitHub's stable “Latest” badge; `/releases/latest` is not the download link.

Each release has five downloadable assets:

- `emacs-kiosk-x86_64.iso`
- `boot-evidence.tar.gz` — real VM screenshots, OCR, logs, manifests and test report
- `source-sha.txt` and `build-metadata.json` — exact source/run identity and image digest
- `SHA256SUMS` — verify with `sha256sum -c SHA256SUMS` after downloading all five together

Tags use `build-<run-id>-<build-attempt>-<source-SHA-prefix>`. The workflow never
moves tags, overwrites assets or deletes old releases. It uploads to a draft,
checks every asset's server SHA-256 digest, then publishes. A retry reconciles the
same build's existing release/assets; a conflict fails safely. “Immutable” here is
a workflow guarantee, not a claim that repository-level immutable releases are enabled.

Only the isolated release job has `contents: write`; it cannot run for PRs,
forks or non-main branches. Failed boot/UI tests never publish a release.
Release assets have no configured expiry and are separate from diagnostic Actions
artifacts, which still expire after 14 days. No new repository secrets are needed.

## Build and boot

On a disposable Linux builder with Docker, QEMU, Python 3, Pillow and Tesseract installed:

```sh
make check
make image ARCH=x86_64
make visual ARCH=x86_64
make evidence
```

To explore manually, with no disk or network attached:

```sh
qemu-system-x86_64 -m 4096 -vga std -cdrom build/emacs-kiosk-x86_64.iso -boot d -nic none
```

The Docker build is an explicit source allowlist and does **not** use privileged mode. It fetches public Alpine packages into a fresh root, records the resolved versions, and packs a RAM filesystem plus kernel into an ISOLINUX BIOS ISO. No host home, credentials, environment files or Git metadata enter the image. Only the output directory is mounted into the builder.

The base is `alpine:3.24.3`; repositories are the explicit `v3.24/main` and `v3.24/community` branches. `image/packages.txt` is the requested manifest. `packages-resolved.txt` records all exact installed versions. This is **not byte-for-byte reproducible**: the base tag and branch packages can change. Source file timestamps are normalized but no package-digest lock or immutable repository snapshot is claimed. Image size is measured in each run, not promised as a tiny fixed number.

## What the visual gate proves

GitHub Actions builds the ISO, then boots it with QEMU (TCG, 4 GiB RAM, no network and no disk). The test:

1. Waits for text in the actual guest Emacs framebuffer, not a web/mock screenshot.
2. Verifies Linux/X boot and synthetic Slack/tmux output in the guest serial log.
3. Sends QMP keyboard events and asserts typed text using screenshot OCR.
4. Cancels an interrupted file-opening flow, switches buffers twice and returns to the original buffer.
5. Opens a real Emacs shell, runs the offline Slack parser and reads the tmux session output.

The artifacts contain screenshots, OCR text, serial/QEMU logs, a machine-readable test report, source SHA, exact package manifest, ISO and SHA-256 checksums. This is real boot/UI testing, **not pixel-diff testing**, and it does not prove security hardening or compatibility with real hardware. Failure evidence is uploaded too; read `test-report.json` and the workflow conclusion before claiming a pass.

Find the exact commit's run under [Actions](https://github.com/newdarwindev/emacs-kiosk-demo/actions). Download `boot-evidence-<run-id>-<build-attempt>-<commit>` (14-day retention), or use the durable assets on the [Releases page](https://github.com/newdarwindev/emacs-kiosk-demo/releases). A successful static-check job alone is not a passing build/boot result.

## Inside the demo

- `C-x b`: switch buffer. `C-g`: cancel. `M-x shell`: terminal shell.
- `C-x C-c`: exits Emacs; the kiosk launcher restarts the session. Normal Emacs save prompts still apply.
- The `demo` tmux session receives one harmless synthetic command at boot.
- `/opt/kiosk/slack-mock.py` reads two bundled synthetic events. It makes no network calls and sends no messages.
- Emacs runs as the locked, unprivileged `kiosk` user. Xorg/PID 1 run as root for this isolated demonstration; no login/SSH service starts.

See [agent/Slack choices](docs/integrations.md) and [security limits](docs/security.md). OpenHands and Claude Code are optional operator-selected choices, **not bundled agents**. Real Slack Bolt/Socket Mode requires a separate app, reviewed scopes and runtime-only secrets; it is not part of this credential-free demo.

## Scope and safety

This is an educational RAM-boot system, not a general desktop distribution or production kiosk. It deliberately has no installer or real account setup. Do not use it for sensitive work, connect it to an untrusted network, or regard its UI as an access-control boundary. For persistence, hardware deployment, networking or agent integration, start with a supported installed distribution and design those features separately.

## Public references

- [Alpine release support](https://alpinelinux.org/releases/)
- [Alpine custom ISO documentation](https://wiki.alpinelinux.org/wiki/How_to_make_a_custom_ISO_image)
- [QEMU QMP reference](https://www.qemu.org/docs/master/interop/qemu-qmp-ref.html)
- [GNU Emacs manual](https://www.gnu.org/software/emacs/manual/html_node/emacs/)
- [tmux documentation](https://github.com/tmux/tmux/wiki)
- [Slack Socket Mode](https://docs.slack.dev/apis/events-api/using-socket-mode/)

Demo source is MIT-licensed. Alpine packages retain their respective upstream licenses.
