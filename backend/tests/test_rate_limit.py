"""Tests for rate limiter client IP extraction."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.rate_limit import _get_real_client_ip


class TestGetRealClientIp:
    """Tests for _get_real_client_ip key function."""

    def _make_request(self, headers=None, client_host=None):
        """Create a mock Starlette Request."""
        request = MagicMock()
        request.headers = headers or {}
        if client_host is not None:
            request.client = MagicMock()
            request.client.host = client_host
        else:
            request.client = None
        return request

    def test_uses_x_forwarded_for_first_ip(self):
        request = self._make_request(
            headers={"X-Forwarded-For": "203.0.113.50, 70.41.3.18, 150.172.238.178"},
            client_host="10.0.0.1",
        )
        assert _get_real_client_ip(request) == "203.0.113.50"

    def test_uses_x_forwarded_for_single_ip(self):
        request = self._make_request(
            headers={"X-Forwarded-For": "203.0.113.50"},
            client_host="10.0.0.1",
        )
        assert _get_real_client_ip(request) == "203.0.113.50"

    def test_strips_whitespace_from_forwarded_ip(self):
        request = self._make_request(
            headers={"X-Forwarded-For": "  203.0.113.50 , 10.0.0.1"},
        )
        assert _get_real_client_ip(request) == "203.0.113.50"

    def test_falls_back_to_client_host(self):
        request = self._make_request(client_host="192.168.1.100")
        assert _get_real_client_ip(request) == "192.168.1.100"

    def test_falls_back_to_localhost_when_no_client(self):
        request = self._make_request()
        assert _get_real_client_ip(request) == "127.0.0.1"

    def test_ignores_empty_x_forwarded_for(self):
        request = self._make_request(
            headers={"X-Forwarded-For": ""},
            client_host="10.0.0.5",
        )
        assert _get_real_client_ip(request) == "10.0.0.5"
