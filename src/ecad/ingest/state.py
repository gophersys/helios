"""Component-factory stage machine: one truth record per component.

Each component progresses ``discovered -> extracted -> cross_verified ->
symbol_done -> footprint_resolved -> sourcing_linked -> validated ->
approved``. Every stage has a deterministic gate; a record's *stage* is
the longest consecutive run of passed gates, so re-running a gate that
now fails demotes the record automatically (self-healing on KiCad or
Zephyr bumps). Truth lives in ``data/ingest/<id>/record.json``;
``COMPONENTS.md`` is a projection rendered by :func:`render_components_md`.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from . import crossverify


class Stage(StrEnum):
    """Factory stages, in pipeline order."""

    DISCOVERED = "discovered"
    EXTRACTED = "extracted"
    CROSS_VERIFIED = "cross_verified"
    SYMBOL_DONE = "symbol_done"
    FOOTPRINT_RESOLVED = "footprint_resolved"
    SOURCING_LINKED = "sourcing_linked"
    VALIDATED = "validated"
    APPROVED = "approved"


STAGE_ORDER: tuple[Stage, ...] = tuple(Stage)

Clock = Callable[[], str]


def utc_now() -> str:
    """Default clock: UTC ISO-8601 to the second (injectable in tests)."""
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass(frozen=True)
class GateResult:
    ok: bool
    detail: str = ""


@dataclass
class StageState:
    """Persisted outcome of one stage's gate."""

    status: str = "pending"        # "pending" | "passed" | "failed"
    gate_output: str = ""
    timestamp: str = ""            # stamped from the injected clock on change


GateFn = Callable[["ComponentRecord", dict], GateResult]

_GATES: dict[Stage, GateFn] = {}


def register_gate(stage: Stage) -> Callable[[GateFn], GateFn]:
    """Register (or override) the gate callable for a stage."""
    def deco(fn: GateFn) -> GateFn:
        _GATES[stage] = fn
        return fn
    return deco


def gate_for(stage: Stage) -> GateFn:
    return _GATES[stage]


@dataclass
class ComponentRecord:
    """One component's factory state; persists to <root>/<id>/record.json."""

    id: str
    vendor: str = ""
    kind: str = ""                 # "module" | "soc"
    meta: dict = field(default_factory=dict)
    stages: dict[Stage, StageState] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for s in STAGE_ORDER:
            self.stages.setdefault(s, StageState())

    # ── persistence ─────────────────────────────────────────────────────────

    @staticmethod
    def path_for(root: Path, comp_id: str) -> Path:
        return root / comp_id / "record.json"

    def record_dir(self, root: Path) -> Path:
        return root / self.id

    def save(self, root: Path) -> Path:
        path = self.path_for(root, self.id)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "id": self.id,
            "vendor": self.vendor,
            "kind": self.kind,
            "meta": self.meta,
            "stages": {str(s): asdict(st) for s, st in self.stages.items()},
        }
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        return path

    @classmethod
    def load(cls, root: Path, comp_id: str) -> ComponentRecord:
        payload = json.loads(cls.path_for(root, comp_id).read_text())
        stages = {
            Stage(name): StageState(**st)
            for name, st in payload.get("stages", {}).items()
        }
        return cls(id=payload["id"], vendor=payload.get("vendor", ""),
                   kind=payload.get("kind", ""), meta=payload.get("meta", {}),
                   stages=stages)

    # ── stage queries ───────────────────────────────────────────────────────

    @property
    def stage(self) -> Stage:
        """Longest consecutive run of passed gates from the start."""
        current = STAGE_ORDER[0]
        for s in STAGE_ORDER:
            if self.stages[s].status != "passed":
                break
            current = s
        return current

    def next_stage(self) -> Stage | None:
        if self.stages[STAGE_ORDER[0]].status != "passed":
            return STAGE_ORDER[0]
        idx = STAGE_ORDER.index(self.stage)
        return STAGE_ORDER[idx + 1] if idx + 1 < len(STAGE_ORDER) else None

    def blocked_on(self) -> str:
        """Gate output of the first failed stage, or empty string."""
        for s in STAGE_ORDER:
            if self.stages[s].status == "failed":
                return self.stages[s].gate_output
        return ""

    def updated(self) -> str:
        return max((st.timestamp for st in self.stages.values()), default="")

    # ── gate execution ─────────────────────────────────────────────────────

    def run_gate(self, stage: Stage, ctx: dict | None = None,
                 clock: Clock = utc_now) -> GateResult:
        """Run one stage's gate and persist the outcome in-place.

        The timestamp is stamped from the injected clock only when the
        outcome *changes*, so repeated recomputes are byte-stable.
        """
        res = _GATES[stage](self, ctx or {})
        st = self.stages[stage]
        status = "passed" if res.ok else "failed"
        if st.status != status or st.gate_output != res.detail:
            st.status = status
            st.gate_output = res.detail
            st.timestamp = clock()
        return res

    def advance(self, ctx: dict | None = None,
                clock: Clock = utc_now) -> GateResult:
        """Attempt exactly one stage transition (idempotent on failure)."""
        nxt = self.next_stage()
        if nxt is None:
            return GateResult(True, "already approved")
        return self.run_gate(nxt, ctx, clock)

    def recompute(self, ctx: dict | None = None,
                  clock: Clock = utc_now) -> Stage:
        """Re-run gates in order, promoting while ok; stop at first failure.

        A previously-passed gate that re-fails demotes the record (its
        later 'passed' states no longer count toward :attr:`stage`).
        """
        for s in STAGE_ORDER:
            if not self.run_gate(s, ctx, clock).ok:
                break
        return self.stage


