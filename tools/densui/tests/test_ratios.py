"""Ratio rows become a general, EXECUTED predicate (W1 of deep-craft).

`demos/telemetry/panel.toml` has declared ratio expectations for months:

    [ratio]
    panel_w = [1120, 5]
    panel_h = [320, 5]
    dial = [28, 1]
    row = [72, 4]

Nothing ever read them. `spec.py` validated their shape, `cli audit` never
looked at `cfg["ratio"]`, `run_battery` has no ratio check, and the verifier
agent claims the ratio table runs in `ctl.sh geometry` — true only of
`demos/operator/build/ratio_audit.py`, which hand-writes its own rows. A
believed check that checks nothing, on the defect class Mateo named first
(wrong size ratios). These tests are what makes the rows real.

Four properties are load-bearing and each has a test here:

1. a row that is outside tolerance fails and its message carries the row name,
   the measured value, the want and the tol — a failure that says only "ratio
   failed" cannot be acted on;
2. a multi-instance kind reduces by MEDIAN (not mean: one drifted instance must
   not drag the reported value), and the instance spread is its OWN failure —
   three dials at 27/27/33 are a defect even though their median is exact;
3. a row measuring nothing (unknown kind, no instances) FAILS. Zero violations
   from a row that matched no element is the same lie in a new place;
4. the old untyped `name = [want, tol]` form dies with a named migration error.
   No legacy acceptance: a spec that silently keeps working while its rows mean
   something new is how a dormant check survives a rewrite.

Imports of `check_ratios` are attribute lookups on `densui.audit` inside each
test on purpose: a module-level `from densui.audit import check_ratios` would
collapse this whole file into one collection error before the feature lands,
and a red that names no test is not evidence.
"""

import json
import pathlib
import re
import tomllib

import pytest

from densui import audit
from densui.spec import SpecError, load_panel

REPO = pathlib.Path(__file__).resolve().parents[3]
TELEMETRY = REPO / "demos" / "telemetry" / "panel.toml"
DOC = REPO / "docs" / "spec.md"


def part(c, kind, owner, r):
    return {"c": c, "kind": kind, "owner": owner, "r": list(r)}


# One plate, one knob unit: dial 27x27 at (10,20), label ink 50x12 under it.
# root is the probe root rect — W1 adds it so panel_w/panel_h are measurable.
PANEL = {
    "root": [0, 0, 200, 67],
    "containers": [{"id": "p", "r": (0, 0, 200, 67)}],
    "parts": [
        part("p", "dial", "a", (10, 20, 37, 47)),
        part("p", "label", "a", (10, 50, 60, 62)),
    ],
}


def with_parts(*parts) -> dict:
    return {
        "root": list(PANEL["root"]),
        "containers": list(PANEL["containers"]),
        "parts": list(parts),
    }


def minimal_spec(font_path: str, ratio: dict) -> dict:
    """The smallest spec that validates today, so a failure below is about the
    [ratio] table and nothing else."""
    return {
        "panel": {"name": "t", "width": 200, "height": 67},
        "font": {"path": font_path, "size": 16},
        "ratio": ratio,
    }


def doc_example() -> str:
    m = re.search(r"```toml\n(.*?)```", DOC.read_text(), re.DOTALL)
    assert m, "docs/spec.md lost its canonical example"
    return m.group(1)


# --------------------------------------------------------------------------
# the predicate
# --------------------------------------------------------------------------


def test_measure_row_failure_names_the_row_got_want_and_tol():
    """The message is the whole product of a failed row. Whoever reads the gate
    output must be able to fix the panel without re-running anything, so the
    row name and all three numbers travel with it."""
    fails = audit.check_ratios(
        PANEL, [{"name": "dial_h", "measure": "dial.h", "want": 45.0, "tol": 1.5}]
    )

    assert len(fails) == 1, fails
    msg = fails[0]
    for token in ("dial_h", "27", "45", "1.5"):
        assert token in msg, f"failure must carry {token!r}: {msg}"


