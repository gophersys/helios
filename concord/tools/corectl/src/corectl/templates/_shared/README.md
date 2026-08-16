# {{product}} / {{board}} — {{pkg_type}} tests

Scaffolded by `corectl test init`. The test framework is
[`corekinect.test`](https://concord.ad.corekinect.com/docs/testing/).

## Next steps

1. Fill in the `# >>> INSERT YOUR CODE HERE` markers in the stage files.
2. Run locally against a fixture:

   ```bash
   corectl validate       # pre-flight — no hardware needed
   corectl run smoke      # single stage on a local fixture
   corectl run            # all stages
   ```

3. Publish to the platform so others (and CI) can run it:

   ```bash
   corectl upload         # development version
   corectl upload --release   # promote to a semver release
   ```

## Layout

```
concord.yaml             manifest — owned by the backend, kept in sync by `corectl test sync`
pyproject.toml           package name + framework dependency
conftest.py              one-line framework plugin loader
testbeds/{{board}}/      testbed controller + profile (backend-authoritative)
tests/
  <stage>/               one directory per enabled stage
    test_*.py            test modules — use the `assert_and_record` DSL
```

## Devcontainer assumes the concord monorepo is on disk

The supplied `.devcontainer` is wired for the editable development
workflow: the concord monorepo is expected to be mounted at
`/workspaces/concord` so changes to `libs/python/corekinect/` land in
this container without a wheel rebuild.

Set up once:

1. Clone `concord/concord` next to this test app.
2. Make sure the devcontainer mounts it. The default `devcontainer.json`
   contains a bind mount along the lines of:

   ```jsonc
   "mounts": [
     "source=${localWorkspaceFolder}/../concord,target=/workspaces/concord,type=bind"
   ]
   ```

`.devcontainer/post-create.sh` will fail loudly if
`/workspaces/concord/libs/python/corekinect` is missing while
`CONCORD_DEV_MODE=1` is in effect — fix the layout (or unset the
env var) before the dev loop starts. Without the mount the editable
install silently picks up the wheel-from-PyPI version, and nothing
in the dev loop reflects local edits.

## Keeping this project in sync

The backend is the source of truth for the product slug, board revision,
and testbed controller class. If ops bumps a board revision or swaps a
testbed:

```bash
corectl test sync      # diff remote vs local, apply with confirm
```

Any command (`validate`, `run`, `upload`) will surface drift as a
non-fatal warning so you never run against a stale manifest silently.
