# Standard includes
import atexit
import logging
import os
import signal
import traceback
from typing import Optional
import eventlet

eventlet.monkey_patch(socket=True, select=False, time=False, os=False, thread=False)

from api.v2.router import register_v2_routes

# App includes
from config import env_config

# Corekinect includes
from corekinect.utils import EnvConfig, Logger, print_banner

# 3rd party includes
from flask import Flask, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO
from src.services.database.prisma import init_postgres_client, get_db_client
from src.services.kubernetes.client import init_kubernetes_client
from src.services.log.logger import init_logger
from src.services.scheduler import start_scheduler
from src.services.storage.client import init_storage_client, close_storage_client
from src.services.mtib_observability import init_observability_service, get_observability_service

# -------------------------------------------------
#                                            Server
# -------------------------------------------------
server = Flask(__name__)
server.json.sort_keys = False
server.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100 MB upload limit

_cors_origins = [o.strip() for o in env_config.CORS_ORIGINS.split(",") if o.strip()]
CORS(server, origins=_cors_origins)
socketio = SocketIO(
    server,
    debug=(env_config.ENVIRONMENT == "development"),
    cors_allowed_origins=_cors_origins,
    async_mode="eventlet",
    logger=(env_config.ENVIRONMENT == "development"),
)


@server.after_request
def set_security_headers(response):
    """Add security headers to every response."""
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if env_config.ENVIRONMENT != "development":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


# -------------------------------------------------
#                                    Health / Ready
# -------------------------------------------------
@server.route("/health")
def health():
    """Liveness probe endpoint."""
    return jsonify({"status": "ok", "service": "http-api"}), 200


@server.route("/ready")
def ready():
    """Readiness probe endpoint that verifies database connectivity."""
    try:
        db = get_db_client()
        db.user.count()
        return jsonify({"status": "ready", "service": "http-api"}), 200
    except Exception:
        return jsonify({"status": "not_ready", "service": "http-api"}), 503


# -------------------------------------------------
#                                  Graceful Shutdown
# -------------------------------------------------
_shutdown_initiated = False


def graceful_shutdown(signum=None, frame=None):
    """Cleanly close all external service connections on shutdown."""
    global _shutdown_initiated
    if _shutdown_initiated:
        return
    _shutdown_initiated = True

    sig_name = signal.Signals(signum).name if signum else "atexit"
    logging.getLogger("server").info("Graceful shutdown initiated (%s)", sig_name)

    # 0. Signal background scheduler threads to stop BEFORE closing DB.
    # Daemon threads poll the DB — if we close DB first, they log errors.
    try:
        from src.services.queue_scheduler import stop_scheduler
        stop_scheduler()
    except Exception:
        pass

    # Give in-flight scheduler ticks 2s to finish their current DB query
    import time
    time.sleep(2)

    # 1. Stop MTIB observability polling and gRPC channels
    try:
        obs_service = get_observability_service()
        if obs_service is not None:
            obs_service.stop()
            logging.getLogger("server").info("MTIB observability service stopped")
    except Exception as e:
        logging.getLogger("server").warning("Error stopping observability service: %s", e)

    # 2. Close Prisma database connection
    try:
        from src.services.database.prisma import get_db_client

        client = get_db_client()
        if client is not None:
            client.disconnect()
            logging.getLogger("server").info("Database connection closed")
    except Exception as e:
        logging.getLogger("server").warning("Error closing database connection: %s", e)

    # 3. Close MinIO storage client (clear urllib3 connection pool)
    try:
        close_storage_client()
        logging.getLogger("server").info("Storage client closed")
    except Exception as e:
        logging.getLogger("server").warning("Error closing storage client: %s", e)

    # 5. Close Kubernetes API client
    try:
        from src.services.kubernetes.client import close_kubernetes_client

        close_kubernetes_client()
        logging.getLogger("server").info("Kubernetes client closed")
    except Exception as e:
        logging.getLogger("server").warning("Error closing Kubernetes client: %s", e)

    logging.getLogger("server").info("Graceful shutdown complete")


signal.signal(signal.SIGTERM, graceful_shutdown)
signal.signal(signal.SIGINT, graceful_shutdown)
atexit.register(graceful_shutdown)


# -------------------------------------------------
#                                             Entry
# -------------------------------------------------
if __name__ == "__main__":
    logger: Optional[Logger] = None

    try:
        # Initialize the logger
        log_config = Logger.Config(
            logger_name="server",
            log_directory=env_config.LOG_PATH,
            overall_log_level=env_config.LOG_LEVEL,
            console_log_level=env_config.LOG_LEVEL,
            file_log_level=logging.DEBUG,  # Always log everything to file
            enable_log_color=True,
        )
        logger = Logger(log_config)

        # Initialize the storage client
        init_storage_client()

        # Initialize the database client
        init_postgres_client()

        # Initialize the Kubernetes client
        init_kubernetes_client()

        # Initialize the logger
        init_logger(log_config)

        # Start background scheduler (audit log cleanup)
        start_scheduler()

        # Start observability polling service
        init_observability_service(poll_interval_s=5)

        # Initialize CkBoards service (board definition discovery)
        # Must run synchronously — eventlet monkey-patching breaks subprocess in threads.
        # Best-effort: CkBoards depends on external git access (may be firewalled).
        # The platform works without it — board auto-discovery is a convenience feature.
        try:
            from api.v2.products.board_discovery import init_ck_boards_service
            init_ck_boards_service(env_config)
            logger.info("CkBoards service ready")
        except Exception as e:
            logger.warning("CkBoards service unavailable (board discovery disabled): %s", e)

        # Routes
        register_v2_routes(logger, server, socketio)

        # Print startup banner with build metadata
        print_banner(
            "concord-http-api",
            logger=logger,
            Port=str(env_config.SERVER_PORT),
        )

        # Start the server
        socketio.run(
            app=server,
            host="0.0.0.0",
            port=env_config.SERVER_PORT,
            debug=False,
            log_output=True,
            log=logger,
        )

    except Exception as e:
        if logger:
            # Print the entire traceback
            logger.error(f"Failed to start server: {e}")
        else:
            print(f"Failed to start server: {e}\n{traceback.format_exc()}")
