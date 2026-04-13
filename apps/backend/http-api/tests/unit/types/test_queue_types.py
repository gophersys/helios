"""Tests for validation queue request type validation."""
import pytest
from api.v2.runs.types import QueueEntryCreateRequest, QueueEntryUpdateRequest


class TestQueueEntryCreateRequest:
    def test_valid_create(self):
        req, err = QueueEntryCreateRequest.from_json({
            "assetSetId": "pipe-123",
            "stage": 5,
        })
        assert err is None
        assert req.assetSetId == "pipe-123"
        assert req.stage == 5
        assert req.priority is None

    def test_missing_asset_set_id(self):
        _, err = QueueEntryCreateRequest.from_json({"stage": 1})
        assert err is not None
        assert "assetSetId" in err

    def test_missing_stage(self):
        _, err = QueueEntryCreateRequest.from_json({"assetSetId": "p1"})
        assert err is not None
        assert "stage" in err.lower()

    def test_invalid_stage(self):
        _, err = QueueEntryCreateRequest.from_json({"assetSetId": "p1", "stage": 6})
        assert err is not None

    def test_with_priority(self):
        req, err = QueueEntryCreateRequest.from_json({
            "assetSetId": "p1",
            "stage": 4,
            "priority": 75,
            "reason": "regression run",
        })
        assert err is None
        assert req.priority == 75
        assert req.reason == "regression run"

    def test_invalid_priority(self):
        _, err = QueueEntryCreateRequest.from_json({
            "assetSetId": "p1", "stage": 1, "priority": 300,
        })
        assert err is not None

    def test_empty_body(self):
        _, err = QueueEntryCreateRequest.from_json(None)
        assert err is not None


class TestQueueEntryUpdateRequest:
    def test_valid_update_status(self):
        req, err = QueueEntryUpdateRequest.from_json({"status": "ASSIGNED"})
        assert err is None
        assert req.status == "ASSIGNED"

    def test_invalid_status(self):
        _, err = QueueEntryUpdateRequest.from_json({"status": "INVALID"})
        assert err is not None

    def test_update_priority(self):
        req, err = QueueEntryUpdateRequest.from_json({"priority": 100})
        assert err is None

    def test_empty_update(self):
        _, err = QueueEntryUpdateRequest.from_json({})
        assert err is not None

    def test_null_body(self):
        _, err = QueueEntryUpdateRequest.from_json(None)
        assert err is not None
