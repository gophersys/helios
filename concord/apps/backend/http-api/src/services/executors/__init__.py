"""Unified job executor interface for Concord.

Abstracts the difference between spawning Docker containers (dev + builds)
and Kubernetes Jobs (staging/production validation).
"""

from src.services.executors.base import ExecutorResult, JobExecutor
from src.services.executors.factory import get_executor

__all__ = ["ExecutorResult", "JobExecutor", "get_executor"]
