"""K8s job creation for validation runs (TestRun/RunTarget models).

Renders the validation_job.yaml template and submits to K8s.
Supports multi-slot fixtures via extra_env injection.
"""

import hashlib
import os
import re
from typing import Dict, Optional
import yaml  # type: ignore[import-untyped]
from config.env import env_config

from src.services.kubernetes.client import get_batch_v1_api
from src.services.kubernetes.runner_dispatch import (
    framework_env_var,
    normalize_framework,
    runner_command_for_framework,
)
from src.services.kubernetes.runner_env import build_common_runner_env
from src.services.log.logger import get_logger


# -------------------------------------------------
#                                           Helpers
# -------------------------------------------------


def create_k8s_job_name(product: str, job_id: str, firmware_version: Optional[str] = None) -> str:
    """Create a Kubernetes-compliant job name (max 63 chars, RFC 1123 compliant)"""
    # Ensure product name is lowercase and valid for K8s
    product_clean = re.sub(r"[^a-z0-9-]", "-", product.lower()).strip("-")
    product_clean = re.sub(r"-+", "-", product_clean)

    # Normalize firmware version: replace dots/underscores with hyphens for K8s compatibility
    version_suffix = ""
    if firmware_version:
        # Replace dots and underscores with hyphens, remove any invalid characters
        version_clean = re.sub(r"[^a-zA-Z0-9._-]", "", firmware_version)
        version_clean = version_clean.replace(".", "-").replace("_", "-")
        # Remove consecutive hyphens
        version_clean = re.sub(r"-+", "-", version_clean).strip("-")
        if version_clean:
            version_suffix = f"-{version_clean}"

    # Split FIRST to extract test name before replacing underscores
    # Format: uuid-testname (where testname may have underscores)
    parts = job_id.rsplit("-", 1)
    if len(parts) == 2 and len(parts[0]) > 20:  # Likely UUID-testname format
        uuid_part = parts[0]
        test_name = parts[1]  # Keep original test name with underscores for now

        # Hash UUID to first 8 chars to keep it short
        uuid_hash = hashlib.md5(uuid_part.encode()).hexdigest()[:8]  # nosec B324

        # Now replace underscores in test name with hyphens
        test_name_clean = test_name.replace("_", "-")

        # Combine: hash-testname-version
        job_id_clean = f"{uuid_hash}-{test_name_clean}{version_suffix}"
    else:
        # No test name, just hash the whole thing
        job_id_clean = job_id.replace("_", "-").replace("/", "-")
        if len(job_id_clean) > 40:
            job_id_clean = hashlib.md5(job_id_clean.encode()).hexdigest()[:12]  # nosec B324
        job_id_clean = f"{job_id_clean}{version_suffix}"

    # Remove any trailing hyphens and ensure it ends with alphanumeric
    job_id_clean = job_id_clean.rstrip("-")
    if not job_id_clean[-1].isalnum():
        job_id_clean += "0"

    # Create job name following RFC 1123 subdomain rules (max 63 chars)
    # Format: {product}-val-{short_id}-{version}
    job_name = f"{product_clean}-val-{job_id_clean}"

    # Truncate if still too long (K8s limit is 63 chars)
    if len(job_name) > 63:
        # Keep product and "val", truncate the rest (including version if needed)
        max_id_len = 63 - len(product_clean) - 5  # 5 for "-val-"
        if max_id_len > 0:
            job_id_clean = job_id_clean[:max_id_len].rstrip("-")
            job_name = f"{product_clean}-val-{job_id_clean}"
        else:
            # Product name itself is too long, just use hash
            job_name = f"val-{hashlib.md5(job_id.encode()).hexdigest()[:12]}"  # nosec B324

    # Ensure it starts and ends with alphanumeric characters
    if not job_name[0].isalnum():
        job_name = f"j{job_name}"
    if not job_name[-1].isalnum():
        job_name = f"{job_name}0"

    return job_name[:63]  # Final safety check



