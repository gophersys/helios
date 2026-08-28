"""The rendered face is the solved face (W3 of deep-craft).

Every reserved box in this system is computed from a TTF: `ui.solve` asks
`ui.fontmetrics.Face` for the advance of the widest string and hands back a
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
   advance is what the reserved box was computed from. The sentinel is measured
   at ONE canonical integral size (16px) in each kind's resolved family — never
   at the kind's own rendered size, and never rescaled to the declared size.
   Identity is size-independent, and both of the other choices drag a
   platform's fractional-size behaviour into the verdict; the fleet proved that
   on operator's autoscaled kinds (see the comparison-point test). Measured in
   real chrome over ten embedded faces, canvas `measureText` and `Face.adv()`
   agree to 0.0000px once kerning is off, and disagree by 3.55px (Arial) to
   5.05px (DejaVu Sans) with it on. A real substitution at 16px is 5.27px
   (DejaVu Sans against its Mono) to 40.23px (Arial against Courier New), so
   the 0.5px band separates faces, never arithmetic;
3. a substitution fails and the message carries the kind, BOTH advances and the
   delta. "font mismatch" is not something anyone can act on;
4. it reaches every gate path. The face comes from the `[font]` table every
   panel already declares, travels on `audit.Rules`, and is composed into
   `run_battery` and the `ui audit` report — W1's lesson, where a declared
   table sat unexecuted for months while its rc stayed 0;
5. the scorecard flips `font-identity` to measured, which makes
   tests/test_scorecard.py demand the corpus seed by name.

Imports of the new symbols are attribute lookups inside each test on purpose:
a module-level `from ui.audit import check_font_identity` would collapse
this whole file into one collection error before the feature lands, and a red
that names no test is not evidence.
"""

import base64
import json
import pathlib
import tomllib

from ui.fontmetrics import Face

REPO = pathlib.Path(__file__).resolve().parents[3]
PROBE_JS = REPO / "tools" / "ui" / "src" / "ui" / "probe.js"

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


# The canonical identity size. Which FACE a page drew is not a fact about the
# size a kind happens to render at, and Face.adv scales exactly, so the
# sentinel is measured at ONE integral size for every kind and the platform's
# fractional-size behaviour never reaches the comparison. The fleet is what
# bought this number: operator's autoscaled kinds (num at 15.552px) measured
# 0.0875% narrow there, while the 16px kinds on the same page, in the same run,
# with the same face, were exact.
CANONICAL_PX = 16.0


