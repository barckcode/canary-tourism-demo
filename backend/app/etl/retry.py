"""Retry utility with exponential backoff for ETL HTTP calls.

Provides an async helper that wraps httpx HTTP requests with automatic
retry on transient errors (connection failures, timeouts, 5xx status codes).
Permanent errors like 4xx are not retried.
"""

import asyncio
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Default retry configuration
DEFAULT_MAX_RETRIES = 3
DEFAULT_BASE_DELAY = 5.0
DEFAULT_BACKOFF_MULTIPLIER = 3.0


def _is_retryable_error(exc: Exception) -> bool:
    """Determine whether an exception represents a transient, retryable error.

    Retryable errors include:
    - Connection errors (httpx.ConnectError, httpx.ConnectTimeout)
    - Read/write timeouts (httpx.ReadTimeout, httpx.WriteTimeout, httpx.PoolTimeout)
    - HTTP 5xx server errors

    Non-retryable errors include:
    - HTTP 4xx client errors (bad request, not found, etc.)
    - Decoding errors, invalid URLs, etc.
    """
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    if isinstance(exc, (httpx.ConnectError, httpx.ConnectTimeout)):
        return True
    if isinstance(exc, (httpx.ReadTimeout, httpx.WriteTimeout, httpx.PoolTimeout)):
        return True
    if isinstance(exc, httpx.TimeoutException):
        return True
    return False


def _compute_delay(attempt: int, base_delay: float, multiplier: float) -> float:
    """Compute the delay in seconds for a given retry attempt.

    Uses exponential backoff: delay = base_delay * multiplier^attempt
    Attempt 0 -> base_delay (e.g. 5s)
    Attempt 1 -> base_delay * multiplier (e.g. 15s)
    Attempt 2 -> base_delay * multiplier^2 (e.g. 45s)
    """
    return base_delay * (multiplier ** attempt)


async def async_fetch_with_retry(
    client: httpx.AsyncClient,
    url: str,
    *,
    max_retries: int = DEFAULT_MAX_RETRIES,
    base_delay: float = DEFAULT_BASE_DELAY,
    backoff_multiplier: float = DEFAULT_BACKOFF_MULTIPLIER,
    source_name: str = "HTTP",
    **kwargs: Any,
) -> httpx.Response:
    """Perform an HTTP GET request with automatic retry on transient failures.

    Args:
        client: The httpx async client to use for the request.
        url: The URL to fetch.
        max_retries: Maximum number of retry attempts (default 3).
        base_delay: Base delay in seconds before the first retry (default 5.0).
        backoff_multiplier: Multiplier for exponential backoff (default 3.0).
        source_name: Human-readable source name for log messages (e.g. "ISTAC").
        **kwargs: Additional keyword arguments passed to ``client.get()``.

    Returns:
        The successful httpx.Response.

    Raises:
        httpx.HTTPStatusError: If a non-retryable HTTP error occurs (4xx).
        httpx.RequestError: If all retry attempts are exhausted.
    """
    last_exception: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            resp = await client.get(url, **kwargs)
            resp.raise_for_status()
            return resp
        except Exception as exc:
            last_exception = exc

            if not _is_retryable_error(exc):
                raise

            if attempt < max_retries:
                delay = _compute_delay(attempt, base_delay, backoff_multiplier)
                logger.warning(
                    "Retry %d/%d for %s after %.0fs delay: %s: %s",
                    attempt + 1,
                    max_retries,
                    source_name,
                    delay,
                    type(exc).__name__,
                    exc,
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    "All %d retries exhausted for %s: %s: %s",
                    max_retries,
                    source_name,
                    type(exc).__name__,
                    exc,
                )
                raise
    # This should never be reached, but satisfy type checkers
    raise last_exception  # type: ignore[misc]
