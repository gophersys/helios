# Standard includes
import logging
from dataclasses import dataclass
from typing import List, Optional, Tuple

from corekinect.http.response import ConcordHttpResponse
from corekinect.utils import Logger

# 3rd party includes
from flask import Blueprint, jsonify, request
from kubernetes import client as k8s_client

# App includes
from src.middleware.permissions import authMiddleware
from src.services.database.prisma import get_db_client
from src.services.kubernetes.client import get_core_v1_api
from src.services.log.logger import get_logger

# Flask Route
v2_mtib_register_bp = Blueprint("mtib_register", __name__)


# If an MTIB is of validation type, when registering, we need to
# - Tell the backend which AppId is connected to which JLINK in the device
# - Specify which optional features are supported (Joulescope, Motion, etc.)

# -------------------------------------------------
#                                             Input
# -------------------------------------------------


@dataclass
class AppIdMapping:
    """Structure for AppId to JLINK mapping"""

    jlink: int
    appId: int


@dataclass
class MtibRegisterRequest:
    """Request structure for registering a MTIB"""

    name: str
    hostname: str
    mtibType: str
    features: List[str]
    appIds: List[AppIdMapping]

    @classmethod
    def from_json(cls, data: dict) -> Tuple["MtibRegisterRequest", Optional[str]]:
        """Parse JSON data into request object with validation"""
        if not data:
            return None, "Request body must contain JSON data"

        name = data.get("name")
        if not name:
            return None, "Field 'name' is required"

        # Validate name starts with "verdin-"
        if not name.startswith("verdin-"):
            return None, "MTIB name must start with 'verdin-'"

        hostname = data.get("hostname")
        if not hostname:
            return None, "Field 'hostname' is required"

        mtib_type = data.get("mtibType")
        if not mtib_type:
            return None, "Field 'mtibType' is required"

        # Validate mtib type
        if mtib_type not in ["validation", "manufacturing"]:
            return None, "mtibType must be either 'validation' or 'manufacturing'"

        features = data.get("features", [])
        if not isinstance(features, list):
            return None, "Field 'features' must be a list"

        # Validate features
        valid_features = ["joulescope", "motion"]
        for feature in features:
            if feature.lower() not in valid_features:
                return None, f"Invalid feature '{feature}'. Valid features are: {', '.join(valid_features)}"

        app_ids = data.get("appIds", [])
        if not isinstance(app_ids, list):
            return None, "Field 'appIds' must be a list"

        # Validate appId mappings
        app_id_mappings = []
        for mapping in app_ids:
            if not isinstance(mapping, dict):
                return None, "Each appId mapping must be an object"

            jlink = mapping.get("jlink")
            app_id = mapping.get("appId")

            if jlink is None or not isinstance(jlink, int):
                return None, "Each appId mapping must have a valid 'jlink' number"

            if app_id is None or not isinstance(app_id, int):
                return None, "Each appId mapping must have a valid 'appId' number"

            app_id_mappings.append(AppIdMapping(jlink=jlink, appId=app_id))

        return cls(name=name, hostname=hostname, mtibType=mtib_type, features=features, appIds=app_id_mappings), None


# -------------------------------------------------
#                                           Handler
# -------------------------------------------------
@v2_mtib_register_bp.route("/v2/mtib/register", methods=["POST"])
@authMiddleware.check_permissions(["Concord.Cluster.Manage"])
def mtib_register_handler():
    """
    Register a new MTIB node

    Payload:
    {
        "name": "string (must start with 'verdin-')",
        "hostname": "string",
        "mtibType": "string (validation|manufacturing)",
        "features": ["joulescope", "motion"],
        "appIds": [
            {
                "jlink": 0,
                "appId": 101
            },
            {
                "jlink": 1,
                "appId": 102
            }
        ]
    }
    """
    logger: Logger = get_logger()

    try:
        # Parse input data
        data, error = MtibRegisterRequest.from_json(request.get_json())
        if error:
            return jsonify(ConcordHttpResponse(data=None, errors=[{"message": error}]).to_dict()), 400

        logger.info(f"Registering MTIB: {data.name} (Type: {data.mtibType})")

        # Check if MTIB already exists in database
        existing_mtib = get_db_client().mtib.find_unique(where={"id": data.hostname})
        if existing_mtib:
            return (
                jsonify(
                    ConcordHttpResponse(
                        data=None, errors=[{"message": f"MTIB with hostname '{data.hostname}' already exists"}]
                    ).to_dict()
                ),
                409,
            )

        # Check that node exists in cluster
        try:
            core_v1_api = get_core_v1_api()
            node = core_v1_api.read_node(data.hostname)
            if not node:
                return (
                    jsonify(
                        ConcordHttpResponse(
                            data=None,
                            errors=[{"message": f"Node with hostname '{data.hostname}' not found in cluster"}],
                        ).to_dict()
                    ),
                    400,
                )
        except k8s_client.ApiException as e:
            if e.status == 404:
                return (
                    jsonify(
                        ConcordHttpResponse(
                            data=None,
                            errors=[{"message": f"Node with hostname '{data.hostname}' not found in cluster"}],
                        ).to_dict()
                    ),
                    400,
                )
            else:
                logger.warning(f"Could not verify node existence in cluster: {e}")
                # Continue with registration even if we can't verify node existence

        # Validate that all AppIds exist
        app_ids_to_check = [mapping.appId for mapping in data.appIds]
        existing_app_ids = get_db_client().appid.find_many(where={"appId": {"in": app_ids_to_check}})
        existing_app_id_numbers = [app.appId for app in existing_app_ids]

        missing_app_ids = set(app_ids_to_check) - set(existing_app_id_numbers)
        if missing_app_ids:
            return (
                jsonify(
                    ConcordHttpResponse(
                        data=None, errors=[{"message": f"AppIds not found: {list(missing_app_ids)}"}]
                    ).to_dict()
                ),
                400,
            )

        # Convert features to enum values
        feature_enums = []
        for feature in data.features:
            if feature.lower() == "joulescope":
                feature_enums.append("JOULESCOPE")
            elif feature.lower() == "motion":
                feature_enums.append("MOTION")

        # Convert nodeType to enum
        mtib_type = "VALIDATION" if data.mtibType.lower() == "validation" else "MANUFACTURING"

        # Create MTIB with appId mappings in a transaction
        with get_db_client().tx() as transaction:
            # Create the MTIB first
            mtib = transaction.mtib.create(
                data={
                    "id": data.hostname,
                    "name": data.name,
                    "type": mtib_type,
                    "features": feature_enums,
                }
            )

            # Create appId mappings separately
            for mapping in data.appIds:
                transaction.mtibappidmapping.create(
                    data={
                        "mtibId": mtib.id,
                        "jlink": mapping.jlink,
                        "appId": mapping.appId,
                    }
                )

        logger.info(f"Successfully registered MTIB: {data.name} with {len(data.appIds)} appId mappings")

        # Create success response
        response_data = {
            "id": mtib.id,
            "name": mtib.name,
            "hostname": mtib.id,
            "mtibType": data.mtibType,
            "features": data.features,
            "appIds": data.appIds,
            "status": "registered",
            "message": f"MTIB {data.name} registered successfully",
        }

        return jsonify(ConcordHttpResponse.new_create_response(response_data).to_dict()), 201

    except Exception as e:
        logger.error(f"An error occurred while registering MTIB: {str(e)}")
        return (
            jsonify(
                ConcordHttpResponse(data=None, errors=[{"message": f"Internal server error: {str(e)}"}]).to_dict()
            ),
            500,
        )
