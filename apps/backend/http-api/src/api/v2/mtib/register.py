from flask import jsonify, request
from kubernetes import client as k8s_client

from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, conflict, internal_error
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client
from src.services.kubernetes.client import get_core_v1_api
from src.services.log.logger import get_logger

from .types import MtibRegisterRequest


@require_permissions(Permissions.MTIB_MANAGE)
def register_mtib():
    """Register a new MTIB node."""
    logger = get_logger()

    try:
        # Parse input data
        data, error = MtibRegisterRequest.from_json(request.get_json())
        if error:
            return bad_request(error)

        logger.info(f"Registering MTIB: {data.name} (Type: {data.mtibType})")

        # Check if MTIB already exists in database
        existing_mtib = get_db_client().mtib.find_unique(where={"id": data.hostname})
        if existing_mtib:
            return conflict(f"MTIB with hostname '{data.hostname}' already exists")

        # Check that node exists in cluster
        try:
            core_v1_api = get_core_v1_api()
            node = core_v1_api.read_node(data.hostname)
            if not node:
                return bad_request(f"Node with hostname '{data.hostname}' not found in cluster")
        except k8s_client.ApiException as e:
            if e.status == 404:
                return bad_request(f"Node with hostname '{data.hostname}' not found in cluster")
            else:
                logger.warning(f"Could not verify node existence in cluster: {e}")
                # Continue with registration even if we can't verify node existence

        # Validate that all AppIds exist
        app_ids_to_check = [mapping.appId for mapping in data.appIds]
        existing_app_ids = get_db_client().appid.find_many(where={"appId": {"in": app_ids_to_check}})
        existing_app_id_numbers = [app.appId for app in existing_app_ids]

        missing_app_ids = set(app_ids_to_check) - set(existing_app_id_numbers)
        if missing_app_ids:
            return bad_request(f"AppIds not found: {list(missing_app_ids)}")

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

        return jsonify(ApiResponse.created(response_data).to_dict()), 201

    except Exception as e:
        logger.error(f"An error occurred while registering MTIB: {str(e)}")
        return internal_error(f"Internal server error: {str(e)}")
