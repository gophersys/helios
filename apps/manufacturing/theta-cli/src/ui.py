from typing import Dict, List, Optional

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


# Step status symbols
PASS = Text("\u2713", style="bold green")
FAIL = Text("\u2717", style="bold red")
RUNNING = Text("\u25cf", style="bold yellow")
PENDING = Text("-", style="dim")
SKIPPED = Text("-", style="dim")


class DeviceStatus:
    def __init__(self, slot: int, hostname: str, snr: str):
        self.slot = slot
        self.hostname = hostname
        self.snr = snr
        self.electrical: Optional[bool] = None  # None=pending, True=pass, False=fail
        self.flash: Optional[bool] = None
        self.post: Optional[bool] = None
        self.active = True
        self.error: Optional[str] = None
        self.current_step: Optional[str] = None

    @property
    def status_text(self) -> Text:
        if self.error:
            return Text("FAIL", style="bold red")
        if not self.active and self.error is None:
            return Text("SKIPPED", style="dim")
        if self.post is True:
            return Text("PASS", style="bold green")
        if self.current_step:
            return Text(self.current_step, style="yellow")
        return Text("IDLE", style="dim")


class ManufacturingUI:
    def __init__(self, mode: str):
        self.console = Console()
        self.mode = mode
        self.devices: Dict[str, DeviceStatus] = {}
        self.errors: List[str] = []
        self.live: Optional[Live] = None
        self.scan_count = 0

    def set_devices(self, snr_map: Dict[str, str]):
        """Initialize device tracking from validate_snr response."""
        self.devices.clear()
        self.errors.clear()
        for i, (hostname, snr) in enumerate(snr_map.items(), start=1):
            self.devices[hostname] = DeviceStatus(slot=i, hostname=hostname, snr=snr)

    def _build_table(self) -> Table:
        table = Table(show_header=True, header_style="bold cyan", expand=True)
        table.add_column("Slot", justify="center", width=4)
        table.add_column("SNR", justify="center", width=6)
        table.add_column("Electrical", justify="center", width=10)
        table.add_column("Flash", justify="center", width=7)
        table.add_column("POST", justify="center", width=6)
        table.add_column("Status", justify="left", min_width=16)

        for dev in sorted(self.devices.values(), key=lambda d: d.slot):
            def step_icon(val, active, is_current):
                if not active and val is None:
                    return SKIPPED
                if is_current:
                    return RUNNING
                if val is True:
                    return PASS
                if val is False:
                    return FAIL
                return PENDING

            elec_current = dev.current_step and "Electrical" in dev.current_step
            flash_current = dev.current_step and "Flash" in dev.current_step
            post_current = dev.current_step and "POST" in dev.current_step

            table.add_row(
                str(dev.slot),
                dev.snr,
                step_icon(dev.electrical, dev.active, elec_current),
                step_icon(dev.flash, dev.active, flash_current),
                step_icon(dev.post, dev.active, post_current),
                dev.status_text,
            )

        return table

    def _build_display(self) -> Panel:
        table = self._build_table()

        error_lines = []
        for err in self.errors[-5:]:  # Show last 5 errors
            error_lines.append(Text(err, style="red"))

        content = table
        if error_lines:
            from rich.console import Group
            error_panel = Panel(
                Group(*error_lines),
                title="Errors",
                border_style="red",
                expand=True,
            )
            content = Group(table, error_panel)

        mode_label = "Panel" if self.mode == "panel" else "Singleton"
        return Panel(content, title=f"Theta Manufacturing - {mode_label}", border_style="blue")

    def start_live(self):
        self.live = Live(self._build_display(), console=self.console, refresh_per_second=4)
        self.live.start()

    def stop_live(self):
        if self.live:
            self.live.stop()
            self.live = None

    def refresh(self):
        if self.live:
            self.live.update(self._build_display())

    def mark_test_running(self, test_name: str, nodes: List[str]):
        for hostname in nodes:
            if hostname in self.devices:
                self.devices[hostname].current_step = test_name
        self.refresh()

    def mark_step_result(self, hostname: str, test_name: str, success: bool, error: Optional[str] = None):
        if hostname not in self.devices:
            return
        dev = self.devices[hostname]

        if "Electrical" in test_name:
            dev.electrical = success
        elif "Flash" in test_name:
            dev.flash = success
        elif "POST" in test_name:
            dev.post = success

        if not success:
            dev.active = False
            dev.current_step = None
            dev.error = error
            if error:
                self.errors.append(f"Slot {dev.slot} ({dev.snr}): {error}")
        else:
            dev.current_step = None

        self.refresh()

    def mark_test_done(self, test_name: str, nodes: List[str]):
        for hostname in nodes:
            if hostname in self.devices:
                dev = self.devices[hostname]
                if dev.active:
                    dev.current_step = None
        self.refresh()

    def print_summary(self):
        self.console.print()
        passed = sum(1 for d in self.devices.values() if d.post is True)
        failed = sum(1 for d in self.devices.values() if d.error is not None)
        total = len(self.devices)

        if failed == 0:
            self.console.print(f"  [bold green]ALL {total} DEVICES PASSED[/bold green]")
        else:
            self.console.print(f"  [green]{passed}/{total} passed[/green], [red]{failed}/{total} failed[/red]")
        self.console.print()
