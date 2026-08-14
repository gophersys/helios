"""The craft scorecard — coverage and failures, never an aesthetic verdict.

W0 of deep-craft. The scorecard exists because the honest answer to "does this
panel read as generated?" is a table of what we MEASURE and what we do not,
plus every violation found. Three properties are load-bearing and each has a
test here:

1. A registry row that names a predicate symbol which does not exist is itself
   a failure — the ratio rows in demos/telemetry/panel.toml were declared,
   believed, and executed by nothing for months.
2. A class with no predicate reports UNMEASURED, and UNMEASURED can never be
   read as a pass. Zero violations from a check that never ran is the exact
   lie this repository has already shipped once.
3. A predicate that misses its OWN seeded defect fails the run. A check that
   cannot fail is the defect.

Imports of densui.score are inside each test on purpose: until the module
exists, a module-level import would collapse the whole file into one
collection error, and a red that names no test is not evidence.
"""

import json
import pathlib
import tomllib

REPO = pathlib.Path(__file__).resolve().parents[3]

# Mateo's callouts (the AI tells he named) plus the classes the proof battery
# already measures. Kebab-case keys, because the CLI table and the corpus
# directory names are the same strings.
REQUIRED_CLASSES = {
    "size-ratio",
    "padding-rhythm",
    "axis-sprawl",
    "hit-pitch",
    "fractional-edges",
    "font-identity",
    "component-anatomy",
    "colour",
    "overlap",
    "crowding",
    "gap-law",
    "containment",
    "breathing",
    "alignment",
}
BATTERY_CLASSES = {"overlap", "crowding", "gap-law", "containment", "breathing", "alignment"}
FUTURE_CLASSES = {"component-anatomy", "colour"}

CLASS_ROW_KEYS = {"measured", "violations", "seed_caught"}
REPORT_KEYS = {"classes", "failures"}


def part(c, kind, owner, r):
    return {"c": c, "kind": kind, "owner": owner, "r": list(r)}


# Geometry proven clean by the battery (test_audit's clean-input case) and the
# same geometry with ONE deliberate overlap — the seed for the overlap class.
CLEAN = {
    "containers": [{"id": "p", "r": (0, 0, 200, 67)}],
    "parts": [
        part("p", "dial", "a", (10, 20, 37, 47)),
        part("p", "value", "a", (34, 50, 80, 62)),
    ],
}
SEEDED_OVERLAP = {
    "containers": [{"id": "p", "r": (0, 0, 200, 67)}],
    "parts": [
        part("p", "dial", "a", (0, 0, 27, 27)),
        part("p", "value", "b", (10, 10, 60, 24)),
    ],
}


def measured_classes(registry) -> set:
    """Which classes claim a predicate — derived from the registry, never a
    list typed here, so a class flipping to measured cannot be forgotten."""
    from densui import score

    return {name for name, row in registry.items() if row.predicate is not score.UNMEASURED}


def write_corpus_class(root: pathlib.Path, cls: str, *, defect: bool) -> pathlib.Path:
    """A corpus seed directory: page.html + panel.toml + TELL.md, named for its
    defect class. `defect=False` writes the same page WITHOUT the defect — the
    case that must expose a predicate which cannot catch its own seed."""
    d = root / cls
    d.mkdir(parents=True)
    left = 40 if defect else 70
    (d / "page.html").write_text(f"""<!doctype html><meta charset="utf-8">
<div id="root" style="position:relative;width:300px;height:100px">
 <div class="plate" style="position:absolute;left:0;top:0;width:300px;height:100px">
  <div class="blk" data-addr="one"
       style="position:absolute;left:10px;top:10px;width:50px;height:30px"></div>
  <div class="blk" data-addr="two"
       style="position:absolute;left:{left}px;top:20px;width:50px;height:30px"></div>
 </div></div>""")
    (d / "panel.toml").write_text("""
[probe]
root = "#root"
[probe.containers]
plate = ".plate"
[probe.parts]
blk = ".blk"
""")
    (d / "TELL.md").write_text(f"# {cls}\n\nblk(one) and blk(two) share pixels.\n")
    return d


def test_registry_names_every_defect_class():
    """The registry is the vocabulary. A tell Mateo named but nobody wrote
    down is a tell nothing will ever measure."""
    from densui.score import REGISTRY

    missing = sorted(REQUIRED_CLASSES - set(REGISTRY))
    assert not missing, f"defect classes absent from densui.score.REGISTRY: {missing}"