def test_every_dimension_resolves_and_a_row_within_tolerance_is_silent():
    """h/w/cx/cy on the same part, all correct: an empty list is the pass, as
    everywhere else in the battery. Without this companion the test above
    passes on a predicate that fails every row."""
    rows = [
        {"name": "h", "measure": "dial.h", "want": 27.0, "tol": 0.5},
        {"name": "w", "measure": "dial.w", "want": 27.0, "tol": 0.5},
        {"name": "cx", "measure": "dial.cx", "want": 23.5, "tol": 0.5},
        {"name": "cy", "measure": "dial.cy", "want": 33.5, "tol": 0.5},
    ]
    assert audit.check_ratios(PANEL, rows) == []


def test_ratio_row_is_the_text_to_control_identity():
    """The quotient form, and the reason this predicate exists: label.h/dial.h
    is the identity-carrying ratio (DENSE-UI §Ratios — Operator sits near 0.8;
    library defaults land near 0.44 and read as generated). Absolute sizes can
    all be plausible while the relation between them is the tell."""
    row = {"name": "text_control", "ratio": ["label.h", "dial.h"], "want": 0.593, "tol": 0.06}

    fails = audit.check_ratios(PANEL, [row])
    assert len(fails) == 1, fails
    assert "text_control" in fails[0] and "0.44" in fails[0], fails[0]

    row["want"], row["tol"] = 0.444, 0.01
    assert audit.check_ratios(PANEL, [row]) == []


def test_multi_instance_median_passes_while_spread_is_its_own_failure():
    """Three dials at 27/27/33: the MEDIAN is exactly 27, so the want check is
    silent (a MEAN of 29 would fire it and blame the wrong thing), and the 6px
    disagreement between instances is reported as what it is — a spread. Two
    different defects must never be reported as one number."""
    out = with_parts(
        part("p", "dial", "a", (10, 20, 37, 47)),
        part("p", "dial", "b", (50, 20, 77, 47)),
        part("p", "dial", "c", (90, 20, 117, 53)),  # 33 tall
    )
    row = {"name": "dial_h", "measure": "dial.h", "want": 27.0, "tol": 1.0}

    fails = audit.check_ratios(out, [row])
    assert len(fails) == 1, f"the median is exact — only the spread is a defect: {fails}"
    assert "spread" in fails[0] and "dial_h" in fails[0] and "6" in fails[0], fails[0]

    tight = with_parts(
        part("p", "dial", "a", (10, 20, 37, 46.6)),
        part("p", "dial", "b", (50, 20, 77, 47.0)),
        part("p", "dial", "c", (90, 20, 117, 47.4)),
    )
    assert audit.check_ratios(tight, [row]) == []


def test_root_rect_makes_panel_dimensions_measurable():
    """panel_w/panel_h are the rows telemetry has been declaring; they measure
    the probe ROOT, which has no part kind. Pinned form: probe_out["root"] is a
    rect, addressed as the reserved kind "root"."""
    good = {"name": "panel_w", "measure": "root.w", "want": 200.0, "tol": 1.0}
    bad = {"name": "panel_w", "measure": "root.w", "want": 800.0, "tol": 5.0}

    assert audit.check_ratios(PANEL, [good]) == []
    fails = audit.check_ratios(PANEL, [bad])
    assert len(fails) == 1 and "200" in fails[0] and "800" in fails[0], fails


def test_row_that_measures_nothing_fails_rather_than_passing_silently():
    """A row naming a kind the page does not contain matched no element, so it
    proved nothing. Reporting it clean is exactly the failure this workstream
    exists to end — the row must fail and name what it could not find."""
    fails = audit.check_ratios(
        PANEL, [{"name": "ghost", "measure": "nosuch.h", "want": 27.0, "tol": 1.0}]
    )

    assert len(fails) == 1, f"a row that measured nothing must fail: {fails}"
    assert "ghost" in fails[0] and "nosuch" in fails[0], fails[0]


# --------------------------------------------------------------------------
# the spec
# --------------------------------------------------------------------------


