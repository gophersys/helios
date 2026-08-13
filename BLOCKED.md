# BLOCKED — questions for Mateo

## 2026-08-14 — arm the durable loop?
Context: an in-session 10-min loop is running while the founding Claude session
stays open; `loop/install.sh` arms a launchd agent that runs a headless Claude
every 10 min INDEFINITELY (unattended token spend, acceptEdits permission mode).
Decision needed: run `zsh ~/code/dense-ui/loop/install.sh` yourself, or keep
the loop session-bound. Default if forced: stay session-bound.


## 2026-08-14 — grant GHCR_PULL_TOKEN to dense-ui (base-child image rebase)
Context: the house convention (eden/.devcontainer/base) is base -> child
images adding domain toolchains; dense-ui-ci currently sits on debian
directly (deliberate at the time: no pull secret, ubuntu snap-chromium, CDN
egress). Mateo asked for the base-child layering.
Decision needed: add gophersys/dense-ui to the GHCR_PULL_TOKEN org secret's
repo list (or grant an equivalent read:packages credential).
On grant: the loop rebases ci/Dockerfile to FROM ghcr.io/gophersys/base with
google-chrome-stable via Google's apt repo, and the fleet re-proves the chain.
Default if forced: stay on debian (working, proven, lighter).
