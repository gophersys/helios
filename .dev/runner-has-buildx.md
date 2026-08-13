# runner-has-buildx

phase:    plan
repo:     gophersys/.devcontainer
branch:   feat/runner-has-buildx
worktree: ~/code/.worktrees/dc-buildx
pr:       -
attempt:  1/2

## Goal

The runner image has no `docker buildx`, so CI cannot use the Mac mini as a
native arm64 builder. Add the plugin to the image, and add the assertion that
notices if it ever goes missing again.

## The blocker, MEASURED twice — do not re-derive

Against the pinned image `ghcr.io/gophersys/base-runner:e0c6bc5`:

```
/usr/local/lib/docker/cli-plugins:   docker-compose        <- buildx ABSENT
docker buildx version             -> docker: unknown command: docker buildx
```

`base/Dockerfile:482` installs `docker-ce-cli`, and lines 493-496 then download
ONLY the compose plugin into `/usr/local/lib/docker/cli-plugins`. buildx ships
separately (`docker-buildx-plugin`, or a direct release binary the same way
compose is fetched). Nothing installs it.

## Why this matters now

`gophersys/infrastructure` branch `feat/mini-buildx` mounts a dial-only SSH key
into the arc-org pool so image builds can reach the mini, which builds arm64
**3.44x faster** than the amd64 runners can emulate it (4.02s vs 13.8s, measured;
transfer cost ~100 MB/s, so 1-2s for a realistic context). Every part of that is
proven EXCEPT this: the documented workflow step cannot run, because the image
has no buildx.

The infrastructure implementer deliberately refused to work around it by
downloading buildx inside the job, citing `ci-substrate.md`'s rule that software
capability belongs in the image and the fact that `validate.yml` carries no
tool-install step for exactly that reason. That was right, and it is why this is
a separate change rather than a hack.

## Plan

APPROVED (self, under delegated authority, 2026-08-13).

1. Install the buildx plugin in `base/Dockerfile`, PINNED by an `ARG` the way the
   other tools in this image are pinned. Follow whatever the compose install
   already does — do not invent a second style.
2. Assert it. The image already has a verification path; the assertion must fail
   if buildx is absent, and it must name the tool.

## Deliberately NOT in this change

- Reversing D42, or adding `linux/arm64` to any image's platform list. That lands
  only after the builder is proven in CI.
- Anything in `gophersys/infrastructure`.

## Proven

Nothing yet. Phase 2 owes a RED test.

## Blocked

Nothing.

## Next

Test author: a red assertion that the runner image carries buildx.
