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
    # Named by Mateo, predicate due in the workstream noted; UNMEASURED today.
    "size-ratio": Row(UNMEASURED),  # W1
    "padding-rhythm": Row(UNMEASURED),  # W1
    "axis-sprawl": Row(UNMEASURED),  # W2
    "hit-pitch": Row(UNMEASURED),  # W2
    "fractional-edges": Row(UNMEASURED),  # W2
    "font-identity": Row(UNMEASURED),  # W3
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
