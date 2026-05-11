# git-poller — knowledge

The branch + PR watcher. Single-process Python service that asks the HTTP API which repos and branches matter, polls Bitbucket for new commits on those branches and for open PRs, and dispatches `RepoEvent` payloads to the HTTP API when something changes. It has no DB of its own — its only job is to turn "Git changed" into "POST /v2/builds/events" calls. The HTTP API decides what to build.

Refresh this file when: the watch-target discovery shape changes (new fields read from `/v2/products`, new trigger types, new filtering rules), the polling cadence or backoff changes, the state model in `state.py` changes shape, the Bitbucket API surface used by `pr_watcher.py` changes, or a new env var is added to `GitPollerConfig`.

## Location

- Code: `apps/backend/git-poller/`
- Entry point: `src/main.py`
- Tests: `tests/`
- Container: `deploy/Dockerfile`
- Config: `src/config.py` (`GitPollerConfig` extends `corekinect.utils.EnvConfig`)

## Responsibilities

Owns:

- Watch-target discovery — fetching enabled stage configs from `GET /v2/products` and turning them into `WatchTarget` rows.
- Branch-merge detection (`pr_merge` trigger type) via `git ls-remote` over SSH.
- PR-push detection (`pr_push` trigger type) via the Bitbucket Cloud REST API (Basic auth, email + token).
- In-memory per-process dedup so a commit observed twice doesn't fire two builds in one process lifetime.
- Persisting tracked branch SHAs and tracked PR metadata via `PUT/GET /v2/system/poller-state` (PostgreSQL-backed; see `PollCache`).
- A minimal health/ready HTTP server on `SERVICE_PORT` (default 9003) so K8s can probe it.

Does not own:

- The decision of *what* to build — the HTTP API's `handle_repo_event` maps a `RepoEvent` to one or more `BuildRun`s based on matching `StageConfig` rows.
- Webhook ingest — Bitbucket webhooks land directly on the HTTP API (`POST /v2/builds/webhook`). The poller is the polling alternative.
- Long-term state — the only durable state is what's persisted to the HTTP API's `PollCache` table. The in-process `_triggered` dedup set is process-lifetime only.
- Any direct talk to build-service — every trigger goes via the HTTP API.

The HTTP API also runs an *in-process* Bitbucket poll thread (gated by `BITBUCKET_POLLER_ENABLED`) that calls the same `webhook_trigger.poll_for_changes()` code path. The standalone `git-poller` service is the K8s-scheduled equivalent and can run independently per cluster.

## Internal structure

```
apps/backend/git-poller/
├── src/
│   ├── main.py             # Entry: SSH key, health server, signal handlers, run loop
│   ├── config.py           # GitPollerConfig — env-var schema + property aliases
│   ├── models.py           # WatchTarget, PRInfo dataclasses
│   ├── poller.py           # GitPoller — poll_once() orchestrator; per-repo branch +
│   │                       #   PR processing; in-process dedup set keyed by
│   │                       #   (repo, sha, stage, trigger_type)
│   ├── discovery.py        # ProductDiscovery — caches GET /v2/products and parses
│   │                       #   stageConfigs[] into WatchTarget objects; only includes
│   │                       #   enabled stages with BUILD_SERVICE in assetSources and
│   │                       #   triggerTypes containing pr_push or pr_merge
│   ├── branch_watcher.py   # BranchWatcher — `git ls-remote refs/heads/<branch>` via
│   │                       #   SSH; runner is injectable for tests
│   ├── pr_watcher.py       # PRWatcher — Bitbucket Cloud REST: GET pullrequests with
│   │                       #   HTTPBasicAuth(email, api_token); returns None on rate
│   │                       #   limit / transient error so the cycle is skipped
│   ├── trigger.py          # BuildTrigger — POST /v2/builds/events with the
│   │                       #   RepoEvent payload; ApiKey auth; verify=False
│   └── state.py            # PollerState — API-backed write-through cache (GET/PUT
│                           #   /v2/system/poller-state), mirrors old file-based shape
└── tests/                  # poller, discovery, branch_watcher, pr_watcher, trigger,
                            #   state, config, coverage_gaps
```

