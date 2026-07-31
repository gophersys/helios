"""Evidence ledger: cross-verify datasheet extraction against independent
sources (installed official KiCad symbol, Zephyr devicetree/HAL, resolved
footprint pads).

Every comparison is a *claim* with per-source values; disagreements are
recorded conflicts — never silently resolved — and the ``cross_verified``
gate reads ``summary()["conflicts"] == 0``. A human can unlock a specific
conflict with a waiver carrying {reason, cited_source, author}.

Normalization rules (applied before comparison):
- primary name before slash: ``TXD0/GPIO1`` → ``TXD0``
- ``GPIOn`` ≡ ``IOn`` (both fold to ``IOn``, leading zeros dropped)
- case fold to upper
- GND dedup: name-set comparison collapses repeated ground pads, so nine
  stacked GND pins on one side equal one GND entry on the other.

The ``zephyr`` argument is duck-typed against the ``SocInfo`` contract from
``ingest/zephyr.py`` (built in parallel): optional attributes ``ngpios``
(int), ``input_only`` (set[int]), ``strapping`` (set[int]) and ``signals``
(dict[str, set[int]] signal-group → allowed GPIOs). Absent attributes
simply produce no claims.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from ..model import ElectricalType, PinRole, PinSpec
from .kicad_official import OfficialSymbol

# Footprint pads allowed beyond the pin set (mirrors footprints.py gate).
_SURPLUS_OK_RE = re.compile(r"^$|^EP\d*$|^MP\d*$|^SH\d*$|^PAD$", re.IGNORECASE)
_GPIO_RE = re.compile(r"^(?:GPIO|IO)(\d+)$")


def normalize_name(name: str) -> str:
    """Normalize a pin name for cross-source comparison (rules above)."""
    primary = name.split("/", 1)[0].strip()
    up = primary.upper()
    m = _GPIO_RE.fullmatch(up)
    if m:
        return f"IO{int(m.group(1))}"
    return up


def _pad_key(pad: str) -> tuple[int, int | str]:
    return (0, int(pad)) if pad.isdigit() else (1, pad)


@dataclass
class Claim:
    """One cross-source assertion with per-source values."""

    kind: str                      # "pin_name" | "pad_set" | "name_set" | ...
    key: str                       # pad number or comparison id
    values: dict[str, str]         # source → normalized value
    status: str                    # "agreed" | "single_source" | "conflict" | "waived"
    detail: str = ""
    waiver: dict[str, str] | None = None


@dataclass
class Evidence:
    """The full ledger for one component."""

    component: str = ""
    claims: list[Claim] = field(default_factory=list)

    def find(self, kind: str, key: str) -> Claim | None:
        for c in self.claims:
            if c.kind == kind and c.key == key:
                return c
        return None

    def summary(self) -> dict[str, int]:
        counts = {"claims": len(self.claims), "agreed": 0,
                  "single_source": 0, "conflicts": 0, "waived": 0}
        for c in self.claims:
            if c.status == "agreed":
                counts["agreed"] += 1
            elif c.status == "single_source":
                counts["single_source"] += 1
            elif c.status == "waived":
                counts["waived"] += 1
            else:
                counts["conflicts"] += 1
        return counts

    def waive(self, kind: str, key: str, *, reason: str, cited_source: str,
              author: str) -> Claim:
        """Unlock one conflicting claim with a cited human waiver."""
        if not (reason and cited_source and author):
            raise ValueError("waiver requires reason, cited_source and author")
        claim = self.find(kind, key)
        if claim is None:
            raise KeyError(f"no claim {kind}:{key}")
        if claim.status != "conflict":
            raise ValueError(f"claim {kind}:{key} is {claim.status!r}, "
                             "only conflicts can be waived")
        claim.status = "waived"
        claim.waiver = {"reason": reason, "cited_source": cited_source,
                        "author": author}
        return claim


def _add(claims: list[Claim], kind: str, key: str, values: dict[str, str],
         ok: bool | None, detail: str = "") -> None:
    """Append a claim; ok=None means only one source could weigh in."""
    if ok is None:
        status = "single_source"
    else:
        status = "agreed" if ok else "conflict"
    claims.append(Claim(kind=kind, key=key, values=values, status=status,
                        detail=detail))


def _set_repr(items: set[str] | set[int]) -> str:
    return ",".join(str(i) for i in sorted(items, key=lambda x: (isinstance(x, str), x)))


def build_evidence(extracted: Sequence[PinSpec],
                   official: OfficialSymbol | None = None,
                   zephyr: Any | None = None,
                   footprint_pads: set[str] | None = None,
                   component: str = "") -> Evidence:
    """Build the ledger from all available sources (deterministic)."""
    claims: list[Claim] = []
    ds_by_pad = {p.pad: p for p in extracted}

    # ── datasheet vs official symbol ────────────────────────────────────────
    if official is not None:
        of_by_pad = {p.pad: p for p in official.pins}

        # Pad-set equality.
        ds_pads, of_pads = set(ds_by_pad), set(of_by_pad)
        detail = ""
        if ds_pads != of_pads:
            missing = sorted(of_pads - ds_pads, key=_pad_key)
            extra = sorted(ds_pads - of_pads, key=_pad_key)
            detail = f"missing_in_datasheet={missing} extra_in_datasheet={extra}"
        _add(claims, "pad_set", "datasheet_vs_official",
             {"datasheet": _set_repr(ds_pads), "official": _set_repr(of_pads)},
             ds_pads == of_pads, detail)

        # Deduped name-set equality (GND dedup: sets collapse repeats).
        ds_names = {normalize_name(p.name) for p in extracted}
        of_names = {normalize_name(p.name) for p in official.pins}
        detail = ""
        if ds_names != of_names:
            detail = (f"only_datasheet={sorted(ds_names - of_names)} "
                      f"only_official={sorted(of_names - ds_names)}")
        _add(claims, "name_set", "datasheet_vs_official",
             {"datasheet": _set_repr(ds_names), "official": _set_repr(of_names)},
             ds_names == of_names, detail)

        # Per-pad name agreement.
        for pad in sorted(ds_pads | of_pads, key=_pad_key):
            values, norm = {}, []
            for source, pins in (("datasheet", ds_by_pad), ("official", of_by_pad)):
                if pad in pins:
                    values[source] = pins[pad].name
                    norm.append(normalize_name(pins[pad].name))
            ok = None if len(norm) < 2 else norm[0] == norm[1]
            _add(claims, "pin_name", pad, values,
                 ok, "" if ok is not False else f"{norm[0]} != {norm[1]}")

    # ── datasheet vs Zephyr ─────────────────────────────────────────────────
    if zephyr is not None:
        ngpios = getattr(zephyr, "ngpios", None)
        input_only = getattr(zephyr, "input_only", None) or set()
        strapping = getattr(zephyr, "strapping", None)
        signals = getattr(zephyr, "signals", None) or {}

        gpio_pins = [p for p in extracted if p.gpio is not None]
        for p in sorted(gpio_pins, key=lambda p: _pad_key(p.pad)):
            gpio: int = p.gpio  # type: ignore[assignment]
            if ngpios is not None:
                _add(claims, "gpio_range", p.pad,
                     {"datasheet": f"IO{gpio}", "zephyr": f"0..{ngpios - 1}"},
                     0 <= gpio < ngpios,
                     "" if 0 <= gpio < ngpios else f"IO{gpio} outside SoC range")
            if gpio in input_only:
                ok = p.etype is ElectricalType.INPUT
                _add(claims, "input_only", p.pad,
                     {"datasheet": p.etype.value, "zephyr": "input-only"},
                     ok, "" if ok else f"IO{gpio} is input-only in silicon")
            for fn in p.functions:
                fn_up = fn.upper()
                if fn_up in signals:
                    allowed = signals[fn_up]
                    ok = gpio in allowed
                    _add(claims, "signal_placement", f"{p.pad}:{fn_up}",
                         {"datasheet": f"{fn_up}@IO{gpio}",
                          "zephyr": f"{fn_up}@{{{_set_repr(allowed)}}}"},
                         ok, "" if ok else f"{fn_up} not routable to IO{gpio}")

        if strapping is not None:
            ds_strap = {p.gpio for p in gpio_pins
                        if p.role is PinRole.STRAPPING}
            if ds_strap:
                detail = ""
                if ds_strap != set(strapping):
                    detail = (f"only_datasheet={sorted(ds_strap - set(strapping))} "
                              f"only_zephyr={sorted(set(strapping) - ds_strap)}")
                _add(claims, "strapping", "set",
                     {"datasheet": _set_repr(ds_strap),
                      "zephyr": _set_repr(set(strapping))},
                     ds_strap == set(strapping), detail)
            else:
                _add(claims, "strapping", "set",
                     {"zephyr": _set_repr(set(strapping))}, None,
                     "datasheet extraction has no strapping-role pins")

    # ── pin set vs footprint pads ───────────────────────────────────────────
    if footprint_pads is not None:
        pin_pads = ({p.pad for p in official.pins} if official is not None
                    else set(ds_by_pad))
        missing = sorted(pin_pads - footprint_pads, key=_pad_key)
        surplus = sorted(footprint_pads - pin_pads, key=_pad_key)
        bad_surplus = [p for p in surplus if not _SURPLUS_OK_RE.match(p)]
        ok = not missing and not bad_surplus
        detail = "" if ok else (f"pins_without_pad={missing} "
                                f"unexplained_pads={bad_surplus}")
        _add(claims, "pad_set", "pins_vs_footprint",
             {"pins": _set_repr(pin_pads),
              "footprint": _set_repr(footprint_pads)}, ok, detail)

    return Evidence(component=component, claims=claims)


# ── persistence ─────────────────────────────────────────────────────────────────

def save_evidence(evidence: Evidence, path: Path) -> Path:
    payload = {
        "component": evidence.component,
        "claims": [asdict(c) for c in evidence.claims],
        "summary": evidence.summary(),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return path


def load_evidence(path: Path) -> Evidence:
    payload = json.loads(path.read_text())
    claims = [Claim(**c) for c in payload.get("claims", [])]
    return Evidence(component=payload.get("component", ""), claims=claims)
