"""Unit tests for the validation queue scheduler.

Tests schedule_queue and on_build_complete logic using a mocked DB client.
K8s job creation is mocked throughout.
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import make_obj

NOW = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)


def _make_build_run(**overrides):
    defaults = dict(
        id="run-1",
        product="alpha",
        productId="prod-1",
        board="alpha_b0",
        branch="main",
        commitSha="abc123",
        status="SUCCESS",
        stageConfigId="stage-1",
        builds=[],
    )
    defaults.update(overrides)
    return make_obj(**defaults)


def _make_stage_config(**overrides):
    defaults = dict(
        id="stage-1",
        stage=4,
        requiresBench=True,
        priority=50,
    )
    defaults.update(overrides)
    return make_obj(**defaults)


def _make_fixture(**overrides):
    defaults = dict(
        id="fix-1",
        lockState="FREE",
        active=True,
        stationId="station-1",
        product=make_obj(id="prod-1", slug="alpha"),
        slots=[],
        metadata={},
    )
    defaults.update(overrides)
    return make_obj(**defaults)


def _make_queue_entry(**overrides):
    defaults = dict(
        id="entry-1",
        assetSetId="as-1",
        stage=4,
        priority=50,
        status="QUEUED",
        fixtureId=None,
        assetSet=make_obj(id="as-1", buildRunId="run-1", status="COMPLETE",
                          productId="prod-1",
                          product=make_obj(id="prod-1", name="Alpha", slug="alpha"),
                          buildRun=_make_build_run()),
        stageConfig=_make_stage_config(),
    )
    defaults.update(overrides)
    return make_obj(**defaults)


@pytest.fixture
def mock_db():
    """Fresh MockPrismaClient for direct service tests."""
    from tests.conftest import MockPrismaClient
    import src.services.database.prisma as prisma_module
    client = MockPrismaClient()
    original = prisma_module.appPostgresClient
    prisma_module.appPostgresClient = client
    yield client
    prisma_module.appPostgresClient = original


class TestScheduleQueue:
    """Tests for schedule_queue()."""

    def test_returns_empty_when_no_queued_entries(self, mock_db):
        """schedule_queue returns empty list when queue is empty."""
        mock_db.validationqueueentry.find_many.return_value = []

        from src.api.v2.runs.scheduler import schedule_queue
        result = schedule_queue()

        assert result == []

    def test_returns_empty_when_no_available_fixtures(self, mock_db):
        """schedule_queue returns empty list when no fixtures are available."""
        mock_db.validationqueueentry.find_many.return_value = [_make_queue_entry()]
        mock_db.fixture.find_many.return_value = []

        from src.api.v2.runs.scheduler import schedule_queue
        result = schedule_queue()

        assert result == []

    def test_assigns_matching_fixture_to_entry(self, mock_db):
        """schedule_queue assigns a fixture matching the entry's product slug."""
        entry = _make_queue_entry()
        fixture = _make_fixture()
        mock_db.validationqueueentry.find_many.return_value = [entry]
        mock_db.fixture.find_many.return_value = [fixture]
        mock_db.validationqueueentry.update.return_value = entry
        mock_db.fixture.update.return_value = fixture

        with patch("api.v2.runs.scheduler.log_audit"), \
             patch("api.v2.runs.scheduler._trigger_validation_job", return_value="job-abc"):
            from src.api.v2.runs.scheduler import schedule_queue
            result = schedule_queue()

        assert len(result) == 1
        assert result[0]["entryId"] == "entry-1"
        assert result[0]["fixtureId"] == "fix-1"

    def test_does_not_assign_mismatched_product(self, mock_db):
        """schedule_queue skips fixtures whose product slug does not match the entry."""
        entry = _make_queue_entry()
        wrong_fixture = _make_fixture(product=make_obj(id="prod-2", slug="beta"))
        mock_db.validationqueueentry.find_many.return_value = [entry]
        mock_db.fixture.find_many.return_value = [wrong_fixture]

        from src.api.v2.runs.scheduler import schedule_queue
        result = schedule_queue()

        assert result == []
        mock_db.validationqueueentry.update.assert_not_called()

    def test_does_not_double_assign_same_fixture(self, mock_db):
        """schedule_queue does not assign the same fixture to two entries in one round."""
        entry1 = _make_queue_entry(id="entry-1")
        entry2 = _make_queue_entry(id="entry-2")
        fixture = _make_fixture()
        mock_db.validationqueueentry.find_many.return_value = [entry1, entry2]
        mock_db.fixture.find_many.return_value = [fixture]
        mock_db.validationqueueentry.update.return_value = entry1
        mock_db.fixture.update.return_value = fixture

        with patch("api.v2.runs.scheduler.log_audit"), \
             patch("api.v2.runs.scheduler._trigger_validation_job", return_value="job-1"):
            from src.api.v2.runs.scheduler import schedule_queue
            result = schedule_queue()

        # Only one assignment should be made (fixture already taken)
        assert len(result) == 1


