"""Executor factory — selects backend based on environment and domain."""

import logging
from typing import Optional

from config.env import env_config
from src.services.executors.base import JobExecutor
from src.services.executors.docker_executor import DockerExecutor
from src.services.executors.kubernetes_executor import KubernetesExecutor

logger = logging.getLogger(__name__)


def get_executor(
    domain: str,
    *,
    network: Optional[str] = None,
    timeout: Optional[int] = None,
) -> JobExecutor:
    """Return the appropriate executor for the current environment and domain.

    Rules:
    - build:         Always DockerExecutor (build-service uses Docker in all envs)
    - validation:    DockerExecutor in development, KubernetesExecutor in staging/prod
    - manufacturing: Same as validation
    """
    is_dev = env_config.ENVIRONMENT == "development"

    if domain == "build":
        return DockerExecutor(
            network=network or "host",
            timeout=timeout or getattr(env_config, "BUILD_TIMEOUT_MINUTES", 45) * 60,
        )

    if domain in ("validation", "manufacturing"):
        if is_dev:
            return DockerExecutor(
                network=network or "host",
                timeout=timeout or getattr(env_config, "VALIDATION_TIMEOUT_MINUTES", 60) * 60,
            )
        return KubernetesExecutor()

    raise ValueError(f"Unknown executor domain: {domain!r}")
