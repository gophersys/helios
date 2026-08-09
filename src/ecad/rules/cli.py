"""``python -m src.ecad.rules check <module>`` — run the rule pack.

    $ python -m src.ecad.rules check examples.esp32_s3_reference
    PWR-003  ERROR  U1 VDD_SPI tied to +3V3
      -> ESP32-S3 DS v1.3 Table 7 'VDD_SPI Voltage Control' ...
      -> waive: PWR-003 target "U1:VDD_SPI+VDD3P3_RTC@+3V3"
    FAILED (1 errors, 0 warnings, 0 waived)

The module argument is anything that exposes ``build()`` returning a
``Design``, a ``{sheet: Design}`` mapping, or a ``GeneratedProject`` — the
last being the contract every example in ``examples/`` honours, whose
``.designs`` are the sheets.

A multi-sheet design is checked **twice**: once per sheet, and once over
the merged board. Both are meaningful and they answer different questions.
A sheet on its own genuinely has undriven rails — power crosses sheets as
KiCad global power symbols and there is no regulator on the MCU sheet. The
merged view is the board. Printing only the merged view would hide a sheet
that is wrong on its own terms; printing only the sheets would report the
hierarchy as a defect.

**Every pass counts toward the exit status.** A per-sheet error that the
hierarchy explains is waived with a citation, not silently dropped — that
is the whole point of having a waiver ledger, and a gate that quietly
ignored a whole class of pass is exactly the failure mode this engine
exists to stop repeating.
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from ..design import Design
from .engine import Report, Severity, Waiver, check, load_waivers, rules

_SEV_ORDER = {Severity.ERROR: 0, Severity.WARNING: 1, Severity.INFO: 2}


def _load_designs(target: str) -> dict[str, Design]:
    """Import ``target`` and pull the design(s) out of it.

    Three shapes are accepted and all three normalise to ``{name: Design}``
    immediately, so nothing downstream sees a union: a bare ``Design``, a
    ``{sheet: Design}`` mapping, and anything carrying a ``designs`` mapping
    — which is what the examples' ``build() -> GeneratedProject`` contract
    returns (``src/pipeline/composer.py``). The rules run on the typed
    designs either way; the project layer around them is irrelevant here.
    """
    try:
        module = importlib.import_module(target)
    except ImportError as e:
        raise SystemExit(f"cannot import {target!r}: {e}") from None
    build = getattr(module, "build", None)
    if build is None:
        raise SystemExit(
            f"{target!r} has no build(); expected a module exposing "
            f"build() -> Design | dict[str, Design] | GeneratedProject")
    built = build()
    if isinstance(built, Design):
        return {built.name: built}
    if isinstance(built, dict) and built:
        return dict(built)
    designs = getattr(built, "designs", None)
    if isinstance(designs, dict) and designs:
        return dict(designs)
    raise SystemExit(f"{target}.build() returned {type(built).__name__}, "
                     f"expected Design, dict[str, Design] or a project with "
                     f"a non-empty .designs mapping")


def _print(report: Report, *, show_info: bool, out) -> None:
    findings = sorted(report.findings,
                      key=lambda f: (_SEV_ORDER[f.severity], f.rule_id,
                                     f.target))
    for f in findings:
        if f.severity is Severity.INFO and not show_info:
            continue
        print(f.format(), file=out)
        if f.citation:
            print(f"  -> {f.citation}", file=out)
        if f.remediation:
            print(f"  -> fix: {f.remediation}", file=out)
        if f.severity is Severity.ERROR:
            print(f'  -> waive: {f.rule_id} target "{f.target}" '
                  f"(needs reason, cited_source, author)", file=out)
    for w in sorted(report.waived,
                    key=lambda w: (w.finding.rule_id, w.finding.target)):
        print(f"{w.finding.rule_id:<8} {'WAIVED':<7} {w.finding.message}",
              file=out)
        print(f"  -> waived by {w.waiver.author}: {w.waiver.reason}", file=out)
        print(f"  -> cited: {w.waiver.cited_source}", file=out)


def main(argv: Sequence[str] | None = None, *, out=None) -> int:
    out = out if out is not None else sys.stdout
    parser = argparse.ArgumentParser(
        prog="python -m src.ecad.rules",
        description="Electrical rule engine (semantic design checks).")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("check", help="run the rule pack over a design module")
    run.add_argument("module",
                     help="importable module exposing build() "
                          "(e.g. examples.esp32_s3_reference)")
    run.add_argument("--waivers", type=Path, default=None,
                     help="JSON ledger of waivers "
                          "[{rule_id,target,reason,cited_source,author}]")
    run.add_argument("--power-source", action="append", default=[],
                     metavar="NET",
                     help="net that arrives already driven (repeatable)")
    run.add_argument("--domain", default=None, help="only this rule domain")
    run.add_argument("--sheets-only", action="store_true",
                     help="skip the merged-board pass")
    run.add_argument("--merged-only", action="store_true",
                     help="skip the per-sheet passes")
    run.add_argument("--quiet-info", action="store_true",
                     help="hide INFO 'no data' findings")
    run.add_argument("--json", action="store_true",
                     help="emit machine-readable JSON instead of text")

    sub.add_parser("list", help="list the registered rules")

    args = parser.parse_args(argv)
    if args.command == "list":
        for rule in rules():
            print(f"{rule.id:<8} {rule.severity.value:<7} {rule.title}",
                  file=out)
            print(f"  -> {rule.citation()}", file=out)
        return 0

    designs = _load_designs(args.module)
    waivers: list[Waiver] = (load_waivers(args.waivers) if args.waivers
                             else [])
    common = {"waivers": waivers, "domain": args.domain,
              "power_sources": tuple(args.power_source)}

    reports: list[tuple[str, Report]] = []
    if not args.merged_only:
        for name, design in designs.items():
            reports.append((f"sheet:{name}", check(design, **common)))
    if len(designs) > 1 and not args.sheets_only:
        reports.append(("merged", check(designs, name=f"{args.module} (merged)",
                                        **common)))
    elif not reports:
        only = next(iter(designs.values()))
        reports.append((f"sheet:{only.name}", check(only, **common)))

    if args.json:
        print(json.dumps({"module": args.module,
                          "reports": {k: r.as_dict() for k, r in reports}},
                         indent=2), file=out)
    else:
        for label, report in reports:
            print(f"\n=== {label} — {report.name}", file=out)
            _print(report, show_info=not args.quiet_info, out=out)
            print(report.summary(), file=out)

    total = {"errors": 0, "warnings": 0, "waived": 0}
    for _, r in reports:
        c = r.counts()
        for k in total:
            total[k] += c[k]
    if not args.json:
        print(f"\n{'OK' if total['errors'] == 0 else 'FAILED'} "
              f"({total['errors']} errors, {total['warnings']} warnings, "
              f"{total['waived']} waived) over {len(reports)} pass(es)",
              file=out)
    return 0 if total["errors"] == 0 else 1
