"""The rendered face is the solved face (W3 of deep-craft).

Every reserved box in this system is computed from a TTF: `densui.solve` asks
`densui.fontmetrics.Face` for the advance of the widest string and hands back a
width. If the browser then draws a DIFFERENT face — the family was never
installed, a webfont did not load, the stack's first entry does not exist on
this host — every one of those boxes reserves room for text that is not there.
Silent font fallback is a named AI tell AND it invalidates the geometry the
rest of the battery proves. Nothing could see it until now: parts carry glyph
INK, and ink is where the glyphs are, never which face drew them.

Five properties are load-bearing and each has a test here:

1. the probe reports the RESOLVED family, not the declared list.
   `getComputedStyle(el).fontFamily` returns what the CSS asked for: measured
   in real chrome, a page declaring `'Nonsense Font ABC', <real>` reports the
   nonsense name from that API while the canvas draws the fallback. An
   implementation reading the declared list would report a face that is not on
   the machine and call it identity;
2. the discriminator is the measured ADVANCE of a pinned sentinel, because the
   advance is what the reserved box was computed from. Measured in real chrome
   over ten embedded faces at 16px and 13px, canvas `measureText` and
   `Face.adv()` agree to 0.0000px once kerning is off, and disagree by 3.55px
   (Arial) to 5.05px (DejaVu Sans) with it on. So the 0.5px band is spent on
   substitution and nothing else;
3. a substitution fails and the message carries the kind, BOTH advances and the
   delta. "font mismatch" is not something anyone can act on;
4. it reaches every gate path. The face comes from the `[font]` table every
   panel already declares, travels on `audit.Rules`, and is composed into
   `run_battery` and the `densui audit` report — W1's lesson, where a declared
   table sat unexecuted for months while its rc stayed 0;
5. the scorecard flips `font-identity` to measured, which makes
   tests/test_scorecard.py demand the corpus seed by name.

Imports of the new symbols are attribute lookups inside each test on purpose:
a module-level `from densui.audit import check_font_identity` would collapse
this whole file into one collection error before the feature lands, and a red
that names no test is not evidence.
"""

import base64
import json
import pathlib
import tomllib

from densui.fontmetrics import Face

REPO = pathlib.Path(__file__).resolve().parents[3]
PROBE_JS = REPO / "tools" / "densui" / "src" / "densui" / "probe.js"

# The pinned sentinel. Why this string:
#   * every character is printable ASCII, so no Latin text face can miss a
#     glyph — Face.adv() RAISES on a missing glyph, and a sentinel that can
#     raise is a check that cannot run;
#   * 73 glyphs of both cases plus the figures and the space: a per-glyph
#     difference of a thousandth of an em becomes tenths of a px, and the
#     figures are half the ink on a telemetry panel;
#   * the alphabet runs in strict order, so it contains no ligature sequence
#     (`f` is always followed by `g`, never `i`, `l` or `f`);
#   * the tail is three kerning pairs on purpose. Face.adv() sums glyph
#     advances; canvas measureText KERNS unless told not to, and those are
#     two different quantities. Measured over ten faces at 16px and 13px, the
#     tail costs 3.55px on Arial, 4.46px on Times New Roman and 5.05px on
#     DejaVu Sans with kerning on, and exactly 0.0000px with it off — so an
#     implementation that forgets `fontKerning = 'none'` cannot quietly spend
#     half the band on a face nobody substituted.
SENTINEL = "ABCDEFGHIJKLMNOPQRSTUVWXYZ abcdefghijklmnopqrstuvwxyz 0123456789 AV To Wa"
TOL_PX = 0.5

# The family name the fixtures give the embedded face. It is deliberately not
# a real family: what the page renders must come from the bytes we embed, on
# every host, or the test would only be measuring what the host happens to
# have installed.
EMBEDDED = "DensuiFace"


