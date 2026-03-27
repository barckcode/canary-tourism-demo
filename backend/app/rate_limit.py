"""Shared rate limiter instance for the application."""

from starlette.requests import Request
from slowapi import Limiter


def _get_real_client_ip(request: Request) -> str:
    """Extract the real client IP, checking X-Forwarded-For for proxy setups."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "127.0.0.1"


limiter = Limiter(key_func=_get_real_client_ip)
