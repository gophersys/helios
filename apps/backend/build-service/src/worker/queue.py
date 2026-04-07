"""JobQueue — in-memory priority queue for build job notifications.

Wraps Python's queue.PriorityQueue to provide a simple interface for
receiving push notifications from the HTTP-API and dequeuing the
highest-priority job for processing.
"""

from __future__ import annotations

import logging
import queue
import time
from dataclasses import dataclass, field
from typing import Optional

log = logging.getLogger("build-service")


@dataclass(order=True)
class _QueueItem:
    """Priority queue item. Lower priority number = higher priority (min-heap)."""
    # Negate priority so highest priority value dequeues first
    sort_key: int
    timestamp: float = field(compare=True)
    job_id: str = field(compare=False)


class JobQueue:
    """Thread-safe priority queue for job notifications.

    The HTTP-API pushes notifications here via POST /jobs/notify.
    The worker loop dequeues the highest-priority job.
    """

    def __init__(self):
        self._queue: queue.PriorityQueue[_QueueItem] = queue.PriorityQueue()
        self._seen: set = set()  # Deduplicate notifications

    def enqueue(self, job_id: str, priority: int = 50):
        """Add a job notification to the queue.

        Higher priority number = dequeued first (e.g., manual=100 before webhook=50).
        Duplicate job_ids are silently dropped.
        """
        if job_id in self._seen:
            log.debug("Duplicate notification for %s, skipping", job_id[:8])
            return

        self._seen.add(job_id)
        # Negate priority so PriorityQueue (min-heap) dequeues highest first
        item = _QueueItem(sort_key=-priority, timestamp=time.time(), job_id=job_id)
        self._queue.put(item)
        log.info("Job notification queued: %s (priority=%d, depth=%d)",
                 job_id[:8], priority, self._queue.qsize())

    def dequeue(self, timeout: float = 60.0) -> Optional[str]:
        """Wait for and return the highest-priority job_id.

        Returns None on timeout (no notifications received).
        """
        try:
            item = self._queue.get(timeout=timeout)
            self._seen.discard(item.job_id)
            return item.job_id
        except queue.Empty:
            return None

    def clear_seen(self, job_id: str):
        """Remove a job_id from the seen set (after processing completes)."""
        self._seen.discard(job_id)

    @property
    def depth(self) -> int:
        return self._queue.qsize()

    @property
    def is_empty(self) -> bool:
        return self._queue.empty()
