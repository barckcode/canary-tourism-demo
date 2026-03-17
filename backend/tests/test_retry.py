"""Tests for the ETL retry utility with exponential backoff."""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.etl.retry import (
    DEFAULT_BACKOFF_MULTIPLIER,
    DEFAULT_BASE_DELAY,
    DEFAULT_MAX_RETRIES,
    _compute_delay,
    _is_retryable_error,
    async_fetch_with_retry,
)


# ---------------------------------------------------------------------------
# _is_retryable_error
# ---------------------------------------------------------------------------


class TestIsRetryableError:
    """Tests for the _is_retryable_error helper."""

    def test_5xx_is_retryable(self):
        response = MagicMock()
        response.status_code = 500
        exc = httpx.HTTPStatusError("Server Error", request=MagicMock(), response=response)
        assert _is_retryable_error(exc) is True

    def test_502_is_retryable(self):
        response = MagicMock()
        response.status_code = 502
        exc = httpx.HTTPStatusError("Bad Gateway", request=MagicMock(), response=response)
        assert _is_retryable_error(exc) is True

    def test_503_is_retryable(self):
        response = MagicMock()
        response.status_code = 503
        exc = httpx.HTTPStatusError("Service Unavailable", request=MagicMock(), response=response)
        assert _is_retryable_error(exc) is True

    def test_4xx_is_not_retryable(self):
        response = MagicMock()
        response.status_code = 404
        exc = httpx.HTTPStatusError("Not Found", request=MagicMock(), response=response)
        assert _is_retryable_error(exc) is False

    def test_400_is_not_retryable(self):
        response = MagicMock()
        response.status_code = 400
        exc = httpx.HTTPStatusError("Bad Request", request=MagicMock(), response=response)
        assert _is_retryable_error(exc) is False

    def test_connect_error_is_retryable(self):
        exc = httpx.ConnectError("Connection refused")
        assert _is_retryable_error(exc) is True

    def test_connect_timeout_is_retryable(self):
        exc = httpx.ConnectTimeout("Timed out")
        assert _is_retryable_error(exc) is True

    def test_read_timeout_is_retryable(self):
        exc = httpx.ReadTimeout("Read timed out")
        assert _is_retryable_error(exc) is True

    def test_pool_timeout_is_retryable(self):
        exc = httpx.PoolTimeout("Pool timed out")
        assert _is_retryable_error(exc) is True

    def test_generic_exception_is_not_retryable(self):
        exc = ValueError("something went wrong")
        assert _is_retryable_error(exc) is False


# ---------------------------------------------------------------------------
# _compute_delay
# ---------------------------------------------------------------------------


class TestComputeDelay:
    """Tests for exponential backoff delay computation."""

    def test_first_attempt(self):
        assert _compute_delay(0, 5.0, 3.0) == 5.0

    def test_second_attempt(self):
        assert _compute_delay(1, 5.0, 3.0) == 15.0

    def test_third_attempt(self):
        assert _compute_delay(2, 5.0, 3.0) == 45.0

    def test_custom_base_and_multiplier(self):
        assert _compute_delay(0, 2.0, 2.0) == 2.0
        assert _compute_delay(1, 2.0, 2.0) == 4.0
        assert _compute_delay(2, 2.0, 2.0) == 8.0


# ---------------------------------------------------------------------------
# async_fetch_with_retry
# ---------------------------------------------------------------------------


def _make_response(status_code: int = 200) -> httpx.Response:
    """Create a minimal httpx.Response for testing."""
    return httpx.Response(
        status_code=status_code,
        request=httpx.Request("GET", "https://example.com"),
    )


