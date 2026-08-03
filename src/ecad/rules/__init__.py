"""Electrical rule engine — the semantic oracle over a typed ``Design``.

    from src.ecad.rules import check
    report = check(design)
    report.ok          # errors == 0 after waivers

Importing this package registers every shipped rule pack (power today), so
:func:`rules` is populated without the caller naming a domain module.

See :mod:`src.ecad.rules.engine` for the contract (context, waivers,
report) and :mod:`src.ecad.rules.power` for the rules and their citations.
"""

from __future__ import annotations

from .engine import (
    CapView,
    Finding,
    NetView,
    PartFacts,
    RailVoltage,
    RegulatorFacts,
    Report,
    Rule,
    RuleContext,
    Severity,
    WaivedFinding,
    Waiver,
    check,
    get_rule,
    load_waivers,
    register_facts,
    register_rule,
    rules,
)

# Registers the power pack (rules + its cited datasheet-facts provider).
from . import power  # noqa: E402,F401  (import for side effect, must come last)

__all__ = [
    "CapView",
    "Finding",
    "NetView",
    "PartFacts",
    "RailVoltage",
    "RegulatorFacts",
    "Report",
    "Rule",
    "RuleContext",
    "Severity",
    "WaivedFinding",
    "Waiver",
    "check",
    "get_rule",
    "load_waivers",
    "power",
    "register_facts",
    "register_rule",
    "rules",
]
