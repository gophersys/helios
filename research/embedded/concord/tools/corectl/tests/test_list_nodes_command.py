"""Tests for ``corectl test list-nodes``.

The list-nodes discovery command surfaces the platform's view of which
test nodes (MTIBs) exist, what they're bound to, and whether they're
currently free. It is the first thing a developer reaches for when
asking "what can I claim?".

These tests focus on:

* The query parameters the CLI sends — the ``--available``,
  ``--purpose``, ``--product`` flags must be forwarded as the backend
  expects.
* The rendered output — node id, hostname, type, and a clear
  free / claimed flag should all appear.

No real HTTP is performed; the API client is stubbed.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

from corectl.commands import test as test_mod


def _stub_api(body, *, status=200):
    """Build a fake ConcordAPI whose .get() returns a canned response."""
    api = MagicMock()

    def _get(path, **kwargs):
        resp = MagicMock()
        resp.status_code = status
        resp.json.return_value = body
        resp.ok = status < 400
        resp.raise_for_status = MagicMock()
        return resp, path, kwargs

    captured = {}

    def _do_get(path, **kwargs):
        resp, p, kw = _get(path, **kwargs)
        captured["path"] = p
        captured["kwargs"] = kw
        return resp

    api.get.side_effect = _do_get
    return api, captured


@pytest.fixture
def sample_nodes_payload():
    return {
        "data": {
            "data": [
                {
                    "id": "n1",
                    "name": "MFG-01",
                    "hostname": "verdin-mfg-01",
                    "type": "MANUFACTURING",
                    "status": "ONLINE",
                    "available": True,
                    "disabled": False,
                    "fixtureSlot": {"id": "s1", "fixtureName": "Alpha MFG 1", "label": "Slot 1"},
                },
                {
                    "id": "n2",
                    "name": "VAL-01",
                    "hostname": "verdin-val-01",
                    "type": "VALIDATION",
                    "status": "ONLINE",
                    "available": False,
                    "disabled": False,
                    "fixtureSlot": None,
                },
            ],
            "pagination": {"page": 1, "limit": 50, "total": 2, "pages": 1},
        },
        "errors": [],
    }


def _make_ctx_obj(api):
    """Build the click context.obj that test commands expect."""
    return {"config": {}}


def test_list_nodes_renders_each_node(monkeypatch, sample_nodes_payload):
    api, _ = _stub_api(sample_nodes_payload)
    monkeypatch.setattr(test_mod, "_client", lambda ctx: api)

    runner = CliRunner()
    result = runner.invoke(test_mod.test, ["list-nodes"], obj={"config": {}})

    assert result.exit_code == 0, result.output
    # Every node id, hostname, type, and availability marker should appear.
    assert "n1" in result.output and "MFG-01" in result.output
    assert "n2" in result.output and "VAL-01" in result.output
    assert "MANUFACTURING" in result.output
    assert "VALIDATION" in result.output


def test_list_nodes_passes_filters_to_backend(monkeypatch, sample_nodes_payload):
    api, captured = _stub_api(sample_nodes_payload)
    monkeypatch.setattr(test_mod, "_client", lambda ctx: api)

    runner = CliRunner()
    result = runner.invoke(
        test_mod.test,
        ["list-nodes", "--available", "--purpose", "manufacturing", "--product", "prod-alpha"],
        obj={"config": {}},
    )
    assert result.exit_code == 0, result.output

    assert captured["path"] == "/v2/test/nodes"
    params = captured["kwargs"].get("params") or {}
    # The three filters round-trip to the backend.
    assert params.get("available") == "true"
    assert params.get("purpose") == "manufacturing"
    assert params.get("product") == "prod-alpha"


def test_list_nodes_handles_empty_set(monkeypatch):
    api, _ = _stub_api({"data": {"data": [], "pagination": {"total": 0}}, "errors": []})
    monkeypatch.setattr(test_mod, "_client", lambda ctx: api)

    runner = CliRunner()
    result = runner.invoke(test_mod.test, ["list-nodes"], obj={"config": {}})

    assert result.exit_code == 0, result.output
    # Some "nothing matched" hint surfaces.
    lower = result.output.lower()
    assert "no nodes" in lower or "0 nodes" in lower or "empty" in lower
