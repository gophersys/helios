"""Pin the MTIB env-var contract: validation fixtures get motion enabled,
manufacturing fixtures don't. Regression test for the MOTION_ENABLED bug
where every MTIB came up with motion=false because env was hard-coded
to {} on the deploy path.
"""

from types import SimpleNamespace

from src.api.v2.fixtures.fixtures import _mtib_env_for_fixture
from src.api.v2.nodes.nodes import _deploy_mtib_for_node


def _fx(type_: str):
    return SimpleNamespace(id="fix-1", type=type_)


def test_mtib_env_validation_fixture_enables_motion():
    env = _mtib_env_for_fixture(_fx("VALIDATION"))
    assert env == {"MOTION_ENABLED": "true"}


def test_mtib_env_manufacturing_fixture_disables_motion():
    env = _mtib_env_for_fixture(_fx("MANUFACTURING"))
    assert env == {"MOTION_ENABLED": "false"}


def test_mtib_env_unknown_type_disables_motion():
    # Defensive default — only VALIDATION turns motion on.
    env = _mtib_env_for_fixture(_fx("WHATEVER"))
    assert env == {"MOTION_ENABLED": "false"}


def test_standalone_node_deploy_uses_node_type_for_motion(monkeypatch):
    # The standalone-node path mirrors the fixture-bound path's contract.
    seen = {}

    def fake_create(node_hostname, fixture_id, deployment_id, slot_index, config):
        seen["config"] = config
        return "deploy-name"

    monkeypatch.setattr("src.api.v2.nodes.nodes.create_mtib_deployment", fake_create)

    _deploy_mtib_for_node("verdin-imx8mm-test", "VALIDATION")
    assert seen["config"]["env"]["MOTION_ENABLED"] == "true"

    _deploy_mtib_for_node("verdin-imx8mm-test2", "MANUFACTURING")
    assert seen["config"]["env"]["MOTION_ENABLED"] == "false"
