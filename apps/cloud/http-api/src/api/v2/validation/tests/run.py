# Standard includes
import os
import re
import shutil
import tempfile
import uuid
import zipfile
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import yaml
from config.env import env_config
from corekinect.http.response import ConcordHttpResponse
from corekinect.utils import Logger

# 3rd party includes
from flask import Blueprint, jsonify, request

# App includes
from src.middleware.permissions import authMiddleware
from src.services.kubernetes.client import get_batch_v1_api
from src.services.log.logger import get_logger
from src.services.storage.client import get_firmware_bucket_name, get_storage_client
from werkzeug.utils import secure_filename

# Flask Route
v2_validation_tests_run_bp = Blueprint("v2_validation_tests_run", __name__)

# -------------------------------------------------
#                                             Input
# -------------------------------------------------


@dataclass
class ValidationTestsRunRequest:
    """Request structure for running a validation test"""

    product: str
    zip_file_path: str
    additional_fields: Dict[str, str]

    @classmethod
    def from_form_data(cls, form_data: dict, zip_file_path: str) -> Tuple["ValidationTestsRunRequest", Optional[str]]:
        """Parse form data into request object with validation"""
        if not form_data:
            return None, "Request must contain form data"

        product = form_data.get("product")
        if not product:
            return None, "Field 'product' is required"

        # Extract additional fields (excluding name, product, and file)
        additional_fields = {}
        for key, value in form_data.items():
            if key not in ["product", "file"] and value:
                additional_fields[key] = value

        return cls(product=product, zip_file_path=zip_file_path, additional_fields=additional_fields), None


# -------------------------------------------------
#                                           Helpers
# -------------------------------------------------


def create_k8s_job_name(product: str, job_id: str, firmware_version: Optional[str] = None) -> str:
    """Create a Kubernetes-compliant job name (max 63 chars, RFC 1123 compliant)"""
    import hashlib

    # Ensure product name is lowercase and valid for K8s
    product_clean = product.lower().replace("_", "-")

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
        uuid_hash = hashlib.md5(uuid_part.encode()).hexdigest()[:8]

        # Now replace underscores in test name with hyphens
        test_name_clean = test_name.replace("_", "-")

        # Combine: hash-testname-version
        job_id_clean = f"{uuid_hash}-{test_name_clean}{version_suffix}"
    else:
        # No test name, just hash the whole thing
        job_id_clean = job_id.replace("_", "-").replace("/", "-")
        if len(job_id_clean) > 40:
            job_id_clean = hashlib.md5(job_id_clean.encode()).hexdigest()[:12]
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
            job_name = f"val-{hashlib.md5(job_id.encode()).hexdigest()[:12]}"

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
    logger: Logger = get_logger()

    # Create a unique path for this firmware upload
    firmware_filename = f"{product}-{job_id}.zip"
    bucket_path = f"{product}/{job_id}/{firmware_filename}"

    logger.info(f"Uploading firmware to bucket: {zip_file_path} -> {bucket_path}")

    try:
        # Get the storage client and bucket name
        storage_client = get_storage_client()
        bucket_name = get_firmware_bucket_name()

        # Upload the file to MinIO
        storage_client.fput_object(
            bucket_name=bucket_name, object_name=bucket_path, file_path=zip_file_path, content_type="application/zip"
        )

        logger.info(f"Successfully uploaded firmware to bucket path: {bucket_path}")
        logger.info(f"Returning firmware_path: '{bucket_path}'")
        return bucket_path, None
    except Exception as e:
        logger.error(f"An error occurred while uploading the firmware to the bucket: {str(e)}")
        return None, f"An error occurred while uploading the firmware to the bucket: {str(e)}"


def create_kubernetes_job(
    product: str,
    job_id: str,
    firmware_path: str,
    test_type: str,
    test_enable: Dict[str, bool],
    required_features: Optional[Dict[str, str]] = None,
    firmware_version: Optional[str] = None,
) -> Optional[str]:
    """
    Create a new kubernetes job with the new firmware file environment variables.
    The job will be scheduled automatically by Kubernetes on any available node
    that matches the nodeSelector and tolerations, with pod anti-affinity ensuring
    only one validation job per node.

    Args:
        product: Product name
        job_id: Job ID (UUID)
        firmware_path: Path to firmware in storage bucket
        test_type: Test type identifier (from product YAML config)
        test_enable: Dict of test enable flags from product YAML config
        required_features: Optional dict of required feature labels

    Returns:
        Kubernetes job name if successful, None if error
    """
    logger: Logger = get_logger()
    logger.info(f"Creating kubernetes job for product: {product}, job_id: {job_id} (will be scheduled automatically)")

    try:
        # Load the job template
        template_path = os.path.join(env_config.ASSETS_FOLDER, "templates", "validation_job.yaml")

        with open(template_path, "r") as f:
            job_template = f.read()

        # Create Kubernetes-compliant job name
        job_name = create_k8s_job_name(product, job_id, firmware_version)

        # Set test enable flags from config
        test_enable_electrical = "true" if test_enable.get("electrical", False) else "false"
        test_enable_app_post = "true" if test_enable.get("app_post", False) else "false"
        test_enable_comm_post = "true" if test_enable.get("comm_post", False) else "false"

        # Replace placeholders in the template
        job_yaml = job_template.replace("{{JOB_ID}}", job_id)
        job_yaml = job_yaml.replace("{{PRODUCT}}", product)
        job_yaml = job_yaml.replace("{{FIRMWARE_PATH}}", firmware_path)
        job_yaml = job_yaml.replace("{{JOB_NAME}}", job_name)
        job_yaml = job_yaml.replace("{{ENVIRONMENT}}", env_config.ENVIRONMENT)
        job_yaml = job_yaml.replace("{{MTIB_PORT}}", "50053")
        job_yaml = job_yaml.replace("{{TEST_ENABLE_ELECTRICAL}}", test_enable_electrical)
        job_yaml = job_yaml.replace("{{TEST_ENABLE_APP_POST}}", test_enable_app_post)
        job_yaml = job_yaml.replace("{{TEST_ENABLE_COMM_POST}}", test_enable_comm_post)

        # Parse the YAML and create the job
        job_spec = yaml.safe_load(job_yaml)

        # Override the job name in the spec to ensure it includes the product
        job_spec["metadata"]["name"] = job_name

        # Add required feature labels to node selector if specified
        if required_features:
            node_selector = job_spec["spec"]["template"]["spec"].get("nodeSelector", {})
            for feature_key, feature_value in required_features.items():
                label_key = f"corekinect.com/validation/{feature_key}"
                node_selector[label_key] = feature_value
            job_spec["spec"]["template"]["spec"]["nodeSelector"] = node_selector

        # Create the Kubernetes job
        batch_v1 = get_batch_v1_api()
        batch_v1.create_namespaced_job(namespace="default", body=job_spec)

        logger.info(f"Successfully created Kubernetes job: {job_name}")
        return job_name

    except Exception as e:
        logger.error(f"An error occurred while creating the kubernetes job: {str(e)}")
        return None


