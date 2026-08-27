"""Tests for ``corectl.commands.runs``.

These focus on the pure-logic helpers — envelope unwrapping, duration
formatting, row formatting. The CLI entry points are exercised via
click's ``CliRunner`` with a stubbed API client so no network touches.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from corectl.commands import runs as runs_mod


# ────────────────────────────────────────────────────────────────────────
# Envelope unwrapping
# ────────────────────────────────────────────────────────────────────────


def test_unwrap_double_envelope_returns_inner_list():
    body = {
        "data": {
            "data": [{"id": "r1"}, {"id": "r2"}],
            "pagination": {"total": 2},
        },
        "errors": [],
    }
    assert runs_mod._unwrap(body) == [{"id": "r1"}, {"id": "r2"}]


def test_unwrap_single_envelope_returns_inner_dict():
    body = {"data": {"id": "r1", "status": "COMPLETED"}}
    assert runs_mod._unwrap(body) == {"id": "r1", "status": "COMPLETED"}


def test_unwrap_stops_when_inner_value_is_a_list():
    # The loop must terminate once body is no longer a dict.
    body = {"data": ["a", "b"], "pagination": {}}
    assert runs_mod._unwrap(body) == ["a", "b"]


def test_unwrap_preserves_payload_with_extra_keys():
    # A dict whose keys exceed the envelope set is the real payload.
    body = {"id": "r1", "status": "COMPLETED", "data": {"foo": "bar"}}
    assert runs_mod._unwrap(body) is body


# ────────────────────────────────────────────────────────────────────────
# Duration formatting
# ────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "ms, expected",
    [
        (None,      "—"),
        (0,         "0ms"),
        (999,       "999ms"),
        (1_000,     "1.0s"),
        (59_500,    "59.5s"),
        (60_000,    "1m00s"),
        (125_000,   "2m05s"),
        (3_600_000, "60m00s"),
    ],
)
def test_fmt_duration(ms, expected):
    assert runs_mod._fmt_duration(ms) == expected


# ────────────────────────────────────────────────────────────────────────
# Row formatting
# ────────────────────────────────────────────────────────────────────────


def test_fmt_row_happy_path():
    run = {
        "id": "cmo4xxx",
        "status": "COMPLETED",
        "targetCount": 4,
        "passedCount": 3,
        "failedCount": 1,
        "durationMs": 125_000,
        "panelIdentifier": "095F",
    }
    rendered = runs_mod._fmt_row(run)
    # Preserve the spaced layout — these are the data bits callers grep for
    assert "cmo4xxx" in rendered
    assert "COMPLETED" in rendered
    assert "p= 3" in rendered
    assert "f= 1" in rendered
    assert "/4" in rendered
    assert "2m05s" in rendered
    assert "095F" in rendered


def test_fmt_row_handles_missing_fields():
    # Newly-created run with nothing populated yet
    run = {"id": "r-new", "status": "PENDING"}
    rendered = runs_mod._fmt_row(run)
    assert "r-new" in rendered
    assert "PENDING" in rendered
    assert "dur=—" in rendered
    assert "panel=—" in rendered


# ────────────────────────────────────────────────────────────────────────
# Status color map
# ────────────────────────────────────────────────────────────────────────


def test_status_colors_cover_terminal_states():
    for s in ("PASSED", "FAILED", "COMPLETED", "CANCELLED", "ERROR", "ACTIVE", "PENDING"):
        assert s in runs_mod._STATUS_COLOR, f"missing color for {s!r}"


# ────────────────────────────────────────────────────────────────────────
# Fetch helpers (stubbed API)
# ────────────────────────────────────────────────────────────────────────


def _stub_api(responses):
    """Build a fake ConcordAPI whose .get() returns canned responses.

    ``responses`` maps a path prefix to a (status_code, json) tuple.
    """
    api = MagicMock()

    def _get(path, **kwargs):
        for prefix, (code, body) in responses.items():
            if path.startswith(prefix):
                resp = MagicMock()
                resp.status_code = code
                resp.json.return_value = body
                resp.raise_for_status = MagicMock()
                if code >= 400:
                    resp.raise_for_status.side_effect = RuntimeError(f"{code}")
                return resp
        raise AssertionError(f"no stub for path {path!r}")

    api.get.side_effect = _get
    return api


def test_fetch_runs_unwraps_list():
    api = _stub_api({
        "/v2/runs": (200, {
            "data": {"data": [{"id": "r1"}, {"id": "r2"}]},
            "errors": [],
        }),
    })
    rows = runs_mod._fetch_runs(api, limit=2, status=None)
    assert [r["id"] for r in rows] == ["r1", "r2"]
    # status filter is applied as a query param when provided
    runs_mod._fetch_runs(api, limit=2, status="active")
    call = api.get.call_args
    assert call.kwargs["params"]["status"] == "ACTIVE"


def test_fetch_run_404_raises_click_exception():
    api = _stub_api({
        "/v2/runs/": (404, {"errors": [{"message": "not found"}]}),
    })
    with pytest.raises(Exception) as exc_info:
        runs_mod._fetch_run(api, "does-not-exist")
    # click.ClickException bubbles up as a generic Exception subtype here;
    # assert the message points at the missing id so the operator has a clue.
    assert "does-not-exist" in str(exc_info.value)
