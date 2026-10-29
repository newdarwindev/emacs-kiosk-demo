#!/bin/sh
set -eu
openbox >/tmp/openbox.log 2>&1 &
wm=$!
trap 'kill "$wm" 2>/dev/null || true' EXIT
emacs -Q -l /opt/kiosk/emacs-init.el --fullscreen "$HOME/demo/README.txt"
