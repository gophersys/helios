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

def blocks() -> Sequence[Block]:     # optional — src.ecad.circuits blocks,
    ...                              # whose .provenance is cited in the README
```

`build()` must return a `src.pipeline.composer.GeneratedProject` (or anything
with the same shape: `name`, `files`, `bom`, `wiring_notes`, `warnings`,
`designs`, `layout_issues`). Nothing else is registered anywhere — discovery is
by directory scan, so the new example appears in the gallery, the zip and the
per-example README automatically.

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
