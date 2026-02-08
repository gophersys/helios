import math
from typing import Any

from flask import g, jsonify, request
from database import Json

from src.lib.audit import log_audit
from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, conflict, internal_error, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client

from .types import DeploymentCreateRequest


def _serialize_deployment(d: Any) -> dict:
    data = {
        "id": d.id,
        "name": d.name,
        "productId": d.productId,
        "fixtureId": d.fixtureId,
        "status": d.status,
        "config": d.config,
        "version": d.version,
        "createdAt": d.createdAt.isoformat(),
        "updatedAt": d.updatedAt.isoformat(),
    }
    if hasattr(d, "fixture") and d.fixture:
        data["fixtureName"] = d.fixture.name
        if hasattr(d.fixture, "product") and d.fixture.product:
            data["productName"] = d.fixture.product.name
    elif hasattr(d, "product") and d.product:
        data["productName"] = d.product.name
    if hasattr(d, "createdBy") and d.createdBy:
        data["createdBy"] = {"id": d.createdBy.id, "name": d.createdBy.name}
    return data


# -- List deployments -------------------------------------------------------


@require_permissions(Permissions.ADMIN_DEPLOYMENTS_VIEW)
def list_deployments():
    db = get_db_client()

    page = max(1, request.args.get("page", 1, type=int))
    limit = min(max(1, request.args.get("limit", 50, type=int)), 100)
    skip = (page - 1) * limit

    where: dict = {}
    fixture_id = request.args.get("fixtureId", type=str)
    if fixture_id:
        where["fixtureId"] = fixture_id.strip()

    total = db.deployment.count(where=where)
    deployments = db.deployment.find_many(
        where=where,
        skip=skip,
        take=limit,
        order={"createdAt": "desc"},
        include={
            "fixture": {"include": {"product": True}},
            "product": True,
            "createdBy": True,
        },
    )

    return jsonify(ApiResponse.ok({
        "data": [_serialize_deployment(d) for d in deployments],
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": math.ceil(total / limit) if limit > 0 else 0,
        },
    }).to_dict()), 200


# -- Create deployment ------------------------------------------------------


@require_permissions(Permissions.ADMIN_DEPLOYMENTS_MANAGE)
def create_deployment():
    data, error = DeploymentCreateRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    db = get_db_client()

    # Verify fixture exists
    fixture = db.fixture.find_unique(
        where={"id": data.fixtureId},
        include={"product": True},
    )
    if not fixture:
        return not_found("Fixture not found")

    user = getattr(g, "current_user", None)
    created_by_id = user["sub"] if user else None

    deployment = db.deployment.create(
        data={
            "name": data.name,
            "fixtureId": data.fixtureId,
            "productId": fixture.productId,
            "status": "PENDING",
            "config": Json(data.config) if data.config else None,
            "version": data.version,
            "createdById": created_by_id,
        },
        include={
            "fixture": {"include": {"product": True}},
            "product": True,
            "createdBy": True,
        },
    )

    log_audit("deployment.create", "Deployment", deployment.id, {
        "name": data.name,
        "fixtureId": data.fixtureId,
        "productId": fixture.productId,
    })

    return jsonify(ApiResponse.ok(_serialize_deployment(deployment)).to_dict()), 201


# -- Get deployment ---------------------------------------------------------


@require_permissions(Permissions.ADMIN_DEPLOYMENTS_VIEW)
def get_deployment(deployment_id: str):
    db = get_db_client()
    deployment = db.deployment.find_unique(
        where={"id": deployment_id},
        include={
            "fixture": {"include": {"product": True}},
            "product": True,
            "createdBy": True,
        },
    )
    if not deployment:
        return not_found("Deployment not found")

    return jsonify(ApiResponse.ok(_serialize_deployment(deployment)).to_dict()), 200


# -- Delete deployment ------------------------------------------------------


@require_permissions(Permissions.ADMIN_DEPLOYMENTS_MANAGE)
def delete_deployment(deployment_id: str):
    db = get_db_client()
    deployment = db.deployment.find_unique(where={"id": deployment_id})
    if not deployment:
        return not_found("Deployment not found")

    if deployment.status == "RUNNING":
        return conflict("Cannot delete a running deployment. Stop it first.")

    db.deployment.delete(where={"id": deployment_id})
    log_audit("deployment.delete", "Deployment", deployment_id, {"name": deployment.name})

    return jsonify(ApiResponse.ok({"deleted": True}).to_dict()), 200


# -- Deploy fixture ---------------------------------------------------------


