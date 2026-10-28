#!/bin/zsh
set -e
skill_dir="${0:A:h}"
exec /usr/bin/python3 "$skill_dir/scripts/launch.py" --open
