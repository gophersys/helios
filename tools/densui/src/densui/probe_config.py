"""densui.probe_config — a panel.toml's [probe]/[rules]/[ratio] as inputs.

One panel.toml is the single source of what a panel is measured with, and
three gates read it: `densui audit`, `densui score`, and the operator demo's
own audit. They go through THESE two functions so a selector, a text kind or a
declared row cannot be honoured on one path and ignored on another — that
divergence is exactly how demos/telemetry's [ratio] rows stayed dormant.

    collect_panel(page, cfg["probe"])  -> probe output for that page
    rules_from(cfg)                    -> audit.Rules, [ratio] table included
"""

from __future__ import annotations

import pathlib


def collect_panel(page: str | pathlib.Path, probe_cfg: dict, extra_js: str = "") -> dict:
    """Probe `page` with the selectors a panel.toml's [probe] table declares."""
    from densui import probe

    return probe.collect(
        page,
        root=probe_cfg["root"],
        containers=probe_cfg.get("containers", {}),
        parts=probe_cfg.get("parts", {}),
        text_kinds=set(probe_cfg.get("text_kinds", [])),
        owner_attr=probe_cfg.get("owner_attr", "data-addr"),
        root_width=probe_cfg.get("root_width"),
        extra_js=extra_js,
    )


def rules_from(cfg: dict):
    """audit.Rules from a panel.toml's [rules], carrying its [ratio] rows and
    its [font].

    The rows travel with the rules because every consumer of the battery must
    execute what the file declared; a malformed row raises SpecError here
    rather than measuring nothing quietly. The face travels the same way and
    through the same ladder the demo builds resolve with (fontmetrics.
    resolve_path), so the audit judges the page against the face the page was
    actually built with.
    """
    from densui import audit
    from densui.fontmetrics import Face, resolve_path
    from densui.spec import ratio_rows, rules_table

    rules_cfg = rules_table(cfg)
    legal = None
    if "graze_max_height" in rules_cfg:
        legal = audit.knob_value_graze(
            rules_cfg["graze_max_height"], rules_cfg.get("graze_min_dx", 8.0)
        )
    # Declared keys only, so audit.Rules stays the single source of every
    # default — a floor copied to here is a second number to keep in step.
    scalars = (
        "axis_budget_floor",
        "axis_budget_reason",
        "axis_budget_exempt",
        "hit_kinds_reason",
        "snap_kinds_reason",
    )
    declared = {k: rules_cfg[k] for k in scalars if k in rules_cfg}
    for key in ("hit_kinds", "snap_kinds"):
        if key in rules_cfg:
            declared[key] = frozenset(rules_cfg[key])
    # A panel that declares no [font] has no face to be judged against, and
    # check_font_identity says nothing about it — the [ratio] contract exactly.
    font_cfg = cfg.get("font", {})
    if font_cfg:
        declared["face"] = Face(resolve_path(font_cfg.get("path")))
        if "size" in font_cfg:
            declared["font_size"] = font_cfg["size"]
    return audit.Rules(
        min_sibling_gap=rules_cfg.get("min_sibling_gap", 2.0),
        breathing_floor=rules_cfg.get("breathing_floor", 2.5),
        legal_overlap=legal,
        spill_slack={(c, k): float(v) for c, k, v in rules_cfg.get("spill", [])},
        ratio_rows=tuple(ratio_rows(cfg)),
        **declared,
    )
