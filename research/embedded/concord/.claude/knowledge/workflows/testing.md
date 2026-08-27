# Testing — knowledge

How to run pytest, vitest, and Playwright against the Concord codebase, the markers that gate test selection, and what's forbidden (mocking the DB, mocking the MTIB).

Refresh this file when: a new pytest marker is added, the vitest/Playwright config changes, the dev compose stack changes shape, or a CI gate is added/removed.

## Prerequisites

- Devcontainer running (the `base` image bundles pytest, vitest, Playwright). Tests never run on the host.
- The local platform stack up (`nx start platform`) for any test that hits a real DB, MinIO, or MTIB.
- Submodules pulled (`git submodule update --init --recursive`) — manufacturing/validation submodules contribute fixture profiles consumed by integration tests.

## The flow

### Backend (Python / pytest)

```bash
nx test http-api                          # full suite
nx test http-api -- -k test_create_user   # filter by name
nx test http-api -- -m unit               # only unit tests
nx test http-api -- -m "not slow"         # skip slow tests
nx test http-api -- tests/api/v2/builds   # path subset
```

Pytest config lives in `apps/backend/http-api/pytest.ini`:

- `testpaths = tests`
- `addopts = -v --tb=short -n auto` — parallelized across CPUs by `pytest-xdist`.
- `pythonpath = src ../../../libs/python ../../../libs/protocols ../../../libs` — source modules and the generated `database` package resolve without an editable install.

#### Markers

| Marker | Meaning | When used |
|---|---|---|
| `unit` | Fast, isolated, no I/O | Default for new tests. Run on every pre-push. |
| `integration` | Uses real DB / MinIO / external services | Requires `nx start platform`. Run in CI on PR. |
| `contract` | Validates request/response envelope shape against `types.py` and `models.ts` | Run nightly + on schema changes. |
| `slow` | Takes >1s | Excluded from the default CI gate; run nightly. |

Mark every test with exactly one of `unit`, `integration`, `contract`, `slow`. Unmarked tests count as `unit` but reviewers will ask you to add the marker explicitly.

#### Fixtures

`apps/backend/http-api/tests/conftest.py` provides the shared fixtures:

- `db` — Prisma client pointing at the compose Postgres on `localhost:5433`. Wraps each test in a transaction that rolls back at teardown.
- `client` — Flask test client with an admin JWT pre-baked.
- `minio` — boto3 client against the compose MinIO.
- `mtib_stub` — gRPC stub against a recorded-response MTIB. Only acceptable mock; see "What's forbidden" below.

#### Other Python projects

```bash
nx test build-service
nx test git-poller
nx test mtib-server     # only on arm64; cross-compile via the mtib devcontainer
nx test corekinect      # libs/python/ — the SDK wheel's own tests
```

All inherit the same marker convention.

### Frontend (TypeScript)

#### Vitest (unit + component)

```bash
nx test app             # full vitest suite
nx test app -- --watch  # iterative dev
nx test app -- src/lib/stores
```

Config at `apps/frontend/app/vitest.config.ts`:

- Environment: `jsdom` (DOM available; no real browser).
- File patterns: `src/**/*.test.ts`, `src/**/*.spec.ts`.
- SvelteKit `$app/*` modules are stubbed via the aliases in `vitest.config.ts → resolve.alias`.
- Coverage: `v8` provider, includes `src/lib/**`.

#### Playwright (E2E)

```bash
nx run app:test:e2e                        # all E2E
nx run app:test:e2e -- --grep @smoke       # tagged subset
nx run app:test:e2e -- --headed            # see the browser
nx run app:test:e2e -- --update-snapshots  # regen visual baselines
```

Config: `apps/frontend/app/playwright.config.ts` (functional) and `playwright-visual.config.ts` (screenshot regression). E2E tests assume:

- `nx start platform` is running (the API is on `:9001`).
- `nx serve app` is running on `:4200` (Playwright spawns it itself if not).
- `AUTH_ENABLED=false` (the synthetic admin is logged in automatically).

Place E2E files at `apps/frontend/app/tests/e2e/`. Use `*.spec.ts` for functional, `*.visual.spec.ts` for visual.

### Platform-level (cross-service)

```bash
nx run platform:test                # full integration suite under tests/
nx run platform:test:smoke          # tests/smoke/ — post-deploy sanity
nx run platform:test:e2e            # tests/development/e2e/
```

