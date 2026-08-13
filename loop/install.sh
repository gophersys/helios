#!/bin/zsh
# Arm the durable loop. Run this yourself — it spends tokens unattended.
set -euo pipefail
chmod +x ~/code/dense-ui/loop/claude-loop.sh
cp ~/code/dense-ui/loop/com.mateosegura.dense-ui-loop.plist ~/Library/LaunchAgents/
launchctl unload ~/Library/LaunchAgents/com.mateosegura.dense-ui-loop.plist 2>/dev/null || true
launchctl load ~/Library/LaunchAgents/com.mateosegura.dense-ui-loop.plist
echo "armed: dense-ui loop every 10 min (disarm: launchctl unload ~/Library/LaunchAgents/com.mateosegura.dense-ui-loop.plist)"
