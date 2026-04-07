"""Build notifier — pushes job notifications to the build service.

Fire-and-forget HTTP POST to the build service's /jobs/notify endpoint.
If the build service is unreachable, the notification is silently dropped —
the build service's fallback poll will pick it up within 60 seconds.
"""

import logging

import requests  # type: ignore[import-untyped]

from config import env_config

log = logging.getLogger(__name__)

# Short timeout — this is fire-and-forget, never block the API
_NOTIFY_TIMEOUT = 2


def notify_build_service(job_id: str, priority: int = 50):
    """Notify the build service that a new job is available.

    This is a best-effort push notification. If it fails, the build
    service will discover the job via its fallback poll.
    """
    build_service_url = env_config.BUILD_SERVICE_URL
    if not build_service_url:
        log.debug("BUILD_SERVICE_URL not configured, skipping notification")
        return

    url = f"{build_service_url}/jobs/notify"
    try:
        resp = requests.post(
            url,
            json={"jobId": job_id, "priority": priority},
            timeout=_NOTIFY_TIMEOUT,
        )
        if resp.status_code == 202:
            log.debug("Build service notified: job=%s priority=%d", job_id[:8], priority)
        else:
            log.warning("Build service notification returned %d: %s",
                        resp.status_code, resp.text[:200])
    except requests.RequestException as e:
        log.warning("Build service notification failed (job=%s): %s — "
                    "will be picked up by fallback poll", job_id[:8], e)
