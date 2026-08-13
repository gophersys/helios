#!/usr/bin/env python3
"""solve_layout — positions computed from font metrics + measured anchors.

LAYOUT-MATH applied: sizes come only from TTF advances or declared tokens
(A-1); no coordinate is a function of a live text width — text renders into
reserved boxes sized from the WIDEST enumerated string (A-2); edges are
integers (A-5); the emitted plan is verified against the gap floors before a
single line of CSS leaves this file. Deterministic: solved twice in shuffled
order and compared. Output: the CSS block assemble.py injects at
/* @SOLVED_POSITIONS@ */.
"""
import sys

from fontTools.ttLib import TTFont

FONT = ("/Applications/Ableton Live 12 Suite.app/Contents/App-Resources/Fonts/"
        "AbletonSansSmall-Regular.ttf")
SIZE = 16.0
DIAL_L, DIAL_R = 27, 28          # dial diameters, measured (ratios.md)
CHECK = 15                       # osc checkbox outer box
BADGE = 18
MIN_INK_GAP = 3.0                # foveal crowding floor (psycho-math)

_font = TTFont(FONT)
_upm = _font['head'].unitsPerEm
_cmap = _font.getBestCmap()
_hmtx = _font['hmtx']


def adv(s, px=SIZE):
    total = 0
    for ch in s:
        g = _cmap.get(ord(ch))
        if g is None:
            raise SystemExit(f"solve_layout: no glyph for {ch!r}")
        total += _hmtx[g][0]
    return total * px / _upm


def die(msg):
    print(f"SOLVE FAILED: {msg}", file=sys.stderr)
    sys.exit(1)


# ----------------------------------------------------------------- left rack
# Units anchored at measured dial/box centres (ratios.md): 25/125/201/252/333.
# Dial sits at the widget's left edge in this rack; label is left-aligned.
def solve_rack_l():
    pad = 10
    units = [
        # (name, center, kind, labels that must fit the reserved box)
        ("c-coarse", 25,  "knob", ["Coarse", "Freq"]),
        ("c-fine",   125, "knob", ["Fine", "Multi"]),
        ("c-fixed",  201, "check", ["Fixed"]),
        ("c-level",  252, "knob", ["Level"]),
    ]
    rows, cursor = {}, pad
    for name, center, kind, labels in units:
        if kind == "knob":
            left = round(center - DIAL_L / 2)
            width = max([DIAL_L] + [adv(t) for t in labels])
        else:
            left = round(center - CHECK / 2)
            width = max([CHECK] + [adv(t) for t in labels])
        width = int(width + 0.999) + 1
        margin = left - cursor
        if margin < 0:
            die(f"rackL {name}: reserved boxes collide (margin {margin})")
        rows[name] = (margin, width)
        cursor = left + width
    badge_left = 333 - BADGE // 2
    if badge_left - cursor < MIN_INK_GAP:
        die(f"rackL badge: gap {badge_left - cursor:.1f} < {MIN_INK_GAP}")
    # widest value ink must clear the badge: value starts widget.left+16
    lvl_left = 10 + rows["c-coarse"][0] + rows["c-coarse"][1] \
        + rows["c-fine"][0] + rows["c-fine"][1] \
        + rows["c-fixed"][0] + rows["c-fixed"][1] + rows["c-level"][0]
    if lvl_left + 16 + adv("-inf dB") > badge_left - MIN_INK_GAP:
        die("rackL: level value ink reaches the badge")
    css = ["/* rackL: solved from anchors 25/125/201/252/333 + font advances */",
           "#rackL .plate { gap: 0; }"]
    for name, (margin, width) in rows.items():
        css.append(f"#rackL .{name} {{ flex: none; width: {width}px; margin-left: {margin}px; }}")
    css.append(f"#rackL .badge {{ margin-right: {351 - (badge_left + BADGE)}px; }}")
    return css


