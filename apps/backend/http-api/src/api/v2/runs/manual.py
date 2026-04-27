"""K8s job creation for validation runs (TestRun/RunTarget models).

Renders the validation_job.yaml template and submits to K8s.
Supports multi-slot fixtures via extra_env injection.
"""

import hashlib
import os
import re
import shutil
import tempfile
import uuid
import zipfile
from typing import Dict, Optional, Tuple
import yaml  # type: ignore[import-untyped]
from config.env import env_config
from flask import jsonify, request
from werkzeug.utils import secure_filename

from src.lib.audit import log_audit
from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, internal_error
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.kubernetes.client import get_batch_v1_api
from src.services.kubernetes.runner_env import build_common_runner_env
from src.services.log.logger import get_logger
from src.services.storage.client import get_bucket_name, get_storage_client, StoragePrefixes, storage_key

from src.api.v2.runs.types import ValidationTestsRunRequest


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


def extract_and_validate_firmware(zip_file_path: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract and validate the firmware from the zip file.
    Returns: (error_message, firmware_version)
    """
    try:
        with zipfile.ZipFile(zip_file_path, "r") as zip_ref:
            # Test if zip file is valid
            zip_ref.testzip()

            # Create extraction directory (parent directory of the zip file)
            extract_dir = os.path.dirname(zip_file_path)

            # Path traversal prevention: ensure no entry escapes the extraction directory
            real_extract_dir = os.path.realpath(extract_dir)
            for member in zip_ref.namelist():
                member_path = os.path.realpath(os.path.join(extract_dir, member))
                if not member_path.startswith(real_extract_dir + os.sep) and member_path != real_extract_dir:
                    return "Zip file contains invalid path entries", None

            zip_ref.extractall(extract_dir)

            # Try to extract firmware version from extracted folder structure
            # Look for folders matching version patterns like "0.1.4", "0_1_4", "v0.1.4", etc.
            firmware_version = None
            try:
                extracted_items = os.listdir(extract_dir)
                # Pattern to match version-like folder names: digits separated by dots, underscores, or hyphens
                version_pattern = re.compile(r"^v?(\d+[._-]\d+([._-]\d+)*)$", re.IGNORECASE)

                for item in extracted_items:
                    item_path = os.path.join(extract_dir, item)
                    if os.path.isdir(item_path):
                        match = version_pattern.match(item)
                        if match:
                            firmware_version = match.group(1)  # Get version without 'v' prefix if present
                            break
            except Exception as e:
                # If we can't determine version, continue without it
                logger = get_logger()
                logger.warning(f"Could not extract firmware version: {str(e)}")

            return None, firmware_version
    except zipfile.BadZipFile:
        return "The zip file is invalid, please check the file and try again", None


def upload_firmware_to_bucket(zip_file_path: str, job_id: str, product: str) -> Tuple[Optional[str], Optional[str]]:
    """Upload the firmware to the bucket and return the bucket path"""
    logger = get_logger()

    # Create a unique path for this firmware upload
    firmware_filename = f"{product}-{job_id}.zip"
    bucket_path = storage_key(StoragePrefixes.FIRMWARE_UPLOADS, f"{product}/{job_id}/{firmware_filename}")

    logger.info(f"Uploading firmware to bucket: {zip_file_path} -> {bucket_path}")

    try:
        # Get the storage client and bucket name
        storage_client = get_storage_client()
        bucket_name = get_bucket_name()

        # Upload the file to MinIO
        storage_client.fput_object(
            bucket_name=bucket_name, object_name=bucket_path, file_path=zip_file_path, content_type="application/zip"
        )

        logger.info(f"Successfully uploaded firmware to bucket path: {bucket_path}")
        logger.info(f"Returning firmware_path: '{bucket_path}'")
        return bucket_path, None
    except Exception as e:
        logger.error(f"An error occurred while uploading the firmware to the bucket: {str(e)}")
        return None, "An error occurred while uploading the firmware to the bucket"


def create_kubernetes_job(
    product: str,
    job_id: str,
    firmware_path: str,  # MinIO path (prefer build_run_id when available)
    test_type: str,
    test_enable: Dict[str, bool],
    required_features: Optional[Dict[str, str]] = None,
    firmware_version: Optional[str] = None,
    run_id: Optional[str] = None,
    api_key: Optional[str] = None,
    api_url: Optional[str] = None,
    # Fixture-related params (from scheduler or trigger)
    mtib_address: Optional[str] = None,
    bench_id: Optional[str] = None,
    device_id: Optional[str] = None,
    device_snr: Optional[str] = None,
    fixture_profile_path: Optional[str] = None,
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

        # Set test enable flags from config
        test_enable_electrical = "true" if test_enable.get("electrical", False) else "false"
        test_enable_app_post = "true" if test_enable.get("app_post", False) else "false"
        test_enable_comm_post = "true" if test_enable.get("comm_post", False) else "false"

        # Replace placeholders in the template
        job_yaml = job_template.replace("{{JOB_ID}}", job_id)
        job_yaml = job_yaml.replace("{{PRODUCT}}", product_k8s)
        job_yaml = job_yaml.replace("{{FIRMWARE_PATH}}", firmware_path)
        job_yaml = job_yaml.replace("{{JOB_NAME}}", job_name)
        job_yaml = job_yaml.replace("{{ENVIRONMENT}}", env_config.ENVIRONMENT)
        job_yaml = job_yaml.replace("{{MTIB_PORT}}", str(env_config.MTIB_PORT))
        job_yaml = job_yaml.replace("{{TEST_ENABLE_ELECTRICAL}}", test_enable_electrical)
        job_yaml = job_yaml.replace("{{TEST_ENABLE_APP_POST}}", test_enable_app_post)
        job_yaml = job_yaml.replace("{{TEST_ENABLE_COMM_POST}}", test_enable_comm_post)

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

        # Device/fixture identity env vars -- use FIXTURE_ID as the canonical name,
        # but keep BENCH_ID in the template for backward compat
        job_yaml = job_yaml.replace("{{DEVICE_ID}}", device_id or os.environ.get("DEVICE_ID", ""))
        job_yaml = job_yaml.replace("{{DEVICE_SNR}}", device_snr or os.environ.get("DEVICE_SNR", ""))
        job_yaml = job_yaml.replace("{{FIXTURE_PROFILE_PATH}}", fixture_profile_path or os.environ.get("FIXTURE_PROFILE_PATH", ""))
        job_yaml = job_yaml.replace("{{DEVICE_IMEI}}", device_imei or os.environ.get("DEVICE_IMEI", ""))
        job_yaml = job_yaml.replace("{{DEVICE_ICCIDS}}", device_iccids or os.environ.get("DEVICE_ICCIDS", ""))
        # MTIB address from fixture scheduler (single-slot backward compat)
        job_yaml = job_yaml.replace("{{MTIB_ADDRESS}}", mtib_address or os.environ.get("MTIB_ADDRESS", ""))
        job_yaml = job_yaml.replace("{{BENCH_ID}}", bench_id or "")

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

        # Test package version (for generic runner to download)
        job_yaml = job_yaml.replace("{{TEST_PACKAGE_VERSION}}", test_package_version or "latest")

        # Stage config: test directory and marker from ProductStageConfig
        job_yaml = job_yaml.replace("{{PYTEST_DIR}}", test_directory or "")
        job_yaml = job_yaml.replace("{{PYTEST_MARKER}}", test_marker or "")

        # Parse the YAML and create the job
        job_spec = yaml.safe_load(job_yaml)

        # Override the job name in the spec to ensure it includes the product
        job_spec["metadata"]["name"] = job_name

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

        # CONCORD_SESSION_ID and FIXTURE_ID are now set directly in the
        # template (aliased to CONCORD_RUN_ID and BENCH_ID respectively),
        # so no post-parse injection is needed.

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


# -------------------------------------------------
#                                           Handler
# -------------------------------------------------
@require_permissions(Permissions.VALIDATION_RUN)
def run_tests():
    """POST -- upload a test ZIP and launch a manual validation K8s job."""
    logger = get_logger()
    zip_file_path = None
    temp_dir = None

    try:
        # Check if file is present in the request
        if "file" not in request.files:
            return bad_request("No file provided")

        file = request.files["file"]
        if file.filename == "":
            return bad_request("No file selected")

        # Validate file extension
        if not file.filename.lower().endswith(".zip"):
            return bad_request("File must be a zip archive")

        # Save uploaded file to temporary location
        filename = secure_filename(file.filename)
        temp_dir = tempfile.mkdtemp()
        zip_file_path = os.path.join(temp_dir, filename)
        file.save(zip_file_path)

        logger.info(f"Created temporary directory: {temp_dir}")

        # Validate zip file
        try:
            with zipfile.ZipFile(zip_file_path, "r") as zip_ref:
                zip_ref.testzip()
        except zipfile.BadZipFile:
            return bad_request("Invalid zip file")

        # Parse form data
        form_data = request.form.to_dict()
        data, error = ValidationTestsRunRequest.from_form_data(form_data, zip_file_path)
        if error:
            return bad_request(error)

        # Generate unique job ID using UUID
        job_id = str(uuid.uuid4())

        logger.info(f"Creating validation test jobs for product: {data.product}")
        logger.info(f"Job ID: {job_id}")
        logger.info(f"Additional fields: {data.additional_fields}")
        logger.info(f"Firmware zip file: {zip_file_path}")

        # 1. Extract and validate the zip file
        error, firmware_version = extract_and_validate_firmware(zip_file_path)
        if error:
            return bad_request(error)

        logger.info(f"Extracted firmware version: {firmware_version}")

        # 2. Upload the firmware to the bucket
        firmware_path, error = upload_firmware_to_bucket(zip_file_path, job_id, data.product)
        if error:
            return bad_request(error)

        # 3. Create 3 Kubernetes jobs directly - one for each test type (skip database)
        job_statuses = []

        # Define 3 test jobs: electrical, app_post, comm_post
        test_jobs = [
            {
                "name": "electrical",
                "test_type": "electrical",
                "test_enable": {"electrical": True, "app_post": False, "comm_post": False},
            },
            {
                "name": "app_post",
                "test_type": "app_post",
                "test_enable": {"electrical": False, "app_post": True, "comm_post": False},
            },
            {
                "name": "comm_post",
                "test_type": "comm_post",
                "test_enable": {"electrical": False, "app_post": False, "comm_post": True},
            },
        ]

        try:
            for test_job_config in test_jobs:
                # Generate unique job ID for each test
                test_job_id = f"{job_id}-{test_job_config['name']}"

                logger.info(
                    f"Creating Kubernetes job: {test_job_id} (test: {test_job_config['name']}, type: {test_job_config['test_type']})"
                )

                # Create Kubernetes job directly (no database)
                k8s_job_name = create_kubernetes_job(
                    product=data.product,
                    job_id=test_job_id,
                    firmware_path=firmware_path,
                    test_type=test_job_config["test_type"],
                    test_enable=test_job_config["test_enable"],
                    required_features=None,
                    firmware_version=firmware_version,
                )

                if k8s_job_name:
                    logger.info(f"Successfully created Kubernetes job: {k8s_job_name} for {test_job_id}")
                    job_statuses.append(
                        {
                            "job_id": test_job_id,
                            "test_type": test_job_config["test_type"],
                            "status": "CREATED",
                            "k8s_job_name": k8s_job_name,
                            "node_hostname": None,  # Will be set when K8s schedules it
                        }
                    )
                else:
                    logger.error(f"Failed to create Kubernetes job for {test_job_id}")
                    job_statuses.append(
                        {
                            "job_id": test_job_id,
                            "test_type": test_job_config["test_type"],
                            "status": "FAILED",
                            "k8s_job_name": None,
                            "node_hostname": None,
                        }
                    )

            response_data = {
                "message": "Validation test jobs created successfully",
                "product": data.product,
                "build_job_id": job_id,  # Parent job ID for the build
                "firmware_path": firmware_path,
                "jobs": job_statuses,
                "additional_fields": data.additional_fields,
            }

            log_audit("validation.run", "ValidationTest", job_id, {
                "product": data.product,
                "firmwareVersion": firmware_version,
                "jobCount": len(job_statuses),
                "jobs": [{"id": j["job_id"], "type": j["test_type"], "status": j["status"]} for j in job_statuses],
            })

            return jsonify(ApiResponse.created(response_data).to_dict()), 201

        except Exception as e:
            logger.error(f"Error creating Kubernetes jobs: {str(e)}")
            return internal_error("Failed to create validation jobs. Please try again or contact support.")

    except Exception as e:
        logger.error(f"An error occurred while running validation test: {str(e)}")
        return internal_error("Internal server error")
    finally:
        # Clean up temporary directory and all its contents
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
                logger.info(f"Successfully cleaned up temporary directory: {temp_dir}")
            except OSError as e:
                logger.warning(f"Could not clean up temporary directory {temp_dir}: {str(e)}")