def embed(path: str, family: str = EMBEDDED) -> str:
    """@font-face for a TTF on disk, inlined as a data URI.

    The demos already ship this idiom (demos/operator/build/assemble.py), and
    it is the only way to make "the page rendered THIS face" true on a Mac and
    on the CI image at once: a family name resolves to different files on the
    two hosts, bytes do not.
    """
    b64 = base64.b64encode(pathlib.Path(path).read_bytes()).decode()
    return (
        f"@font-face {{ font-family: '{family}'; font-display: block; "
        f"src: url(data:font/ttf;base64,{b64}); }}"
    )


def page_html(css: str) -> str:
    """One plate, one label at 16px, one value at 13px — two text kinds at two
    sizes, so a comparison that ignores the rendered size cannot pass. Clean
    under the rest of the battery (same owner, no rhythm kind, 47px of bottom
    clearance), so an exit code below is font identity and nothing else."""
    return f"""<!doctype html><meta charset="utf-8"><style>{css}</style>
<div class="panel" style="position:relative;width:400px;height:120px">
 <div class="plate" style="position:absolute;left:0;top:0;width:400px;height:120px">
  <div class="label" data-addr="one" style="position:absolute;left:10px;top:10px">Gain</div>
  <div class="value" data-addr="one" style="position:absolute;left:10px;top:60px">-12.0 dB</div>
 </div></div>"""


PROBE_TOML = """
[probe]
root = ".panel"
text_kinds = ["label", "value"]
[probe.containers]
plate = ".plate"
[probe.parts]
label = ".label"
value = ".value"
"""


def evidence(face: Face, size_px: float, *, off: float = 0.0, family: str = EMBEDDED) -> dict:
    """One kind's font evidence as the probe reports it: the resolved family,
    the size that kind rendered at, and the sentinel's advance at that size.
    `off` displaces the advance by px AT THE REFERENCE SIZE (16), so a test can
    say "0.6px wrong" once and mean the same thing for a 13px kind."""
    return {
        "family": family,
        "size_px": size_px,
        "advance_px": face.adv(SENTINEL, size_px) + off * size_px / 16.0,
    }


def probed(fonts: dict) -> dict:
    """Probe output carrying font evidence and nothing the battery can fault."""
    return {"scale": 1, "root": [0, 0, 400, 120], "containers": [], "parts": [], "fonts": fonts}


# --------------------------------------------------------------------------
# the predicate
# --------------------------------------------------------------------------


def test_substituted_face_fails_and_names_the_kind_both_advances_and_the_delta(
    font_path, other_font_path
):
    """The page rendered `other`, the panel declared `font_path`. Whoever reads
    the gate output has to know WHICH text is wrong and BY HOW MUCH before they
    can decide whether the CSS, the webfont or the spec is at fault, so the
    kind, the resolved family, both advances and the delta all travel with the
    failure."""
    from densui import audit

    declared, rendered = Face(font_path), Face(other_font_path)
    out = probed({"value": evidence(rendered, 16)})

    fails = audit.check_font_identity(out, declared, 16)

    assert len(fails) == 1, fails
    msg = fails[0]
    delta = rendered.adv(SENTINEL, 16) - declared.adv(SENTINEL, 16)
    for token in (
        "value",
        EMBEDDED,
        f"{rendered.adv(SENTINEL, 16):.2f}",
        f"{declared.adv(SENTINEL, 16):.2f}",
        f"{abs(delta):.2f}",
    ):
        assert token in msg, f"the failure must carry {token!r}: {msg}"


def test_the_face_the_page_rendered_is_silent(font_path):
    """The companion that makes the failure above evidence rather than noise:
    the same predicate over a page that DID render the declared face returns
    the empty list, as everywhere else in the battery. Without it, an
    implementation that fails every kind passes the test above."""
    from densui import audit

    face = Face(font_path)
    out = probed({"label": evidence(face, 16), "value": evidence(face, 13)})

    assert audit.check_font_identity(out, face, 16) == []


