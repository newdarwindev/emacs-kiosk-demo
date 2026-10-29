#!/bin/sh
set -eu
[ "${1:-x86_64}" = x86_64 ] || { echo 'Only x86_64 is supported; aarch64 is not implemented' >&2; exit 2; }
command -v docker >/dev/null || { echo 'Docker is required for image builds' >&2; exit 127; }
mkdir -p build evidence
docker build --platform linux/amd64 -t emacs-kiosk-builder .
docker run --rm --platform linux/amd64 --network bridge -v "$PWD/build:/output" emacs-kiosk-builder x86_64
printf 'source_commit=%s\nbuilder=alpine:3.24.3\narchitecture=x86_64\n' "$(git rev-parse HEAD)" > build/build-metadata.txt
