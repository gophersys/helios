#!/bin/zsh
# Durable form of the dense-ui loop: one headless Claude run following LOOP.md.
# Installed via loop/install.sh (launchd, every 10 min). Logs to loop/runs/.
set -euo pipefail
cd ~/code/research-ui
mkdir -p loop/runs
exec /usr/local/bin/claude -p "Read ~/code/research-ui/LOOP.md and follow it exactly for one run." \
  --permission-mode acceptEdits \
  >> "loop/runs/$(date -u +%Y%m%d).log" 2>&1