## Key patterns

### Main loop

`GitPoller.run(on_first_success)` in `src/poller.py`:

1. Call `poll_once()`.
2. After the first cycle that does not raise, invoke the `on_first_success` callback. `src/main.py` uses this to flip a module-level `_ready` flag so `/ready` returns 200.
3. `self._shutdown.wait(timeout=poll_interval)` — sleeps for `POLL_INTERVAL` seconds (default 5) or returns early on shutdown.
4. Repeat until `signal_shutdown()` sets the event.

`poll_once()` calls `ProductDiscovery.get_watch_targets()` (cached for `PRODUCT_CACHE_TTL` seconds, default 60), groups the resulting targets by `repo_slug`, and processes each repo once per cycle. Branch SHA lookups are deduplicated within a cycle so multiple stages watching the same `(repo, branch)` only run one `git ls-remote`.

### Per-repo processing

`_process_repo()` partitions a repo's targets by trigger type:

- **`pr_merge` targets** — for each unique `(ssh_url, branch)`, get the current SHA via `BranchWatcher.get_branch_sha`. Compare against `PollerState.get_branch_sha(repo, branch)`:
  - First sight: record SHA, no trigger.
  - Same SHA: no-op.
  - New SHA: call `_fire_trigger(target, current_sha, "pr_merge", pr_info=None)` and on success update the stored SHA.

- **`pr_push` targets** — for each unique watch branch, call `PRWatcher.get_open_prs(repo_slug, target_branch=branch)`. If it returns `None` (rate-limited or transient error), skip this cycle to avoid falsely marking tracked PRs as closed. Otherwise:
  - Reconcile open PR IDs against `PollerState.get_tracked_pr_ids(repo)`; remove any that closed.
  - For each open PR, compare `pr.head_sha` against `PollerState.get_pr_sha(repo, pr.pr_id)`:
    - New PR or updated head SHA → fire `_fire_trigger(target, pr.head_sha, "pr_push", pr_info=pr)`.

### Dedup

