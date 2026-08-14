"""Empirical probe of the forbidden-zone thresholds (G-1: equal within
max(6%,1px) or >=1.45x) on the REAL solved layouts of every demo, under
every locally available font.

Method (a blind system cannot run human subjects; it can probe its own
rule's robustness): extract every same-kind adjacent gap the solver
produces, compute all pair ratios, and ask two questions —
1. Does any real layout land inside the deep forbidden core (1.06..1.40)?
   If yes, our own layouts violate our own law and one of them is wrong.
2. Is 1.45 on a plateau? Sweep the threshold 1.20..1.60 and count
   classification flips; a cliff near 1.45 would mean the constant is
   load-bearing in a fragile way.
Results are recorded in framework/research/forbidden-zone-probe.md; this
test IS the probe, re-run on every gate, so the record cannot go stale.
"""

import pathlib
import tomllib

from densui.solve import solve

ROOT = pathlib.Path(__file__).resolve().parents[3]
PANELS = [
    ROOT / "demos/operator/panel.toml",
    ROOT / "demos/telemetry/panel.toml",
    ROOT / "demos/bench/panel.toml",
]
FONTS = [
    p
    for p in [
        "/Applications/Ableton Live 12 Suite.app/Contents/App-Resources/Fonts/AbletonSansSmall-Regular.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    if pathlib.Path(p).exists()
]


def all_gap_ratios():
    ratios = []
    for panel in PANELS:
        data = tomllib.loads(panel.read_text())
        for font in FONTS:
            data["font"]["path"] = font
            out = solve({"font": data["font"], **data["solve"]})
            for row_name, row in out.get("knob_rows", {}).items():
                spec_row = data["solve"]["knob_rows"][row_name]
                dial = spec_row.get("dial", 28)
                units = [u["name"] for u in spec_row["units"]]
                edges = [(row[n]["center"] - dial / 2, row[n]["center"] + dial / 2) for n in units]
                gaps = [edges[i + 1][0] - edges[i][1] for i in range(len(edges) - 1)]
                for i in range(len(gaps)):
                    for j in range(i + 1, len(gaps)):
                        g1, g2 = sorted((gaps[i], gaps[j]))
                        if g1 > 0:
                            ratios.append(g2 / g1)
    assert ratios, "probe found no gap pairs — the probe itself cannot run"
    return ratios


def test_no_real_layout_lands_in_the_deep_forbidden_core():
    core = [r for r in all_gap_ratios() if 1.06 < r < 1.40]
    assert core == [], f"our own layouts violate our own law: {core}"


def test_threshold_sits_on_a_plateau_not_a_cliff():
    ratios = all_gap_ratios()
    flips = {}
    for t100 in range(120, 161, 5):
        t = t100 / 100
        flips[t] = sum(1 for r in ratios if 1.06 < r < t)
    # every threshold in 1.20..1.60 classifies our real layouts identically:
    # the constant is not load-bearing on this corpus — a plateau, not a cliff
    assert len(set(flips.values())) == 1, f"threshold sensitivity found: {flips}"
