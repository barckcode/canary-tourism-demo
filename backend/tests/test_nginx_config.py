"""Tests for nginx configuration security headers and gzip settings.

Validates that frontend/nginx.conf includes required security headers,
gzip compression, and has valid directive structure.
"""

import os

NGINX_CONF_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "frontend", "nginx.conf"
)


def _read_nginx_conf() -> str:
    with open(NGINX_CONF_PATH) as f:
        return f.read()


class TestNginxSecurityHeaders:
    """Verify that all required security headers are present in nginx.conf."""

    def test_hsts_header(self):
        conf = _read_nginx_conf()
        assert 'Strict-Transport-Security' in conf
        assert 'max-age=31536000' in conf
        assert 'includeSubDomains' in conf

    def test_csp_header(self):
        conf = _read_nginx_conf()
        assert 'Content-Security-Policy' in conf
        assert "default-src 'self'" in conf
        assert "script-src 'self'" in conf
        assert "style-src 'self'" in conf
        assert "img-src 'self'" in conf

    def test_csp_allows_map_tiles(self):
        conf = _read_nginx_conf()
        assert 'tile.openstreetmap.org' in conf
        assert 'basemaps.cartocdn.com' in conf

    def test_csp_allows_inline_styles(self):
        conf = _read_nginx_conf()
        assert "'unsafe-inline'" in conf

    def test_csp_allows_data_uris(self):
        conf = _read_nginx_conf()
        assert 'data:' in conf

    def test_permissions_policy_header(self):
        conf = _read_nginx_conf()
        assert 'Permissions-Policy' in conf
        assert 'camera=()' in conf
        assert 'microphone=()' in conf
        assert 'geolocation=()' in conf

    def test_x_frame_options(self):
        conf = _read_nginx_conf()
        assert 'X-Frame-Options' in conf
        assert 'SAMEORIGIN' in conf

    def test_x_content_type_options(self):
        conf = _read_nginx_conf()
        assert 'X-Content-Type-Options' in conf
        assert 'nosniff' in conf

    def test_referrer_policy(self):
        conf = _read_nginx_conf()
        assert 'Referrer-Policy' in conf
        assert 'strict-origin-when-cross-origin' in conf


class TestNginxGzip:
    """Verify gzip compression is properly configured."""

    def test_gzip_enabled(self):
        conf = _read_nginx_conf()
        assert 'gzip on' in conf

    def test_gzip_types(self):
        conf = _read_nginx_conf()
        assert 'gzip_types' in conf
        for content_type in [
            'text/plain',
            'text/css',
            'application/json',
            'application/javascript',
        ]:
            assert content_type in conf, f"gzip_types missing {content_type}"

    def test_gzip_min_length(self):
        conf = _read_nginx_conf()
        assert 'gzip_min_length' in conf


class TestNginxStructure:
    """Basic structural validation of nginx.conf."""

    def test_server_block_exists(self):
        conf = _read_nginx_conf()
        assert 'server {' in conf

    def test_proxy_pass_to_backend(self):
        conf = _read_nginx_conf()
        assert 'proxy_pass http://backend:8000/api/' in conf

    def test_balanced_braces(self):
        conf = _read_nginx_conf()
        assert conf.count('{') == conf.count('}'), "Unbalanced braces in nginx.conf"

    def test_all_directives_end_with_semicolon_or_brace(self):
        """Each non-empty, non-comment line should end with ; or { or }."""
        conf = _read_nginx_conf()
        for i, line in enumerate(conf.splitlines(), 1):
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                continue
            assert stripped.endswith((';', '{', '}')), (
                f"Line {i} does not end with ; or brace: {stripped!r}"
            )
