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
fixtures/{{board}}/      fixture controller + profile (backend-authoritative)
tests/
  <stage>/               one directory per enabled stage
    test_*.py            test modules — use the `assert_and_record` DSL
```

## Keeping this project in sync

The backend is the source of truth for the product slug, board revision,
and fixture controller class. If ops bumps a board revision or swaps a
testbed:

```bash
corectl test sync      # diff remote vs local, apply with confirm
```

Any command (`validate`, `run`, `upload`) will surface drift as a
non-fatal warning so you never run against a stale manifest silently.
