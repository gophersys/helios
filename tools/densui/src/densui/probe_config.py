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
    """audit.Rules from a panel.toml's [rules], carrying its [ratio] rows.

    The rows travel with the rules because every consumer of the battery must
    execute what the file declared; a malformed row raises SpecError here
    rather than measuring nothing quietly.
    """
    from densui import audit
    from densui.spec import ratio_rows

    rules_cfg = cfg.get("rules", {})
    legal = None
    if "graze_max_height" in rules_cfg:
        legal = audit.knob_value_graze(
            rules_cfg["graze_max_height"], rules_cfg.get("graze_min_dx", 8.0)
        )
    return audit.Rules(
        min_sibling_gap=rules_cfg.get("min_sibling_gap", 2.0),
        breathing_floor=rules_cfg.get("breathing_floor", 2.5),
        legal_overlap=legal,
        spill_slack={(c, k): float(v) for c, k, v in rules_cfg.get("spill", [])},
        ratio_rows=tuple(ratio_rows(cfg)),
    )
