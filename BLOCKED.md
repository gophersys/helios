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

**Re-verified 2026-08-14 (loop):** the assumption above was wrong — it is a
REPO-level secret, not an org secret: eden holds `GHCR_PULL_TOKEN` as its own
repo secret (set 2026-07-07); dense-ui has none; the org secrets API answers
403 to this token. So the grant is exactly one command with the same PAT:

    bw get password <ghcr-pull-token item> | \
      gh secret set GHCR_PULL_TOKEN -R gophersys/dense-ui --body-file -

Bitwarden was locked this run, so the loop could not do it itself. The
Keychain does hold a ghcr.io docker credential, but its scope is
unverifiable and it may be a WRITE token — refused on least privilege; the
dedicated pull PAT is the only correct value. Unlock `bw` in a session (or
run the command above) and the loop takes the rebase box on its next firing.
On grant: the loop rebases ci/Dockerfile to FROM ghcr.io/gophersys/base with
google-chrome-stable via Google's apt repo, and the fleet re-proves the chain.
Default if forced: stay on debian (working, proven, lighter).

**Loop is idle-hot as of 2026-08-14T00:50Z:** every PLAN box except this one
is ticked and fleet-certified. Until the grant lands, each 5-minute firing
can only re-verify the blocker and find nothing to do. Decision for Mateo:
either run the one-command grant above (the loop then takes the rebase and
the plan closes), or slow/disarm the launchd cadence until then — firings
are cheap but not free.