def create_kubernetes_job(
    product: str,
    job_id: str,
    firmware_path: str,  # MinIO path (prefer build_run_id when available)
    test_type: str,
    required_features: Optional[Dict[str, str]] = None,
    firmware_version: Optional[str] = None,
    run_id: Optional[str] = None,
    api_key: Optional[str] = None,
    api_url: Optional[str] = None,
    # Fixture-related params (from scheduler or trigger)
    mtib_address: Optional[str] = None,
    fixture_id: Optional[str] = None,
    device_id: Optional[str] = None,
    device_snr: Optional[str] = None,
    # Stage 4: Build-run-based firmware (preferred)
    build_run_id: Optional[str] = None,
    # Product slug for catalog API lookup
    product_slug: Optional[str] = None,
    # Device identity (from fixture slot)
    device_imei: Optional[str] = None,
    device_iccids: Optional[str] = None,
    # Validation stage and image tag
    stage: str = "fuota",
    image_tag: Optional[str] = None,
    # Test package version (downloaded by generic runner at startup)
    test_package_version: Optional[str] = None,
    # Test filtering
    pytest_filter: Optional[str] = None,
    fuota_label: Optional[str] = None,
    # Stage config: test directory and marker from ProductStageConfig
    test_directory: Optional[str] = None,
    test_marker: Optional[str] = None,
    # Multi-slot: additional env vars injected into the job YAML
    extra_env: Optional[Dict[str, str]] = None,
    # Multi-slot: comma-separated MTIB hosts (alongside single mtib_address)
    mtib_hosts: Optional[str] = None,
    # Test framework dispatch — resolved from the TestPackage's framework
    # column. ``None`` collapses to PYTEST (back-compat).
    framework: Optional[str] = None,
) -> Optional[str]:
    """
    Create a new kubernetes job with the new firmware file environment variables.
    The job will be scheduled automatically by Kubernetes on any available node
    that matches the nodeSelector and tolerations, with pod anti-affinity ensuring
    only one validation job per node.

    Accepts an optional extra_env dict whose key/value pairs are injected as
    additional env vars into the rendered job YAML. This supports multi-slot
    fields (MTIB_HOSTS, SLOT_SNRS, SLOT_DEVICE_IDS, CONCORD_TARGET_ID, etc.)
    without modifying the template.
    """
    logger = get_logger()
    logger.info(f"Creating kubernetes job for product: {product}, job_id: {job_id} (will be scheduled automatically)")

    try:
        # Load the job template
        template_path = os.path.join(env_config.ASSETS_FOLDER, "templates", "validation_job.yaml")

        with open(template_path, "r") as f:
            job_template = f.read()

        # Sanitize product name for K8s (lowercase, no spaces, RFC 1123 compliant)
        product_k8s = re.sub(r"[^a-z0-9-]", "-", product.lower()).strip("-")
        product_k8s = re.sub(r"-+", "-", product_k8s)

        # Create Kubernetes-compliant job name
        job_name = create_k8s_job_name(product_k8s, job_id, firmware_version)

        # Replace placeholders in the template
        job_yaml = job_template.replace("{{JOB_ID}}", job_id)
        job_yaml = job_yaml.replace("{{PRODUCT}}", product_k8s)
        job_yaml = job_yaml.replace("{{FIRMWARE_PATH}}", firmware_path)
        job_yaml = job_yaml.replace("{{JOB_NAME}}", job_name)
        job_yaml = job_yaml.replace("{{ENVIRONMENT}}", env_config.ENVIRONMENT)
        job_yaml = job_yaml.replace("{{MTIB_PORT}}", str(env_config.MTIB_PORT))

        # Set both CONCORD_RUN_ID and CONCORD_SESSION_ID for backward compat
        job_yaml = job_yaml.replace("{{CONCORD_RUN_ID}}", run_id or "")
        job_yaml = job_yaml.replace("{{CONCORD_SESSION_ID}}", run_id or "")
        job_yaml = job_yaml.replace("{{RUN_ID}}", run_id or "")
        # Common runner env — same builder used by the manufacturing
        # runner deployment, so storage URL FQDN resolution and the
        # Concord API contract stay in sync between the two paths.
        common_env = build_common_runner_env(
            product_slug=product_slug or product_k8s,
            test_package_version=test_package_version or "",
            api_key=api_key or "",
            api_url=api_url or "https://10.4.45.11:443",
        )
        job_yaml = job_yaml.replace("{{CONCORD_API_KEY}}", common_env["CONCORD_API_KEY"])
        job_yaml = job_yaml.replace("{{CONCORD_API_URL}}", common_env["CONCORD_API_URL"])
        job_yaml = job_yaml.replace("{{CONCORD_API_HOST}}", common_env["CONCORD_API_HOST"])
        job_yaml = job_yaml.replace("{{STORAGE_URL}}", common_env["STORAGE_URL"])
        job_yaml = job_yaml.replace("{{STORAGE_ACCESS_KEY}}", common_env["STORAGE_ACCESS_KEY"])
        job_yaml = job_yaml.replace("{{STORAGE_SECRET_ACCESS_KEY}}", common_env["STORAGE_SECRET_ACCESS_KEY"])
        job_yaml = job_yaml.replace("{{STORAGE_BUCKET_NAME}}", common_env["STORAGE_BUCKET_NAME"])

        # Device/fixture identity env vars
        job_yaml = job_yaml.replace("{{DEVICE_ID}}", device_id or os.environ.get("DEVICE_ID", ""))
        job_yaml = job_yaml.replace("{{DEVICE_SNR}}", device_snr or os.environ.get("DEVICE_SNR", ""))
        job_yaml = job_yaml.replace("{{DEVICE_IMEI}}", device_imei or os.environ.get("DEVICE_IMEI", ""))
        job_yaml = job_yaml.replace("{{DEVICE_ICCIDS}}", device_iccids or os.environ.get("DEVICE_ICCIDS", ""))
        # MTIB address from fixture scheduler (single-slot)
        job_yaml = job_yaml.replace("{{MTIB_ADDRESS}}", mtib_address or os.environ.get("MTIB_ADDRESS", ""))
        job_yaml = job_yaml.replace("{{FIXTURE_ID}}", fixture_id or "")

        # Build run ID for firmware asset fetching
        job_yaml = job_yaml.replace("{{BUILD_RUN_ID}}", build_run_id or "")

        # Product slug for catalog API lookup (e.g., "alpha_b0")
        job_yaml = job_yaml.replace("{{PRODUCT_SLUG}}", product_slug or "")

        # Validation stage and image tag
        job_yaml = job_yaml.replace("{{STAGE}}", stage)
        resolved_image_tag = image_tag or env_config.ENVIRONMENT
        job_yaml = job_yaml.replace("{{IMAGE_TAG}}", resolved_image_tag)

        # Test filtering (temporary -- revert once FUOTA debug-flag issue is resolved)
        job_yaml = job_yaml.replace("{{PYTEST_FILTER}}", pytest_filter or "")
        job_yaml = job_yaml.replace("{{FUOTA_LABEL}}", fuota_label or "")

        # Test package version — required by the runner entrypoint, no
        # ``latest`` fallback. The backend resolves this from the stage
        # binding before calling create_kubernetes_job, so an empty
        # value here is a backend bug, not a runtime decision.
        if not test_package_version:
            logger.error(
                "create_kubernetes_job called for %s without TEST_PACKAGE_VERSION — "
                "the runner entrypoint will refuse to start. Caller must resolve "
                "the package via test_package_resolver before reaching this point.",
                product,
            )
            return None
        job_yaml = job_yaml.replace("{{TEST_PACKAGE_VERSION}}", test_package_version)

        # Stage config: test directory and marker from ProductStageConfig
        job_yaml = job_yaml.replace("{{PYTEST_DIR}}", test_directory or "")
        job_yaml = job_yaml.replace("{{PYTEST_MARKER}}", test_marker or "")

        # Framework dispatch — selects pytest vs ztest at the runner pod.
        # ``framework`` may be:
        #   * a TestFramework enum value from the resolved TestPackage,
        #   * a raw "pytest"/"ztest" string from corectl trigger payloads,
        #   * or None — in which case we collapse to PYTEST (back-compat
        #     for every test package created before the dispatch existed).
        try:
            resolved_framework = framework_env_var(framework)
        except ValueError as fw_exc:
            logger.error("Invalid framework %r for job %s: %s", framework, job_id, fw_exc)
            return None
        job_yaml = job_yaml.replace("{{TEST_FRAMEWORK}}", resolved_framework)

        # Parse the YAML and create the job
        job_spec = yaml.safe_load(job_yaml)

        # Override the job name in the spec to ensure it includes the product
        job_spec["metadata"]["name"] = job_name

        # Framework dispatch — override the container ``command`` for
        # ZTEST so the runner pod bypasses the pytest entrypoint and goes
        # straight to ``python -m corekinect.test.ztest_runner``. PYTEST
        # leaves command unset, which means the image's ENTRYPOINT
        # (``/app/entrypoint.sh``) runs unchanged — guaranteeing
        # back-compat for every test package created before the dispatch.
        if resolved_framework != "PYTEST":
            override_command = runner_command_for_framework(resolved_framework)
            containers = job_spec["spec"]["template"]["spec"].get("containers", [])
            if containers:
                containers[0]["command"] = override_command
                containers[0]["args"] = []

        # Inject extra_env vars into the container spec
        if extra_env:
            containers = job_spec["spec"]["template"]["spec"].get("containers", [])
            if containers:
                env_list = containers[0].get("env", [])
                for key, value in extra_env.items():
                    env_list.append({"name": key, "value": str(value)})
                containers[0]["env"] = env_list

        # Inject MTIB_HOSTS if provided (multi-slot comma-separated hosts)
        if mtib_hosts:
            containers = job_spec["spec"]["template"]["spec"].get("containers", [])
            if containers:
                env_list = containers[0].get("env", [])
                env_list.append({"name": "MTIB_HOSTS", "value": mtib_hosts})
                containers[0]["env"] = env_list

        # Add required feature labels to node selector if specified
        if required_features:
            node_selector = job_spec["spec"]["template"]["spec"].get("nodeSelector", {})
            for feature_key, feature_value in required_features.items():
                label_key = f"corekinect.com/validation/{feature_key}"
                node_selector[label_key] = feature_value
            job_spec["spec"]["template"]["spec"]["nodeSelector"] = node_selector

        # Create the Kubernetes job in the validation namespace (same as MinIO/API for network access)
        batch_v1 = get_batch_v1_api()
        batch_v1.create_namespaced_job(namespace=env_config.VALIDATION_NAMESPACE, body=job_spec)

        logger.info(f"Successfully created Kubernetes job: {job_name}")
        return job_name

    except Exception as e:
        logger.error(f"An error occurred while creating the kubernetes job: {str(e)}")
        return None