def test_typed_ratio_rows_validate(font_path):
    """Both row forms survive load_panel untouched — the spec is where a row is
    declared, and the predicate consumes exactly what was declared."""
    rows = {
        "panel_w": {"measure": "root.w", "want": 200, "tol": 5},
        "text_control": {"ratio": ["label.h", "dial.h"], "want": 0.593, "tol": 0.06},
    }

    out = load_panel(minimal_spec(font_path, rows))

    assert out["ratio"]["panel_w"]["measure"] == "root.w"
    assert out["ratio"]["text_control"]["ratio"] == ["label.h", "dial.h"]


def test_malformed_typed_rows_are_named_by_path_and_by_problem(font_path):
    """Typed does not mean rubber-stamped. A bad dimension, a quotient that is
    not a pair, and a row with no tolerance are three different mistakes; each
    is named at its full path, and the dimension error names the legal set so
    the fix does not require reading spec.py."""
    rows = {
        "bad_dim": {"measure": "dial.q", "want": 27, "tol": 1},
        "one_sided": {"ratio": ["label.h"], "want": 0.6, "tol": 0.05},
        "no_tol": {"measure": "dial.h", "want": 27},
    }

    with pytest.raises(SpecError) as exc:
        load_panel(minimal_spec(font_path, rows))

    errs = exc.value.errors
    for name in ("ratio.bad_dim", "ratio.one_sided", "ratio.no_tol"):
        assert any(name in e for e in errs), f"{name} unnamed in {errs}"
    dim_err = next(e for e in errs if "ratio.bad_dim" in e)
    assert "cx" in dim_err, f"the dimension error must name the legal dims: {dim_err}"


def test_legacy_pair_form_is_a_named_migration_error(font_path):
    """The exact rows demos/telemetry/panel.toml carries today. They must not
    keep validating: their meaning changed, and a spec that quietly accepts the
    old shape is how a dormant check survives its own rewrite."""
    legacy = {"panel_w": [1120, 5], "panel_h": [320, 5], "dial": [28, 1], "row": [72, 4]}

    with pytest.raises(SpecError) as exc:
        load_panel(minimal_spec(font_path, legacy))

    errs = exc.value.errors
    for name in ("ratio.panel_w", "ratio.panel_h", "ratio.dial", "ratio.row"):
        assert any(name in e for e in errs), f"{name} unnamed in {errs}"
    assert any("measure" in e for e in errs), f"the error must name the new form: {errs}"


def test_telemetry_ratio_rows_are_migrated_to_the_typed_form(font_path):
    """The demo whose dormant rows started this. Migrated in the same change or
    the feature is half-landed: the file is repository truth and its rows now
    run on every gate."""
    data = tomllib.loads(TELEMETRY.read_text())
    data["font"]["path"] = font_path

    untyped = sorted(k for k, v in data.get("ratio", {}).items() if not isinstance(v, dict))
    assert not untyped, f"demos/telemetry/panel.toml still carries untyped rows: {untyped}"
    assert load_panel(data)["ratio"], "the migrated rows must validate"


def test_docs_example_uses_the_typed_ratio_form():
    """docs/spec.md's example is executed by two existing tests; left untyped
    it would fail them the moment the spec tightens. The documented shape is
    the shape."""
    data = tomllib.loads(doc_example())

    untyped = sorted(k for k, v in data.get("ratio", {}).items() if not isinstance(v, dict))
    assert not untyped, f"docs/spec.md documents the dead pair form: {untyped}"


# --------------------------------------------------------------------------
# the CLI, through real chrome
# --------------------------------------------------------------------------

PAGE = """<!doctype html><meta charset="utf-8">
<div id="root" style="position:relative;width:300px;height:100px">
 <div class="plate" style="position:absolute;left:0;top:0;width:300px;height:100px">
  <div class="blk" data-addr="one"
       style="position:absolute;left:10px;top:10px;width:50px;height:30px"></div>
  <div class="blk" data-addr="two"
       style="position:absolute;left:100px;top:10px;width:50px;height:30px"></div>
 </div></div>"""

CONFIG = """
[probe]
root = "#root"
[probe.containers]
plate = ".plate"
[probe.parts]
blk = ".blk"

[ratio]
blk_h = {{ measure = "blk.h", want = {want}, tol = 1 }}
panel_w = {{ measure = "root.w", want = 300, tol = 1 }}
"""


