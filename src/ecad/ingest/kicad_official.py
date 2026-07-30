"""Parse installed official KiCad symbols into typed component data.

The installed symbol libraries are the lowest-variance source of
pad↔name↔etype truth for parts KiCad already curates (and they pre-link
the footprint). This module is deterministic: kiutils parse only, no LLM.

Derived symbols (``(extends "Parent")``) are resolved within their
library: pins and body geometry come from the parent; properties
(Footprint, Datasheet, Description, Value) come from the child where set.
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
        pin_source = sym
        if extends:
            parent = self._by_name.get(extends)
            if parent is None:
                raise KeyError(
                    f"{self.library}:{name} extends unknown symbol {extends!r}")
            pin_source = parent

        props = {p.key: p.value for p in (sym.properties or [])}
        if extends:
            parent_props = {p.key: p.value
                            for p in (self._by_name[extends].properties or [])}
            for k, v in parent_props.items():
                props.setdefault(k, v)

        pins = []
        seen: dict[str, str] = {}
        for unit in pin_source.units or []:
            for p in unit.pins or []:
                pad = str(p.number)
                if pad in seen:
                    # Official symbols may stack same-numbered pins (parallel
                    # pads); keep the first, they are electrically identical.
                    continue
                seen[pad] = p.name
                pins.append(PinSpec(
                    pad=pad,
                    name=p.name,
                    etype=ElectricalType.parse(p.electricalType),
                ))

        return OfficialSymbol(
            library=self.library,
            name=name,
            pins=tuple(pins),
            footprint=props.get("Footprint", "") or "",
            datasheet=props.get("Datasheet", "") or "",
            description=props.get("Description", "") or "",
            extends=extends or None,
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
