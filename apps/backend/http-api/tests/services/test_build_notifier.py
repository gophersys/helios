"""Tests for services/build_notifier.py — fire-and-forget build notifications."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestNotifyBuildService:
    """Tests for notify_build_service()."""

    @patch("src.services.build_notifier.requests.post")
    @patch("config.env_config.BUILD_SERVICE_URL", "http://build-svc:8080")
    def test_successful_notification(self, mock_post):
        """Sends POST to build service and succeeds."""
        from src.services.build_notifier import notify_build_service

        mock_post.return_value = MagicMock(status_code=202)

        notify_build_service("job-12345678", priority=50)

        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == "http://build-svc:8080/jobs/notify"
        assert call_args[1]["json"]["jobId"] == "job-12345678"
        assert call_args[1]["json"]["priority"] == 50

    @patch("src.services.build_notifier.requests.post")
    @patch("config.env_config.BUILD_SERVICE_URL", "http://build-svc:8080")
    def test_non_202_status_logs_warning(self, mock_post):
        """Non-202 response is logged as warning but does not raise."""
        from src.services.build_notifier import notify_build_service

        mock_post.return_value = MagicMock(status_code=500, text="Internal Error")

        # Should not raise
        notify_build_service("job-12345678")

    @patch("src.services.build_notifier.requests.post")
    @patch("config.env_config.BUILD_SERVICE_URL", "http://build-svc:8080")
    def test_request_exception_handled(self, mock_post):
        """RequestException is caught and logged without raising."""
        import requests
        from src.services.build_notifier import notify_build_service

        mock_post.side_effect = requests.RequestException("Connection refused")

        # Should not raise
        notify_build_service("job-12345678")

    @patch("config.env_config.BUILD_SERVICE_URL", "")
    def test_no_url_skips_notification(self):
        """Skips notification when BUILD_SERVICE_URL is empty."""
        from src.services.build_notifier import notify_build_service

        # Should not raise or make any HTTP calls
        notify_build_service("job-12345678")

    @patch("config.env_config.BUILD_SERVICE_URL", None)
    def test_none_url_skips_notification(self):
        """Skips notification when BUILD_SERVICE_URL is None."""
        from src.services.build_notifier import notify_build_service

        notify_build_service("job-12345678")