def test_the_band_is_half_a_pixel_and_it_is_the_outside_that_fails(font_path):
    """0.5px is the eyes-doctrine number: at the reference size, half a pixel
    of advance over a 63-glyph sentinel is beyond any rounding this measurement
    does (chrome and fontTools agree to 0.0000px), and below any real
    substitution (the closest pair measured, Courier New against Menlo, is
    2.0px apart). Inside the band is silence, outside it fails, in both
    directions — a one-sided comparison would let every face that renders
    NARROWER than declared through, and those are the ones that leave holes."""
    from densui import audit

    face = Face(font_path)
    for off in (0.4, -0.4):
        out = probed({"value": evidence(face, 16, off=off)})
        assert audit.check_font_identity(out, face, 16) == [], f"{off:+}px is inside the band"
    for off in (0.6, -0.6):
        out = probed({"value": evidence(face, 16, off=off)})
        fails = audit.check_font_identity(out, face, 16)
        assert len(fails) == 1, f"{off:+}px is outside the band: {fails}"


def test_advance_is_compared_at_the_declared_size_not_the_rendered_one(font_path):
    """A panel renders labels at 16 and stream values at 13; the tolerance must
    mean the same thing for both, so the measured advance is scaled to the
    declared [font].size before the band applies. A 13px kind measured exactly
    right passes, and one that is 0.6px wrong AT 16 fails — even though its raw
    error at 13px is 0.49px, which a comparison at the rendered size would wave
    through with the same number in it."""
    from densui import audit

    face = Face(font_path)
    exact = probed({"value": evidence(face, 13)})
    wrong = probed({"value": evidence(face, 13, off=0.6)})
    raw_error = wrong["fonts"]["value"]["advance_px"] - face.adv(SENTINEL, 13)

    assert audit.check_font_identity(exact, face, 16) == []
    assert raw_error < TOL_PX, f"the wrong case must be inside the band at 13px: {raw_error}"
    assert len(audit.check_font_identity(wrong, face, 16)) == 1


def test_a_declared_face_with_nothing_measured_is_a_failure(font_path):
    """The dormancy shape, in its W3 costume — and the guard is EMPTINESS, not
    key presence.

    A key-presence guard is dead code the moment probe.js always writes
    `fonts: {}`, and the consolidated verify proved it by exploit: deleting
    `text_kinds` from a panel.toml empties the table, and a page rendering
    Courier where the panel declares a sans face went GREEN. Two shapes, one
    verdict — a declared face that reaches here with nothing measured is a
    failure that says so."""
    from densui import audit

    face = Face(font_path)
    absent = {"scale": 1, "containers": [], "parts": []}
    empty = {"scale": 1, "containers": [], "parts": [], "fonts": {}}

    for shape, out in (("no fonts key", absent), ("an empty fonts table", empty)):
        fails = audit.check_font_identity(out, face, 16)
        assert len(fails) == 1, f"a face declared against {shape} must fail: {fails}"
        assert "measured" in fails[0].lower(), (
            f"{shape}: the failure must say nothing was measured: {fails[0]}"
        )


def test_a_panel_that_declares_no_face_measures_nothing(font_path):
    """The corpus seeds for overlap, crowding and the rest declare `[probe]`
    and nothing else; they have no TTF to be compared against and this class
    has nothing to say about them. Same contract as the [ratio] table (W1):
    what a panel does not declare, the predicate does not invent — which is
    exactly why the seed below is the thing that proves this check can fire."""
    from densui import audit

    out = probed({"value": evidence(Face(font_path), 16, off=99)})

    assert audit.check_font_identity(out, None, 16) == []


def test_the_sentinel_is_pinned_and_the_probe_measures_the_same_string(font_path):
    """The expectation is computed in Python from the TTF and the measurement
    is taken in JavaScript from the canvas: two copies of one string, in two
    languages, and a drift between them is a check comparing two different
    sentences and calling the difference a substitution."""
    from densui import audit

    assert audit.FONT_SENTINEL == SENTINEL
    assert audit.FONT_IDENTITY_TOL_PX == TOL_PX
    assert Face(font_path).adv(audit.FONT_SENTINEL, 16) > 0, "every glyph must exist in the face"
    assert json.dumps(SENTINEL) in PROBE_JS.read_text(), (
        f"{PROBE_JS} does not carry the pinned sentinel — the two ends measure different strings"
    )


# --------------------------------------------------------------------------
# the seam: how the face reaches the predicate
# --------------------------------------------------------------------------


