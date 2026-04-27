---
min_role: MAINTAINER
---
# Fixture Designs

A fixture design captures the hardware contract a test package
expects: which board revision it targets, what capabilities the rig
needs to expose, and the full fixture profile (power config, slot
defaults, capability list). Every test package owns exactly one
design — the design is created automatically when the package is
uploaded and travels with it for the package's lifetime.

[Fixture instances](instances.md) are the physical rigs that
implement a design. A fixture's `purpose` (`DEV` or `RELEASE`) gates
which package status it accepts: dev packages run only on dev rigs;
released packages run only on release rigs.

## Where designs come from

Designs are not created by hand in the API. They are extracted from
the test package's `concord.yaml` and `fixtures/*/fixture.yaml` at
upload time:

```yaml
# concord.yaml
fixture:
  design: "Alpha B0 Validation Fixture"
  revision: "1.0"
  profile: fixtures/alpha_b0/fixture.yaml
```

```yaml
# fixtures/alpha_b0/fixture.yaml
name: "Alpha B0 Validation Fixture"
revision: "1.0"
capabilities: [power, jlink, button]
power:
  ch0: { voltage_v: 4.5 }
# ...
```

When `corectl test upload` lands a package, the backend reads
`fixture.profile` from the manifest, parses the fixture YAML, and
upserts a `FixtureDesign` record keyed on the package id. Re-running
a dev upload overwrites the same design's profile in place. A
release uploads the same way — the design is immutable from that
point because the owning package is.

See the [corectl reference](../reference/corectl.md#test-packages)
for the upload flow.

## Design status

A design's status mirrors its owning package:

| Package status | Design status |
|----------------|---------------|
| `DEVELOPMENT` | `DEVELOPMENT` |
| `RELEASED` | `RELEASED` |

Promoting a package to `RELEASED` (`corectl test release` or the UI
release endpoint) propagates the status change to the design too, so
release-purpose fixtures can match against it.

## Listing designs

```bash
curl https://concord.local/v2/fixtures/designs \
  -H "Authorization: Bearer <token>"
```

Returns a paginated list including the owning package id, status,
board revision, and full profile template.

## Design detail

```bash
curl https://concord.local/v2/fixtures/designs/<design-id> \
  -H "Authorization: Bearer <token>"
```

## Lifecycle

Designs cascade from their TestPackage with `onDelete: Cascade`:
deleting a package removes its design too. Fixtures pin the design
they're set up for with `onDelete: Restrict`, so a design that is
currently bound to any fixture cannot be removed until the fixture
is reassigned. The retention cron also skips test packages whose
design is in use, surfacing a "stale fixture is holding this design"
log instead of attempting a destructive delete.

---

See also: [Fixture instances](instances.md) for the physical rigs
that implement a design, [Managing fixtures](managing-fixtures.md)
for the full fixture lifecycle, [Board revisions](../products/board-revisions.md)
for the revision records that designs reference.
