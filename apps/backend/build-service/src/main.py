"""Build Service — independent firmware build execution service.

Starts a Flask API for visibility/management and a worker loop
that polls the Concord API for build jobs.
"""
import atexit
import signal
import sys
import threading

# Logger must initialize before any other imports that use logging
from corekinect.utils import Logger, print_banner

log = Logger(log_name="build-service")


def _setup_ssh_key(config):
    """Decode base64 SSH key to file if provided via env var.

    In K8s, the key is volume-mounted directly at SSH_KEY_PATH (read-only).
    The env var path is a fallback for Docker Compose / local dev.
    """
    import base64
    from pathlib import Path

    key_path = Path(config.ssh_key_path)

    # K8s volume mount: file or parent dir exists as read-only secret projection
    if key_path.exists():
        log.info(f"SSH key found at {key_path} (volume mount)")
        return
    if key_path.parent.exists() and key_path.parent.is_mount():
        log.info(f"SSH key mount at {key_path.parent} (waiting for secret projection)")
        return

    if config.bitbucket_ssh_key:
        try:
            ssh_dir = key_path.parent
            ssh_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
            key_data = base64.b64decode(config.bitbucket_ssh_key)
            key_path.write_bytes(key_data)
            key_path.chmod(0o600)
            log.info(f"SSH key written to {key_path} ({len(key_data)} bytes)")
        except OSError as e:
            log.warning(f"Cannot write SSH key to {key_path}: {e} — assuming read-only mount")
    else:
        log.warning("No SSH key available — git clone will fail")


def main():
    from src.config import BuildServiceConfig
    from src.clients.concord import ConcordClient
    from src.worker.loop import BuildWorkerLoop

    config = BuildServiceConfig.from_env()

    # ── Banner ──────────────────────────────────────────────────────────────
    print_banner(
        "concord-build-service",
        Port=str(config.service_port),
        Worker=config.worker_id,
        Mode=config.builder_mode,
    )

    # ── Logger ──────────────────────────────────────────────────────────────
    Logger.Config(
        logger_name="build-service",
        overall_log_level=20,  # INFO
        log_directory="logs",
        enable_log_color=True,
    )

    # ── SSH ──────────────────────────────────────────────────────────────────
    _setup_ssh_key(config)

    # ── Orphan container cleanup ─────────────────────────────────────────────
    # Kill any builder containers left behind from a previous instance
    # (e.g., pod was killed mid-build during a rolling update)
    if config.builder_mode == "docker":
        from src.worker.docker_runner import DockerBuildRunner
        DockerBuildRunner.cleanup_orphaned_containers()

    # ── API client ───────────────────────────────────────────────────────────
    client = ConcordClient(config.api_url, config.api_key)

    # ── Job queue (push-based delivery) ──────────────────────────────────────
    from src.worker.queue import JobQueue
    job_queue = JobQueue()

    # ── Flask API (background thread) ────────────────────────────────────────
    try:
        from src.app import create_app
        from src.api.jobs import set_job_queue
        app = create_app(config)
        set_job_queue(job_queue)
        api_thread = threading.Thread(
            target=lambda: app.run(host="0.0.0.0", port=config.service_port, use_reloader=False),
            daemon=True,
            name="api-server",
        )
        api_thread.start()
        log.info(f"API server started on :{config.service_port}")
    except ImportError as e:
        log.warning(f"Flask API not available (missing dependency?): {e}")
    except Exception as e:
        log.warning(f"Failed to start API server: {e}")

    # ── Graceful shutdown ────────────────────────────────────────────────────
    shutdown = threading.Event()

    def handle_signal(signum, _frame):
        name = signal.Signals(signum).name
        log.info(f"Received {name}, shutting down gracefully...")
        shutdown.set()

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    # ── Worker loop (blocks until shutdown) ───────────────────────────────────
    worker = BuildWorkerLoop(config=config, client=client, shutdown_event=shutdown, job_queue=job_queue)
    try:
        worker.run()
    except Exception:
        log.error("Worker loop crashed", exc_info=True)
        sys.exit(1)
    finally:
        # Clean up any running builder container after the worker loop exits.
        # This runs AFTER the current build finishes (worker.run() blocks until
        # process_job completes), so it only kills containers from abnormal exits.
        if worker.docker_runner:
            worker.docker_runner.cleanup()
        log.info("Build Service stopped")


if __name__ == "__main__":
    main()