def test_run_battery_composes_font_identity(font_path, other_font_path):
    """Composed into the battery, or every caller has to remember to run it —
    and the one that forgets is the one measuring a demo on every gate."""
    from densui import audit

    rules = audit.Rules(face=Face(font_path), font_size=16)
    out = probed({"value": evidence(Face(other_font_path), 16)})
    out["containers"] = [{"id": "p", "r": (0, 0, 400, 120)}]

    fails = audit.run_battery(out, rules)

    assert len(fails) == 1, f"the battery must carry the font-identity failure alone: {fails}"
    assert "value" in fails[0], fails[0]


def test_rules_carry_the_declared_face_and_the_declared_size(font_path):
    """The seam, pinned: `[font]` is the table every panel already declares, so
    `probe_config.rules_from` — the one path `densui audit`, `densui score` and
    the operator gate all go through — turns it into the face and the reference
    size on audit.Rules. `size` is read from the file, never defaulted: a panel
    that solves at 13 must be judged at 13."""
    from densui.probe_config import rules_from

    cfg = tomllib.loads(f'[font]\npath = "{font_path}"\nsize = 13\n' + PROBE_TOML)

    rules = rules_from(cfg)

    assert rules.font_size == 13
    assert rules.face is not None, "a declared [font] must produce a face"
    assert rules.face.adv(SENTINEL, 16) == Face(font_path).adv(SENTINEL, 16)


def test_the_face_compared_is_the_face_the_page_was_built_with(
    font_path, other_font_path, monkeypatch
):
    """DENSUI_FONT first, exactly as demos/telemetry/build/build.py chooses the
    face it SOLVES with. The demo panels declare the CI image's DejaVu path and
    are built on a Mac against something else entirely; if the audit resolved
    the declared path while the build resolved the environment, this check
    would compare the page against a face nothing ever used and fail for a
    reason that is not a defect."""
    from densui.probe_config import rules_from

    cfg = tomllib.loads(f'[font]\npath = "{font_path}"\nsize = 16\n' + PROBE_TOML)
    monkeypatch.setenv("DENSUI_FONT", other_font_path)

    rules = rules_from(cfg)

    assert rules.face.adv(SENTINEL, 16) == Face(other_font_path).adv(SENTINEL, 16), (
        "DENSUI_FONT must win over the declared path, as every demo build resolves it"
    )


def test_a_declared_path_absent_on_this_host_falls_back_rather_than_dying(monkeypatch):
    """demos/telemetry/panel.toml names /usr/share/fonts/.../DejaVuSans.ttf,
    which does not exist on a Mac; build.py falls through to a present face and
    solves with THAT. The audit path must fall through the same way, or
    `./ctl.sh score` dies on the machine this repository is written on."""
    from densui.probe_config import rules_from

    monkeypatch.delenv("DENSUI_FONT", raising=False)
    cfg = tomllib.loads('[font]\npath = "/nonexistent/DejaVuSans.ttf"\nsize = 16\n' + PROBE_TOML)

    rules = rules_from(cfg)

    assert rules.face is not None, "a font absent on this host must resolve to a present one"
    assert rules.face.adv(SENTINEL, 16) > 0


def test_a_config_with_no_font_table_declares_no_face():
    """A corpus seed for another class declares [probe] and nothing else. It
    gets no face, and (by the predicate above) contributes no font-identity
    measurement — rather than an exception on a path that has nine other
    classes to report."""
    from densui.probe_config import rules_from

    rules = rules_from(tomllib.loads(PROBE_TOML))

    assert rules.face is None


# --------------------------------------------------------------------------
# the probe, through real chrome
# --------------------------------------------------------------------------

PROBE_ARGS = {
    "root": ".panel",
    "containers": {"plate": ".plate"},
    "parts": {"label": ".label", "value": ".value"},
}


def styled(font, family=EMBEDDED, stack=None):
    """A page that renders `font`'s BYTES under `family`, label at 16, value at
    13. `stack` overrides what the two kinds declare."""
    declared = stack or f"'{family}'"
    return page_html(
        embed(font, family)
        + f".label {{ font: 16px {declared}, monospace; }}"
        + f".value {{ font: 13px {declared}, monospace; }}"
    )


