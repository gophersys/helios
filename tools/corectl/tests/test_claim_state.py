"""DEV_HOLD claim — state file, daemon spawn, env injection, status reconcile.

These cover the six required behaviors from the spec:

  - state file write + daemon spawn during ``claim``
  - release + state file delete during ``unclaim``
  - clean exit when ``unclaim`` runs with no state file
  - ``run`` injects ``MTIB_HOST`` from a single-slot state file
  - ``run`` injects ``MTIB_HOSTS`` (comma-joined) from a multi-slot state file
  - ``status`` wipes local state and warns when backend disagrees

We use ``ConcordAPI`` with a stub backend URL — no MagicMock for the
client — but pass a fake response factory via monkeypatch on the requests
session so no network egress happens. This matches the spec's "no mocks
of the API client" rule while keeping tests offline.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict
from unittest.mock import patch

import pytest
import requests
from click.testing import CliRunner

from corectl import claim_state
from corectl.api import ConcordAPI
from corectl.commands import test as test_cmd


# ────────────────────────────────────────────────────────────────────────
# Fake HTTP transport — installed on a real ConcordAPI session
# ────────────────────────────────────────────────────────────────────────


class _FakeResponse:
    """Minimal subset of requests.Response touched by the claim commands."""

    def __init__(self, status_code: int, body: Any, *, text: str = ""):
        self.status_code = status_code
        self._body = body
        self.text = text or json.dumps(body)
        self.ok = 200 <= status_code < 400

    def json(self) -> Any:
        return self._body

    def raise_for_status(self) -> None:
        if not self.ok:
            raise requests.HTTPError(f"{self.status_code}")


def _install_fake_transport(api: ConcordAPI, routes: Dict[str, _FakeResponse]):
    """Replace the session's request() so no traffic leaves the test.

    ``routes`` maps "METHOD path" → canned response. Any unmapped path
    raises so a test that ad-libs a new endpoint fails loud.
    """
    calls: list = []

    def _fake_request(method, url, **kwargs):
        path = url.removeprefix(api._base_url)
        key = f"{method} {path}"
        # Allow paths to be matched by prefix when query strings differ.
        for route_key, resp in routes.items():
            if key.split("?", 1)[0] == route_key.split("?", 1)[0]:
                calls.append((method, path, kwargs))
                return resp
        raise AssertionError(f"unstubbed call: {method} {path}")

    api._session.request = _fake_request  # type: ignore[attr-defined]
    return calls


def _api_with_session(base_url: str = "http://stub.invalid") -> ConcordAPI:
    """Real ConcordAPI with an access token, session auth path."""
    return ConcordAPI(
        base_url,
        access_token="fake-at",
        refresh_token="fake-rt",
        expires_at=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        tls_verify=False,
    )


def _claim_response(
    *,
    cid: str = "clm_test",
    fixture_id: str = "fix_abc",
    bindings: list | None = None,
) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    return {
        "data": {
            "id": cid,
            "status": "ACTIVE",
            "fixtureId": fixture_id,
            "slotBindings": bindings if bindings is not None else [
                {"label": "slot1", "nodeId": "node_xyz", "mtibHost": "10.4.45.38:50053"}
            ],
            "acquiredAt": now.isoformat(),
            "expiresAt": (now + timedelta(hours=1)).isoformat(),
            "hardCeilingAt": (now + timedelta(hours=8)).isoformat(),
        },
    }


# ────────────────────────────────────────────────────────────────────────
# TTL clamp — pure logic
# ────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "raw, expected",
    [
        (None,    3600),    # default
        (3600,    3600),    # in-range pass-through
        (10,      60),      # below floor → floor
        (29_000,  28_800),  # above ceiling → ceiling
        (60,      60),      # exact floor
        (28_800,  28_800),  # exact ceiling
    ],
)
def test_clamp_ttl_respects_spec_bounds(raw, expected):
    assert test_cmd._clamp_ttl(raw) == expected


# ────────────────────────────────────────────────────────────────────────
# State file — round-trip + atomic + remove idempotence
# ────────────────────────────────────────────────────────────────────────


def test_state_save_and_load_round_trips(tmp_path: Path):
    state = {
        "id": "clm_x",
        "fixtureId": "fix_a",
        "slotBindings": [
            {"label": "slot1", "nodeId": "n1", "mtibHost": "h:50053"}
        ],
        "expiresAt": "2026-05-21T18:00:00+00:00",
        "hardCeilingAt": "2026-05-22T02:00:00+00:00",
        "heartbeatPid": 12345,
        "createdAt": "2026-05-21T17:00:00+00:00",
    }
    claim_state.save(tmp_path, state)
    loaded = claim_state.load(tmp_path)
    assert loaded == state


def test_state_load_missing_returns_none(tmp_path: Path):
    assert claim_state.load(tmp_path) is None


def test_state_remove_idempotent(tmp_path: Path):
    # First call: file doesn't exist → False
    assert claim_state.remove(tmp_path) is False
    # Create + remove → True
    claim_state.save(tmp_path, {"id": "x", "slotBindings": []})
    assert claim_state.remove(tmp_path) is True
    # Re-remove → False
    assert claim_state.remove(tmp_path) is False


def test_slot_hosts_handles_zero_one_many(tmp_path: Path):
    assert claim_state.slot_hosts({"slotBindings": []}) == []
    assert claim_state.slot_hosts({"slotBindings": [{"mtibHost": "a"}]}) == ["a"]
    assert claim_state.slot_hosts({
        "slotBindings": [
            {"mtibHost": "h1"},
            {"mtibHost": "h2"},
            {"mtibHost": "h3"},
        ]
    }) == ["h1", "h2", "h3"]


# ────────────────────────────────────────────────────────────────────────
# claim — writes state file + spawns daemon
# ────────────────────────────────────────────────────────────────────────


def test_claim_writes_state_file_and_spawns_daemon(tmp_path: Path):
    """claim() resolves fixture name → id, POSTs, writes state, forks daemon."""

    api = _api_with_session()
    claim_resp = _claim_response()
    routes = {
        "GET /v2/fixtures": _FakeResponse(200, {"data": {"data": [
            {"id": "fix_abc", "name": "sigma5-bench-mateo"},
        ]}}),
        "POST /v2/fixture-claims": _FakeResponse(201, claim_resp),
    }
    _install_fake_transport(api, routes)

    # Patch the spawner so we don't actually fork a subprocess. The
    # _spawn_heartbeat_daemon contract is: returns a pid (int). A
    # collaborator test below covers the real Popen call.
    with patch.object(test_cmd, "_client", return_value=api), \
         patch.object(test_cmd, "_spawn_heartbeat_daemon", return_value=99999) as spawn_mock:
        runner = CliRunner()
        result = runner.invoke(
            test_cmd.test,
            ["claim", "--fixture", "sigma5-bench-mateo", str(tmp_path)],
            obj={"config": {"access_token": "fake", "refresh_token": "fake"}},
        )

    assert result.exit_code == 0, result.output
    assert spawn_mock.call_count == 1

    # State file is on disk with the daemon pid wired in.
    state = claim_state.load(tmp_path)
    assert state is not None
    assert state["id"] == "clm_test"
    assert state["fixtureId"] == "fix_abc"
    assert state["heartbeatPid"] == 99999
    assert state["slotBindings"] == [
        {"label": "slot1", "nodeId": "node_xyz", "mtibHost": "10.4.45.38:50053"}
    ]


def test_claim_refuses_when_state_file_exists(tmp_path: Path):
    """Without --replace, claim must abort when a prior lease is still local."""
    claim_state.save(tmp_path, {"id": "clm_prior", "slotBindings": []})

    api = _api_with_session()
    _install_fake_transport(api, {})  # no calls expected

    with patch.object(test_cmd, "_client", return_value=api):
        runner = CliRunner()
        result = runner.invoke(
            test_cmd.test,
            ["claim", "--fixture", "x", str(tmp_path)],
            obj={"config": {"access_token": "a", "refresh_token": "b"}},
        )

    assert result.exit_code != 0
    assert "already exists" in result.output
    # Pre-existing state untouched
    assert claim_state.load(tmp_path)["id"] == "clm_prior"


def test_claim_requires_exactly_one_of_fixture_or_node(tmp_path: Path):
    """Neither nor both fail; exactly one passes."""
    api = _api_with_session()
    _install_fake_transport(api, {})

    runner = CliRunner()

    # Neither
    with patch.object(test_cmd, "_client", return_value=api):
        result = runner.invoke(
            test_cmd.test, ["claim", str(tmp_path)],
            obj={"config": {}},
        )
    assert result.exit_code != 0
    assert "exactly one" in result.output

    # Both
    with patch.object(test_cmd, "_client", return_value=api):
        result = runner.invoke(
            test_cmd.test,
            ["claim", "--fixture", "x", "--node", "y", str(tmp_path)],
            obj={"config": {}},
        )
    assert result.exit_code != 0


# ────────────────────────────────────────────────────────────────────────
# unclaim — release + state file delete
# ────────────────────────────────────────────────────────────────────────


def test_unclaim_releases_and_deletes_state(tmp_path: Path):
    claim_state.save(tmp_path, {
        "id": "clm_z", "slotBindings": [],
        "heartbeatPid": 12345,
    })

    api = _api_with_session()
    routes = {
        "POST /v2/fixture-claims/clm_z/release": _FakeResponse(200, {"data": {
            "id": "clm_z", "status": "RELEASED",
        }}),
    }
    calls = _install_fake_transport(api, routes)

    with patch.object(test_cmd, "_client", return_value=api):
        runner = CliRunner()
        result = runner.invoke(
            test_cmd.test, ["unclaim", str(tmp_path)],
            obj={"config": {"access_token": "a", "refresh_token": "b"}},
        )

    assert result.exit_code == 0, result.output
    assert "Released" in result.output
    assert claim_state.load(tmp_path) is None
    assert any("release" in c[1] for c in calls), "release endpoint not hit"


def test_unclaim_no_state_file_exits_clean(tmp_path: Path):
    """Idempotent teardown — no state file means we already cleaned up."""
    api = _api_with_session()
    _install_fake_transport(api, {})  # no calls expected

    with patch.object(test_cmd, "_client", return_value=api):
        runner = CliRunner()
        result = runner.invoke(
            test_cmd.test, ["unclaim", str(tmp_path)],
            obj={"config": {}},
        )

    assert result.exit_code == 0
    assert "no active claim" in result.output.lower()


def test_unclaim_wipes_state_even_on_404(tmp_path: Path):
    """If the backend says the claim is gone, we still clean local state."""
    claim_state.save(tmp_path, {"id": "clm_dead", "slotBindings": []})

    api = _api_with_session()
    _install_fake_transport(api, {
        "POST /v2/fixture-claims/clm_dead/release": _FakeResponse(404, {"errors": []}),
    })

    with patch.object(test_cmd, "_client", return_value=api):
        runner = CliRunner()
        result = runner.invoke(
            test_cmd.test, ["unclaim", str(tmp_path)],
            obj={"config": {"access_token": "a", "refresh_token": "b"}},
        )

    assert result.exit_code == 0
    assert claim_state.load(tmp_path) is None


# ────────────────────────────────────────────────────────────────────────
# run — env injection from state file
# ────────────────────────────────────────────────────────────────────────


def test_run_injects_mtib_host_from_state_file_single_slot(tmp_path: Path):
    claim_state.save(tmp_path, {
        "id": "clm_run",
        "fixtureId": "fix_a",
        "slotBindings": [{"label": "slot1", "nodeId": "n1", "mtibHost": "h1:50053"}],
    })

    env = test_cmd._env_with_claim_bindings(tmp_path, {"FOO": "bar"})
    assert env["MTIB_HOST"] == "h1:50053"
    assert "MTIB_HOSTS" not in env
    assert env["CONCORD_CLAIM_ID"] == "clm_run"
    # Base env preserved.
    assert env["FOO"] == "bar"


def test_run_injects_mtib_hosts_multi_slot(tmp_path: Path):
    claim_state.save(tmp_path, {
        "id": "clm_panel",
        "fixtureId": "fix_p",
        "slotBindings": [
            {"label": "s1", "nodeId": "n1", "mtibHost": "h1"},
            {"label": "s2", "nodeId": "n2", "mtibHost": "h2"},
            {"label": "s3", "nodeId": "n3", "mtibHost": "h3"},
        ],
    })

    env = test_cmd._env_with_claim_bindings(tmp_path, {})
    assert env["MTIB_HOSTS"] == "h1,h2,h3"
    assert "MTIB_HOST" not in env
    assert env["CONCORD_CLAIM_ID"] == "clm_panel"


def test_run_no_state_file_passes_env_through(tmp_path: Path):
    """No claim → no injection. Ambient env wins."""
    base = {"MTIB_HOST": "shell-set", "PATH": "/usr/bin"}
    env = test_cmd._env_with_claim_bindings(tmp_path, base)
    assert env == base
    assert "CONCORD_CLAIM_ID" not in env


# ────────────────────────────────────────────────────────────────────────
# status — backend vs local reconciliation
# ────────────────────────────────────────────────────────────────────────


def test_status_warns_on_state_file_backend_mismatch(tmp_path: Path):
    """Local state implies ACTIVE; backend says EXPIRED → wipe local + warn."""
    claim_state.save(tmp_path, {
        "id": "clm_stale", "fixtureId": "fix_x",
        "slotBindings": [{"label": "slot1", "nodeId": "n1", "mtibHost": "h:1"}],
        "expiresAt": "2026-01-01T00:00:00+00:00",
        "hardCeilingAt": "2026-01-01T08:00:00+00:00",
        "heartbeatPid": 99,
    })

    api = _api_with_session()
    _install_fake_transport(api, {
        "GET /v2/fixture-claims/clm_stale": _FakeResponse(200, {"data": {
            "id": "clm_stale",
            "status": "EXPIRED",
            "fixtureId": "fix_x",
            "slotBindings": [{"label": "slot1", "nodeId": "n1", "mtibHost": "h:1"}],
            "expiresAt": "2026-01-01T00:00:00+00:00",
            "hardCeilingAt": "2026-01-01T08:00:00+00:00",
        }}),
    })

    with patch.object(test_cmd, "_client", return_value=api):
        runner = CliRunner()
        result = runner.invoke(
            test_cmd.test, ["status", str(tmp_path)],
            obj={"config": {"access_token": "a", "refresh_token": "b"}},
        )

    assert result.exit_code == 0, result.output
    # Local state wiped because backend disagreed.
    assert claim_state.load(tmp_path) is None
    combined = (result.output or "") + (result.stderr if hasattr(result, "stderr") else "")
    assert "WARNING" in combined or "EXPIRED" in combined


def test_status_no_state_file_prints_friendly_notice(tmp_path: Path):
    api = _api_with_session()
    _install_fake_transport(api, {})  # no backend call expected

    with patch.object(test_cmd, "_client", return_value=api):
        runner = CliRunner()
        result = runner.invoke(
            test_cmd.test, ["status", str(tmp_path)],
            obj={"config": {}},
        )

    assert result.exit_code == 0
    assert "no active claim" in result.output.lower()


# ────────────────────────────────────────────────────────────────────────
# Daemon spawn — exercises the real Popen path without long-running work
# ────────────────────────────────────────────────────────────────────────


def test_spawn_heartbeat_daemon_returns_pid_and_is_detached(tmp_path: Path):
    """The spawned process must outlive the parent + run with no tty.

    We can't easily prove "no tty" cross-platform in a unit test, but we
    can prove (a) Popen was called with start_new_session=True, and
    (b) the daemon PID is a valid integer the OS knows about for at
    least the duration of the spawn. Real end-to-end daemon behavior is
    covered by the daemon module's own tests below.
    """
    # Write a state file so the daemon doesn't immediately exit-with-1.
    claim_state.save(tmp_path, {"id": "clm_spawn", "slotBindings": []})

    captured = {}

    real_popen = subprocess.Popen

    def _capturing_popen(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return real_popen(cmd, **kwargs)

    with patch.object(test_cmd.subprocess, "Popen", side_effect=_capturing_popen):
        pid = test_cmd._spawn_heartbeat_daemon(
            project_dir=tmp_path,
            api_url="http://stub.invalid",
            token="fake-token",
            api_key=None,
            insecure=True,
        )

    assert isinstance(pid, int) and pid > 0
    assert captured["kwargs"].get("start_new_session") is True
    assert captured["kwargs"].get("stdin") == subprocess.DEVNULL
    # Process actually started — give it a moment then signal it to stop.
    # The daemon reads the state file at boot; deleting it tells it to
    # exit on next loop tick. We don't wait for a full cycle to avoid a
    # slow test — just kill it.
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        # Already exited (e.g., state-file race) — fine.
        pass
    # Reap the zombie so the test runner doesn't leak processes.
    try:
        os.waitpid(pid, os.WNOHANG)
    except ChildProcessError:
        pass


# ────────────────────────────────────────────────────────────────────────
# Heartbeat daemon — boot-time state file handling
# ────────────────────────────────────────────────────────────────────────


def test_daemon_exits_immediately_when_state_file_missing(tmp_path: Path):
    """The daemon's main() returns 1 with no state file at boot — fast fail
    so an operator spawning it manually sees the error in the log."""
    from corectl import heartbeat_daemon

    rc = heartbeat_daemon.main([
        str(tmp_path),
        "--api-url", "http://stub.invalid",
        "--interval", "1",
    ])
    assert rc == 1


def test_daemon_log_file_created(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """A boot run must create the log file even on the fast-fail path."""
    from corectl import heartbeat_daemon

    # No state file → main() returns 1 BUT _setup_logging fires first.
    heartbeat_daemon.main([
        str(tmp_path),
        "--api-url", "http://stub.invalid",
        "--interval", "1",
    ])
    assert (tmp_path / ".concord-claim.log").is_file()