def evidence(
    face: Face,
    size_px: float,
    *,
    off: float = 0.0,
    family: str = EMBEDDED,
    measured_at_px: float = CANONICAL_PX,
) -> dict:
    """One kind's font evidence as the probe reports it.

    `size_px` is the size that kind actually RENDERED at — evidence, and the
    world check_ratios judges, never the comparison point. `measured_at_px` is
    the size the sentinel was measured at, and `advance_px` is its advance
    there. `off` displaces the advance in px at the measured size, which is
    where the band applies."""
    return {
        "family": family,
        "size_px": size_px,
        "measured_at_px": measured_at_px,
        "advance_px": face.adv(SENTINEL, measured_at_px) + off,
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
    failure.

    The margin is also pinned, and it is what makes 0.5px a safe band: measured
    at the canonical size, a real substitution is 5px (DejaVu Sans against its
    own Mono, the CI image's only pair) to 40px (Arial against Courier New)
    wide. Nothing that is merely arithmetic reaches 5px; nothing that is a
    different face lands inside 0.5px."""
    from ui import audit

    declared, rendered = Face(font_path), Face(other_font_path)
    out = probed({"value": evidence(rendered, size_px=13)})

    fails = audit.check_font_identity(out, declared, 16)

    assert len(fails) == 1, fails
    msg = fails[0]
    delta = rendered.adv(SENTINEL, CANONICAL_PX) - declared.adv(SENTINEL, CANONICAL_PX)
    assert abs(delta) >= 5.0, f"a substitution must be decisive at {CANONICAL_PX}px: {delta}"
    for token in (
        "value",
        EMBEDDED,
        f"{rendered.adv(SENTINEL, CANONICAL_PX):.2f}",
        f"{declared.adv(SENTINEL, CANONICAL_PX):.2f}",
        f"{abs(delta):.2f}",
    ):
        assert token in msg, f"the failure must carry {token!r}: {msg}"


def test_the_face_the_page_rendered_is_silent(font_path):
    """The companion that makes the failure above evidence rather than noise:
    the same predicate over a page that DID render the declared face returns
    the empty list, as everywhere else in the battery. Without it, an
    implementation that fails every kind passes the test above."""
    from ui import audit

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
    from ui import audit

    face = Face(font_path)
    for off in (0.4, -0.4):
        out = probed({"value": evidence(face, 16, off=off)})
        assert audit.check_font_identity(out, face, 16) == [], f"{off:+}px is inside the band"
    for off in (0.6, -0.6):
        out = probed({"value": evidence(face, 16, off=off)})
        fails = audit.check_font_identity(out, face, 16)
        assert len(fails) == 1, f"{off:+}px is outside the band: {fails}"


def test_the_comparison_happens_at_the_size_the_sentinel_was_measured_at(font_path):
    """The band applies where the measurement was taken, and the measurement is
    taken at ONE integral size on every kind. `Face.adv()` scales exactly, so
    `adv(SENTINEL, measured_at_px)` is the expectation, and no rescaling step
    exists anywhere.

    THE BAND IS UNCHANGED AT 0.5px. This is not a widened tolerance; it is the
    fractional size leaving the measurement instead of being tolerated in the
    arithmetic, and the fleet earned it. The first shape of this predicate
    normalized the measurement to the declared size (`advance_px * size /
    size_px`), multiplying every measurement error by `size / size_px`. On
    operator, whose grid autoscale renders `clabel` and `num` at fractional
    sizes, the fleet reported

        clabel: rendered face Ableton Sans Small advances 707.85px over the
        sentinel, the declared face 708.47px (-0.62px, tol ±0.5)

    with the family resolved CORRECTLY — a substitution is 5 to 40px, so 0.62px
    was arithmetic, not a face. That page passes on macOS chrome, which agrees
    with fontTools to -0.0005px at those same fractional sizes (measured:
    operator clabel 15.1px, num 15.6px), and the fleet's own 16px kinds passed
    on the same page in the same run. Removing the normalization alone would
    have left -0.585px there, still outside the band: the fractional size had
    to leave the measurement.

    So a kind's rendered size is EVIDENCE, never the comparison point, and the
    three discriminators are:

    * a kind rendered at 15.552px whose sentinel was measured at 16 and is
      exact passes — a normalizing predicate rescales it by 16/15.552 and
      reports a 68px substitution that is not there;
    * 0.45px wrong is inside the band and 0.55px is outside it, whatever the
      kind renders at;
    * the verdict does not depend on the declared [font].size at all, that
      being a fact about the spec rather than about what the browser drew."""
    from ui import audit

    face = Face(font_path)
    autoscaled = probed({"num": evidence(face, size_px=15.552)})
    inside = probed({"value": evidence(face, size_px=13, off=0.45)})
    outside = probed({"value": evidence(face, size_px=20, off=0.55)})

    assert audit.check_font_identity(autoscaled, face, 16) == [], (
        "a fractional RENDERED size cannot move a measurement taken at 16px"
    )
    assert audit.check_font_identity(inside, face, 16) == [], "0.45px is inside the 0.5px band"
    assert len(audit.check_font_identity(outside, face, 16)) == 1, "0.55px is outside it"

    for declared in (16, 13, 15.552, 20):
        assert audit.check_font_identity(inside, face, declared) == [], declared
        assert len(audit.check_font_identity(outside, face, declared)) == 1, declared


def test_the_failure_names_the_size_the_sentinel_was_measured_at(font_path):
    """The message has to carry the comparison point or a reader cannot check
    the arithmetic — and it must be the MEASURED-at size, not the declared one
    and not the kind's rendered one, because those are three different numbers
    on an autoscaled panel."""
    from ui import audit

    face = Face(font_path)
    out = probed({"num": evidence(face, size_px=15.552, measured_at_px=20, off=3)})

    fails = audit.check_font_identity(out, face, 16)

    assert len(fails) == 1, fails
    assert "20" in fails[0], f"the measured-at size is the comparison point: {fails[0]}"
    assert f"{face.adv(SENTINEL, 20):.2f}" in fails[0], (
        f"the expectation must be the one at 20px, not at the declared 16: {fails[0]}"
    )


def test_a_declared_face_with_nothing_measured_is_a_failure(font_path):
    """The dormancy shape, in its W3 costume — and the guard is EMPTINESS, not
    key presence.

    A key-presence guard is dead code the moment probe.js always writes
    `fonts: {}`, and the consolidated verify proved it by exploit: deleting
    `text_kinds` from a panel.toml empties the table, and a page rendering
    Courier where the panel declares a sans face went GREEN. Two shapes, one
    verdict — a declared face that reaches here with nothing measured is a
    failure that says so."""
    from ui import audit

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
    from ui import audit

    out = probed({"value": evidence(Face(font_path), 16, off=99)})

    assert audit.check_font_identity(out, None, 16) == []


def test_the_sentinel_is_pinned_and_the_probe_measures_the_same_string(font_path):
    """The expectation is computed in Python from the TTF and the measurement
    is taken in JavaScript from the canvas: two copies of one string, in two
    languages, and a drift between them is a check comparing two different
    sentences and calling the difference a substitution."""
    from ui import audit

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
    from ui import audit

    rules = audit.Rules(face=Face(font_path), font_size=16)
    out = probed({"value": evidence(Face(other_font_path), 16)})
    out["containers"] = [{"id": "p", "r": (0, 0, 400, 120)}]

    fails = audit.run_battery(out, rules)

    assert len(fails) == 1, f"the battery must carry the font-identity failure alone: {fails}"
    assert "value" in fails[0], fails[0]


def test_rules_carry_the_declared_face_and_the_declared_size(font_path):
    """The seam, pinned: `[font]` is the table every panel already declares, so
    `probe_config.rules_from` — the one path `ui audit`, `ui score` and
    the operator gate all go through — turns it into the face and the reference
    size on audit.Rules. `size` is read from the file, never defaulted: a panel
    that solves at 13 must be judged at 13."""
    from ui.probe_config import rules_from

    cfg = tomllib.loads(f'[font]\npath = "{font_path}"\nsize = 13\n' + PROBE_TOML)

    rules = rules_from(cfg)

    assert rules.font_size == 13
    assert rules.face is not None, "a declared [font] must produce a face"
    assert rules.face.adv(SENTINEL, 16) == Face(font_path).adv(SENTINEL, 16)


def test_the_face_compared_is_the_face_the_page_was_built_with(
    font_path, other_font_path, monkeypatch
):
    """UI_FONT first, exactly as demos/telemetry/build/build.py chooses the
    face it SOLVES with. The demo panels declare the CI image's DejaVu path and
    are built on a Mac against something else entirely; if the audit resolved
    the declared path while the build resolved the environment, this check
    would compare the page against a face nothing ever used and fail for a
    reason that is not a defect."""
    from ui.probe_config import rules_from

    cfg = tomllib.loads(f'[font]\npath = "{font_path}"\nsize = 16\n' + PROBE_TOML)
    monkeypatch.setenv("UI_FONT", other_font_path)

    rules = rules_from(cfg)

    assert rules.face.adv(SENTINEL, 16) == Face(other_font_path).adv(SENTINEL, 16), (
        "UI_FONT must win over the declared path, as every demo build resolves it"
    )


def test_a_declared_path_absent_on_this_host_falls_back_rather_than_dying(monkeypatch):
    """demos/telemetry/panel.toml names /usr/share/fonts/.../DejaVuSans.ttf,
    which does not exist on a Mac; build.py falls through to a present face and
    solves with THAT. The audit path must fall through the same way, or
    `./ctl.sh score` dies on the machine this repository is written on."""
    from ui.probe_config import rules_from

    monkeypatch.delenv("UI_FONT", raising=False)
    cfg = tomllib.loads('[font]\npath = "/nonexistent/DejaVuSans.ttf"\nsize = 16\n' + PROBE_TOML)

    rules = rules_from(cfg)

    assert rules.face is not None, "a font absent on this host must resolve to a present one"
    assert rules.face.adv(SENTINEL, 16) > 0


def test_a_config_with_no_font_table_declares_no_face():
    """A corpus seed for another class declares [probe] and nothing else. It
    gets no face, and (by the predicate above) contributes no font-identity
    measurement — rather than an exception on a path that has nine other
    classes to report."""
    from ui.probe_config import rules_from

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
    from ui import probe

    page = tmp_path / "page.html"
    page.write_text(styled(font_path))

    out = probe.collect(page, text_kinds={"label", "value"}, **PROBE_ARGS)

    fonts = out["fonts"]
    assert set(fonts) == {"label", "value"}, f"one entry per declared text kind: {fonts}"
    assert (fonts["label"]["size_px"], fonts["value"]["size_px"]) == (16, 13), fonts
    face = Face(font_path)
    for kind, ev in fonts.items():
        assert ev["family"] == EMBEDDED, f"{kind}: rendered face unnamed: {ev}"
        want = face.adv(SENTINEL, ev["measured_at_px"])
        assert abs(ev["advance_px"] - want) <= 0.05, f"{kind}: {ev['advance_px']} vs {want}"
    assert len(out["parts"]) == 2, "the existing output must be unchanged by the addition"


def test_the_sentinel_is_measured_at_the_canonical_identity_size(tmp_path, font_path):
    """Where the fractional size actually leaves: the PROBE picks the size the
    sentinel is measured at, and it picks the same integral one for every kind.

    Identity is a property of the face. The size a kind renders at is
    check_ratios' business and stays in the evidence for the report's honesty —
    but it is not the comparison point, and it is exactly the term that made
    the fleet red on a correctly-resolved face. This page renders its label at
    16 and its value at 13; both must report the sentinel measured at 16. A
    probe that measures each kind at its own rendered size passes every unit
    test in this file and still hands the fleet the number that failed it."""
    from ui import audit, probe

    page = tmp_path / "page.html"
    page.write_text(styled(font_path))

    out = probe.collect(page, text_kinds={"label", "value"}, **PROBE_ARGS)

    assert audit.FONT_IDENTITY_SIZE_PX == CANONICAL_PX
    assert "FONT_IDENTITY_SIZE_PX" in PROBE_JS.read_text(), (
        f"{PROBE_JS} must name the canonical size it measures at, greppable from both ends"
    )
    face = Face(font_path)
    for kind, ev in sorted(out["fonts"].items()):
        assert ev["measured_at_px"] == CANONICAL_PX, f"{kind}: measured at {ev}"
        want = face.adv(SENTINEL, ev["measured_at_px"])
        assert abs(ev["advance_px"] - want) <= 0.05, f"{kind}: {ev['advance_px']} vs {want}"
    assert (out["fonts"]["label"]["size_px"], out["fonts"]["value"]["size_px"]) == (16, 13), (
        "the RENDERED sizes stay in the evidence — the report may not lose them"
    )


def test_probe_reports_the_resolved_family_not_the_declared_list(tmp_path, font_path):
    """THE discriminator. `getComputedStyle(el).fontFamily` returns
    `"Nonsense Font ABC", "DensuiFace"` — the declared list, verbatim, with a
    family that exists on no machine at its head — and an implementation built
    on that API would report a face nobody has and call it identity. What the
    page actually draws is the fallback, and that is what has to be reported.

    Chrome also answers `document.fonts.check('16px "Nonsense Font ABC"')` with
    TRUE (measured), so that API cannot carry this either."""
    from ui import probe

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
    from ui import probe

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
    another, and `ui audit` has to leave the shell non-zero. Everything
    else on this page is clean, so the rc is font identity and nothing else."""
    from ui.cli import main

    monkeypatch.delenv("UI_FONT", raising=False)
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
    from ui.cli import main

    monkeypatch.delenv("UI_FONT", raising=False)
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
    from ui.score import REGISTRY, UNMEASURED

    row = REGISTRY["font-identity"]
    assert row.predicate is not UNMEASURED, "font-identity must be measured after W3"
    assert row.predicate == "ui.audit.check_font_identity", row.predicate


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
    from ui import audit, score

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
    from ui.score import REGISTRY, UNMEASURED

    for cls in ("component-anatomy", "colour"):
        assert REGISTRY[cls].predicate is UNMEASURED, f"{cls} claims a predicate it does not have"
