"""Design: a named collection of component instances and their nets,
with definition-time lint (`check()`) that runs before any ERC."""

from __future__ import annotations

from .component import Component
from .model import ElectricalType, Issue, PinRole
from .net import Net


class Design:
    def __init__(self, name: str) -> None:
        if not name:
            raise ValueError("Design name must be non-empty")
        self.name = name
        self.components: list[Component] = []
        self._ref_counters: dict[str, int] = {}
        self._nets_by_name: dict[str, Net] = {}

    def add(self, *components: Component) -> Component | tuple[Component, ...]:
        """Register components, assigning sequential refs per prefix.

        Auto-assigned refs skip any ref already taken (including manually
        preset ones); duplicate refs are always rejected.
        """
        for comp in components:
            if comp in self.components:
                continue
            taken = {c.ref for c in self.components}
            if not comp.ref:
                prefix = comp.reference_prefix or "U"
                n = self._ref_counters.get(prefix, 0)
                while True:
                    n += 1
                    if f"{prefix}{n}" not in taken:
                        break
                self._ref_counters[prefix] = n
                comp.ref = f"{prefix}{n}"
            elif comp.ref in taken:
                raise ValueError(f"Duplicate ref {comp.ref!r} in design {self.name!r}")
            self.components.append(comp)
        return components[0] if len(components) == 1 else components

    def net(self, name: str, *, group: str | None = None) -> Net:
        """Get-or-create the design-registered net with this name.

        Using this instead of bare Net() guarantees one Net object per name
        within the design (bare Net() duplicates are still caught by check()).
        """
        existing = self._nets_by_name.get(name)
        if existing is not None:
            return existing
        n = Net(name, group=group)
        self._nets_by_name[name] = n
        return n

    @property
    def nets(self) -> list[Net]:
        """Distinct nets: design-registered ones plus any referenced by a
        registered pin, in first-seen order (so an empty design.net() is
        still visible to check())."""
        seen: dict[int, Net] = {id(n): n for n in self._nets_by_name.values()}
        for comp in self.components:
            for pin in comp.pins:
                if pin.net is not None and id(pin.net) not in seen:
                    seen[id(pin.net)] = pin.net
        return list(seen.values())

    def intended_netlist(self) -> dict[str, set[str]]:
        """net name → {"REF:pad", ...} — the ground truth the schematic
        emitters and kicad-cli netlist export are checked against.

        Same-named Net objects merge here (netlist semantics); check() still
        reports duplicate-net-name so the mistake is visible.
        """
        out: dict[str, set[str]] = {}
        for net in self.nets:
            out.setdefault(net.name, set()).update(
                f"{p.owner.ref}:{p.pad}" for p in net.pins
                if p.owner in self.components)
        return out

    # ── lint ────────────────────────────────────────────────────────────────

    def check(self) -> list[Issue]:
        """Definition-time lint. Errors mean the design is not emittable."""
        issues: list[Issue] = []
        net_names: dict[str, Net] = {}

        for net in self.nets:
            if net.name in net_names and net_names[net.name] is not net:
                issues.append(Issue("error", "duplicate-net-name",
                                    f"Two distinct Net objects named {net.name!r}",
                                    net=net.name))
            net_names.setdefault(net.name, net)
            design_pins = [p for p in net.pins if p.owner in self.components]
            if len(design_pins) < 2:
                issues.append(Issue("error", "single-pin-net",
                                    f"Net {net.name!r} has {len(design_pins)} pin(s)",
                                    net=net.name))
            outputs = [p for p in design_pins
                       if p.etype in (ElectricalType.OUTPUT, ElectricalType.POWER_OUT)]
            if len(outputs) > 1:
                refs = ", ".join(f"{p.owner.ref}.{p.name}" for p in outputs)
                issues.append(Issue("error", "output-conflict",
                                    f"Net {net.name!r} has multiple drivers: {refs}",
                                    net=net.name))

        for comp in self.components:
            if comp.footprint is None:
                issues.append(Issue("error", "missing-footprint",
                                    f"{comp.ref} ({comp.part_name}) has no footprint",
                                    ref=comp.ref))
            for pin in comp.pins:
                if pin.role is PinRole.NC:
                    if pin.net is not None:
                        issues.append(Issue("warning", "nc-connected",
                                            f"{comp.ref}.{pin.name} is NC but on "
                                            f"net {pin.net.name!r}", ref=comp.ref,
                                            net=pin.net.name))
                    continue
                if pin.net is None:
                    if pin.etype is ElectricalType.POWER_IN:
                        issues.append(Issue("error", "unconnected-power",
                                            f"{comp.ref}.{pin.name} (power_in, "
                                            f"pad {pin.pad}) is unconnected",
                                            ref=comp.ref))
                    elif pin.etype is ElectricalType.INPUT:
                        issues.append(Issue("warning", "floating-input",
                                            f"{comp.ref}.{pin.name} (input, pad "
                                            f"{pin.pad}) is floating", ref=comp.ref))
        return issues

    def check_ok(self) -> bool:
        return not any(i.is_error for i in self.check())

    def __repr__(self) -> str:
        return (f"Design({self.name!r}, components={len(self.components)}, "
                f"nets={len(self.nets)})")