These talk to the running compose stack and exercise the entire vertical (frontend → API → build worker → MinIO → audit log).

## What's forbidden

### Never mock the database

The dev compose stack provides a real Postgres on `:5433`. Use it. Integration tests wrap each test in a transaction (`async with db.tx() as tx: ...`) and roll back at teardown — there's no need for the speed of a mock.

If you find yourself writing `mock_db.product.find_unique.return_value = ...`, the test is in the wrong category. Either:

- Make it a `unit` test that doesn't touch persistence at all, or
- Promote it to `integration` and hit the real DB.

The single legitimate exception: testing the Prisma client wrapper itself (extremely rare, lives in `libs/python/database/tests/`).

### Never mock the MTIB in integration tests

Hardware contracts are too sharp to mock — gRPC stubs always drift from real device behavior. For integration tests of hardware-driven flows:

- Either run against a real fixture node and mark with `integration`.
- Or skip the test in environments without hardware (`@pytest.mark.skipif(not has_fixture_node(), ...)`).

The `mtib_stub` fixture in `conftest.py` is only for `contract` tests — validating the protobuf shapes match what `mtib-server` emits. It is **not** for asserting that a stage passes against fake data.

This rule is load-bearing. The 2025 Q4 manufacturing slot-swap incident traced to a mocked-pass test that masked a real wiring bug. See the relevant incident report under `/home/bottinger/work/docs/incidents/`.

### Don't bump test tolerances to make a test pass

If a measurement test was spec'd to ±2% and reality drifts to ±3%, the answer is:

- Confirm reality has actually shifted (calibration, hardware revision change).
- Update the spec — both the test value and the contract knowledge in `.claude/knowledge/`.
- Never silently widen a tolerance.

### Don't use bare `pytest` or `vitest`

Always go through Nx (`nx test <project>`). Bare tool invocations skip caching, env setup, and shared lint/typecheck preconditions. See [`../../rules/nx-only.md`](../../rules/nx-only.md).

## CI gates

The Bitbucket pipelines triggered on PR run, in order:

1. `nx affected:lint`
2. `nx affected:typecheck`
3. `nx affected:test -- -m "unit or contract"` — fast tests only
4. `nx affected:test -- -m integration` — against an ephemeral compose stack
5. `nx run app:test:e2e -- --grep @smoke` — sanity E2E

Nightly pipelines additionally run:

- `nx affected:test -- -m slow`
- `nx run platform:test:e2e` — full E2E
- `nx run app:test:e2e -- --grep @visual` — visual regression

The CI dashboard at `apps/frontend/ci-admin/` surfaces the nightly results.

## Local CI rehearsal

To run what CI runs before pushing:

```bash
nx affected:lint
nx affected:typecheck
nx affected:test -- -m "unit or contract"
nx affected:test -- -m integration
```

## Troubleshooting

**`prisma client not generated`** — run `npx prisma generate` from `prisma/` (the devcontainer post-start does this, but if you've blown away `libs/python/database/client/` you need to regenerate).

**`Connection refused` to Postgres in integration tests** — `nx start platform` isn't running, or it's running but `:5433` is bound to a different container. `docker compose ps` to confirm.

**Playwright tests timing out at login** — the frontend is hitting the wrong API URL. Check `apps/frontend/app/.env` — `VITE_API_URL` should be `http://localhost:9001` for local E2E.

**`pytest` reports `no tests ran` for a marker** — the marker isn't registered. Check `pytest.ini` `[pytest] markers =` block; add new markers there before using them.

**Visual snapshot diffs in CI but not locally** — font rendering differs between the CI Linux box and your devcontainer. Regenerate baselines inside the devcontainer with `nx run app:test:e2e -- --update-snapshots`, commit the new PNGs.

**Test hangs forever** — most often a leaked `socketio` connection. Add `@pytest.fixture(autouse=True)` cleanup or call `socketio_test_client.disconnect()` explicitly in teardown.

## Related knowledge

- [`local-dev.md`](local-dev.md) — getting the stack into a testable state
- [`debugging.md`](debugging.md) — debugging failures, including reading prod logs
- [`../conventions.md`](../conventions.md) — handler shape that tests assert
- [`../../rules/nx-only.md`](../../rules/nx-only.md) — why `nx test` and not `pytest`
- [`../../rules/prisma-flow.md`](../../rules/prisma-flow.md) — schema changes drive contract test updates