`_fire_trigger` checks `(repo_slug, commit_sha, stage, trigger_type)` against an in-process set. If already seen this process lifetime, the call is a no-op that returns `True` (treated as success so state isn't re-asserted). This guards against a server-side flake that causes the same SHA to be re-processed within a single process. Restart clears the set — by design, because the HTTP API's `handle_repo_event` is also idempotent.

### State

`PollerState` (`src/state.py`) is an API-backed write-through cache. On construction it `load()`s all rows via `GET /v2/system/poller-state` into an in-memory dict shaped like:

```
{ repo_slug: { "branches": { branch: sha }, "prs": { pr_id: {"sha": ..., "source": ...} } } }
```

Reads hit the in-memory dict. Writes go to the API (and then update the cache). `PollerState.save()` is called at the end of `poll_once()`. The HTTP API persists via the `PollCache` Prisma model; nothing on the poller's local disk.

### SSH key

`_setup_ssh_key()` in `src/main.py` handles three cases:

1. **SSH agent active** (`SSH_AUTH_SOCK` set and exists) — use the agent, ignore everything else.
2. **`BITBUCKET_SSH_KEY` set** — base64-decode and write to `SSH_KEY_PATH`, mode `0400`.
3. **Neither** — log a warning if the key file does not already exist; subsequent `git ls-remote` calls will fail loudly.

`BranchWatcher` builds `GIT_SSH_COMMAND=ssh -i <ssh_key_path> -o StrictHostKeyChecking=no` (see `branch_watcher._build_env`) and passes it via `env=` to `subprocess.run`.

### Health server

A `BaseHTTPRequestHandler` runs in a daemon thread on `SERVICE_PORT`:

- `GET /health` → always 200 `{"status":"ok"}`.
- `GET /ready` → 200 once the first poll cycle has finished, 503 before that.
- Anything else → 404. Access logs are suppressed.

### Trigger payload

`BuildTrigger.trigger_build` POSTs to `<api>/v2/builds/events` with `Authorization: ApiKey <api_key>`. The body is the `RepoEvent` shape consumed by `services/integrations/webhook_trigger.handle_repo_event` on the HTTP API side — see that module for the exact field list. Any 4xx/5xx is logged but returns `False` so the caller can decide whether to retry next cycle. TLS verification is disabled (`verify=False`) to accommodate self-signed dev/staging certs.

## External dependencies

| Dep | Env var(s) | Notes |
|---|---|---|
| HTTP API | `CONCORD_API_URL`, `CONCORD_API_KEY` | Reads watch targets, reads/writes poller state, dispatches `RepoEvent`. All requests use `Authorization: ApiKey <key>` |
| Bitbucket Cloud (SSH) | `SSH_KEY_PATH`, `BITBUCKET_SSH_KEY` | Used by `git ls-remote` for branch SHAs |
| Bitbucket Cloud (REST) | `BITBUCKET_WORKSPACE` (default `corekinect`), `BITBUCKET_EMAIL`, `BITBUCKET_API_TOKEN` | Used by `PRWatcher` (Basic auth — email + API token) for `GET /2.0/repositories/<workspace>/<repo>/pullrequests` |
| Health port | `SERVICE_PORT` (default 9003) | K8s readiness/liveness probes |
| Cadence | `POLL_INTERVAL` (default 5 s), `PRODUCT_CACHE_TTL` (default 60 s) | Poll interval is independent of the product-cache TTL; cache governs how often watch-target discovery hits the HTTP API |

Credentials and rotation — see [`../../deploy/secrets.md`](../../deploy/secrets.md). Every env value lives in all three of `deploy/development/docker-compose.yaml`, `deploy/production/helm/values-staging.yaml`, and `deploy/production/helm/values-production.yaml` (see [`../../../rules/all-three-envs.md`](../../../rules/all-three-envs.md)).

## How to add common things

### Add a new repo to poll

You don't — the poller picks repos up dynamically. The HTTP API's `Product` model is the source of truth:

1. Create the `Product` with `fwRepoSlug` (or `mfgFwRepoSlug`) pointing at the Bitbucket repo slug.
2. Add at least one `StageConfig` row with `enabled=true`, `assetSources` containing `BUILD_SERVICE`, and `triggerTypes` listing `pr_push` and/or `pr_merge`.
3. Wait up to `PRODUCT_CACHE_TTL` seconds for `ProductDiscovery` to re-fetch. Tests sometimes call `_discovery._cache_invalidate_if_present()` directly to bypass the wait.

`discovery._parse_watch_targets` filters out products whose `status != "ACTIVE"`, whose `repoSshUrl` is empty, and stages whose `BUILD_SERVICE` is not in `assetSources` or whose `triggerTypes` are neither `pr_push` nor `pr_merge`.

### Change the polling interval

Tune `POLL_INTERVAL` (loop cadence) and `PRODUCT_CACHE_TTL` (how often we refresh watch targets). Both are env vars on `GitPollerConfig` and need to be added to `deploy/development/docker-compose.yaml` + both helm values files in the same commit. Defaults are 5 s and 60 s respectively.

The HTTP API also has its own in-process poll thread keyed off `BITBUCKET_POLLER_INTERVAL_S` (default 300 s) — they coexist; don't conflate them.

### Add a new trigger type

`_VALID_TRIGGER_TYPES` in `src/discovery.py` is currently `{"pr_push", "pr_merge"}`. Adding a new value requires:

1. Add the value to the Prisma `StageConfigTriggerType` enum (or whatever the field's enum type is) — see [`../../../rules/prisma-flow.md`](../../../rules/prisma-flow.md).
2. Add it to `_VALID_TRIGGER_TYPES`.
3. Add a corresponding processing path in `GitPoller._process_repo` (or a new helper) that knows how to detect the event and synthesise a `RepoEvent`.
4. Extend `BuildTrigger._build_event_payload` if the payload shape differs.
5. Extend `handle_repo_event` on the HTTP API to know what to do with it.
6. Add a stage-config test under `apps/backend/http-api/tests/` and a poller test under `apps/backend/git-poller/tests/`.

### Add a new env var

1. Add the field to `GitPollerConfig` in `src/config.py` with a default; add the `@property` alias.
2. Update `deploy/development/docker-compose.yaml`, `values-staging.yaml`, and `values-production.yaml` (see [`../../../rules/all-three-envs.md`](../../../rules/all-three-envs.md)).
3. If it's a credential, update the K8s `Secret` plumbing and [`../../deploy/secrets.md`](../../deploy/secrets.md).

## Common failure modes

- **`/ready` stays 503.** The first `poll_once()` raised. Inspect logs for `Poller: unhandled error in poll cycle`. Common root causes: HTTP API unreachable (network / DNS), `CONCORD_API_KEY` not set or invalid (401 from `/v2/products`), or `BITBUCKET_API_TOKEN`/`BITBUCKET_EMAIL` missing (PR watcher cannot authenticate).
- **`git ls-remote` fails for all repos.** SSH key not in place. Check `_setup_ssh_key` logs (`SSH: key written to ...`, `SSH: using agent at ...`, or the warning when neither is true). In K8s, confirm the `Secret` is mounted and the volume mode is `0400`-compatible.
- **PR triggers stop firing.** `PRWatcher.get_open_prs` returns `None` on rate-limit or transient HTTP error, and the cycle deliberately skips so tracked PRs aren't falsely marked closed. Check `Poller: ... skipped` log lines and Bitbucket rate-limit headers; consider raising `POLL_INTERVAL` or using a more privileged token.
- **Same commit triggered twice across restarts.** The in-process dedup set is cleared on restart. That's expected — the HTTP API's `handle_repo_event` should be idempotent. If duplicate `BuildRun`s appear, the bug is on the API side (look at `handle_repo_event` for missing dedup on `(productId, commitSha, stage)`).
- **State loss.** `PollerState.load()` is silent on failure — if the HTTP API was unreachable at startup, the poller starts with empty state and will treat every branch as "first sight" (recording the SHA without triggering). That's the safe failure mode; it does *not* fire a build for an old commit. If you genuinely lose state mid-run, the next change will retrigger as expected.
- **Discovery returns zero targets.** Watch-target filtering is strict — `status==ACTIVE`, non-empty `repoSshUrl`, stage `enabled==true`, `BUILD_SERVICE in assetSources`, and at least one valid trigger type. A product missing any of these silently disappears from the poller's view. Hit `/v2/products` directly and inspect the response shape vs. `_parse_watch_targets`.

## Related knowledge

- [`../../architecture.md`](../../architecture.md) — where git-poller sits.
- [`../../glossary.md`](../../glossary.md) — `BuildRun`, `Codebase`, `ReleaseTrack`.
- [`http-api.md`](http-api.md) — the API this service depends on; see `services/integrations/webhook_trigger.py` for the receiving handler.
- [`build-service.md`](build-service.md) — the downstream worker that consumes the BuildJobs created from a `RepoEvent`.
- [`../../product-domains/builds.md`](../../product-domains/builds.md) — end-to-end build flow including the polling vs. webhook entry points.
- [`../../deploy/secrets.md`](../../deploy/secrets.md) — SSH key, API key, Bitbucket token.
- [`../../prisma/schema-overview.md`](../../prisma/schema-overview.md) — `Product`, `StageConfig`, `PollCache` models.
- [`../../../rules/all-three-envs.md`](../../../rules/all-three-envs.md), [`../../../rules/prisma-flow.md`](../../../rules/prisma-flow.md).