def test_probe_reports_the_face_the_page_actually_rendered(tmp_path, font_path):
    """The measurement, in the browser that draws the panel. Two kinds at two
    sizes, so the evidence is per kind and carries the size it was taken at.

    The 0.05px agreement is not the shipped 0.5px band: it is the statement
    that the probe measures the SAME QUANTITY Face.adv() computes — a sum of
    glyph advances, kerning off. Measured over ten embedded faces the two agree
    to 0.0000px that way; with kerning left on, this fixture's own face is
    3.55px out on a Mac and 5.05px on the CI image, for no substitution at
    all."""
    from densui import probe

    page = tmp_path / "page.html"
    page.write_text(styled(font_path))

    out = probe.collect(page, text_kinds={"label", "value"}, **PROBE_ARGS)

    fonts = out["fonts"]
    assert set(fonts) == {"label", "value"}, f"one entry per declared text kind: {fonts}"
    assert (fonts["label"]["size_px"], fonts["value"]["size_px"]) == (16, 13), fonts
    face = Face(font_path)
    for kind, ev in fonts.items():
        assert ev["family"] == EMBEDDED, f"{kind}: rendered face unnamed: {ev}"
        want = face.adv(SENTINEL, ev["size_px"])
        assert abs(ev["advance_px"] - want) <= 0.05, f"{kind}: {ev['advance_px']} vs {want}"
    assert len(out["parts"]) == 2, "the existing output must be unchanged by the addition"


def test_probe_reports_the_resolved_family_not_the_declared_list(tmp_path, font_path):
    """THE discriminator. `getComputedStyle(el).fontFamily` returns
    `"Nonsense Font ABC", "DensuiFace"` — the declared list, verbatim, with a
    family that exists on no machine at its head — and an implementation built
    on that API would report a face nobody has and call it identity. What the
    page actually draws is the fallback, and that is what has to be reported.

    Chrome also answers `document.fonts.check('16px "Nonsense Font ABC"')` with
    TRUE (measured), so that API cannot carry this either."""
    from densui import probe

    page = tmp_path / "page.html"
    page.write_text(styled(font_path, stack=f"'Nonsense Font ABC', '{EMBEDDED}'"))

    out = probe.collect(page, text_kinds={"label", "value"}, **PROBE_ARGS)

    ev = out["fonts"]["label"]
    assert "Nonsense" not in ev["family"], f"the declared list is not the rendered face: {ev}"
    assert ev["family"] == EMBEDDED, ev
    want = Face(font_path).adv(SENTINEL, 16)
    assert abs(ev["advance_px"] - want) <= 0.05, f"the fallback's advance is the evidence: {ev}"


def test_probe_emits_the_fonts_table_even_when_no_text_kind_is_declared(tmp_path, font_path):
    """Always present, possibly empty. `fonts` missing means a probe that
    cannot measure identity at all, and the predicate fails on that; if the key
    came and went with the configuration, that failure would fire on every
    panel whose parts are all boxes."""
    from densui import probe

    page = tmp_path / "page.html"
    page.write_text(styled(font_path))

    out = probe.collect(page, text_kinds=set(), **PROBE_ARGS)

    assert out["fonts"] == {}


# --------------------------------------------------------------------------
# the CLI, through real chrome
# --------------------------------------------------------------------------


def audit_config(tmp_path, font) -> pathlib.Path:
    cfg = tmp_path / "panel.toml"
    cfg.write_text(f'[font]\npath = "{font}"\nsize = 16\n' + PROBE_TOML)
    return cfg


def test_audit_cli_fails_when_the_rendered_face_is_not_the_declared_face(
    tmp_path, font_path, other_font_path, monkeypatch, capsys
):
    """The gate, end to end: the page draws one face, the panel declares
    another, and `densui audit` has to leave the shell non-zero. Everything
    else on this page is clean, so the rc is font identity and nothing else."""
    from densui.cli import main

    monkeypatch.delenv("DENSUI_FONT", raising=False)
    page = tmp_path / "page.html"
    page.write_text(styled(other_font_path))
    cfg = audit_config(tmp_path, font_path)

    rc = main(["audit", str(page), "--config", str(cfg)])
    out = json.loads(capsys.readouterr().out)

    assert rc == 1, f"a substituted face must fail the command: {out}"
    assert any("label" in f for f in out["failures"]), out["failures"]
    assert any("value" in f for f in out["failures"]), out["failures"]


