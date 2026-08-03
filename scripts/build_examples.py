#!/usr/bin/env python3
"""Build every viewing surface for the hardware pipeline from one source.

Stage F4. One script, one source of truth, four surfaces:

    build/examples/<name>/                 a real KiCad project you can open
      <name>.kicad_pro + .kicad_sch + sub-sheets + sym-lib-table + fp-lib-table
      render/root.svg, render/<sheet>.svg  kicad-cli sch export svg
      README.md                            BOM, nets, ERC, warnings, provenance
      erc.json                             src.pipeline.validate.run_erc
      netlist.xml                          kicad-cli sch export netlist
    build/parts/<part>/*.svg               kicad-cli sym export svg, per unit
    build/gallery.html                     self-contained status page
    build/hardware-examples-<date>.zip     all of the above

Adding an example is a one-directory change: drop
``examples/<name>/design.py`` with a ``build() -> GeneratedProject`` function
(see ``examples/README.md``). Discovery is a directory scan — there is no
registry to update.

Honest degradation: without ``kicad-cli`` on PATH (or with ``--no-render``) the
projects, READMEs, gallery and zip are still produced, and every surface says
in words that renders / ERC / netlist were skipped. Nothing implies an artifact
exists when it does not.

Reproducibility: the bundle date comes from ``--date`` or, failing that, from
the newest mtime of the build's own inputs (example modules + symbol
libraries + this script). There is no hidden clock call, so two runs over the
same tree produce the same file names, and the zip entries carry that date
rather than the wall clock.
"""

from __future__ import annotations

import argparse
import dataclasses
import html
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import zipfile
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from types import ModuleType
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.pipeline.kicad_cli import find_kicad_cli, kicad_cli_version  # noqa: E402
from src.pipeline.validate import run_erc  # noqa: E402

EXAMPLES_DIR = REPO_ROOT / "examples"
LIBRARY_DIR = REPO_ROOT / "src" / "ecad" / "library"
COMPONENTS_MD = REPO_ROOT / "COMPONENTS.md"
DEFAULT_OUT = REPO_ROOT / "build"

CLI_TIMEOUT = 180


# ---------------------------------------------------------------------------
# SVG handling
# ---------------------------------------------------------------------------

_XML_DECL = re.compile(r"<\?xml[^>]*\?>\s*")
_DOCTYPE = re.compile(r"<!DOCTYPE[^>]*>\s*")
_SVG_TITLE_DATE = re.compile(r"(<title>[^<]*?) date \d{4}-\d\d-\d\dT[\d:]+\s*")
_INKSCAPE_NS = re.compile(r'\s*xmlns:inkscape="[^"]*"')
_SVG_OPEN = re.compile(r"<svg\b[^>]*>", re.S)
_SIZE_ATTR = re.compile(r'\s(?:width|height)="[^"]*"')
_SVG_META = re.compile(r"\s*<(title|desc)>.*?</\1>", re.S)


def sanitize_svg(text: str) -> str:
    """Strip the wall-clock stamp and the XML prologue from a kicad-cli SVG.

    kicad-cli writes ``<title>SVG Image created as foo.svg date 2026-08-02T11:52:17 </title>``.
    That timestamp is the only non-deterministic byte in the output, and it
    would make every committed render show up in ``git diff`` on every rebuild.
    The prologue goes because these files are also inlined into the gallery,
    where a DOCTYPE referencing an external DTD has no business being.
    """
    text = _XML_DECL.sub("", text)
    text = _DOCTYPE.sub("", text)
    text = _INKSCAPE_NS.sub("", text)
    return _SVG_TITLE_DATE.sub(r"\1", text).lstrip()


def inline_svg(text: str, css_class: str, label: str) -> str:
    """A sanitized SVG ready to drop into HTML: responsive, no fixed size.

    The generator's own ``<title>``/``<desc>`` go: inlined into a page they
    become the image's accessible name, and "SVG Image created as mcu.svg" is
    not what a screen reader should announce.
    """
    svg = sanitize_svg(text)
    svg = _SVG_META.sub("", svg, count=2)
    match = _SVG_OPEN.search(svg)
    if match is None:
        return ""
    tag = _SIZE_ATTR.sub("", match.group(0))
    tag = (tag[:-1].rstrip()
           + f' class="{css_class}" role="img"'
           + f' aria-label="{html.escape(label, quote=True)}">')
    return svg[: match.start()] + tag + svg[match.end():]