# -------------------------------------------------
#                                           Handler
# -------------------------------------------------
@v2_validation_tests_run_bp.route("/v2/validation/tests/run", methods=["POST"])
@authMiddleware.check_permissions(["Concord.Validation.Tests.Run"])
def validation_tests_run_handler():
    logger: Logger = get_logger()
    zip_file_path = None
    temp_dir = None

    try:
        # Check if file is present in the request
        if "file" not in request.files:
            return jsonify(ConcordHttpResponse(data=None, errors=[{"message": "No file provided"}]).to_dict()), 400

        file = request.files["file"]
        if file.filename == "":
            return jsonify(ConcordHttpResponse(data=None, errors=[{"message": "No file selected"}]).to_dict()), 400

        # Validate file extension
        if not file.filename.lower().endswith(".zip"):
            return (
                jsonify(ConcordHttpResponse(data=None, errors=[{"message": "File must be a zip archive"}]).to_dict()),
                400,
            )

        # Save uploaded file to temporary location
        filename = secure_filename(file.filename)
        temp_dir = tempfile.mkdtemp()
        zip_file_path = os.path.join(temp_dir, filename)
        file.save(zip_file_path)

        logger.info(f"Created temporary directory: {temp_dir}")

        # Validate zip file
        try:
            with zipfile.ZipFile(zip_file_path, "r") as zip_ref:
                # Test if zip file is valid
                zip_ref.testzip()
        except zipfile.BadZipFile:
            return jsonify(ConcordHttpResponse(data=None, errors=[{"message": "Invalid zip file"}]).to_dict()), 400

        # Parse form data
        form_data = request.form.to_dict()
        data, error = ValidationTestsRunRequest.from_form_data(form_data, zip_file_path)
        if error:
            return jsonify(ConcordHttpResponse(data=None, errors=[{"message": error}]).to_dict()), 400

        # Generate unique job ID using UUID
        job_id = str(uuid.uuid4())

        logger.info(f"Creating validation test jobs for product: {data.product}")
        logger.info(f"Job ID: {job_id}")
        logger.info(f"Additional fields: {data.additional_fields}")
        logger.info(f"Firmware zip file: {zip_file_path}")

        # 1. Extract and validate the zip file
        error, firmware_version = extract_and_validate_firmware(zip_file_path)
        if error:
            return jsonify(ConcordHttpResponse(data=None, errors=[{"message": error}]).to_dict()), 400

        logger.info(f"Extracted firmware version: {firmware_version}")

        # 2. Upload the firmware to the bucket
        firmware_path, error = upload_firmware_to_bucket(zip_file_path, job_id, data.product)
        if error:
            return jsonify(ConcordHttpResponse(data=None, errors=[{"message": error}]).to_dict()), 400

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

            return (
                jsonify(ConcordHttpResponse.new_create_response(data=response_data).to_dict()),
                201,
            )

        except Exception as e:
            logger.error(f"Error creating Kubernetes jobs: {str(e)}")
            return (
                jsonify(
                    ConcordHttpResponse(
                        data=None, errors=[{"message": f"Error creating Kubernetes jobs: {str(e)}"}]
                    ).to_dict()
                ),
                500,
            )

    except Exception as e:
        logger.error(f"An error occurred while running validation test: {str(e)}")
        return (
            jsonify(
                ConcordHttpResponse(data=None, errors=[{"message": f"Internal server error: {str(e)}"}]).to_dict()
            ),
            500,
        )
    finally:
        # Clean up temporary directory and all its contents
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
                logger.info(f"Successfully cleaned up temporary directory: {temp_dir}")
            except OSError as e:
                logger.warning(f"Could not clean up temporary directory {temp_dir}: {str(e)}")
