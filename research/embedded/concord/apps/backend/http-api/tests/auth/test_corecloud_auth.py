"""Tests for services/auth/corecloud.py — Core Cloud authentication."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.services.auth.corecloud import (
    authenticate_corecloud,
    _make_auth_request,
    _parse_auth_response,
)


class TestAuthenticateCorecloud:
    @patch("src.services.auth.corecloud.env_config")
    def test_no_auth_url_returns_error(self, mock_config):
        mock_config.AUTH_SERVER_URL = ""
        mock_config.AUTH_SERVER_API_KEY = ""

        result, err = authenticate_corecloud("test@test.com", "password")
        assert result is None
        assert "not configured" in err

    @patch("src.services.auth.corecloud._parse_auth_response")
    @patch("src.services.auth.corecloud._make_auth_request")
    @patch("src.services.auth.corecloud.env_config")
    def test_success_returns_user_info(self, mock_config, mock_make, mock_parse):
        mock_config.AUTH_SERVER_URL = "https://auth.example.com"
        mock_config.AUTH_SERVER_API_KEY = "test-key"
        mock_make.return_value = (MagicMock(), None)
        mock_parse.return_value = ({"accessToken": "tok"}, None)

        result, err = authenticate_corecloud("user@example.com", "pass123")
        assert err is None
        assert result["email"] == "user@example.com"
        assert result["name"] == "user"

    @patch("src.services.auth.corecloud._make_auth_request")
    @patch("src.services.auth.corecloud.env_config")
    def test_request_failure_returns_error(self, mock_config, mock_make):
        mock_config.AUTH_SERVER_URL = "https://auth.example.com"
        mock_config.AUTH_SERVER_API_KEY = ""
        mock_make.return_value = (None, "Auth server unreachable")

        result, err = authenticate_corecloud("user@example.com", "pass")
        assert result is None
        assert err == "Auth server unreachable"

    @patch("src.services.auth.corecloud._parse_auth_response")
    @patch("src.services.auth.corecloud._make_auth_request")
    @patch("src.services.auth.corecloud.env_config")
    def test_parse_failure_returns_error(self, mock_config, mock_make, mock_parse):
        mock_config.AUTH_SERVER_URL = "https://auth.example.com"
        mock_config.AUTH_SERVER_API_KEY = ""
        mock_make.return_value = (MagicMock(), None)
        mock_parse.return_value = (None, "Invalid email or password")

        result, err = authenticate_corecloud("user@example.com", "wrong")
        assert result is None
        assert "Invalid" in err


class TestMakeAuthRequest:
    @patch("src.services.auth.corecloud.requests")
    def test_success(self, mock_requests):
        resp = MagicMock(status_code=200)
        mock_requests.post.return_value = resp

        result, err = _make_auth_request("https://auth.example.com/token", {}, {})
        assert result == resp
        assert err is None

    @patch("src.services.auth.corecloud.requests")
    def test_connection_error(self, mock_requests):
        import requests
        mock_requests.post.side_effect = requests.exceptions.ConnectionError()
        mock_requests.exceptions = requests.exceptions

        result, err = _make_auth_request("https://auth.example.com/token", {}, {})
        assert result is None
        assert "unreachable" in err

    @patch("src.services.auth.corecloud.requests")
    def test_timeout(self, mock_requests):
        import requests
        mock_requests.post.side_effect = requests.exceptions.Timeout()
        mock_requests.exceptions = requests.exceptions

        result, err = _make_auth_request("https://auth.example.com/token", {}, {})
        assert result is None
        assert "timed out" in err

    @patch("src.services.auth.corecloud.requests")
    def test_generic_error(self, mock_requests):
        import requests
        mock_requests.post.side_effect = Exception("unknown error")
        mock_requests.exceptions = requests.exceptions

        result, err = _make_auth_request("https://auth.example.com/token", {}, {})
        assert result is None
        assert "error" in err.lower()


class TestParseAuthResponse:
    def test_401_returns_invalid_credentials(self):
        resp = MagicMock(status_code=401)
        result, err = _parse_auth_response(resp)
        assert result is None
        assert "Invalid" in err

    def test_500_returns_server_error(self):
        resp = MagicMock(status_code=500, text="Internal Server Error")
        result, err = _parse_auth_response(resp)
        assert result is None
        assert "500" in err

    def test_invalid_json_returns_error(self):
        resp = MagicMock(status_code=200)
        resp.json.side_effect = ValueError("no json")
        result, err = _parse_auth_response(resp)
        assert result is None
        assert "Invalid response" in err

    def test_no_token_returns_error(self):
        resp = MagicMock(status_code=200)
        resp.json.return_value = {"data": "no token field"}
        result, err = _parse_auth_response(resp)
        assert result is None
        assert "no token" in err

    def test_access_token_field(self):
        resp = MagicMock(status_code=200)
        resp.json.return_value = {"accessToken": "my-token"}
        result, err = _parse_auth_response(resp)
        assert result is not None
        assert err is None

    def test_jwt_field(self):
        resp = MagicMock(status_code=200)
        resp.json.return_value = {"jwt": "my-jwt-token"}
        result, err = _parse_auth_response(resp)
        assert result is not None
        assert err is None
