"""densui.score — the craft scorecard: what we measure, and what failed.

The honest answer to "does this panel read as generated?" is not a verdict; it
is a table of named defect classes, each with a predicate behind it or nothing
behind it, plus every violation found. This module owns that table (REGISTRY)
and runs it over probe output (run_scorecard). Two lies are refused by
construction:

- a class with no predicate reports UNMEASURED and can never read as clean —
  zero violations from a check that never ran is the shipped lie this exists
  to prevent;
- a predicate that misses its OWN seeded defect fails the run: a check that
  cannot fail is the defect.

There is deliberately no field for how a panel looks (docs/eyes.md). Nothing
here can support one.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable
from dataclasses import dataclass

from densui import audit


class _Unmeasured:
    """No predicate exists for this class yet.

    A sentinel rather than a string: "todo" is something a caller can print,
    compare, or mistake for a measurement.
    """

    def __repr__(self) -> str:
        return "UNMEASURED"


UNMEASURED = _Unmeasured()

Adapter = Callable[[Callable, dict, audit.Rules], list]


def _of_parts(fn: Callable, out: dict, rules: audit.Rules) -> list:
    return fn(out["parts"])


def _of_parts_rules(fn: Callable, out: dict, rules: audit.Rules) -> list:
    return fn(out["parts"], rules)


def _of_parts_containers_rules(fn: Callable, out: dict, rules: audit.Rules) -> list:
    return fn(out["parts"], out["containers"], rules)


def _of_snappable_parts(fn: Callable, out: dict, rules: audit.Rules) -> list:
    """The integer-edge rule reads geometry AND the page's scale, and judges only
    authored edges — the same two conditions run_battery applies, because a
    glyph-ink box (A-4) is measured rather than placed and a scaled page has
    fractional CSS px by construction."""
    return fn(audit.snappable(out["parts"], rules), out.get("scale", 1))


def _of_declared_rows(fn: Callable, out: dict, rules: audit.Rules) -> list:
    """The rows come from the target's own panel.toml (probe_config.rules_from
    carries them), so this class measures what each panel DECLARED — a target
    declaring nothing contributes nothing, which is why the corpus seed is the
    thing that proves the predicate can fire."""
    return fn(out, rules.ratio_rows)


def _of_declared_face(fn: Callable, out: dict, rules: audit.Rules) -> list:
    """The face and the reference size come from the target's own [font], which
    probe_config.rules_from resolved the same way its build did. A target that
    declares no face contributes nothing, so the corpus seed is again the thing
    that proves the predicate can fire."""
    return fn(out, rules.face, rules.font_size)


@dataclass(frozen=True)
class Row:
    """A defect class: the dotted predicate symbol, and how it is called.

    The symbol is a string so the registry can be checked against the code —
    a row naming something that does not exist is a believed check that runs
    nothing, and tests/test_scorecard.py fails on it.
    """

    predicate: str | _Unmeasured
    call: Adapter | None = None


REGISTRY: dict[str, Row] = {
    # Measured since the proof battery landed — one class per battery check.
    "overlap": Row("densui.audit.check_overlaps", _of_parts_rules),
    "crowding": Row("densui.audit.check_crowding", _of_parts_rules),
    "gap-law": Row("densui.audit.check_gap_law", _of_parts_rules),
    "containment": Row("densui.audit.check_containment", _of_parts_containers_rules),
    "breathing": Row("densui.audit.check_breathing", _of_parts_containers_rules),
    "alignment": Row("densui.audit.check_level", _of_parts),
    "size-ratio": Row("densui.audit.check_ratios", _of_declared_rows),
    "axis-sprawl": Row("densui.audit.check_axis_budget", _of_parts_rules),
    "hit-pitch": Row("densui.audit.check_hit_pitch", _of_parts_rules),
    "fractional-edges": Row("densui.audit.check_integer_edges", _of_snappable_parts),
    "font-identity": Row("densui.audit.check_font_identity", _of_declared_face),
    # Named by Mateo, predicate due in the workstream noted; UNMEASURED today.
    "padding-rhythm": Row(UNMEASURED),  # W1
    # No predicate is planned yet: bitmap assay and contrast maths.
    "component-anatomy": Row(UNMEASURED),
    "colour": Row(UNMEASURED),
}


@dataclass
class Target:
    """One scoreable thing: geometry as densui.probe.collect returns it.

    `seeds` names the ONE defect class deliberately planted in it (a corpus
    seed), or None for anything that must simply be clean.
    """

    name: str
    probe_out: dict
    seeds: str | None = None
    rules: audit.Rules | None = None


def _resolve(dotted: str) -> Callable:
    module_name, _, symbol = dotted.rpartition(".")
    return getattr(importlib.import_module(module_name), symbol)


def run_scorecard(targets: list[Target]) -> dict:
    """Score every target against every registered class.

    Returns {"classes": {cls: {measured, violations, seed_caught}},
    "failures": [str]} — coverage and failures, nothing else.
    """
    classes = {
        name: {
            "measured": row.predicate is not UNMEASURED,
            "violations": [],
            "seed_caught": None,
        }
        for name, row in REGISTRY.items()
    }
    failures: list[str] = []

    for t in targets:
        rules = t.rules if t.rules is not None else audit.Rules()
        if t.seeds is not None and t.seeds not in REGISTRY:
            failures.append(f"{t.name}: seeds unknown defect class {t.seeds!r}")
        elif t.seeds is not None and REGISTRY[t.seeds].predicate is UNMEASURED:
            failures.append(
                f"{t.name}: seeds {t.seeds}, which is UNMEASURED — nothing can catch it"
            )
        for name, row in REGISTRY.items():
            if row.predicate is UNMEASURED or row.call is None:
                continue
            found = row.call(_resolve(row.predicate), t.probe_out, rules)
            classes[name]["violations"].extend(f"{t.name}: {v}" for v in found)
            if t.seeds == name:
                caught = bool(found)
                prev = classes[name]["seed_caught"]
                classes[name]["seed_caught"] = caught if prev is None else (prev and caught)
                if not caught:
                    failures.append(f"{t.name}: seeded {name} defect not caught by {row.predicate}")
            else:
                failures.extend(f"{t.name}: {name}: {v}" for v in found)

    return {"classes": classes, "failures": failures}