def test_every_declared_predicate_symbol_resolves():
    """A row naming `densui.audit.check_nothing` is a believed check that runs
    nothing — the telemetry [ratio] failure mode, in registry form."""
    import importlib

    from densui.score import REGISTRY, UNMEASURED

    dangling = []
    for name, row in REGISTRY.items():
        if row.predicate is UNMEASURED:
            continue
        dotted = row.predicate
        assert isinstance(dotted, str), f"{name}: predicate must be a dotted symbol, got {dotted!r}"
        module_name, _, symbol = dotted.rpartition(".")
        try:
            obj = getattr(importlib.import_module(module_name), symbol)
        except (ImportError, AttributeError) as exc:
            dangling.append(f"{name} -> {dotted} ({exc})")
            continue
        if not callable(obj):
            dangling.append(f"{name} -> {dotted} (not callable)")
    assert not dangling, f"registry rows naming symbols that do not exist: {dangling}"


def test_battery_classes_are_measured():
    """These six have had predicates since the proof battery landed. Declaring
    any of them UNMEASURED would under-report coverage we already own."""
    from densui.score import REGISTRY, UNMEASURED

    unmeasured = sorted(c for c in BATTERY_CLASSES if REGISTRY[c].predicate is UNMEASURED)
    assert not unmeasured, f"battery classes wrongly declared UNMEASURED: {unmeasured}"


def test_future_classes_are_honestly_unmeasured():
    """component-anatomy needs bitmap predicates and colour needs contrast
    maths; neither exists at W0. The registry must say so with the sentinel —
    a string like "todo" is something a UI can invent, print, and mistake."""
    from densui.score import REGISTRY, UNMEASURED

    assert not isinstance(UNMEASURED, str), "UNMEASURED must be a sentinel, not a string"
    wrong = sorted(c for c in FUTURE_CLASSES if REGISTRY[c].predicate is not UNMEASURED)
    assert not wrong, f"classes claiming a predicate they do not have: {wrong}"


def test_unmeasured_is_reported_and_never_reads_as_a_pass():
    """Zero violations from a check that never ran is the shipped lie this
    whole phase exists to prevent: the unmeasured row must be distinguishable
    from a real clean row by a field, not by a reader's memory."""
    from densui import score

    report = score.run_scorecard([score.Target(name="clean", probe_out=CLEAN, seeds=None)])

    assert set(report["classes"]) == set(score.REGISTRY), "every class gets a row, measured or not"
    colour, overlap = report["classes"]["colour"], report["classes"]["overlap"]
    assert colour == {"measured": False, "violations": [], "seed_caught": None}, (
        f"an unmeasured class must report measured=False, got {colour}"
    )
    assert overlap == {"measured": True, "violations": [], "seed_caught": None}, (
        f"a measured class with nothing to report is measured=True, got {overlap}"
    )
    assert report["failures"] == [], "a clean target with no seed is not a failure"


def test_predicate_that_misses_its_own_seed_fails_the_scorecard():
    """A check that cannot fail is the defect. The seed says this target holds
    an overlap; if the overlap predicate reports nothing, the run fails and
    names the class — silence here would certify a blind check as working."""
    from densui import score

    report = score.run_scorecard(
        [score.Target(name="corpus/overlap", probe_out=CLEAN, seeds="overlap")]
    )

    assert report["classes"]["overlap"]["seed_caught"] is False
    assert report["failures"], "a missed seed must fail the run"
    assert any("overlap" in f for f in report["failures"]), report["failures"]


def test_seeded_target_caught_by_its_predicate_is_not_a_failure():
    """The load-bearing companion: the failure above comes from the MISS, not
    from seeding. Violations of the seeded class on its own seed are the
    expected catch, so the run stays clean."""
    from densui import score

    report = score.run_scorecard(
        [score.Target(name="corpus/overlap", probe_out=SEEDED_OVERLAP, seeds="overlap")]
    )

    assert report["classes"]["overlap"]["seed_caught"] is True
    assert report["classes"]["overlap"]["violations"], "the caught seed must be evidenced"
    assert report["failures"] == [], f"a caught seed is the check working: {report['failures']}"


