"""Stage F4 — `scripts/build_examples.py` produces every viewing surface.

Two tiers, deliberately:

* the bulk of the suite runs with ``--no-render``, so it exercises discovery,
  the project write, the README, the gallery and the zip on a machine with no
  KiCad at all — and asserts that the output *says* renders were skipped rather
  than quietly implying they exist;
* one kicad-gated test does a real render and holds the GPS tracker to the
  actual gate: SVGs on disk and ``erc.json`` reporting **0 errors**.
"""

from __future__ import annotations

import html.parser
import importlib.util
import json
import re
import sys
import zipfile
from pathlib import Path

import pytest

from src.pipeline.kicad_cli import find_kicad_cli

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "build_examples.py"

requires_kicad = pytest.mark.skipif(
    find_kicad_cli() is None, reason="kicad-cli not available")


def _load_builder():
    """Import the script by path — scripts/ is not an importable package."""
    spec = importlib.util.spec_from_file_location("_build_examples_under_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


builder = _load_builder()

STAMP = "2026-01-02"


@pytest.fixture(scope="module")
def dry_build(tmp_path_factory):
    """One --no-render build, shared by every KiCad-free assertion."""
    out = tmp_path_factory.mktemp("build_norender")
    rc = builder.main(["--out", str(out), "--no-render", "--zip", "--date", STAMP])
    assert rc == 0
    return out


@pytest.fixture(scope="module")
def rendered_build(tmp_path_factory):
    """One real build with kicad-cli — renders, ERC and netlist for real."""
    if find_kicad_cli() is None:
        pytest.skip("kicad-cli not available")
    out = tmp_path_factory.mktemp("build_rendered")
    rc = builder.main(["--out", str(out), "--zip", "--date", STAMP])
    assert rc == 0, "a gate failed during the rendered build"
    return out


# ---------------------------------------------------------------------------
# Discovery + the KiCad project
# ---------------------------------------------------------------------------

def test_gps_tracker_is_discovered():
    names = [e.name for e in builder.discover_examples(REPO_ROOT / "examples")]
    assert "gps_tracker" in names


def test_example_module_honours_the_build_contract():
    """Every example must expose build() -> GeneratedProject; nothing else."""
    for example in builder.discover_examples(REPO_ROOT / "examples"):
        assert callable(example.module.build), example.name
        project = example.module.build()
        for attr in ("name", "files", "bom", "warnings", "designs", "layout_issues"):
            assert hasattr(project, attr), f"{example.name}.build() lacks {attr}"


def test_project_dir_has_the_expected_files(dry_build):
    project = dry_build / "examples" / "gps_tracker"
    names = {p.name for p in project.iterdir()}
    assert {
        "gps_tracker.kicad_pro",
        "gps_tracker.kicad_sch",
        "power.kicad_sch",
        "mcu.kicad_sch",
        "gps.kicad_sch",
        "sym-lib-table",
        "fp-lib-table",
        "README.md",
        "erc.json",
    } <= names
    # a real hierarchical project: root plus one sheet per sub-design
    assert len(list(project.glob("*.kicad_sch"))) == 4
    assert "(kicad_sch" in (project / "gps_tracker.kicad_sch").read_text()
    json.loads((project / "gps_tracker.kicad_pro").read_text())


# ---------------------------------------------------------------------------
# README
# ---------------------------------------------------------------------------

def test_readme_has_bom_nets_and_erc_sections(dry_build):
    readme = (dry_build / "examples" / "gps_tracker" / "README.md").read_text()
    for section in ("## Gates", "## Bill of materials", "## Nets", "## ERC",
                    "## Layout issues", "## Composer warnings",
                    "## Circuit block provenance"):
        assert section in readme, f"missing {section}"

    # the BOM is the real one, not a placeholder
    assert "| ref | value | lib_id | footprint | sheet |" in readme
    assert "ESP32-S3-WROOM-1" in readme
    assert "NEO-6M" in readme
    assert "`Regulator_Linear:AP2112K-3.3`" in readme
    assert "`Capacitor_SMD:C_0402_1005Metric`" in readme

    # the net table names real nets on real pads
    assert "| net | sheet | pins |" in readme
    assert "`+3.3V`" in readme and "`GND`" in readme


def test_readme_admits_when_nothing_was_rendered(dry_build):
    """The honesty gate: no render must never read as a successful render."""
    readme = (dry_build / "examples" / "gps_tracker" / "README.md").read_text()
    assert "ERC was **not run**" in readme
    assert "Not everything ran" in readme
    assert "--no-render" in readme
    assert "![" not in readme, "README links images that were never produced"


def test_erc_json_is_written_even_when_erc_did_not_run(dry_build):
    data = json.loads((dry_build / "examples" / "gps_tracker" / "erc.json").read_text())
    assert data["available"] is False
    assert data["reason"]
    assert data["errors"] is None


# ---------------------------------------------------------------------------
# Gallery
# ---------------------------------------------------------------------------

class _Parser(html.parser.HTMLParser):
    """Well-formedness check: every non-void tag closes, in order."""

    VOID = {"meta", "br", "hr", "img", "input", "link", "source", "path",
            "rect", "circle", "line", "polyline", "polygon", "use", "ellipse"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[str] = []
        self.errors: list[str] = []
        self.tags: set[str] = set()

    def handle_starttag(self, tag, attrs):
        self.tags.add(tag)
        if tag not in self.VOID:
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        self.tags.add(tag)

    def handle_endtag(self, tag):
        if tag in self.VOID:
            return
        if not self.stack:
            self.errors.append(f"</{tag}> with nothing open")
        elif self.stack[-1] != tag:
            self.errors.append(f"</{tag}> closes <{self.stack[-1]}>")
            if tag in self.stack:
                while self.stack and self.stack.pop() != tag:
                    pass
        else:
            self.stack.pop()


def _parse(text: str) -> _Parser:
    p = _Parser()
    p.feed(text)
    return p


def test_gallery_is_valid_self_contained_html(dry_build):
    gallery = dry_build / "gallery.html"
    text = gallery.read_text()

    assert text.startswith("<!doctype html>")
    parsed = _parse(text)
    assert parsed.errors == [], parsed.errors
    assert parsed.stack == [], f"unclosed tags: {parsed.stack}"
    assert {"html", "head", "body", "title", "style"} <= parsed.tags

    # self-contained: styles are inline, and nothing is fetched from anywhere
    assert "<style>" in text
    assert "<link" not in text
    assert "<script" not in text
    assert "@import" not in text
    for pattern in (r'src\s*=\s*"https?://', r'href\s*=\s*"https?://',
                    r"url\(\s*['\"]?https?://"):
        assert not re.search(pattern, text), f"external asset reference: {pattern}"

    # namespace declarations are the only URLs allowed to survive, and they
    # are never fetched
    urls = set(re.findall(r"https?://[^\"'>\s]+", text))
    assert urls <= {"http://www.w3.org/2000/svg", "http://www.w3.org/1999/xlink"}, urls


def test_gallery_is_theme_aware(dry_build):
    text = (dry_build / "gallery.html").read_text()
    assert "prefers-color-scheme: dark" in text
    assert "color-scheme: light dark" in text


def test_gallery_lists_parts_with_pins_footprint_and_status(dry_build):
    text = (dry_build / "gallery.html").read_text()
    assert "ESP32-S3-WROOM-1" in text
    assert "<dt>pins</dt><dd>41</dd>" in text
    assert "RF_Module:ESP32-S3-WROOM-1" in text
    assert "validated" in text, "COMPONENTS.md status is not surfaced"


def test_gallery_says_so_when_nothing_was_rendered(dry_build):
    text = (dry_build / "gallery.html").read_text()
    assert "<svg" not in text, "gallery shows renders that were never produced"
    assert "No renders in this build" in text
    assert "ERC not run" in text


# ---------------------------------------------------------------------------
# Zip
# ---------------------------------------------------------------------------

def test_zip_contains_what_it_claims(dry_build):
    archive = dry_build / f"hardware-examples-{STAMP}.zip"
    assert archive.is_file(), sorted(p.name for p in dry_build.iterdir())

    with zipfile.ZipFile(archive) as zf:
        assert zf.testzip() is None
        names = set(zf.namelist())
        # every file in the output tree, and nothing invented
        on_disk = {
            str(p.relative_to(dry_build)) for p in dry_build.rglob("*")
            if p.is_file() and p != archive
        }
        assert names == on_disk
        assert "gallery.html" in names
        assert "examples/gps_tracker/README.md" in names
        assert "examples/gps_tracker/gps_tracker.kicad_sch" in names
        # contents are real, not stubs
        assert b"Bill of materials" in zf.read("examples/gps_tracker/README.md")
        # entries carry the bundle date, not the wall clock
        for info in zf.infolist():
            assert info.date_time[:3] == (2026, 1, 2), info.filename


def test_zip_name_comes_from_the_date_argument(dry_build):
    assert (dry_build / f"hardware-examples-{STAMP}.zip").is_file()


def test_date_falls_back_to_input_mtime_not_the_clock(tmp_path):
    """No hidden clock call: with no --date the stamp is an input's mtime."""
    source = tmp_path / "design.py"
    source.write_text("")
    import os
    stamp_epoch = 1_500_000_000  # 2017-07-14 UTC
    os.utime(source, (stamp_epoch, stamp_epoch))
    assert builder.resolve_date(None, [source]).isoformat() == "2017-07-14"
    assert builder.resolve_date("2001-02-03", [source]).isoformat() == "2001-02-03"


# ---------------------------------------------------------------------------
# Flags
# ---------------------------------------------------------------------------

def test_parts_only_skips_examples(tmp_path):
    out = tmp_path / "parts_only"
    assert builder.main(["--out", str(out), "--no-render", "--parts-only",
                         "--date", STAMP]) == 0
    assert not (out / "examples").exists()
    assert (out / "gallery.html").is_file()


def test_examples_only_skips_parts(tmp_path):
    out = tmp_path / "examples_only"
    assert builder.main(["--out", str(out), "--no-render", "--examples-only",
                         "--date", STAMP]) == 0
    assert (out / "examples" / "gps_tracker" / "README.md").is_file()
    assert not (out / "parts").exists()
    assert "No generated part libraries found" in (out / "gallery.html").read_text()


def test_parts_only_and_examples_only_conflict(tmp_path):
    with pytest.raises(SystemExit):
        builder.main(["--out", str(tmp_path / "x"), "--no-render",
                      "--parts-only", "--examples-only"])


def test_no_render_does_not_touch_the_repo(tmp_path):
    """Building into tmp_path must never write into examples/ in the repo."""
    before = {p: p.stat().st_mtime_ns
              for p in (REPO_ROOT / "examples").rglob("*") if p.is_file()}
    assert builder.main(["--out", str(tmp_path / "iso"), "--no-render",
                         "--date", STAMP]) == 0
    after = {p: p.stat().st_mtime_ns
             for p in (REPO_ROOT / "examples").rglob("*") if p.is_file()}
    assert before == after


# ---------------------------------------------------------------------------
# SVG sanitising
# ---------------------------------------------------------------------------

_RAW_SVG = (
    '<?xml version="1.0" standalone="no"?>\n'
    ' <!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN"\n'
    ' "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd"> \n'
    '<svg xmlns="http://www.w3.org/2000/svg"\n'
    '  xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape"\n'
    '  width="25.7302mm" height="13.1064mm" viewBox="0 0 25.7302 13.1064">\n'
    "<title>SVG Image created as mcu.svg date 2026-08-02T11:52:17 </title>\n"
    "  <desc>Image generated by Eeschema-SVG </desc>\n"
    '<rect width="10" height="10" />\n</svg>\n'
)


def test_sanitize_svg_removes_the_wall_clock_stamp():
    """Committed renders must not churn in git diff on every rebuild."""
    out = builder.sanitize_svg(_RAW_SVG)
    assert "date 2026-08-02" not in out
    assert "<title>SVG Image created as mcu.svg</title>" in out
    assert "<?xml" not in out
    assert "DOCTYPE" not in out
    assert "svg11.dtd" not in out
    assert "inkscape" not in out
    assert 'viewBox="0 0 25.7302 13.1064"' in out


_SHEET_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg"\n'
    '  width="419.9890mm" height="297.0022mm"'
    ' viewBox="0.0000 0.0000 419.9890 297.0022">\n'
    # the page-sized background rect must not count as content
    '<rect x="0.000000" y="0.000000" width="419.989000" height="297.002200" />\n'
    '<rect x="27.940000" y="27.940000" width="15.240000" height="5.080000" />\n'
    '<path d="M 24.6380,139.7000\n26.1620,139.7000\n" />\n'
    # glyphs are stroked paths with space-separated absolute coordinates
    '<path d="M22.8599 135.9857\nL60.5000 135.5019\n" />\n'
    "</svg>\n"
)


def test_content_bbox_ignores_the_page_and_finds_every_glyph():
    box = builder.svg_content_bbox(_SHEET_SVG)
    assert box is not None
    minx, miny, maxx, maxy = box
    assert (minx, miny) == (22.8599, 27.94)
    # 60.5 comes from a space-separated "L" glyph path — the format that is
    # easy to miss and that carries all the visible text
    assert (maxx, maxy) == (60.5, 139.7)


def test_crop_svg_tightens_the_viewbox_without_moving_anything():
    out = builder.crop_svg(_SHEET_SVG, margin=2.0)
    root = out[out.index("<svg"):out.index(">") + 1]
    assert 'viewBox="20.8599 25.9400 41.6401 115.7600"' in root
    assert 'width="41.6401mm"' in root and 'height="115.7600mm"' in root
    # not one drawn coordinate changed
    assert '<path d="M 24.6380,139.7000' in out
    assert '<rect x="0.000000" y="0.000000"' in out


def test_crop_svg_leaves_an_empty_sheet_alone():
    empty = ('<svg xmlns="http://www.w3.org/2000/svg" '
             'viewBox="0 0 100 100"></svg>')
    assert builder.crop_svg(empty) == empty


def test_inline_svg_is_responsive_and_labelled():
    out = builder.inline_svg(_RAW_SVG, "part-svg", "ESP32 symbol")
    root = out[out.index("<svg"):out.index(">") + 1]
    assert 'width="25.7302mm"' not in root and 'height="13.1064mm"' not in root
    assert 'class="part-svg"' in root
    assert 'aria-label="ESP32 symbol"' in root
    assert 'role="img"' in root
    # inner geometry keeps its own sizing
    assert '<rect width="10" height="10" />' in out
    # the generator's title/desc do not become the accessible name
    assert "Eeschema-SVG" not in out
    assert "SVG Image created" not in out


# ---------------------------------------------------------------------------
# The real thing — needs KiCad
# ---------------------------------------------------------------------------

@requires_kicad
@pytest.mark.requires_kicad
def test_rendered_build_produces_svgs(rendered_build):
    render_dir = rendered_build / "examples" / "gps_tracker" / "render"
    names = {p.name for p in render_dir.glob("*.svg")}
    assert names == {"root.svg", "power.svg", "mcu.svg", "gps.svg"}, names
    for svg in render_dir.glob("*.svg"):
        text = svg.read_text()
        assert text.startswith("<svg"), f"{svg.name} kept its XML prologue"
        assert svg.stat().st_size > 2_000, f"{svg.name} looks empty"
        assert not re.search(r"date \d{4}-\d\d-\d\dT", text), f"{svg.name} is stamped"


@requires_kicad
@pytest.mark.requires_kicad
def test_rendered_build_erc_is_clean(rendered_build):
    """The gate: the GPS tracker composes to a schematic with 0 ERC errors."""
    data = json.loads(
        (rendered_build / "examples" / "gps_tracker" / "erc.json").read_text())
    assert data["available"] is True
    assert data["errors"] == 0, data["by_type"]
    assert data["schematic"] == "gps_tracker.kicad_sch"


@requires_kicad
@pytest.mark.requires_kicad
def test_rendered_build_exports_a_netlist(rendered_build):
    netlist = rendered_build / "examples" / "gps_tracker" / "netlist.xml"
    assert netlist.is_file()
    text = netlist.read_text()
    assert "<export" in text and "ESP32-S3-WROOM-1" in text
    assert str(rendered_build) not in text, "netlist leaks the build path"


@requires_kicad
@pytest.mark.requires_kicad
def test_rendered_gallery_inlines_every_render(rendered_build):
    text = (rendered_build / "gallery.html").read_text()
    assert text.count("<svg") >= 4 + 1, "sheets and part symbols should be inlined"
    assert "No renders in this build" not in text
    assert "ERC 0 errors" in text
    parsed = _parse(text)
    assert parsed.errors == [] and parsed.stack == []
    for pattern in (r'src\s*=\s*"https?://', r'href\s*=\s*"https?://'):
        assert not re.search(pattern, text)


@requires_kicad
@pytest.mark.requires_kicad
def test_rendered_parts_are_rendered(rendered_build):
    parts = rendered_build / "parts"
    assert (parts / "esp32_s3_wroom_1").is_dir()
    assert list((parts / "esp32_s3_wroom_1").glob("*.svg"))


# ---------------------------------------------------------------------------
# The committed surfaces
# ---------------------------------------------------------------------------

def test_committed_example_surfaces_exist():
    """`examples/gps_tracker/` carries the README + renders that git diffs."""
    example = REPO_ROOT / "examples" / "gps_tracker"
    assert (example / "design.py").is_file()
    readme = example / "README.md"
    assert readme.is_file(), "run: python scripts/build_examples.py --sync-repo"
    text = readme.read_text()
    assert "## Bill of materials" in text
    assert "ESP32-S3-WROOM-1" in text
    renders = {p.name for p in (example / "render").glob("*.svg")}
    assert renders == {"root.svg", "power.svg", "mcu.svg", "gps.svg"}, renders
    for name in sorted(renders):
        assert f"](render/{name})" in text, f"README does not show {name}"