# ── default gates ───────────────────────────────────────────────────────────────
# factory.py may override any of these via register_gate; defaults are
# deterministic checks over the record dir + meta fields.

def _record_dir(record: ComponentRecord, ctx: dict) -> Path | None:
    root = ctx.get("root")
    return Path(root) / record.id if root else None


@register_gate(Stage.DISCOVERED)
def _gate_discovered(record: ComponentRecord, ctx: dict) -> GateResult:
    missing = [f for f in ("id", "vendor", "kind") if not getattr(record, f)]
    if missing:
        return GateResult(False, f"record missing fields: {missing}")
    return GateResult(True, "record complete")


@register_gate(Stage.EXTRACTED)
def _gate_extracted(record: ComponentRecord, ctx: dict) -> GateResult:
    d = _record_dir(record, ctx)
    if d is None:
        return GateResult(False, "no ingest root in ctx")
    path = d / "extracted.json"
    if not path.is_file():
        return GateResult(False, "extracted.json missing")
    try:
        pins = json.loads(path.read_text()).get("pins", [])
    except json.JSONDecodeError as e:
        return GateResult(False, f"extracted.json unreadable: {e}")
    if not pins:
        return GateResult(False, "extracted.json has no pins")
    return GateResult(True, f"{len(pins)} pins extracted")


@register_gate(Stage.CROSS_VERIFIED)
def _gate_cross_verified(record: ComponentRecord, ctx: dict) -> GateResult:
    d = _record_dir(record, ctx)
    if d is None:
        return GateResult(False, "no ingest root in ctx")
    path = d / "evidence.json"
    if not path.is_file():
        return GateResult(False, "evidence.json missing")
    summary = crossverify.load_evidence(path).summary()
    if summary["conflicts"]:
        return GateResult(False, f"{summary['conflicts']} unresolved conflicts")
    return GateResult(True, f"{summary['claims']} claims, 0 conflicts"
                            f" ({summary['waived']} waived)")


@register_gate(Stage.SYMBOL_DONE)
def _gate_symbol_done(record: ComponentRecord, ctx: dict) -> GateResult:
    d = _record_dir(record, ctx)
    if d is None:
        return GateResult(False, "no ingest root in ctx")
    path = d / f"{record.id}.kicad_sym"
    if not path.is_file() or not path.stat().st_size:
        return GateResult(False, f"{path.name} missing or empty")
    return GateResult(True, path.name)


@register_gate(Stage.FOOTPRINT_RESOLVED)
def _gate_footprint(record: ComponentRecord, ctx: dict) -> GateResult:
    fp = record.meta.get("footprint", "")
    if not fp:
        return GateResult(False, "meta.footprint unset")
    return GateResult(True, fp)


@register_gate(Stage.SOURCING_LINKED)
def _gate_sourcing(record: ComponentRecord, ctx: dict) -> GateResult:
    lcsc = record.meta.get("lcsc", "")
    if not lcsc:
        return GateResult(False, "meta.lcsc unset")
    return GateResult(True, lcsc)


@register_gate(Stage.VALIDATED)
def _gate_validated(record: ComponentRecord, ctx: dict) -> GateResult:
    erc = record.meta.get("erc_errors")
    if erc is None:
        return GateResult(False, "meta.erc_errors unset (validation not run)")
    if erc != 0:
        return GateResult(False, f"ERC reported {erc} errors")
    return GateResult(True, "import + ERC 0")


@register_gate(Stage.APPROVED)
def _gate_approved(record: ComponentRecord, ctx: dict) -> GateResult:
    who = record.meta.get("approved_by", "")
    if not who:
        return GateResult(False, "awaiting human approval")
    return GateResult(True, f"approved by {who}")


# ── fleet operations ──────────────────────────────────────────────────────────

def status_all(root: Path, ctx: dict | None = None,
               clock: Clock = utc_now) -> list[ComponentRecord]:
    """Load every record under root, recompute every gate, save, return.

    Deterministic: records sorted by id; unchanged outcomes keep their
    timestamps so repeated runs produce byte-identical files.
    """
    full_ctx = dict(ctx or {})
    full_ctx.setdefault("root", root)
    records: list[ComponentRecord] = []
    for rec_path in sorted(root.glob("*/record.json")):
        record = ComponentRecord.load(root, rec_path.parent.name)
        record.recompute(full_ctx, clock)
        record.save(root)
        records.append(record)
    return records


def _cell(text: str, limit: int = 60) -> str:
    text = text.replace("|", "\\|").replace("\n", " ")
    return text if len(text) <= limit else text[:limit - 1] + "…"


def render_components_md(records: list[ComponentRecord]) -> str:
    """Markdown projection of the fleet (written to COMPONENTS.md by callers)."""
    lines = [
        "# Components",
        "",
        "Generated projection of `data/ingest/*/record.json` — do not edit.",
        "",
        "| id | vendor | kind | stage | gate | blocked_on | updated |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in sorted(records, key=lambda r: r.id):
        nxt = r.next_stage()
        passed = STAGE_ORDER.index(r.stage) + (
            1 if r.stages[r.stage].status == "passed" else 0)
        gate = f"{passed}/{len(STAGE_ORDER)}" + (f" → {nxt}" if nxt else " ✓")
        lines.append(
            f"| {_cell(r.id)} | {_cell(r.vendor)} | {_cell(r.kind)} "
            f"| {r.stage} | {_cell(gate)} | {_cell(r.blocked_on())} "
            f"| {_cell(r.updated())} |")
    return "\n".join(lines) + "\n"
