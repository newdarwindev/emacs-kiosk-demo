#!/bin/sh
set -eu
exec ./scripts/boot-test.sh "${ARCH:-x86_64}"