def test_should_pass_target_with_violations_fails_and_lists_them():
    """Demos and any unseeded target must stay clean; a violation there is a
    real defect and the failure carries the target name and the numbers."""
    from densui import score

    report = score.run_scorecard(
        [score.Target(name="demos/telemetry", probe_out=SEEDED_OVERLAP, seeds=None)]
    )

    assert report["classes"]["overlap"]["violations"], "the violation must be recorded"
    assert report["failures"], "an unseeded target with violations must fail the run"
    joined = " | ".join(report["failures"])
    assert "demos/telemetry" in joined and "overlap" in joined, joined


def test_corpus_has_a_seed_for_every_measured_class():
    """Every measured class owns a minimal page whose single deliberate defect
    the class must catch — that is what makes seed_caught meaningful. The
    exemption is derived from the registry: a class flipping to measured
    without a seed fails here, by name."""
    from densui.score import REGISTRY

    missing = []
    for cls in sorted(measured_classes(REGISTRY)):
        d = REPO / "corpus" / cls
        absent = [f for f in ("page.html", "panel.toml", "TELL.md") if not (d / f).exists()]
        if absent:
            missing.append(f"corpus/{cls}: {absent}")
            continue
        cfg = tomllib.loads((d / "panel.toml").read_text())
        if "probe" not in cfg or "root" not in cfg.get("probe", {}):
            missing.append(f"corpus/{cls}/panel.toml: no [probe] root to measure from")
    assert not missing, f"measured classes without a usable corpus seed: {missing}"


def test_score_cli_exits_nonzero_when_a_seed_is_missed(tmp_path, capsys):
    """`densui score --corpus <dir>` renders every seed directory present and
    scores it; rc follows the report. A partial corpus is scoreable on purpose
    — registry completeness is the separate check above, and conflating the
    two would make the CLI unusable while classes are still landing."""
    from densui.cli import main

    corpus = tmp_path / "corpus"
    write_corpus_class(corpus, "overlap", defect=False)  # the tell was not planted

    rc = main(["score", "--corpus", str(corpus)])
    out = json.loads(capsys.readouterr().out)

    assert rc != 0, "a missed seed must leave the shell non-zero"
    assert out["classes"]["overlap"]["seed_caught"] is False
    assert any("overlap" in f for f in out["failures"]), out["failures"]


def test_score_cli_exits_zero_when_every_seed_is_caught(tmp_path, capsys):
    """The companion that makes the rc load-bearing: the same corpus WITH its
    defect planted exits 0, so the non-zero above is the miss and not the
    command being broken."""
    from densui.cli import main

    corpus = tmp_path / "corpus"
    write_corpus_class(corpus, "overlap", defect=True)

    rc = main(["score", "--corpus", str(corpus)])
    out = json.loads(capsys.readouterr().out)

    assert out["classes"]["overlap"]["seed_caught"] is True, out["classes"]["overlap"]
    assert rc == 0, out["failures"]


def test_report_carries_no_aesthetic_verdict():
    """The eyes doctrine, pinned in the instrument. This tool may report what
    it measured and what failed; it may never say a panel looks good, looks
    human, or passes. Such a field would be believed, and no predicate here
    can support it."""
    from densui import score

    report = score.run_scorecard([score.Target(name="clean", probe_out=CLEAN, seeds=None)])

    assert set(report) == REPORT_KEYS, f"top level is coverage + failures only: {sorted(report)}"
    for name, row in report["classes"].items():
        assert set(row) == CLASS_ROW_KEYS, f"{name}: unexpected row shape {sorted(row)}"

    banned = ("ai_looking", "looks_ai", "passes", "pass", "verdict", "quality", "aesthetic", "ok")
    keys = set(report) | {k for row in report["classes"].values() for k in row}
    offenders = sorted(k for k in keys if k.lower() in banned)
    assert not offenders, f"affirmative verdict fields in the report: {offenders}"


def test_fixture_geometry_is_what_the_battery_actually_sees():
    """Guard on this file, not on the feature: CLEAN must really be clean and
    SEEDED_OVERLAP must really hold exactly one overlap under densui.audit.
    If either drifts, every scorecard test above proves nothing. This is the
    one test here that is green before W0 lands — deliberately, because it
    exercises code that already exists."""
    from densui.audit import Rules, check_overlaps

    assert check_overlaps(CLEAN["parts"], Rules()) == []
    assert len(check_overlaps(SEEDED_OVERLAP["parts"], Rules())) == 1