_VIEWBOX = re.compile(r'viewBox="([-\d.eE\s]+)"')
_PATH_D = re.compile(r'\bd="([^"]*)"')
_RECT = re.compile(r"<rect\b([^>]*?)/?>")
_RECT_ATTR = re.compile(r'\b(x|y|width|height)="(-?[\d.]+)"')
_NUMBER = re.compile(r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")
_PATH_CMD = re.compile(r"[A-DF-Za-df-z]")   # every letter but e/E — exponents stay


def svg_content_bbox(svg: str) -> tuple[float, float, float, float] | None:
    """(minx, miny, maxx, maxy) of everything actually drawn, in user units.

    Exact, not an estimate: kicad-cli's schematic SVGs use only ``M``/``L``/
    ``Z`` — every number in a path is half of an absolute coordinate pair — and
    axis-aligned rects. Glyphs count too, because visible text is emitted as
    stroked paths (the ``<text>`` elements carry ``opacity="0"`` and exist only
    so the SVG stays searchable). The page-sized background rect is excluded:
    it is the thing that makes a three-part sheet claim a whole A3 page.
    """
    page: list[float] | None = None
    match = _VIEWBOX.search(svg)
    if match:
        nums = [float(n) for n in match.group(1).split()]
        page = nums if len(nums) == 4 else None

    xs: list[float] = []
    ys: list[float] = []
    for d in _PATH_D.findall(svg):
        nums = [float(n) for n in _NUMBER.findall(_PATH_CMD.sub(" ", d))]
        xs.extend(nums[0::2])
        ys.extend(nums[1::2])
    for attrs in _RECT.findall(svg):
        vals = dict(_RECT_ATTR.findall(attrs))
        if not {"x", "y", "width", "height"} <= vals.keys():
            continue
        x, y = float(vals["x"]), float(vals["y"])
        w, h = float(vals["width"]), float(vals["height"])
        if page and w >= page[2] - 0.5 and h >= page[3] - 0.5:
            continue
        xs += [x, x + w]
        ys += [y, y + h]

    if not xs or not ys:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def crop_svg(svg: str, margin: float = 3.0) -> str:
    """Tighten a sheet render's viewBox onto its content.

    A three-component power sheet laid out on an A3 page is 90% whitespace; at
    gallery-card size that reads as an empty card. Only the viewBox and the
    root width/height change — not a single drawn coordinate — so the file is
    still exactly what KiCad plotted.
    """
    box = svg_content_bbox(svg)
    match = _SVG_OPEN.search(svg)
    if box is None or match is None:
        return svg
    minx, miny, maxx, maxy = box
    x, y = minx - margin, miny - margin
    w, h = (maxx - minx) + 2 * margin, (maxy - miny) + 2 * margin
    if w <= 0 or h <= 0:
        return svg
    tag = _SIZE_ATTR.sub("", match.group(0))
    tag = _VIEWBOX.sub(
        f'viewBox="{x:.4f} {y:.4f} {w:.4f} {h:.4f}"', tag, count=1)
    tag = tag[:-1].rstrip() + f' width="{w:.4f}mm" height="{h:.4f}mm">'
    return svg[: match.start()] + tag + svg[match.end():]


def slug(text: str) -> str:
    """Lowercase filesystem/anchor-safe token."""
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_") or "unnamed"


def _norm_id(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


# ---------------------------------------------------------------------------
# kicad-cli
# ---------------------------------------------------------------------------

@dataclass
class Toolchain:
    """What we can actually do on this machine, decided once and reported."""

    cli: str | None
    version: str | None
    disabled: bool = False  # --no-render

    @property
    def available(self) -> bool:
        return self.cli is not None and not self.disabled

    @property
    def reason(self) -> str:
        """Why renders/ERC are missing — empty when they are not."""
        if self.disabled:
            return "--no-render was passed; kicad-cli was not invoked"
        if self.cli is None:
            return "kicad-cli was not found on PATH; install KiCad 10 (see docs/ci.md)"
        return ""

    @property
    def label(self) -> str:
        if self.available:
            return f"kicad-cli {self.version or 'unknown version'}"
        return "kicad-cli unavailable"

    def run(self, args: list[str]) -> subprocess.CompletedProcess | None:
        if not self.available:
            return None
        assert self.cli is not None
        try:
            return subprocess.run(
                [self.cli, *args], capture_output=True, text=True,
                timeout=CLI_TIMEOUT, check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return None


def detect_toolchain(no_render: bool) -> Toolchain:
    cli = find_kicad_cli()
    return Toolchain(cli=cli, version=kicad_cli_version() if cli else None,
                     disabled=no_render)


# ---------------------------------------------------------------------------
# Parts
# ---------------------------------------------------------------------------

@dataclass
class PartUnit:
    index: int
    name: str
    path: Path

    @property
    def label(self) -> str:
        return f"unit {self.index} ({self.name})" if self.name else f"unit {self.index}"


@dataclass
class Part:
    part_id: str
    part_name: str
    lib_id: str
    vendor: str
    source: Path                       # the .kicad_sym this part is rendered from
    pin_count: int | None = None
    footprint: str = ""
    description: str = ""
    unit_names: list[str] = field(default_factory=list)
    stage: str = ""
    gate: str = ""
    units: list[PartUnit] = field(default_factory=list)
    render_error: str = ""


def parse_components_md(path: Path) -> dict[str, dict[str, str]]:
    """id -> {vendor, kind, stage, gate} from the generated COMPONENTS.md table.

    Absent or malformed file is not an error: the gallery just shows the parts
    without a validation status rather than inventing one.
    """
    if not path.is_file():
        return {}
    out: dict[str, dict[str, str]] = {}
    for line in path.read_text().splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 5 or cells[0] in {"id", "---"} or set(cells[0]) <= {"-"}:
            continue
        out[_norm_id(cells[0])] = {
            "vendor": cells[1], "kind": cells[2],
            "stage": cells[3], "gate": cells[4],
        }
    return out


def discover_parts(library_dir: Path, components: dict[str, dict[str, str]]) -> list[Part]:
    """Every generated ``library/<vendor>/<part>.kicad_sym``, with its sidecar."""
    parts: list[Part] = []
    for sym in sorted(library_dir.glob("*/*.kicad_sym")):
        meta: dict[str, Any] = {}
        sidecar = sym.with_suffix(".json")
        if sidecar.is_file():
            try:
                meta = json.loads(sidecar.read_text())
            except json.JSONDecodeError:
                meta = {}
        part_id = str(meta.get("id") or sym.stem)
        fp = meta.get("footprint") or {}
        footprint = ""
        if isinstance(fp, dict) and fp.get("name"):
            footprint = f"{fp.get('lib', '')}:{fp['name']}".lstrip(":")
        row = components.get(_norm_id(part_id), {})
        parts.append(Part(
            part_id=part_id,
            part_name=str(meta.get("part_name") or sym.stem),
            lib_id=str(meta.get("lib_id") or ""),
            vendor=row.get("vendor") or sym.parent.name,
            source=sym,
            pin_count=meta.get("pin_count"),
            footprint=footprint,
            description=str(meta.get("description") or ""),
            unit_names=[str(u.get("name", "")) for u in meta.get("unit_plan", [])
                        if isinstance(u, dict)],
            stage=row.get("stage", ""),
            gate=row.get("gate", ""),
        ))
    return parts


_UNIT_SUFFIX = re.compile(r"_unit(\d+)$")


def render_parts(parts: list[Part], out_dir: Path, tools: Toolchain) -> None:
    """``kicad-cli sym export svg`` per part, into ``<out>/parts/<id>/``."""
    for part in parts:
        dest = out_dir / "parts" / slug(part.part_id)
        if not tools.available:
            part.render_error = tools.reason
            continue
        dest.mkdir(parents=True, exist_ok=True)
        result = tools.run(
            ["sym", "export", "svg", "-o", str(dest), str(part.source)])
        if result is None or result.returncode != 0:
            part.render_error = (
                (result.stderr.strip() if result else "kicad-cli did not run")
                or "kicad-cli sym export svg failed"
            )
            continue
        for svg in sorted(dest.glob("*.svg")):
            svg.write_text(sanitize_svg(svg.read_text()))
            match = _UNIT_SUFFIX.search(svg.stem)
            index = int(match.group(1)) if match else 1
            name = (part.unit_names[index - 1]
                    if 0 < index <= len(part.unit_names) else "")
            part.units.append(PartUnit(index=index, name=name, path=svg))
        part.units.sort(key=lambda u: u.index)
        if not part.units:
            part.render_error = "kicad-cli produced no SVG"


def representative_unit(part: Part) -> PartUnit | None:
    """The unit worth showing as the card thumbnail — the one with the most ink.

    Unit 1 is often a four-pin power stub; the largest file is the one a human
    would recognise as the part.
    """
    if not part.units:
        return None
    return max(part.units, key=lambda u: u.path.stat().st_size)


# ---------------------------------------------------------------------------
# Examples
# ---------------------------------------------------------------------------

@dataclass
class Example:
    name: str
    title: str
    summary: str
    module_path: Path
    module: ModuleType


@dataclass
class ExampleBuild:
    example: Example
    out_dir: Path
    project: Any                       # composer.GeneratedProject
    root_sch: str
    renders: list[tuple[str, Path]] = field(default_factory=list)  # (label, path)
    erc: dict[str, Any] = field(default_factory=dict)
    netlist: Path | None = None
    provenance: list[tuple[str, list[str]]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)   # honest "skipped because"

    @property
    def erc_ok(self) -> bool:
        return bool(self.erc.get("available")) and self.erc.get("errors") == 0

    @property
    def gate_summary(self) -> str:
        if self.project.layout_issues:
            return "layout lint failed"
        if not self.erc.get("available"):
            return "ERC not run"
        return "ERC 0 errors" if self.erc.get("errors") == 0 else (
            f"ERC {self.erc['errors']} errors")


def load_example(directory: Path) -> Example:
    """Import ``<dir>/design.py`` under a stable module name."""
    module_path = directory / "design.py"
    mod_name = f"_examples_{slug(directory.name)}_design"
    spec = importlib.util.spec_from_file_location(mod_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot import {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)
    if not callable(getattr(module, "build", None)):
        raise ImportError(
            f"{module_path} does not define build() -> GeneratedProject "
            f"(see examples/README.md)"
        )
    return Example(
        name=directory.name,
        title=str(getattr(module, "TITLE", "") or directory.name),
        summary=str(getattr(module, "SUMMARY", "") or ""),
        module_path=module_path,
        module=module,
    )


def discover_examples(examples_dir: Path) -> list[Example]:
    if not examples_dir.is_dir():
        return []
    return [load_example(d) for d in sorted(examples_dir.iterdir())
            if (d / "design.py").is_file()]


def _format_provenance(value: Any) -> list[str]:
    """Render a block's ``.provenance`` however src.ecad.circuits shapes it."""
    if value is None or value == "":
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple, set)):
        return [line for item in value for line in _format_provenance(item)]
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return [", ".join(f"{k}: {v}" for k, v in dataclasses.asdict(value).items()
                          if v not in (None, "", [], {}))]
    if isinstance(value, dict):
        return [", ".join(f"{k}: {v}" for k, v in value.items() if v)]
    return [str(value)]


def collect_provenance(example: Example) -> list[tuple[str, list[str]]]:
    """``blocks()`` is optional; only designs built from src.ecad.circuits have it."""
    blocks = getattr(example.module, "blocks", None)
    if blocks is None:
        return []
    try:
        items = blocks() if callable(blocks) else blocks
    except Exception as exc:  # noqa: BLE001 - a broken hook must not kill the build
        return [("blocks() raised", [f"{type(exc).__name__}: {exc}"])]
    out: list[tuple[str, list[str]]] = []
    for block in items or []:
        name = str(getattr(block, "name", "") or type(block).__name__)
        cites = _format_provenance(getattr(block, "provenance", None))
        out.append((name, cites or ["(block declares no provenance)"]))
    return out


def build_example(example: Example, out_root: Path, tools: Toolchain,
                  stamp: date) -> ExampleBuild:
    """Compose, write, render, ERC and netlist one example."""
    project = example.module.build()
    out_dir = out_root / "examples" / example.name
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    for filename, content in project.files.items():
        (out_dir / filename).write_text(content)

    pro = next((f for f in sorted(project.files) if f.endswith(".kicad_pro")), None)
    root_sch = (Path(pro).stem + ".kicad_sch") if pro else next(
        f for f in sorted(project.files) if f.endswith(".kicad_sch"))

    build = ExampleBuild(example=example, out_dir=out_dir, project=project,
                         root_sch=root_sch,
                         provenance=collect_provenance(example))

    _render_example(build, tools)
    _erc_example(build, tools)
    _netlist_example(build, tools, stamp)
    # kicad-cli drops a .kicad_prl (local UI state) beside the project. It is
    # gitignored everywhere else in this repo and carries no design content, so
    # it has no business in a reproducible bundle.
    for stray in out_dir.glob("*.kicad_prl"):
        stray.unlink()
    (out_dir / "README.md").write_text(render_readme(build, tools))
    return build


def _render_example(build: ExampleBuild, tools: Toolchain) -> None:
    render_dir = build.out_dir / "render"
    if not tools.available:
        build.notes.append(f"Schematic renders skipped: {tools.reason}.")
        return
    render_dir.mkdir(parents=True, exist_ok=True)
    result = tools.run([
        "sch", "export", "svg", "-o", str(render_dir),
        "--exclude-drawing-sheet", str(build.out_dir / build.root_sch),
    ])
    if result is None or result.returncode != 0:
        build.notes.append(
            "Schematic renders failed: "
            + ((result.stderr.strip() if result else "kicad-cli did not run")
               or "kicad-cli sch export svg failed")
        )
        return

    # kicad-cli names the root sheet <stem>.svg and every sub-sheet
    # <stem>-<Sheet Title>.svg. Rename to render/root.svg + render/<sheet>.svg
    # so the README's image links stay stable when a project is renamed.
    stem = Path(build.root_sch).stem
    taken: set[str] = set()
    for svg in sorted(render_dir.glob("*.svg")):
        if svg.stem == stem:
            label = "root"
        elif svg.stem.startswith(stem + "-"):
            label = svg.stem[len(stem) + 1:]
        else:
            label = svg.stem
        name = slug(label)
        while name in taken:
            name += "_"
        taken.add(name)
        target = render_dir / f"{name}.svg"
        text = crop_svg(sanitize_svg(svg.read_text()))
        svg.unlink()
        target.write_text(text)
        build.renders.append((label, target))
    build.renders.sort(key=lambda item: (item[0] != "root", item[0]))
    if not build.renders:
        build.notes.append("Schematic renders failed: kicad-cli produced no SVG.")


def _erc_example(build: ExampleBuild, tools: Toolchain) -> None:
    root = build.out_dir / build.root_sch
    if not tools.available:
        build.erc = {"schematic": build.root_sch, "available": False,
                     "reason": tools.reason, "errors": None, "warnings": None,
                     "violations": None, "by_type": {}, "details": []}
    else:
        result = run_erc(root)
        if result.get("success"):
            by_type = Counter(
                f"{v.get('severity', '?')}/{v.get('type', '?')}"
                for v in result.get("details", []))
            build.erc = {
                "schematic": build.root_sch, "available": True, "reason": "",
                "errors": result["errors"], "warnings": result["warnings"],
                "violations": result["violations"],
                "by_type": dict(sorted(by_type.items())),
                "details": result.get("details", []),
            }
        else:
            build.erc = {
                "schematic": build.root_sch, "available": False,
                "reason": result.get("stderr") or "kicad-cli sch erc failed",
                "errors": None, "warnings": None, "violations": None,
                "by_type": {}, "details": [],
            }
            build.notes.append(f"ERC did not run: {build.erc['reason']}")
    (build.out_dir / "erc.json").write_text(
        json.dumps(build.erc, indent=2, sort_keys=True) + "\n")


_NETLIST_SOURCE = re.compile(r"<source>.*?</source>", re.S)
_NETLIST_DATE = re.compile(r"<date>.*?</date>", re.S)


def _netlist_example(build: ExampleBuild, tools: Toolchain, stamp: date) -> None:
    target = build.out_dir / "netlist.xml"
    if not tools.available:
        build.notes.append(f"Netlist export skipped: {tools.reason}.")
        return
    result = tools.run([
        "sch", "export", "netlist", "--format", "kicadxml",
        "-o", str(target), str(build.out_dir / build.root_sch),
    ])
    if result is None or result.returncode != 0 or not target.is_file():
        build.notes.append("Netlist export failed: "
                           + ((result.stderr.strip() if result else "kicad-cli did not run")
                              or "kicad-cli sch export netlist failed"))
        return
    # kicad-cli stamps the netlist with the absolute path it was run from and
    # the wall clock. Both are facts about this machine, not about the design,
    # and they are the only thing that would stop two builds of the same tree
    # from producing byte-identical bundles.
    text = target.read_text()
    text = _NETLIST_SOURCE.sub(f"<source>{build.example.name}/{build.root_sch}</source>",
                               text, count=1)
    text = _NETLIST_DATE.sub(f"<date>{stamp.isoformat()}</date>", text, count=1)
    target.write_text(text)
    build.netlist = target


# ---------------------------------------------------------------------------
# README
# ---------------------------------------------------------------------------

def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    if not rows:
        return "_(none)_\n"
    out = ["| " + " | ".join(headers) + " |",
           "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return "\n".join(out) + "\n"


def _net_rows(project: Any) -> list[list[str]]:
    rows: list[list[str]] = []
    for filename in sorted(project.designs):
        design = project.designs[filename]
        for net, pins in sorted(design.intended_netlist().items()):
            rows.append([f"`{net}`", Path(filename).stem,
                         ", ".join(sorted(pins)) or "_none_"])
    return rows


def render_readme(build: ExampleBuild, tools: Toolchain) -> str:
    project = build.project
    ex = build.example
    erc = build.erc

    if erc.get("available"):
        erc_line = f"{erc['errors']} errors, {erc['warnings']} warnings"
    else:
        erc_line = f"not run — {erc.get('reason', 'unknown reason')}"

    if build.renders:
        render_line = f"{len(build.renders)} SVG via {tools.label}"
    else:
        render_line = f"none — {tools.reason or 'render step failed'}"

    parts: list[str] = [
        f"# {ex.title}",
        "",
        ex.summary or "",
        "",
        "Generated by `scripts/build_examples.py` from "
        f"`examples/{ex.name}/design.py` — do not edit by hand.",
        "",
        "## Gates",
        "",
        _md_table(["gate", "result"], [
            ["layout lint",
             "clean" if not project.layout_issues
             else f"{sum(len(v) for v in project.layout_issues.values())} issue(s)"],
            ["ERC", erc_line],
            ["schematic renders", render_line],
            ["netlist export",
             "`netlist.xml`" if build.netlist else "not run"],
            ["composer warnings", str(len(project.warnings))],
            ["components", str(len(project.bom))],
        ]),
    ]

    if build.notes:
        parts += ["> **Not everything ran.**", ">"]
        parts += [f"> - {note}" for note in build.notes]
        parts += [""]

    if build.renders:
        parts += ["## Schematic", ""]
        for label, path in build.renders:
            parts += [f"### {label}", "", f"![{label}](render/{path.name})", ""]

    parts += [
        "## Bill of materials",
        "",
        _md_table(["ref", "value", "lib_id", "footprint", "sheet"], [
            [e["ref"], e["value"], f"`{e['lib_id']}`",
             f"`{e['footprint']}`" if e["footprint"] else "_unset_", e["sheet"]]
            for e in project.bom
        ]),
        "## Nets",
        "",
        _md_table(["net", "sheet", "pins"], _net_rows(project)),
        "## ERC",
        "",
    ]

    if erc.get("available"):
        parts += [
            f"`{erc['schematic']}` — **{erc['errors']} error(s)**, "
            f"{erc['warnings']} warning(s), {erc['violations']} violation(s) total.",
            "",
            _md_table(["severity / type", "count"],
                      [[f"`{k}`", str(v)] for k, v in erc["by_type"].items()]),
        ]
    else:
        parts += [f"ERC was **not run**: {erc.get('reason', 'unknown reason')}.", ""]

    parts += ["## Layout issues", ""]
    if project.layout_issues:
        parts += [_md_table(["sheet", "issue"], [
            [sheet, issue] for sheet, issues in sorted(project.layout_issues.items())
            for issue in issues])]
    else:
        parts += ["None — every sheet came out of the layout engine clean.", ""]

    parts += ["## Composer warnings", ""]
    if project.warnings:
        parts += [f"- {w}" for w in project.warnings] + [""]
    else:
        parts += ["None.", ""]

    parts += ["## Wiring notes", ""]
    parts += ([f"- {n}" for n in project.wiring_notes] or ["None."]) + [""]

    parts += ["## Circuit block provenance", ""]
    if build.provenance:
        for name, cites in build.provenance:
            parts += [f"- **{name}**"] + [f"  - {c}" for c in cites]
        parts += [""]
    else:
        parts += [
            "This design does not use `src.ecad.circuits` blocks, so there is "
            "nothing to cite. Examples built from those blocks list every "
            "block's datasheet/app-note citation here.",
            "",
        ]

    parts += [
        "## Open it in KiCad",
        "",
        "```bash",
        f"python scripts/build_examples.py --examples-only   # writes build/examples/{ex.name}/",
        f"kicad build/examples/{ex.name}/{Path(build.root_sch).stem}.kicad_pro",
        "```",
        "",
    ]
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Gallery
# ---------------------------------------------------------------------------

_CSS = """
:root {
  color-scheme: light dark;
  --bg: #ffffff; --fg: #16181d; --muted: #5c6470; --line: #e2e5ea;
  --card: #fafbfc; --accent: #2f6feb; --ok: #1a7f37; --warn: #9a6700;
  --bad: #b42318; --sheet: #f5f4ef;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #0d1117; --fg: #e6edf3; --muted: #8b949e; --line: #262c36;
    --card: #151b23; --accent: #6ea8ff; --ok: #3fb950; --warn: #d29922;
    --bad: #f85149;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--fg);
  font: 15px/1.55 ui-sans-serif, -apple-system, "Segoe UI", Roboto, sans-serif;
}
.wrap { max-width: 1100px; margin: 0 auto; padding: 2.5rem 1.25rem 4rem; }
h1 { font-size: 1.7rem; margin: 0 0 .35rem; letter-spacing: -.01em; }
h2 { font-size: 1.15rem; margin: 2.75rem 0 .35rem; letter-spacing: -.01em; }
h3 { font-size: .95rem; margin: 0 0 .2rem; }
p { margin: .35rem 0; }
.sub { color: var(--muted); font-size: .875rem; }
.rule { height: 1px; background: var(--line); margin: .9rem 0 1.4rem; }
.meta { display: flex; flex-wrap: wrap; gap: .4rem .9rem; font-size: .8rem;
        color: var(--muted); margin-top: .5rem; }
.meta code { color: var(--fg); }
code, .mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
              font-size: .82em; }
.badge { display: inline-block; padding: .08rem .45rem; border-radius: 999px;
         border: 1px solid var(--line); font-size: .72rem; font-weight: 600;
         letter-spacing: .02em; white-space: nowrap; }
.badge.ok { color: var(--ok); border-color: currentColor; }
.badge.warn { color: var(--warn); border-color: currentColor; }
.badge.bad { color: var(--bad); border-color: currentColor; }
.notice { border: 1px solid var(--warn); border-left-width: 3px;
          border-radius: 6px; padding: .6rem .8rem; margin: 1rem 0;
          color: var(--warn); font-size: .85rem; }
.grid { display: grid; gap: 1rem;
        grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); }
.card { border: 1px solid var(--line); border-radius: 10px;
        background: var(--card); overflow: hidden; }
.card .body { padding: .7rem .8rem .8rem; }
.thumb { background: var(--sheet); border-bottom: 1px solid var(--line);
         padding: .8rem; display: flex; align-items: center;
         justify-content: center; min-height: 130px; }
.thumb svg { width: 100%; height: auto; max-height: 190px; display: block; }
.empty { color: var(--muted); font-size: .78rem; text-align: center;
         padding: 2rem .5rem; }
dl { display: grid; grid-template-columns: auto 1fr; gap: .1rem .6rem;
     margin: .45rem 0 0; font-size: .8rem; }
dt { color: var(--muted); }
dd { margin: 0; overflow-wrap: anywhere; }
.example { border: 1px solid var(--line); border-radius: 10px;
           background: var(--card); padding: 1rem 1.1rem 1.2rem;
           margin-bottom: 1.25rem; }
.sheets { display: grid; gap: .9rem; margin-top: 1rem; align-items: start;
          grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); }
.sheet figure { margin: 0; border: 1px solid var(--line); border-radius: 8px;
                overflow: hidden; background: var(--sheet); }
/* cap the height so a tall MCU sheet and a wide root sheet stay comparable;
   the viewBox letterboxes the drawing rather than distorting it */
.sheet svg { width: 100%; height: auto; max-height: 340px; display: block;
             padding: .5rem; }
.sheet figcaption { font-size: .75rem; color: var(--muted);
                    padding: .35rem .55rem; background: var(--card);
                    border-top: 1px solid var(--line); }
ul.tight { margin: .4rem 0 0; padding-left: 1.1rem; font-size: .85rem; }
footer { margin-top: 3rem; color: var(--muted); font-size: .78rem; }
"""


def _badge(text: str, kind: str) -> str:
    return f'<span class="badge {kind}">{html.escape(text)}</span>'


def _part_badge(part: Part) -> str:
    kind = {"validated": "ok"}.get(part.stage, "warn" if part.stage else "bad")
    return _badge(part.stage or "no COMPONENTS.md row", kind)


def _example_badge(build: ExampleBuild) -> str:
    erc = build.erc
    if build.project.layout_issues:
        return _badge("layout lint failed", "bad")
    if not erc.get("available"):
        return _badge("ERC not run", "warn")
    if erc.get("errors"):
        return _badge(f"ERC {erc['errors']} errors", "bad")
    return _badge("ERC 0 errors", "ok")


def render_gallery(parts: list[Part], builds: list[ExampleBuild],
                   tools: Toolchain, stamp: date) -> str:
    e = html.escape
    out: list[str] = [
        "<!doctype html>", '<html lang="en">', "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        "<title>Hardware pipeline — parts and examples</title>",
        f"<style>{_CSS}</style>", "</head>", "<body>", '<div class="wrap">',
        "<h1>Hardware pipeline — parts and examples</h1>",
        '<p class="sub">Every generated part symbol and every worked example, '
        "rendered from the same source by "
        "<code>scripts/build_examples.py</code>.</p>",
        '<div class="meta">',
        f"<span>bundle date <code>{e(stamp.isoformat())}</code></span>",
        f"<span>toolchain <code>{e(tools.label)}</code></span>",
        f"<span><code>{len(parts)}</code> part{'' if len(parts) == 1 else 's'}</span>",
        f"<span><code>{len(builds)}</code> example{'' if len(builds) == 1 else 's'}</span>",
        "</div>",
    ]

    if not tools.available:
        out.append(
            '<div class="notice"><strong>No renders in this build.</strong> '
            f"{e(tools.reason)}. Every image slot below is empty on purpose — "
            "nothing here was drawn.</div>"
        )

    # ---- examples --------------------------------------------------------
    out += ['<h2>Examples</h2>', '<div class="rule"></div>']
    if not builds:
        out.append('<p class="sub">No examples in this build.</p>')
    for build in builds:
        ex = build.example
        erc = build.erc
        out += [
            '<section class="example">',
            f"<h3>{e(ex.title)} {_example_badge(build)}</h3>",
            f'<p class="sub">{e(ex.summary)}</p>' if ex.summary else "",
            '<div class="meta">',
            f"<span>project <code>examples/{e(ex.name)}/"
            f"{e(Path(build.root_sch).stem)}.kicad_pro</code></span>",
            f"<span><code>{len(build.project.bom)}</code> components</span>",
            f"<span><code>{len(build.project.designs)}</code> sub-sheets</span>",
            f"<span>ERC <code>{erc['errors']} err / {erc['warnings']} warn</code></span>"
            if erc.get("available") else "<span>ERC <code>not run</code></span>",
            f"<span><code>{len(build.project.warnings)}</code> composer warnings</span>",
            "</div>",
        ]
        if build.notes:
            out.append('<div class="notice">'
                       + "<br>".join(e(n) for n in build.notes) + "</div>")
        if build.renders:
            out.append('<div class="sheets">')
            for label, path in build.renders:
                out += [
                    '<div class="sheet"><figure>',
                    inline_svg(path.read_text(), "sheet-svg",
                               f"{ex.title} — {label} sheet schematic"),
                    f"<figcaption>{e(label)} — <code>render/{e(path.name)}"
                    "</code></figcaption>",
                    "</figure></div>",
                ]
            out.append("</div>")
        if build.project.warnings:
            out.append('<ul class="tight">'
                       + "".join(f"<li>{e(w)}</li>" for w in build.project.warnings)
                       + "</ul>")
        out.append("</section>")

    # ---- parts -----------------------------------------------------------
    out += ["<h2>Generated parts</h2>", '<div class="rule"></div>']
    if not parts:
        out.append('<p class="sub">No generated part libraries found.</p>')
    else:
        out.append('<div class="grid">')
        for part in parts:
            unit = representative_unit(part)
            if unit is not None:
                thumb = ('<div class="thumb">'
                         + inline_svg(unit.path.read_text(), "part-svg",
                                      f"{part.part_name} symbol, {unit.label}")
                         + "</div>")
                shown = f"{unit.label} of {len(part.units)}"
            else:
                thumb = ('<div class="thumb"><div class="empty">no render — '
                         + e(part.render_error or tools.reason
                             or "kicad-cli produced nothing")
                         + "</div></div>")
                shown = "not rendered"
            out += [
                '<div class="card">', thumb, '<div class="body">',
                f"<h3>{e(part.part_name)}</h3>",
                f'<p class="sub">{_part_badge(part)} '
                f"<span>{e(part.gate)}</span></p>" if part.gate
                else f'<p class="sub">{_part_badge(part)}</p>',
                "<dl>",
                f"<dt>pins</dt><dd>{part.pin_count if part.pin_count else '?'}</dd>",
                f"<dt>footprint</dt><dd><code>{e(part.footprint or 'unset')}</code></dd>",
                f"<dt>symbol</dt><dd><code>{e(part.lib_id or part.part_id)}</code></dd>",
                f"<dt>shown</dt><dd>{e(shown)}</dd>",
                "</dl>", "</div>", "</div>",
            ]
        out.append("</div>")

    out += [
        "<footer>Self-contained page: every image is an inlined SVG and there "
        "are no external requests. Regenerate with "
        "<code>python scripts/build_examples.py --zip</code>.</footer>",
        "</div>", "</body>", "</html>",
    ]
    return "\n".join(line for line in out if line) + "\n"


# ---------------------------------------------------------------------------
# Repo sync + zip
# ---------------------------------------------------------------------------

def sync_to_repo(build: ExampleBuild) -> list[Path]:
    """Copy the human-facing surfaces back next to the example's source.

    Only ``README.md`` and ``render/*.svg`` — the heavy build products stay in
    the output directory. This is what makes ``git diff`` show visual changes.
    Renders are only replaced when this build actually produced some, so a
    ``--no-render`` run never silently deletes committed images.
    """
    dest = build.example.module_path.parent
    written = [dest / "README.md"]
    (dest / "README.md").write_text((build.out_dir / "README.md").read_text())
    if build.renders:
        render_dir = dest / "render"
        if render_dir.exists():
            shutil.rmtree(render_dir)
        render_dir.mkdir(parents=True)
        for _label, path in build.renders:
            target = render_dir / path.name
            target.write_text(path.read_text())
            written.append(target)
    return written


def write_zip(out_dir: Path, zip_path: Path, stamp: date) -> int:
    """Zip everything in ``out_dir``, reproducibly.

    Entry order, timestamps and permissions are fixed so two runs over the same
    tree produce byte-identical archives — the zip is a build product, not a
    record of when someone happened to run the script.
    """
    files = sorted(p for p in out_dir.rglob("*")
                   if p.is_file() and p != zip_path)
    stamped = (stamp.year, stamp.month, stamp.day, 0, 0, 0)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in files:
            info = zipfile.ZipInfo(str(path.relative_to(out_dir)), date_time=stamped)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, path.read_bytes())
    return len(files)


def resolve_date(arg: str | None, inputs: list[Path]) -> date:
    """The bundle date — from the argument, else the newest input mtime.

    Deliberately never ``date.today()``: a hidden clock call makes the output
    name change for reasons unrelated to the content, which is untestable and
    unreproducible.
    """
    if arg:
        return date.fromisoformat(arg)
    mtimes = [p.stat().st_mtime for p in inputs if p.exists()]
    if not mtimes:
        raise SystemExit(
            "cannot derive a bundle date: no inputs found and --date not given")
    return datetime.fromtimestamp(max(mtimes), tz=timezone.utc).date()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="build_examples.py", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT,
                    help="output directory (default: build/)")
    ap.add_argument("--zip", action="store_true",
                    help="also write hardware-examples-<date>.zip into --out")
    ap.add_argument("--parts-only", action="store_true",
                    help="render generated part symbols only")
    ap.add_argument("--examples-only", action="store_true",
                    help="build examples only, skip part symbol renders")
    ap.add_argument("--no-render", action="store_true",
                    help="never invoke kicad-cli (no SVGs, no ERC, no netlist); "
                         "runs anywhere KiCad is absent and says so in the output")
    ap.add_argument("--sync-repo", action="store_true",
                    help="also write README.md + render/*.svg back into "
                         "examples/<name>/ so git diff shows the change")
    ap.add_argument("--date", metavar="YYYY-MM-DD",
                    help="bundle date (default: newest input mtime)")
    ap.add_argument("--examples-dir", type=Path, default=EXAMPLES_DIR,
                    help=argparse.SUPPRESS)
    ap.add_argument("--library-dir", type=Path, default=LIBRARY_DIR,
                    help=argparse.SUPPRESS)
    args = ap.parse_args(argv)

    if args.parts_only and args.examples_only:
        ap.error("--parts-only and --examples-only are mutually exclusive")

    out_dir: Path = args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    tools = detect_toolchain(args.no_render)

    examples = [] if args.parts_only else discover_examples(args.examples_dir)
    components = parse_components_md(COMPONENTS_MD)
    parts = [] if args.examples_only else discover_parts(args.library_dir, components)

    stamp = resolve_date(args.date, [
        *(ex.module_path for ex in examples),
        *(p.source for p in parts),
        Path(__file__).resolve(),
    ])

    render_parts(parts, out_dir, tools)
    builds = [build_example(ex, out_dir, tools, stamp) for ex in examples]

    if args.sync_repo:
        for build in builds:
            for path in sync_to_repo(build):
                print(f"  synced {path.relative_to(REPO_ROOT)}")

    gallery = out_dir / "gallery.html"
    gallery.write_text(render_gallery(parts, builds, tools, stamp))

    zip_path: Path | None = None
    if args.zip:
        zip_path = out_dir / f"hardware-examples-{stamp.isoformat()}.zip"
        count = write_zip(out_dir, zip_path, stamp)
        print(f"  {zip_path.name}: {count} files")

    # ---- report ----------------------------------------------------------
    print(f"toolchain: {tools.label}" + (f" ({tools.reason})" if tools.reason else ""))
    rendered = sum(1 for p in parts if p.units)
    if parts:
        print(f"parts: {rendered}/{len(parts)} rendered -> {out_dir / 'parts'}")
    for build in builds:
        print(f"example {build.example.name}: {build.gate_summary}, "
              f"{len(build.renders)} render(s) -> {build.out_dir}")
        for note in build.notes:
            print(f"    ! {note}")
    print(f"gallery: {gallery} ({gallery.stat().st_size // 1024} KiB)")

    failed = [b for b in builds
              if b.project.layout_issues or (b.erc.get("errors") or 0) > 0]
    if failed:
        print("FAILED gates: " + ", ".join(b.example.name for b in failed))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
