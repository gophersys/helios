"""Parse installed official KiCad symbols into typed component data.

The installed symbol libraries are the lowest-variance source of
pad↔name↔etype truth for parts KiCad already curates (and they pre-link
the footprint). This module is deterministic: kiutils parse only, no LLM.

Derived symbols (``(extends "Parent")``) are resolved within their
library: pins and body geometry come from the parent; properties
(Footprint, Datasheet, Description, Value) come from the child where set.

Pins KiCad draws unnamed get a synthesized ``P<pad>`` name, listed in
``OfficialSymbol.synthesized_names`` so a consumer can tell an invented
label from one the symbol really carries.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent / "tools"))

from kiutils.symbol import SymbolLib

from ..footprints import kicad_share_dir
from ..model import ElectricalType, PinSpec


@dataclass(frozen=True)
class OfficialSymbol:
    library: str                  # e.g. "RF_Module"
    name: str                     # e.g. "ESP32-S3-WROOM-1"
    pins: tuple[PinSpec, ...]     # pad/name/etype from the symbol (role=SIGNAL)
    footprint: str                # "Lib:Name" or ""
    datasheet: str
    description: str
    extends: str | None           # parent symbol name if derived
    reference: str = ""           # KiCad Reference property prefix: "C", "D", …
    # Pin names this module INVENTED because KiCad drew the pin unnamed.
    # Downstream ingest must not present a synthesized name as symbol-sourced
    # truth: for Device:C the pads really are anonymous, so "P1"/"P2" is our
    # label, not KiCad's. Names here map 1:1 onto pads; find the pads with
    # ``[p.pad for p in sym.pins if p.name in sym.synthesized_names]``.
    synthesized_names: tuple[str, ...] = ()

    @property
    def lib_id(self) -> str:
        return f"{self.library}:{self.name}"


class OfficialLibrary:
    """One parsed .kicad_sym library with extends-resolution."""

    def __init__(self, library: str, path: Path) -> None:
        self.library = library
        self.path = path
        self._lib = SymbolLib.from_file(str(path))
        self._by_name = {s.entryName: s for s in self._lib.symbols}

    @classmethod
    def open(cls, library: str, share_dir: Path | None = None) -> OfficialLibrary:
        share = share_dir or kicad_share_dir()
        path = share / "symbols" / f"{library}.kicad_sym"
        if not path.is_file():
            raise FileNotFoundError(f"No installed symbol library {library!r}")
        return cls(library, path)

    def names(self) -> list[str]:
        return sorted(self._by_name)

    def get(self, name: str) -> OfficialSymbol:
        sym = self._by_name.get(name)
        if sym is None:
            raise KeyError(f"{self.library} has no symbol {name!r}")

        extends = getattr(sym, "extends", None)

        # Walk the WHOLE extends chain. A derived symbol may itself be derived
        # (INA281A2 -> INA281A1 -> AD8211): stopping after one hop leaves
        # pin_source on an intermediate that carries no units, producing a
        # symbol with zero pins that silently passes as a real part. 177 of the
        # installed official symbols are multi-level like this.
        chain = [sym]
        visited = {name}
        cursor = sym
        while parent_name := getattr(cursor, "extends", None):
            if parent_name in visited:
                raise KeyError(
                    f"{self.library}:{name} has a cyclic extends chain "
                    f"through {parent_name!r}")
            parent = self._by_name.get(parent_name)
            if parent is None:
                raise KeyError(
                    f"{self.library}:{name} extends unknown symbol "
                    f"{parent_name!r}")
            visited.add(parent_name)
            chain.append(parent)
            cursor = parent

        # Pins come from the nearest ancestor that actually defines units.
        pin_source = next((s for s in chain if s.units), chain[-1])

        # Properties resolve nearest-first: the derived symbol overrides its
        # parent, which overrides the grandparent. setdefault over the chain in
        # order gives exactly that precedence.
        props: dict[str, str] = {}
        for link in chain:
            for p in link.properties or []:
                props.setdefault(p.key, p.value)

        # Pass 1: collect (pad, raw name, etype), de-duplicating stacked pads.
        # Official symbols may stack same-numbered pins (parallel pads); keep
        # the first, they are electrically identical.
        raw: list[tuple[str, str, str]] = []
        seen: set[str] = set()
        for unit in pin_source.units or []:
            for p in unit.pins or []:
                pad = str(p.number)
                if pad in seen:
                    continue
                seen.add(pad)
                raw.append((pad, (p.name or "").strip(), p.electricalType))

        # Pass 2: name the pins KiCad drew unnamed.
        #
        # KiCad writes (name "") or (name "~") for pins it draws unnamed —
        # every logic gate in 4xxx/74xx does this, and so do Device:C,
        # Device:R and Device:FerriteBead. PinSpec requires a non-empty name,
        # so passing one straight through raised ValueError out of a function
        # documented to return `OfficialSymbol | None` and aborted any
        # corpus-wide ingest on the first logic gate.
        #
        # The synthesized form is "P<pad>", not the bare pad: a bare pad
        # collides in meaning with the pins KiCad genuinely NAMES "1"/"2"
        # (Device:L, Switch:SW_Push), so a consumer could not tell an invented
        # label from a real one. Every synthesized name is recorded in
        # ``synthesized_names`` so the ingest ledger can say so out loud.
        real_names = {n for _, n, _ in raw if n and n != "~"}
        synthesized: list[str] = []
        pins = []
        for pad, pin_name, etype in raw:
            if not pin_name or pin_name == "~":
                # Fall back through candidates so a synthesized label can
                # never collide with a name the symbol really carries.
                for candidate in (f"P{pad}", pad, f"PIN{pad}"):
                    if candidate not in real_names:
                        pin_name = candidate
                        break
                else:                             # pragma: no cover - pathological
                    pin_name = f"PIN_{pad}"
                real_names.add(pin_name)
                synthesized.append(pin_name)
            pins.append(PinSpec(pad=pad, name=pin_name,
                                etype=ElectricalType.parse(etype)))

        return OfficialSymbol(
            library=self.library,
            name=name,
            pins=tuple(pins),
            footprint=props.get("Footprint", "") or "",
            datasheet=props.get("Datasheet", "") or "",
            description=props.get("Description", "") or "",
            extends=extends or None,
            reference=props.get("Reference", "") or "",
            synthesized_names=tuple(synthesized),
        )


def load_official_symbol(lib_id: str,
                         share_dir: Path | None = None) -> OfficialSymbol | None:
    """Fetch ``Lib:Name`` from the installed libraries, or None if absent."""
    if ":" not in lib_id:
        return None
    library, name = lib_id.split(":", 1)
    try:
        lib = OfficialLibrary.open(library, share_dir)
    except FileNotFoundError:
        return None
    try:
        return lib.get(name)
    except KeyError:
        return None
