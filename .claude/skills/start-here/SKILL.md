---
name: start-here
description: First-time setup for a freshly cloned Concord repo. Walks the developer from `git clone` to a working dev loop (`localhost:4200` reachable).
---

# /start-here

You are guiding a developer who just cloned this repo. They want to get to a green dev loop.

## Steps

1. **Read prerequisites**: `.claude/knowledge/workflows/local-dev.md` lists OS/Docker/VS Code requirements. Confirm they're met before moving on. Common blockers: Docker Desktop not running, VS Code Dev Containers extension missing, WSL2 not enabled on Windows.

2. **Submodules**: if the clone wasn't `--recursive`, run `git submodule update --init --recursive` from the repo root.

3. **Identity**: set repo-local git identity per `.claude/rules/git-commits.md`:
   ```bash
   git config user.name "Mateo Segura"
   git config user.email "mateo@corekinect.com"
   ```

4. **Install git hooks** (once per clone — wires the knowledge-freshness check):
   ```bash
   .claude/hooks/install.sh
   ```
   This sets `core.hooksPath=.claude/hooks` and makes the `commit-msg` hook executable. Future commits that touch a tracked code path without updating the matching `.claude/knowledge/` file will be refused (escape hatch: `[no-arch-change]`). See `.claude/rules/update-knowledge-on-change.md`.

5. **Credentials**: walk `.claude/knowledge/workflows/credentials.md`. List every credential they need, point at Bitwarden (`secrets.mateosegura.com`) for the canonical store. Most can wait — for first boot they only need:
   - K8s kubeconfig (only if testing against staging; not required for local dev)
   - Bitbucket API token + SSH key (only if testing the build service)

6. **Open in devcontainer**: VS Code → Reopen in Container → **pick the `base` container**. The `.devcontainer/` folder has several configs (`base`, `mtib`, `ncs-v2.7.0`, `ncs-v3.2.1`, `zephyr-v4.0`); only `base` is the platform dev container. The others are firmware toolchains and aren't needed for normal platform work.

   First-open runs `.devcontainer/ctl.sh create` automatically (~2-3 min): installs deps, sets up Docker buildx, injects CA certs.

7. **Start the stack**:
   ```bash
   nx start platform        # backend (Docker Compose)
   nx serve app             # frontend dev server, separate terminal
   ```

8. **Verify**: open `http://localhost:4200` — the login page should render. With `AUTH_ENABLED=false` (the default in dev), the synthetic admin signs you in automatically. API docs at `http://localhost:9001/v2/docs`, MinIO console at `http://localhost:8676` (admin/concordstorage!), MkDocs at `http://localhost:4000` (after `nx serve docs`).

## After the loop is green

Point the user at:

- `.claude/knowledge/architecture.md` — the system overview.
- `.claude/knowledge/workflows/local-dev.md` — daily commands.
- `/plan-feature` — when they're ready to build something.

## If a step fails

Don't paper over it. Surface the exact error, point at `.claude/knowledge/workflows/debugging.md`, and walk the troubleshooting list. Specific common failures:

- **`docker.sock` permission denied on WSL** → user wasn't added to the `docker` group, or Docker Desktop isn't running on the Windows host.
- **`git submodule update` fails with 403** → SSH key not loaded; check `~/.ssh-devcontainer/` exists on host before opening in container.
- **`nx start platform` reports "concord-postgres unhealthy"** → first-time startup; wait 30s and re-check. If persistent, `docker logs <postgres-container>` shows the init error.
