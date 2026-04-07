"""Tests for JobQueue — priority queue for build notifications."""

from __future__ import annotations

import threading
import time

import pytest

from src.worker.queue import JobQueue


class TestJobQueue:
    def test_enqueue_dequeue(self):
        """Basic enqueue/dequeue."""
        q = JobQueue()
        q.enqueue("job-1", priority=50)
        result = q.dequeue(timeout=1.0)
        assert result == "job-1"

    def test_priority_ordering(self):
        """Higher priority dequeues first."""
        q = JobQueue()
        q.enqueue("low", priority=25)
        q.enqueue("high", priority=100)
        q.enqueue("medium", priority=50)

        assert q.dequeue(timeout=1.0) == "high"
        assert q.dequeue(timeout=1.0) == "medium"
        assert q.dequeue(timeout=1.0) == "low"

    def test_same_priority_fifo(self):
        """Same priority → FIFO order."""
        q = JobQueue()
        q.enqueue("first", priority=50)
        time.sleep(0.01)  # Ensure different timestamps
        q.enqueue("second", priority=50)
        time.sleep(0.01)
        q.enqueue("third", priority=50)

        assert q.dequeue(timeout=1.0) == "first"
        assert q.dequeue(timeout=1.0) == "second"
        assert q.dequeue(timeout=1.0) == "third"

    def test_dequeue_timeout_returns_none(self):
        """Dequeue on empty queue returns None after timeout."""
        q = JobQueue()
        start = time.time()
        result = q.dequeue(timeout=0.1)
        elapsed = time.time() - start
        assert result is None
        assert elapsed >= 0.1

    def test_duplicate_suppression(self):
        """Same job_id enqueued twice → only one dequeue."""
        q = JobQueue()
        q.enqueue("job-1", priority=50)
        q.enqueue("job-1", priority=100)  # Duplicate, should be ignored

        assert q.depth == 1
        result = q.dequeue(timeout=1.0)
        assert result == "job-1"
        assert q.dequeue(timeout=0.1) is None  # Empty now

    def test_clear_seen_allows_requeue(self):
        """After clear_seen, the same job_id can be enqueued again."""
        q = JobQueue()
        q.enqueue("job-1", priority=50)
        q.dequeue(timeout=1.0)  # Consumes and removes from seen

        # Now re-enqueue should work (dequeue already cleared seen)
        q.enqueue("job-1", priority=50)
        assert q.dequeue(timeout=1.0) == "job-1"

    def test_depth_property(self):
        q = JobQueue()
        assert q.depth == 0
        assert q.is_empty

        q.enqueue("a", 50)
        q.enqueue("b", 50)
        assert q.depth == 2
        assert not q.is_empty

        q.dequeue(timeout=1.0)
        assert q.depth == 1

    def test_thread_safety(self):
        """Queue is safe for concurrent enqueue/dequeue."""
        q = JobQueue()
        results = []

        def producer():
            for i in range(100):
                q.enqueue(f"job-{i}", priority=i)

        def consumer():
            while len(results) < 100:
                r = q.dequeue(timeout=0.5)
                if r:
                    results.append(r)

        t1 = threading.Thread(target=producer)
        t2 = threading.Thread(target=consumer)
        t1.start()
        t2.start()
        t1.join()
        t2.join(timeout=10)

        assert len(results) == 100
        # Highest priority should come first
        assert results[0] == "job-99"