class TestOnBuildComplete:
    """Tests for on_build_complete()."""

    def test_returns_none_when_build_run_not_found(self, mock_db):
        """on_build_complete returns None when the build run does not exist."""
        mock_db.buildrun.find_unique.return_value = None

        from src.api.v2.runs.scheduler import on_build_complete
        result = on_build_complete("bad-id")

        assert result is None

    def test_returns_none_when_build_failed(self, mock_db):
        """on_build_complete returns None when any build has FAILED status."""
        failed_build = make_obj(id="build-1", status="FAILED")
        run = _make_build_run(builds=[failed_build], stageConfig=_make_stage_config())
        mock_db.buildrun.find_unique.return_value = run

        from src.api.v2.runs.scheduler import on_build_complete
        result = on_build_complete("run-1")

        assert result is None

    def test_returns_none_when_builds_still_pending(self, mock_db):
        """on_build_complete returns None when builds are still BUILDING."""
        pending_build = make_obj(id="build-1", status="BUILDING")
        run = _make_build_run(builds=[pending_build], stageConfig=_make_stage_config())
        mock_db.buildrun.find_unique.return_value = run

        from src.api.v2.runs.scheduler import on_build_complete
        result = on_build_complete("run-1")

        assert result is None

    def test_returns_none_when_stage_does_not_require_bench(self, mock_db):
        """on_build_complete skips queue creation for stages that don't need a bench."""
        no_bench_config = _make_stage_config(requiresBench=False)
        success_build = make_obj(id="build-1", status="SUCCESS")
        run = _make_build_run(builds=[success_build])
        run.stageConfig = no_bench_config
        mock_db.buildrun.find_unique.return_value = run

        from src.api.v2.runs.scheduler import on_build_complete
        result = on_build_complete("run-1")

        assert result is None

    def test_returns_existing_entry_when_already_queued(self, mock_db):
        """on_build_complete returns existing entry ID if run is already queued."""
        success_build = make_obj(id="build-1", status="SUCCESS")
        run = _make_build_run(builds=[success_build], stageConfig=_make_stage_config())
        existing_entry = make_obj(id="entry-existing", status="QUEUED")
        mock_db.buildrun.find_unique.return_value = run
        mock_db.assetset.find_first.return_value = make_obj(id="as-1", buildRunId="run-1")
        mock_db.validationqueueentry.find_first.return_value = existing_entry

        from src.api.v2.runs.scheduler import on_build_complete
        result = on_build_complete("run-1")

        assert result == "entry-existing"
        mock_db.validationqueueentry.create.assert_not_called()

    def test_creates_queue_entry_when_all_builds_succeed(self, mock_db):
        """on_build_complete creates a queue entry when all builds succeed."""
        success_build = make_obj(id="build-1", status="SUCCESS")
        run = _make_build_run(builds=[success_build], stageConfig=_make_stage_config())
        mock_db.buildrun.find_unique.return_value = run
        mock_db.assetset.find_first.return_value = make_obj(id="as-1", buildRunId="run-1")
        mock_db.validationqueueentry.find_first.return_value = None  # not yet queued
        new_entry = make_obj(id="entry-new", status="QUEUED")
        mock_db.validationqueueentry.create.return_value = new_entry
        mock_db.validationqueueentry.find_many.return_value = []  # for schedule_queue
        mock_db.fixture.find_many.return_value = []

        with patch("api.v2.runs.scheduler.log_audit"):
            from src.api.v2.runs.scheduler import on_build_complete
            result = on_build_complete("run-1")

        assert result == "entry-new"
        mock_db.validationqueueentry.create.assert_called_once()
