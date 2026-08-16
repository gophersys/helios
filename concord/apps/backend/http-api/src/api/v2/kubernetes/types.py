from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class ScaleDeploymentRequest:
    """Validated input for scaling a Deployment to a specific replica count."""

    replicas: int

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["ScaleDeploymentRequest"], Optional[str]]:
        """Parse and validate replica count from a JSON request body.

        Args:
            data: Parsed JSON dict from the request body.

        Returns:
            Tuple of (ScaleDeploymentRequest, None) on success, or (None, error_message) on failure.
        """
        if not data:
            return None, "Request body must contain JSON data"
        if "replicas" not in data:
            return None, "Missing 'replicas' field"
        replicas = data["replicas"]
        if not isinstance(replicas, int) or replicas < 0:
            return None, "'replicas' must be a non-negative integer"
        if replicas > 100:
            return None, "'replicas' cannot exceed 100"
        return cls(replicas=replicas), None


@dataclass
class ApplyResourceYamlRequest:
    """Validated input for applying a Kubernetes resource from a YAML string."""

    yaml: str

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["ApplyResourceYamlRequest"], Optional[str]]:
        """Parse and validate a YAML string from a JSON request body.

        Args:
            data: Parsed JSON dict from the request body.

        Returns:
            Tuple of (ApplyResourceYamlRequest, None) on success, or (None, error_message) on failure.
        """
        if not data:
            return None, "Request body must contain JSON data"
        if "yaml" not in data:
            return None, "Missing 'yaml' field"
        yaml_str = data.get("yaml", "")
        if not isinstance(yaml_str, str) or len(yaml_str) > 100_000:
            return None, "YAML body must be a string under 100KB"
        return cls(yaml=yaml_str), None
