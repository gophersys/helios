"""Installed-KiCad-footprint index and resolver.

Indexes every ``<lib>.pretty/<fp>.kicad_mod`` under the KiCad share
directory with a fast regex pass (full kiutils parsing is reserved for
the one resolved footprint at validation time), records distinct pad
numbers and 3D-model presence, and caches the result as JSON.

Resolution never guesses: a package-descriptor query must produce exactly
one confident winner or it fails asking for an explicit choice.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .model import FootprintRef

INDEX_VERSION = 1

_PAD_RE = re.compile(r'\(pad\s+"([^"]*)"')
_ATTR_SMD_RE = re.compile(r"\(attr\s+smd")

# Pad names allowed to exist on a footprint beyond the symbol's pins:
# exposed pads / mechanical / shield / paste-only ("").
_SURPLUS_OK_RE = re.compile(r"^$|^EP\d*$|^MP\d*$|^SH\d*$|^PAD$", re.IGNORECASE)


def kicad_share_dir() -> Path:
    return Path("/Applications/KiCad.app/Contents/SharedSupport")


@dataclass(frozen=True)
class FootprintInfo:
    lib: str
    name: str
    pad_numbers: tuple[str, ...]   # distinct, non-empty
    pad_total: int                 # raw pad statements incl. repeats/empties
    smd: bool
    has_step: bool

    @property
    def lib_id(self) -> str:
        return f"{self.lib}:{self.name}"


@dataclass(frozen=True)
class PackageSpec:
    """Descriptor-based footprint query, e.g. QFN-56 0.4mm 7x7 with EP."""

    family: str                    # "QFN", "SOT-23", "C_0402", ...
    pads: int | None = None       # electrical pad count expected
    pitch: float | None = None    # mm
    body: str | None = None       # "7x7" (mm), matched as substring "7x7mm"
    ep: bool | None = None        # exposed pad required / forbidden / dontcare


class FootprintIndex:
    def __init__(self, entries: dict[str, FootprintInfo], meta: dict) -> None:
        self._entries = entries    # keyed by "Lib:Name"
        self.meta = meta

    # ── construction / cache ────────────────────────────────────────────────

    @classmethod
    def build(cls, share_dir: Path | None = None) -> FootprintIndex:
        share = share_dir or kicad_share_dir()
        fp_root = share / "footprints"
        model_root = share / "3dmodels"
        entries: dict[str, FootprintInfo] = {}
        for pretty in sorted(fp_root.glob("*.pretty")):
            lib = pretty.stem
            shapes = model_root / f"{lib}.3dshapes"
            for mod in sorted(pretty.glob("*.kicad_mod")):
                text = mod.read_text(errors="replace")
                pads = _PAD_RE.findall(text)
                distinct = tuple(sorted({p for p in pads if p}))
                info = FootprintInfo(
                    lib=lib,
                    name=mod.stem,
                    pad_numbers=distinct,
                    pad_total=len(pads),
                    smd=bool(_ATTR_SMD_RE.search(text)),
                    has_step=(shapes / f"{mod.stem}.step").is_file(),
                )
                entries[info.lib_id] = info
        meta = {
            "index_version": INDEX_VERSION,
            "share_dir": str(share),
            "footprint_count": len(entries),
        }
        return cls(entries, meta)

    def save(self, path: Path) -> None:
        payload = {
            "meta": self.meta,
            "entries": {
                k: {
                    "lib": v.lib, "name": v.name,
                    "pad_numbers": list(v.pad_numbers),
                    "pad_total": v.pad_total, "smd": v.smd,
                    "has_step": v.has_step,
                }
                for k, v in self._entries.items()
            },
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload))

    @classmethod
    def load(cls, path: Path) -> FootprintIndex:
        payload = json.loads(path.read_text())
        entries = {
            k: FootprintInfo(
                lib=e["lib"], name=e["name"],
                pad_numbers=tuple(e["pad_numbers"]),
                pad_total=e["pad_total"], smd=e["smd"],
                has_step=e["has_step"],
            )
            for k, e in payload["entries"].items()
        }
        return cls(entries, payload["meta"])

    @classmethod
    def cached(cls, cache_path: Path, share_dir: Path | None = None) -> FootprintIndex:
        """Load the cache if fresh, else build and write it."""
        share = share_dir or kicad_share_dir()
        if cache_path.is_file():
            try:
                idx = cls.load(cache_path)
                if (idx.meta.get("index_version") == INDEX_VERSION
                        and idx.meta.get("share_dir") == str(share)
                        and idx.meta.get("footprint_count", 0) > 0):
                    return idx
            except (json.JSONDecodeError, KeyError):
                pass
        idx = cls.build(share)
        idx.save(cache_path)
        return idx

    # ── queries ─────────────────────────────────────────────────────────────

    def get(self, lib_id: str) -> FootprintInfo | None:
        return self._entries.get(lib_id)

    def __len__(self) -> int:
        return len(self._entries)

    def candidates(self, spec: PackageSpec) -> list[FootprintInfo]:
        fam = spec.family.upper().replace(" ", "")
        out = []
        for info in self._entries.values():
            name_u = info.name.upper()
            if not name_u.startswith(fam):
                continue
            if spec.pads is not None and len(info.pad_numbers) != spec.pads:
                continue
            if spec.pitch is not None:
                token = f"P{spec.pitch:g}MM"
                if token not in name_u.replace("_", ""):
                    continue
            if spec.body is not None and f"{spec.body.upper()}MM" not in name_u:
                continue
            if spec.ep is not None and ("1EP" in name_u) != spec.ep:
                continue
            if "THERMALVIAS" in name_u or "HANDSOLDER" in name_u:
                continue  # variants; the base footprint is the canonical pick
            out.append(info)
        return sorted(out, key=lambda i: i.lib_id)

    def resolve(self, spec: PackageSpec) -> FootprintInfo:
        """Resolve a package descriptor to exactly one footprint or fail."""
        cands = self.candidates(spec)
        if len(cands) == 1:
            return cands[0]
        if not cands:
            raise LookupError(f"No installed footprint matches {spec}")
        names = ", ".join(c.lib_id for c in cands[:8])
        raise LookupError(
            f"Ambiguous package {spec}: {len(cands)} candidates ({names}"
            f"{', …' if len(cands) > 8 else ''}) — specify an explicit lib:name"
        )


@dataclass(frozen=True)
class FootprintValidation:
    ok: bool
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    info: FootprintInfo | None = None


def validate_footprint(index: FootprintIndex, ref: FootprintRef,
                       pin_pads: set[str]) -> FootprintValidation:
    """Gate: the footprint exists and can carry every symbol pin.

    - symbol pin-number set ⊆ footprint distinct pad-number set
    - surplus footprint pads allowed only for EP/MP/SH/"" classes
    - missing STEP model is a warning, not a failure
    """
    if ref.source == "custom":
        if not (ref.path and Path(ref.path).is_file()):
            return FootprintValidation(False, (f"custom footprint path missing: "
                                               f"{ref.path}",))
        text = Path(ref.path).read_text(errors="replace")
        pads = _PAD_RE.findall(text)
        info = FootprintInfo(lib=ref.lib or "Custom", name=ref.name,
                             pad_numbers=tuple(sorted({p for p in pads if p})),
                             pad_total=len(pads),
                             smd=bool(_ATTR_SMD_RE.search(text)), has_step=False)
    else:
        found = index.get(ref.lib_id)
        if found is None:
            return FootprintValidation(False, (f"footprint {ref.lib_id!r} not in "
                                               f"installed KiCad libraries",))
        info = found

    errors: list[str] = []
    warnings: list[str] = []
    pad_set = set(info.pad_numbers)
    missing = sorted(pin_pads - pad_set)
    if missing:
        errors.append(f"symbol pins with no footprint pad: {missing}")
    surplus = sorted(pad_set - pin_pads)
    bad_surplus = [p for p in surplus if not _SURPLUS_OK_RE.match(p)]
    if bad_surplus:
        errors.append(f"footprint has unexplained extra pads: {bad_surplus}")
    if not info.has_step and ref.source != "custom":
        warnings.append("no STEP model alongside footprint")
    return FootprintValidation(ok=not errors, errors=tuple(errors),
                               warnings=tuple(warnings), info=info)
