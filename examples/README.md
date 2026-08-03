# Examples

Each subdirectory is one worked example. `scripts/build_examples.py` discovers
them, builds them, renders them, and writes the four viewing surfaces described
in `docs/` Stage F4:

| surface | where |
|---|---|
| a real, openable KiCad project | `build/examples/<name>/` |
| SVG renders + a README with BOM/nets/ERC | committed here in `examples/<name>/` |
| a single self-contained status page | `build/gallery.html` |
| a distributable bundle | `build/hardware-examples-<date>.zip` |

## The contract

Adding an example is a one-file change. Create
`examples/<name>/design.py` exposing:

```python
TITLE = "Human Readable Name"        # optional, defaults to <name>
SUMMARY = "One line about it."       # optional

def build() -> GeneratedProject:     # REQUIRED
    ...

def blocks() -> Sequence[Any]:       # optional — anything with .name and
    ...                              # .provenance; cited in the README
```

`build()` must return a `src.pipeline.composer.GeneratedProject` (or anything
with the same shape: `name`, `files`, `bom`, `wiring_notes`, `warnings`,
`designs`, `layout_issues`). Nothing else is registered anywhere — discovery is
by directory scan, so the new example appears in the gallery, the zip and the
per-example README automatically.

**One contract, two ways to satisfy it** — an example is either *composed* or
*authored*, and both end at the same type:

| the design is | `build()` calls | example |
|---|---|---|
| derived from a spec (MCU + peripherals + power) | `src.pipeline.composer.compose_design(spec)` | `gps_tracker` |
| authored sheet by sheet as typed `Design` objects | `src.pipeline.project_assembly.assemble_project(name, sheets)` | `esp32_s3_reference` |

`assemble_project` is the project layer on its own: it renumbers references
into one namespace (a KiCad hierarchy is one designator namespace), promotes
the non-power nets carried by more than one sheet to hierarchical labels,
flags each undriven rail on exactly one sheet, and emits the root. Returning
the raw sheets instead — a `dict[str, Design]` — is **not** the contract; the
builder has one code path on purpose.

Then regenerate the committed surfaces:

```bash
python scripts/build_examples.py --sync-repo --zip
```

## Regenerating

```bash
# everything, into build/ (needs kicad-cli on PATH for renders + ERC)
python scripts/build_examples.py --zip

# no KiCad installed? still produces projects, READMEs and the gallery,
# which say plainly that renders and ERC were skipped
python scripts/build_examples.py --no-render
```
