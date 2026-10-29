# Repository instructions

- This repository builds a Linux system. A passing shell lint is not evidence that it boots. Keep QEMU boot and live UI interaction tests as required CI gates.
- Every UI/TUI change must produce a real screenshot or rendered terminal recording plus logs and assertions. Preserve passing-run evidence and upload evidence after failures. Never describe this as pixel-diff testing unless a baseline comparison is implemented.
- Keep all fixture data synthetic. Reject any credential, dotfile, user home, or host config from build contexts. No real account integration in CI.
- Pin GitHub Actions to full commit SHAs and use least-privilege workflow permissions. Do not create repository secrets.
- Keep Alpine release/repository choices explicit and update package manifests intentionally. Do not silently broaden architectures or image size claims.
- Run `make check`, `make image`, `make visual`, and `make evidence` before claiming local validation. Report unavailable host prerequisites separately.
