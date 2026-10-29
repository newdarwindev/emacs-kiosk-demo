#!/bin/sh
set -eu
session=${1:-demo}
[ "$session" = demo ] || { echo 'only the demo tmux session is allowed' >&2; exit 2; }
tmux has-session -t demo 2>/dev/null || tmux new-session -d -s demo -c "$HOME/demo"
tmux send-keys -t demo 'printf "%s\\n" "Synthetic agent task ready"' C-m
echo 'Queued a synthetic command in tmux session demo.'
