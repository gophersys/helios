"""Flask application factory for the build service API."""

from flask import Flask
from flask_cors import CORS


def create_app(config=None):
    app = Flask(__name__)
    CORS(app)

    if config:
        app.config["BUILD_SERVICE_CONFIG"] = config

    from src.api.health import health_bp
    from src.api.workers import workers_bp
    from src.api.queue import queue_bp
    from src.api.metrics import metrics_bp
    from src.api.jobs import jobs_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(workers_bp, url_prefix="/workers")
    app.register_blueprint(queue_bp, url_prefix="/queue")
    app.register_blueprint(metrics_bp, url_prefix="/metrics")
    app.register_blueprint(jobs_bp, url_prefix="/jobs")

    return app
