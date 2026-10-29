#!/bin/sh
set -eu
[ "${1:-x86_64}" = x86_64 ] || { echo 'Only x86_64 is supported' >&2; exit 2; }
exec python3 scripts/visual-boot.py
