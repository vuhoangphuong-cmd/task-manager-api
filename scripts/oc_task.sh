#!/usr/bin/env bash

# load actor config
if [ -f "$HOME/.openclaw/actor.env" ]; then
  export $(grep -v '^#' "$HOME/.openclaw/actor.env" | xargs)
fi

exec /home/thanh_giong/projects/task-manager-api/.venv/bin/python \
/home/thanh_giong/projects/task-manager-api/scripts/oc_task_cli.py "$@"
