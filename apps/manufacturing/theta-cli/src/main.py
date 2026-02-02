import argparse
import os
import signal
import sys
import threading
from typing import Dict, List

from dotenv import load_dotenv
from rich.console import Console

from .api import ConcordAPI
from .ui import ManufacturingUI

console = Console()

# Test names in execution order
TESTS = [
    ("Electrical", "ELECTRICAL_TEST_UUID"),
    ("Flash", "FW_FLASH_TEST_UUID"),
    ("POST", "POST_TEST_UUID"),
]


def run_test_sequence(api: ConcordAPI, ui: ManufacturingUI, snr_map: Dict[str, str]):
    """Run electrical -> flash -> post on all devices, auto-continuing on failure."""

    # Build config with SNR mapping (nodes use hostnames as keys)
    config = {"snrs": snr_map}

    active_nodes = list(snr_map.keys())

    for test_name, uuid_env in TESTS:
        if not active_nodes:
            break

        test_uuid = os.environ.get(uuid_env)
        if not test_uuid:
            ui.errors.append(f"Missing env var: {uuid_env}")
            ui.refresh()
            break

        ui.mark_test_running(test_name, active_nodes)

        # Track results for this test
        test_failed_nodes = []
        test_error = None
        step_results_by_node: Dict[str, bool] = {n: True for n in active_nodes}

        lock = threading.Lock()

        def on_step_result(sequence, results):
            with lock:
                for r in results:
                    node = r.get("node", "")
                    success = r.get("success", False)
                    error = r.get("error") or r.get("reason")
                    if not success and node in step_results_by_node:
                        step_results_by_node[node] = False
                        test_failed_nodes.append(node)
                        ui.mark_step_result(node, test_name, False, error)
                ui.refresh()

        def on_done(results):
            pass  # Final results handled after done_event

        def on_error(error):
            nonlocal test_error
            test_error = error

        try:
            execution_id, done_event = api.exec_test(
                test_uuid=test_uuid,
                nodes=active_nodes,
                config=config,
                on_step_result=on_step_result,
                on_done=on_done,
                on_error=on_error,
            )
        except RuntimeError as e:
            ui.errors.append(f"{test_name}: {str(e)}")
            ui.refresh()
            break

        # Wait for test to complete
        done_event.wait(timeout=600)

        if test_error:
            ui.errors.append(f"{test_name}: {test_error}")
            ui.refresh()

        # Mark passing devices
        with lock:
            for node in active_nodes:
                if node not in test_failed_nodes:
                    ui.mark_step_result(node, test_name, True)

        # Remove failed nodes from next test
        active_nodes = [n for n in active_nodes if n not in test_failed_nodes]
        ui.mark_test_done(test_name, active_nodes)


def main():
    parser = argparse.ArgumentParser(description="Theta Manufacturing CLI")
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument("--panel", action="store_true", help="Panel mode (4 devices)")
    mode_group.add_argument("--singleton", action="store_true", help="Singleton mode (1 device)")
    args = parser.parse_args()

    load_dotenv()

    api_url = os.environ.get("API_URL")
    cluster_uuid = os.environ.get("CLUSTER_UUID")

    if not api_url or not cluster_uuid:
        console.print("[red]Error: API_URL and CLUSTER_UUID must be set in .env[/red]")
        sys.exit(1)

    api = ConcordAPI(api_url=api_url, cluster_uuid=cluster_uuid)
    mode = "panel" if args.panel else "singleton"
    ui = ManufacturingUI(mode=mode)

    # Graceful shutdown
    def signal_handler(sig, frame):
        ui.stop_live()
        console.print("\n[dim]Shutting down...[/dim]")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    console.print(Panel_header(mode))

    while True:
        try:
            console.print()
            snr = console.input("[bold cyan]Scan serial number:[/bold cyan] ").strip()
            if not snr:
                continue

            # Validate SNR
            console.print(f"[dim]Validating {snr}...[/dim]")
            try:
                snr_map = api.validate_snr(snr, singleton=args.singleton)
            except RuntimeError as e:
                console.print(f"[red]Validation failed: {e}[/red]")
                continue

            # Setup UI for this panel/device
            ui.set_devices(snr_map)

            device_count = len(snr_map)
            snr_list = ", ".join(snr_map.values())
            console.print(f"[green]Valid - {device_count} device(s): {snr_list}[/green]")
            console.print()

            # Run manufacturing with live display
            ui.start_live()
            run_test_sequence(api, ui, snr_map)
            ui.stop_live()

            # Summary
            ui.print_summary()

        except EOFError:
            break
        except KeyboardInterrupt:
            break

    ui.stop_live()
    console.print("\n[dim]Done.[/dim]")


def Panel_header(mode: str) -> str:
    mode_label = "PANEL (4-device)" if mode == "panel" else "SINGLETON (1-device)"
    return (
        f"\n[bold blue]Theta Manufacturing CLI[/bold blue] - {mode_label}\n"
        f"[dim]Scan a serial number to begin. Ctrl+C to exit.[/dim]\n"
    )


if __name__ == "__main__":
    main()
