# BLOCKED — questions for Mateo

## 2026-08-14 — arm the durable loop?
Context: an in-session 10-min loop is running while the founding Claude session
stays open; `loop/install.sh` arms a launchd agent that runs a headless Claude
every 10 min INDEFINITELY (unattended token spend, acceptEdits permission mode).
Decision needed: run `zsh ~/code/dense-ui/loop/install.sh` yourself, or keep
the loop session-bound. Default if forced: stay session-bound.