class TestAsyncFetchWithRetry:
    """Tests for the async_fetch_with_retry function."""

    @pytest.mark.asyncio
    async def test_success_on_first_attempt(self):
        """A successful request should return immediately without retries."""
        mock_client = AsyncMock()
        mock_client.get.return_value = _make_response(200)

        resp = await async_fetch_with_retry(
            mock_client, "https://example.com/data",
            base_delay=0.01, source_name="TEST",
        )

        assert resp.status_code == 200
        assert mock_client.get.call_count == 1

    @pytest.mark.asyncio
    async def test_retry_on_connect_error_then_success(self):
        """Should retry on ConnectError and succeed on the second attempt."""
        mock_client = AsyncMock()
        mock_client.get.side_effect = [
            httpx.ConnectError("Connection refused"),
            _make_response(200),
        ]

        with patch("app.etl.retry.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            resp = await async_fetch_with_retry(
                mock_client, "https://example.com/data",
                base_delay=0.01, source_name="TEST",
            )

        assert resp.status_code == 200
        assert mock_client.get.call_count == 2
        mock_sleep.assert_called_once()

    @pytest.mark.asyncio
    async def test_retry_on_5xx_then_success(self):
        """Should retry on HTTP 500 and succeed on next attempt."""
        error_response = _make_response(500)
        success_response = _make_response(200)

        mock_client = AsyncMock()
        mock_client.get.side_effect = [
            error_response,
            success_response,
        ]

        # The first call will return 500; raise_for_status will raise
        # We need to make the mock return responses that behave correctly
        # with raise_for_status. Use real Response objects.
        resp_500 = httpx.Response(
            status_code=500,
            request=httpx.Request("GET", "https://example.com"),
        )
        resp_200 = httpx.Response(
            status_code=200,
            request=httpx.Request("GET", "https://example.com"),
        )
        mock_client.get.side_effect = [resp_500, resp_200]

        with patch("app.etl.retry.asyncio.sleep", new_callable=AsyncMock):
            resp = await async_fetch_with_retry(
                mock_client, "https://example.com/data",
                base_delay=0.01, source_name="TEST",
            )

        assert resp.status_code == 200
        assert mock_client.get.call_count == 2

    @pytest.mark.asyncio
    async def test_no_retry_on_4xx(self):
        """Should not retry on HTTP 404 -- raises immediately."""
        resp_404 = httpx.Response(
            status_code=404,
            request=httpx.Request("GET", "https://example.com"),
        )
        mock_client = AsyncMock()
        mock_client.get.return_value = resp_404

        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await async_fetch_with_retry(
                mock_client, "https://example.com/data",
                base_delay=0.01, source_name="TEST",
            )

        assert exc_info.value.response.status_code == 404
        assert mock_client.get.call_count == 1

    @pytest.mark.asyncio
    async def test_no_retry_on_400(self):
        """Should not retry on HTTP 400."""
        resp_400 = httpx.Response(
            status_code=400,
            request=httpx.Request("GET", "https://example.com"),
        )
        mock_client = AsyncMock()
        mock_client.get.return_value = resp_400

        with pytest.raises(httpx.HTTPStatusError):
            await async_fetch_with_retry(
                mock_client, "https://example.com/data",
                base_delay=0.01, source_name="TEST",
            )

        assert mock_client.get.call_count == 1

    @pytest.mark.asyncio
    async def test_exhausts_all_retries(self):
        """Should raise after exhausting all retry attempts."""
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.ConnectError("Connection refused")

        with patch("app.etl.retry.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with pytest.raises(httpx.ConnectError):
                await async_fetch_with_retry(
                    mock_client, "https://example.com/data",
                    max_retries=3, base_delay=0.01, source_name="TEST",
                )

        # 1 initial + 3 retries = 4 total calls
        assert mock_client.get.call_count == 4
        # sleep is called for retries 1, 2, and 3
        assert mock_sleep.call_count == 3

    @pytest.mark.asyncio
    async def test_exponential_backoff_delays(self):
        """Verify that retry delays follow exponential backoff pattern."""
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.ConnectError("Connection refused")

        with patch("app.etl.retry.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with pytest.raises(httpx.ConnectError):
                await async_fetch_with_retry(
                    mock_client, "https://example.com/data",
                    max_retries=3, base_delay=5.0, backoff_multiplier=3.0,
                    source_name="TEST",
                )

        delays = [call.args[0] for call in mock_sleep.call_args_list]
        assert delays == [5.0, 15.0, 45.0]

    @pytest.mark.asyncio
    async def test_retry_on_read_timeout_then_success(self):
        """Should retry on ReadTimeout and succeed."""
        mock_client = AsyncMock()
        mock_client.get.side_effect = [
            httpx.ReadTimeout("Read timed out"),
            httpx.ReadTimeout("Read timed out"),
            _make_response(200),
        ]

        with patch("app.etl.retry.asyncio.sleep", new_callable=AsyncMock):
            resp = await async_fetch_with_retry(
                mock_client, "https://example.com/data",
                base_delay=0.01, source_name="TEST",
            )

        assert resp.status_code == 200
        assert mock_client.get.call_count == 3

    @pytest.mark.asyncio
    async def test_kwargs_passed_to_client(self):
        """Extra kwargs should be forwarded to client.get()."""
        mock_client = AsyncMock()
        mock_client.get.return_value = _make_response(200)

        await async_fetch_with_retry(
            mock_client, "https://example.com/data",
            base_delay=0.01, source_name="TEST",
            timeout=30.0, params={"q": "test"},
        )

        mock_client.get.assert_called_once_with(
            "https://example.com/data",
            timeout=30.0, params={"q": "test"},
        )

    @pytest.mark.asyncio
    async def test_max_retries_zero_no_retry(self):
        """With max_retries=0, should not retry at all."""
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.ConnectError("Connection refused")

        with pytest.raises(httpx.ConnectError):
            await async_fetch_with_retry(
                mock_client, "https://example.com/data",
                max_retries=0, base_delay=0.01, source_name="TEST",
            )

        assert mock_client.get.call_count == 1