@require_permissions(Permissions.ADMIN_DEPLOYMENTS_MANAGE)
def deploy_fixture(deployment_id: str):
    db = get_db_client()
    deployment = db.deployment.find_unique(
        where={"id": deployment_id},
        include={
            "fixture": {
                "include": {
                    "slots": {"include": {"node": True}},
                    "product": True,
                },
            },
        },
    )
    if not deployment:
        return not_found("Deployment not found")

    if deployment.status not in ("PENDING", "STOPPED", "FAILED"):
        return conflict(f"Cannot deploy from status '{deployment.status}'. Must be PENDING, STOPPED, or FAILED.")

    if not deployment.fixture:
        return bad_request("Deployment has no fixture assigned")

    slots = deployment.fixture.slots or []
    assigned_slots = [s for s in slots if s.node is not None]
    if not assigned_slots:
        return bad_request("Fixture has no nodes assigned to any slot")

    from src.services.kubernetes.mtib_deployments import create_mtib_deployment

    config = deployment.config if isinstance(deployment.config, dict) else {}
    k8s_deployments = []
    failures = []

    for slot in assigned_slots:
        deploy_name = create_mtib_deployment(
            node_hostname=slot.node.hostname,
            fixture_id=deployment.fixtureId,
            deployment_id=deployment.id,
            slot_index=slot.slotIndex,
            config=config,
        )
        if deploy_name:
            k8s_deployments.append({
                "name": deploy_name,
                "slotIndex": slot.slotIndex,
                "nodeHostname": slot.node.hostname,
            })
        else:
            failures.append({
                "slotIndex": slot.slotIndex,
                "nodeHostname": slot.node.hostname,
                "error": "Failed to create K8s deployment",
            })

    if not k8s_deployments:
        db.deployment.update(
            where={"id": deployment_id},
            data={"status": "FAILED", "config": Json({**config, "k8sDeployments": [], "failures": failures})},
        )
        return internal_error("Failed to create any K8s deployments")

    updated_config = {**config, "k8sDeployments": k8s_deployments}
    if failures:
        updated_config["failures"] = failures

    updated = db.deployment.update(
        where={"id": deployment_id},
        data={"status": "RUNNING", "config": Json(updated_config)},
        include={
            "fixture": {"include": {"product": True}},
            "product": True,
            "createdBy": True,
        },
    )

    log_audit("deployment.deploy", "Deployment", deployment_id, {
        "name": deployment.name,
        "k8sDeployments": [d["name"] for d in k8s_deployments],
        "failures": len(failures),
    })

    return jsonify(ApiResponse.ok(_serialize_deployment(updated)).to_dict()), 200


# -- Stop deployment --------------------------------------------------------


@require_permissions(Permissions.ADMIN_DEPLOYMENTS_MANAGE)
def stop_deployment(deployment_id: str):
    db = get_db_client()
    deployment = db.deployment.find_unique(where={"id": deployment_id})
    if not deployment:
        return not_found("Deployment not found")

    if deployment.status != "RUNNING":
        return conflict(f"Cannot stop deployment with status '{deployment.status}'. Must be RUNNING.")

    from src.services.kubernetes.mtib_deployments import delete_mtib_deployment

    config = deployment.config if isinstance(deployment.config, dict) else {}
    k8s_deployments = config.get("k8sDeployments", [])

    for k8s_dep in k8s_deployments:
        deploy_name = k8s_dep.get("name") if isinstance(k8s_dep, dict) else k8s_dep
        if deploy_name:
            delete_mtib_deployment(deploy_name)

    updated_config = {**config}
    updated_config.pop("k8sDeployments", None)
    updated_config.pop("failures", None)

    updated = db.deployment.update(
        where={"id": deployment_id},
        data={"status": "STOPPED", "config": Json(updated_config) if updated_config else None},
        include={
            "fixture": {"include": {"product": True}},
            "product": True,
            "createdBy": True,
        },
    )

    log_audit("deployment.stop", "Deployment", deployment_id, {"name": deployment.name})

    return jsonify(ApiResponse.ok(_serialize_deployment(updated)).to_dict()), 200


# -- Restart deployment -----------------------------------------------------


@require_permissions(Permissions.ADMIN_DEPLOYMENTS_MANAGE)
def restart_deployment(deployment_id: str):
    db = get_db_client()
    deployment = db.deployment.find_unique(where={"id": deployment_id})
    if not deployment:
        return not_found("Deployment not found")

    if deployment.status != "RUNNING":
        return conflict(f"Cannot restart deployment with status '{deployment.status}'. Must be RUNNING.")

    # Stop existing K8s deployments
    from src.services.kubernetes.mtib_deployments import delete_mtib_deployment

    config = deployment.config if isinstance(deployment.config, dict) else {}
    k8s_deployments = config.get("k8sDeployments", [])

    for k8s_dep in k8s_deployments:
        deploy_name = k8s_dep.get("name") if isinstance(k8s_dep, dict) else k8s_dep
        if deploy_name:
            delete_mtib_deployment(deploy_name)

    # Set to PENDING so deploy_fixture can pick it up
    db.deployment.update(
        where={"id": deployment_id},
        data={
            "status": "PENDING",
            "config": Json({k: v for k, v in config.items() if k not in ("k8sDeployments", "failures")}) or None,
        },
    )

    log_audit("deployment.restart", "Deployment", deployment_id, {"name": deployment.name})

    # Re-deploy
    return deploy_fixture(deployment_id)


# -- Get deployment status --------------------------------------------------


@require_permissions(Permissions.ADMIN_DEPLOYMENTS_VIEW)
def get_deployment_status(deployment_id: str):
    db = get_db_client()
    deployment = db.deployment.find_unique(
        where={"id": deployment_id},
        include={
            "fixture": {"include": {"product": True}},
            "product": True,
            "createdBy": True,
        },
    )
    if not deployment:
        return not_found("Deployment not found")

    result = _serialize_deployment(deployment)

    config = deployment.config if isinstance(deployment.config, dict) else {}
    k8s_deployments = config.get("k8sDeployments", [])

    if k8s_deployments and deployment.status == "RUNNING":
        from src.services.kubernetes.mtib_deployments import get_mtib_deployment_status

        k8s_statuses = []
        for k8s_dep in k8s_deployments:
            deploy_name = k8s_dep.get("name") if isinstance(k8s_dep, dict) else k8s_dep
            if deploy_name:
                status = get_mtib_deployment_status(deploy_name)
                k8s_statuses.append({
                    "name": deploy_name,
                    "slotIndex": k8s_dep.get("slotIndex") if isinstance(k8s_dep, dict) else None,
                    "status": status,
                })
        result["k8sStatus"] = k8s_statuses

    return jsonify(ApiResponse.ok(result).to_dict()), 200
