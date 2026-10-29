#!/bin/sh
set -eu
for file in scripts/*.sh image/*.sh image/init; do sh -n "$file"; done
python3 -m compileall -q scripts
python3 -m unittest discover -s tests -v