def test_audit_cli_reports_the_kinds_it_checked_and_exits_zero(
    tmp_path, font_path, monkeypatch, capsys
):
    """The companion that makes the rc above load-bearing, and the only thing
    that can tell a checked run from an unchecked one: the report states HOW
    MANY text kinds had their identity measured. `rc == 0` alone is what a
    dormant check produces — that is precisely how the [ratio] table survived
    for months."""
    from densui.cli import main

    monkeypatch.delenv("DENSUI_FONT", raising=False)
    page = tmp_path / "page.html"
    page.write_text(styled(font_path))
    cfg = audit_config(tmp_path, font_path)

    rc = main(["audit", str(page), "--config", str(cfg)])
    out = json.loads(capsys.readouterr().out)

    assert out["fonts"] == 2, f"both declared text kinds must be checked: {out}"
    assert rc == 0, out["failures"]


# --------------------------------------------------------------------------
# the scorecard
# --------------------------------------------------------------------------


def test_font_identity_class_is_measured_by_check_font_identity():
    """W3's point, in the one table that reports coverage: font-identity stops
    reading UNMEASURED. tests/test_scorecard.py then demands the seed directory
    automatically — its exemption list is derived from the registry — and
    demands that the named symbol resolves."""
    from densui.score import REGISTRY, UNMEASURED

    row = REGISTRY["font-identity"]
    assert row.predicate is not UNMEASURED, "font-identity must be measured after W3"
    assert row.predicate == "densui.audit.check_font_identity", row.predicate


def test_font_identity_corpus_seed_declares_a_face_and_a_text_kind():
    """The seed is a page whose declared TTF and rendered face genuinely
    differ. Only a declared [font] and at least one text kind make that defect
    catchable: without either, the predicate measures nothing, the class
    reports seed_caught=False and `./ctl.sh score` fails. This says why, in
    pytest, before that happens."""
    panel = REPO / "corpus" / "font-identity" / "panel.toml"
    assert panel.exists(), f"the measured font-identity class has no corpus seed: {panel}"

    cfg = tomllib.loads(panel.read_text())
    font = cfg.get("font", {})
    assert font.get("path") and font.get("size"), f"{panel} declares no face to compare against"
    assert cfg.get("probe", {}).get("text_kinds"), f"{panel} declares no text kind to measure"


def test_the_scorecard_catches_a_seeded_substitution(font_path, other_font_path):
    """The adapter, which is the part of the wiring pytest can prove without
    chrome: the registry row has to hand the predicate the face and the size
    off the target's own Rules. A row wired to `_of_parts` would raise or
    report nothing, and the seed would read as uncaught."""
    from densui import audit, score

    rules = audit.Rules(face=Face(font_path), font_size=16)
    out = probed({"value": evidence(Face(other_font_path), 16)})

    report = score.run_scorecard(
        [
            score.Target(
                name="corpus/font-identity", probe_out=out, seeds="font-identity", rules=rules
            )
        ]
    )

    assert report["classes"]["font-identity"]["measured"] is True
    assert report["classes"]["font-identity"]["seed_caught"] is True
    assert report["classes"]["font-identity"]["violations"], "the catch must be evidenced"
    assert report["failures"] == [], report["failures"]


def test_component_anatomy_and_colour_are_still_unmeasured():
    """Deliberately green, and it stays green: W3 adds ONE predicate. Bitmap
    anatomy and contrast maths do not exist, and a registry that claimed them
    to look complete would be reporting coverage it does not have — the exact
    failure the scorecard was built to make impossible."""
    from densui.score import REGISTRY, UNMEASURED

    for cls in ("component-anatomy", "colour"):
        assert REGISTRY[cls].predicate is UNMEASURED, f"{cls} claims a predicate it does not have"
