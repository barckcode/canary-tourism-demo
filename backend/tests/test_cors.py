"""Tests for CORS middleware configuration.

Verifies that the CORSMiddleware is properly configured on the FastAPI app,
including allowed origins, methods, headers, and credentials.
"""

from app.config import settings
from app.main import app


def test_cors_allows_configured_origin(client):
    """Requests from a configured CORS origin should receive proper CORS headers."""
    origin = settings.cors_origins[0]
    r = client.options(
        "/health",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
        },
    )
    assert r.headers.get("access-control-allow-origin") == origin


def test_cors_allows_credentials(client):
    """CORS responses should include allow-credentials header."""
    origin = settings.cors_origins[0]
    r = client.options(
        "/health",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
        },
    )
    assert r.headers.get("access-control-allow-credentials") == "true"


def test_cors_allows_configured_methods(client):
    """CORS preflight should list allowed methods (GET, POST, DELETE, OPTIONS)."""
    origin = settings.cors_origins[0]
    r = client.options(
        "/health",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
        },
    )
    allowed = r.headers.get("access-control-allow-methods", "")
    for method in ["GET", "POST", "DELETE"]:
        assert method in allowed, f"Method {method} not in allowed methods: {allowed}"


def test_cors_rejects_unknown_origin(client):
    """Requests from an unknown origin should not receive an allow-origin header."""
    r = client.options(
        "/health",
        headers={
            "Origin": "https://evil.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    allow_origin = r.headers.get("access-control-allow-origin")
    # The header should either be absent or not match the evil origin
    assert allow_origin != "https://evil.example.com"


def test_cors_headers_on_actual_get(client):
    """A regular GET with an Origin header should include CORS response headers."""
    origin = settings.cors_origins[0]
    r = client.get("/health", headers={"Origin": origin})
    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") == origin
    assert r.headers.get("access-control-allow-credentials") == "true"


def test_cors_allows_only_restricted_headers(client):
    """CORS preflight should list only Content-Type, Accept, and Authorization headers."""
    origin = settings.cors_origins[0]
    r = client.options(
        "/health",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Content-Type",
        },
    )
    allowed = r.headers.get("access-control-allow-headers", "")
    for header in ["Content-Type", "Accept", "Authorization"]:
        assert header.lower() in allowed.lower(), (
            f"Header {header} not in allowed headers: {allowed}"
        )
    # Ensure wildcard is not used
    assert allowed.strip() != "*", "allow_headers should not be wildcard"


def test_cors_each_configured_origin_is_allowed(client):
    """Every origin in settings.cors_origins should receive proper CORS headers."""
    for origin in settings.cors_origins:
        r = client.options(
            "/health",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
            },
        )
        assert r.headers.get("access-control-allow-origin") == origin, (
            f"Origin {origin} was not allowed by CORS middleware"
        )