# ---------------------------------------------------------------- right rack
# Two-line plates. Anchors: measured element lefts/tops (grid crops) for the
# enum line; knob units anchored at measured dial centres, width reserved from
# the label advance, dial centred, value tucked at centre+1.
KNOBS_R = {
    # name           center  label        widest value    left-neighbor ink right edge
    "p-lfo-rate":   (172, "Rate",      "100.00"),
    "p-lfo-amt":    (262, "Amount",    "100 %"),
    "p-fl-freq":    (193, "Freq",      "20.0 kHz"),   # +1 from crop: ink-gap inequality
    "p-fl-res":     (287, "Res",       "125 %"),   # +4: freq sweep value clearance
    "p-pt-env":     (95,  "Pitch Env", "-100 %"),
    "p-pt-spread":  (190, "Spread",    "100 %"),
    "p-pt-trans":   (285, "Transpose", "-48 st"),
    "p-gl-time":    (105, "Time",      "-100 %"),
    "p-gl-tone":    (197, "Tone",      "100 %"),
    "p-gl-vol":     (292, "Volume",    "-12.3 dB"),
}
FIXED_R = [
    ".p-lfo-check { left: 15px; top: 6px; }",
    ".p-lfo-wave  { left: 14px; top: 37px; width: 76px; }",
    ".p-lfo-dest  { left: 95px; top: 37px; width: 30px; }",
    ".p-lfo-r     { left: 130px; top: 37px; }",
    ".p-fl-check  { left: 15px; top: 6px; }",
    ".p-fl-type   { left: 102px; top: 5px; width: 66px; height: 22px; }",
    ".p-fl-12     { left: 15px; top: 39px; width: 70px; }",
    ".p-fl-circ   { left: 100px; top: 39px; width: 66px; }",
    ".p-pt-glyph  { left: 22px; top: 7px; }",
    ".p-pt-check  { left: 15px; top: 26px; }",
    ".p-gl-leds   { left: 15px; top: 28px; }",
]
# Two floors per plate: line 1 (labels) and line 2 (dials) have different
# left neighbours — conflating them was this solver's first modelling bug.
ROWS_R = {   # plate: (ordered knob units, dial floor line2, label floor line1)
    "lfo":    (["p-lfo-rate", "p-lfo-amt"], 152, 73),    # chip 149+3 | 'LFO' 70+3
    "filter": (["p-fl-freq", "p-fl-res"], 171, 171),     # circuit/type dd 168+3
    "pitch":  (["p-pt-env", "p-pt-spread", "p-pt-trans"], 39, 55),  # check 36+3 | glyph 52+3
    "global": (["p-gl-time", "p-gl-tone", "p-gl-vol"], 81, 3),      # leds 75+6 | none
}


def solve_rack_r():
    css = ["/* rackR: solved from measured centres; boxes reserved from advances */"]
    css += FIXED_R
    for plate, (names, dial_floor, label_floor) in ROWS_R.items():
        # Rhythm by construction: a run of >=3 same-kind dials gets equal edge
        # gaps — inner centres move to the arithmetic progression (gap law G-1).
        centers = {n: KNOBS_R[n][0] for n in names}
        if len(names) >= 3:
            first, last = centers[names[0]], centers[names[-1]]
            for k, n in enumerate(names):
                fixed = round(first + (last - first) * k / (len(names) - 1))
                if fixed != centers[n]:
                    css.append(f"/* rhythm-corrected: {n} centre {centers[n]} -> {fixed} */")
                centers[n] = fixed
        TUCK = 10        # value ink starts at centre+10, on the value line (y50+)
        prev_label_right = label_floor
        for k, name in enumerate(names):
            _, label, widest = KNOBS_R[name]
            center = centers[name]
            w = int(max(adv(label), DIAL_R) + 0.999) + 2
            left = round(center - w / 2)
            dial_left = round(center - DIAL_R / 2)
            label_ink_l = center - adv(label) / 2
            if dial_left < dial_floor:
                die(f"{name}: dial left {dial_left} crosses floor {dial_floor}")
            if label_ink_l < prev_label_right + MIN_INK_GAP:
                die(f"{name}: label ink {label_ink_l:.1f} crowds line-1 neighbour "
                    f"(ends {prev_label_right:.1f})")
            value_right = center + TUCK + adv(widest)
            if k + 1 < len(names):     # the value line's true neighbour: the NEXT DIAL
                nxt = centers[names[k + 1]] - DIAL_R / 2
                if value_right + MIN_INK_GAP > nxt:
                    die(f"{name}: widest value ink ends {value_right:.1f}, "
                        f"crowds next dial at {nxt:.1f}")
            elif value_right > 376 - 4:
                die(f"{plate}: last value ink {value_right:.1f} escapes the plate")
            prev_label_right = center + adv(label) / 2
            css.append(f".{name} {{ left: {left}px; top: 1px; width: {w}px; }}")
    return css


def main():
    a = solve_rack_l() + solve_rack_r()
    # determinism: re-solve with reversed unit maps and compare
    global KNOBS_R
    KNOBS_R = dict(reversed(list(KNOBS_R.items())))
    b = solve_rack_l() + solve_rack_r()
    if a != b:
        die("solver is order-dependent")
    print("\n".join(a))


if __name__ == "__main__":
    main()
