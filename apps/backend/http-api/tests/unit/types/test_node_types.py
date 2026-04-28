"""Unit tests for node types validation."""

import pytest


def test_node_create_valid():
    from src.api.v2.nodes.types import NodeCreateRequest
    data = {"name": "MTIB-01", "hostname": "verdin-imx8mm-15005658", "type": "manufacturing"}
    req, err = NodeCreateRequest.from_json(data)
    assert err is None
    assert req.name == "MTIB-01"
    assert req.hostname == "verdin-imx8mm-15005658"
    assert req.type == "MANUFACTURING"


def test_node_create_missing_name():
    from src.api.v2.nodes.types import NodeCreateRequest
    req, err = NodeCreateRequest.from_json({"hostname": "host1", "type": "manufacturing"})
    assert req is None
    assert err == "Name is required"


def test_node_create_missing_hostname():
    from src.api.v2.nodes.types import NodeCreateRequest
    req, err = NodeCreateRequest.from_json({"name": "Node1", "type": "manufacturing"})
    assert req is None
    assert err == "Hostname is required"


def test_node_create_invalid_type():
    from src.api.v2.nodes.types import NodeCreateRequest
    req, err = NodeCreateRequest.from_json({"name": "Node1", "hostname": "host1", "type": "INVALID"})
    assert req is None
    assert err == "Type must be MANUFACTURING or VALIDATION"


def test_node_create_null_body():
    from src.api.v2.nodes.types import NodeCreateRequest
    req, err = NodeCreateRequest.from_json(None)
    assert req is None
    assert err == "Request body must contain JSON data"


def test_node_update_valid():
    from src.api.v2.nodes.types import NodeUpdateRequest
    data = {"name": "Updated Node", "disabled": True}
    req, err = NodeUpdateRequest.from_json(data)
    assert err is None
    assert req.name == "Updated Node"
    assert req.disabled is True
    update = req.to_update_data()
    assert update["name"] == "Updated Node"
    assert update["disabled"] is True


def test_node_update_empty_name():
    from src.api.v2.nodes.types import NodeUpdateRequest
    req, err = NodeUpdateRequest.from_json({"name": "   "})
    assert req is None
    assert err == "Name cannot be empty"


def test_node_update_invalid_disabled():
    from src.api.v2.nodes.types import NodeUpdateRequest
    req, err = NodeUpdateRequest.from_json({"disabled": "yes"})
    assert req is None
    assert err == "disabled must be a boolean"


def test_node_update_no_fields():
    from src.api.v2.nodes.types import NodeUpdateRequest
    req, err = NodeUpdateRequest.from_json({})
    assert req is None
    assert err == "Request body must contain JSON data"


def test_node_update_null_body():
    from src.api.v2.nodes.types import NodeUpdateRequest
    req, err = NodeUpdateRequest.from_json(None)
    assert req is None
    assert err == "Request body must contain JSON data"


def test_node_update_nullable_ip():
    from src.api.v2.nodes.types import NodeUpdateRequest
    data = {"ipAddress": None}
    req, err = NodeUpdateRequest.from_json(data)
    assert err is None
    update = req.to_update_data()
    assert "ipAddress" in update
    assert update["ipAddress"] is None


def test_node_update_to_update_data_selective():
    from src.api.v2.nodes.types import NodeUpdateRequest
    data = {"name": "New Name"}
    req, err = NodeUpdateRequest.from_json(data)
    assert err is None
    update = req.to_update_data()
    assert update == {"name": "New Name"}
    assert "disabled" not in update
    assert "ipAddress" not in update
