#!/bin/sh
set -eu
mkdir -p evidence
for f in build/*.txt build/SHA256SUMS; do
  [ ! -f "$f" ] || cp "$f" "evidence/$(basename "$f")"
done
(cd evidence && find . -maxdepth 1 -type f ! -name EVIDENCE-SHA256SUMS -print0 | sort -z | xargs -0 -r sha256sum > EVIDENCE-SHA256SUMS)