@pytest.fixture()
def audit_fixture(tmp_path):
    """The page is clean under the battery (no overlap, no crowding, blk is not
    a rhythm kind, no text kinds), so the exit code below is the ratio rows and
    nothing else."""
    (tmp_path / "page.html").write_text(PAGE)
    return tmp_path


def test_audit_cli_fails_on_a_wrong_declared_ratio_row(audit_fixture, capsys):
    """The rc that has been 0 for months: the blocks are 30px tall, the spec
    says 45, and `densui audit` said nothing at all."""
    from densui.cli import main

    cfg = audit_fixture / "panel.toml"
    cfg.write_text(CONFIG.format(want=45))

    rc = main(["audit", str(audit_fixture / "page.html"), "--config", str(cfg)])
    out = json.loads(capsys.readouterr().out)

    assert rc == 1, f"a declared row outside tolerance must fail the command: {out}"
    assert any("blk_h" in f for f in out["failures"]), out["failures"]
    assert not any("panel_w" in f for f in out["failures"]), "the correct row must stay silent"


def test_audit_cli_reports_the_rows_it_executed_and_exits_zero(audit_fixture, capsys):
    """The companion that makes the rc above load-bearing, and the only thing
    that can tell a passing run from an ignored table: the report states HOW
    MANY rows ran. `rc == 0` alone is what the dormant rows already produce."""
    from densui.cli import main

    cfg = audit_fixture / "panel.toml"
    cfg.write_text(CONFIG.format(want=30))

    rc = main(["audit", str(audit_fixture / "page.html"), "--config", str(cfg)])
    out = json.loads(capsys.readouterr().out)

    assert out["ratios"] == 2, f"both declared rows must be executed: {out}"
    assert rc == 0, out["failures"]


# --------------------------------------------------------------------------
# the probe, through real chrome
# --------------------------------------------------------------------------


def test_probe_emits_the_root_rect(tmp_path):
    """panel_w/panel_h cannot be measured from parts or containers — the root
    is neither. Additive field, same rect convention as containers[i]["r"]:
    root-relative, so x0/y0 are 0 and w/h are the design dimensions."""
    from densui import probe

    page = tmp_path / "page.html"
    page.write_text(PAGE)

    out = probe.collect(page, root="#root", containers={"plate": ".plate"}, parts={"blk": ".blk"})

    root = out["root"]
    assert [round(v, 1) for v in (root[0], root[1], root[2], root[3])] == [0.0, 0.0, 300.0, 100.0]
    assert len(out["parts"]) == 2, "the existing output must be unchanged by the addition"


# --------------------------------------------------------------------------
# the scorecard hookup
# --------------------------------------------------------------------------


def test_size_ratio_class_is_measured_by_check_ratios():
    """W1's whole point, in the one table that reports coverage: size-ratio
    stops reading UNMEASURED. tests/test_scorecard.py then requires the seed
    directory automatically (its exemption list is derived from the registry),
    and requires the symbol to resolve."""
    from densui.score import REGISTRY, UNMEASURED

    row = REGISTRY["size-ratio"]
    assert row.predicate is not UNMEASURED, "size-ratio must be measured after W1"
    assert row.predicate == "densui.audit.check_ratios", row.predicate


def test_size_ratio_corpus_seed_declares_the_rows_that_catch_its_defect():
    """test_scorecard.py proves the seed directory EXISTS once the class is
    measured; only declared [ratio] rows make its planted defect catchable. A
    seed nothing can catch would report seed_caught=False and fail `ctl.sh
    score` — this says why, in pytest, before that happens."""
    panel = REPO / "corpus" / "size-ratio" / "panel.toml"
    assert panel.exists(), f"the measured size-ratio class has no corpus seed: {panel}"

    rows = tomllib.loads(panel.read_text()).get("ratio", {})
    assert rows, f"{panel} declares no [ratio] rows — nothing can catch the seeded defect"
    assert all(isinstance(v, dict) for v in rows.values()), f"seed rows must be typed: {rows}"
