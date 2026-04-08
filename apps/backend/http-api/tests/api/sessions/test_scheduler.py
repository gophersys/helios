"""Extended tests for scheduler.py — _create_job_api_key, _create_validation_run, on_fixture_freed."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import make_obj


class TestCreateJobApiKey:
    def test_creates_api_key_with_system_user(self):
        from src.api.v2.sessions.scheduler import _create_job_api_key
        db = MagicMock()
        db.user.find_first.return_value = make_obj(id="sys-user-1")
        db.apikey.create.return_value = None

        key = _create_job_api_key(db, "entry-1")
        assert key.startswith("ck_queue_")
        db.apikey.create.assert_called_once()
        call_data = db.apikey.create.call_args[1]["data"]
        assert call_data["userId"] == "sys-user-1"

    def test_fallback_to_any_user(self):
        from src.api.v2.sessions.scheduler import _create_job_api_key
        db = MagicMock()
        # First call for system user returns None, second call returns any user
        db.user.find_first.side_effect = [None, make_obj(id="fallback-user")]
        db.apikey.create.return_value = None

        key = _create_job_api_key(db, "entry-1")
        assert key.startswith("ck_queue_")

    def test_no_users_uses_none(self):
        from src.api.v2.sessions.scheduler import _create_job_api_key
        db = MagicMock()
        db.user.find_first.return_value = None
        db.apikey.create.return_value = None

        key = _create_job_api_key(db, "entry-1")
        assert key.startswith("ck_queue_")
        call_data = db.apikey.create.call_args[1]["data"]
        assert call_data["userId"] is None


class TestCreateValidationRun:
    def test_product_not_found_returns_none(self):
        from src.api.v2.sessions.scheduler import _create_validation_run
        db = MagicMock()
        db.product.find_first.return_value = None
        build_run = make_obj(product="alpha")
        fixture = make_obj(id="fix-1", slots=[], stationId="st-1")

        result = _create_validation_run(db, "entry-1", build_run, fixture, 4, "regression")
        assert result is None

    def test_no_users_returns_none(self):
        from src.api.v2.sessions.scheduler import _create_validation_run
        db = MagicMock()
        db.product.find_first.return_value = make_obj(id="prod-1")
        db.user.find_first.return_value = None
        build_run = make_obj(product="alpha")
        fixture = make_obj(id="fix-1", slots=[], stationId="st-1")

        result = _create_validation_run(db, "entry-1", build_run, fixture, 4, "regression")
        assert result is None

    def test_creates_session_and_device(self):
        from src.api.v2.sessions.scheduler import _create_validation_run
        db = MagicMock()
        db.product.find_first.return_value = make_obj(id="prod-1")
        db.user.find_first.return_value = make_obj(id="sys-user-1")

        node = make_obj(ipAddress="10.4.45.33")
        slot = make_obj(dutSnr="0964", dutDeviceId="dev-1", node=node)
        fixture = make_obj(id="fix-1", slots=[slot], stationId="st-1")
        build_run = make_obj(id="run-1", product="alpha")

        session = make_obj(id="session-1")
        db.session.create.return_value = session

        result = _create_validation_run(db, "entry-1", build_run, fixture, 4, "regression")
        assert result == "session-1"
        db.session.create.assert_called_once()
        db.device.create.assert_called_once()


class TestOnFixtureFreed:
    @patch("src.api.v2.sessions.scheduler.schedule_queue")
    @patch("src.api.v2.sessions.scheduler.get_db_client")
    def test_fixture_not_found_does_nothing(self, mock_get_db, mock_schedule):
        from src.api.v2.sessions.scheduler import on_fixture_freed
        db = MagicMock()
        mock_get_db.return_value = db
        db.fixture.find_unique.return_value = None

        on_fixture_freed("fix-1")
        mock_schedule.assert_not_called()

    @patch("src.api.v2.sessions.scheduler.schedule_queue")
    @patch("src.api.v2.sessions.scheduler.get_db_client")
    def test_fixture_not_available_does_nothing(self, mock_get_db, mock_schedule):
        from src.api.v2.sessions.scheduler import on_fixture_freed
        db = MagicMock()
        mock_get_db.return_value = db
        db.fixture.find_unique.return_value = make_obj(id="fix-1", status="LOCKED")

        on_fixture_freed("fix-1")
        mock_schedule.assert_not_called()

    @patch("src.api.v2.sessions.scheduler.schedule_queue")
    @patch("src.api.v2.sessions.scheduler.get_db_client")
    def test_available_fixture_triggers_schedule(self, mock_get_db, mock_schedule):
        from src.api.v2.sessions.scheduler import on_fixture_freed
        db = MagicMock()
        mock_get_db.return_value = db
        db.fixture.find_unique.return_value = make_obj(id="fix-1", status="AVAILABLE")

        on_fixture_freed("fix-1")
        mock_schedule.assert_called_once()
