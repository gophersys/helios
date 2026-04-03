"""Build Service — independent firmware build execution service.

Starts a Flask API for visibility/management and a worker loop
that polls the Concord API for build jobs.
"""
import signal
import sys
import threading
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
log = logging.getLogger("build-service")


def _setup_ssh_key(config):
    """Decode base64 SSH key to file if provided via env var."""
    import base64
    from pathlib import Path

    if config.bitbucket_ssh_key:
        ssh_dir = Path(config.ssh_key_path).parent
        ssh_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        key_data = base64.b64decode(config.bitbucket_ssh_key)
        key_path = Path(config.ssh_key_path)
        key_path.write_bytes(key_data)
        key_path.chmod(0o600)
        log.info("SSH key written to %s (%d bytes)", config.ssh_key_path, len(key_data))
    elif not Path(config.ssh_key_path).exists():
        log.warning("No SSH key available — git clone will fail")


def main():
    from src.config import BuildServiceConfig
    from src.db.client import init_db, close_db
    from src.clients.concord import ConcordClient
    from src.worker.loop import BuildWorkerLoop

    config = BuildServiceConfig.from_env()
    log.info("Build Service starting — worker=%s, mode=%s", config.worker_id, config.builder_mode)
    log.info("Environment: %s, Worker: %s, Mode: %s, Port: %d",
             config.environment, config.worker_id, config.builder_mode, config.service_port)

    # Setup SSH key from base64 env var
    _setup_ssh_key(config)

    # Initialize local database
    try:
        init_db()
        log.info("Local database connected")
    except Exception as e:
        log.warning("Local database unavailable (running without local state): %s", e)

    # Create Concord API client
    client = ConcordClient(config.api_url, config.api_key)

    # Start Flask API in background thread (if api module has create_app)
    api_thread = None
    try:
        from src.app import create_app
        app = create_app(config)
        api_thread = threading.Thread(
            target=lambda: app.run(host="0.0.0.0", port=config.service_port, use_reloader=False),
            daemon=True,
            name="api-server",
        )
        api_thread.start()
        log.info("API server started on :%d", config.service_port)
    except ImportError:
        log.info("No API module found, running worker-only mode")
    except Exception as e:
        log.warning("Failed to start API server: %s", e)

    # Setup graceful shutdown
    shutdown = threading.Event()

    def handle_signal(sig, frame):
        log.info("Received signal %s, shutting down...", sig)
        shutdown.set()

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    # Run worker loop (blocks until shutdown)
    worker = BuildWorkerLoop(config=config, client=client, shutdown_event=shutdown)
    try:
        worker.run()
    finally:
        close_db()
        log.info("Build Service stopped")


if __name__ == "__main__":
    main()
