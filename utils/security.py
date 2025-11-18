"""Security middleware and utilities."""
from functools import wraps
from flask import redirect, request


def add_security_headers(app):
    """Add security headers to all responses."""

    @app.after_request
    def set_security_headers(resp):
        """Set security headers on every response."""
        # Prevent clickjacking
        resp.headers['X-Frame-Options'] = 'DENY'

        # Prevent MIME type sniffing
        resp.headers['X-Content-Type-Options'] = 'nosniff'

        # Enable XSS protection (browser built-in)
        resp.headers['X-XSS-Protection'] = '1; mode=block'

        # Strict Transport Security (HSTS) - only set when using HTTPS
        # max-age: 1 year, include subdomains, preload for HSTS preload list
        if request.scheme == 'https':
            resp.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains; preload'

        # Content Security Policy - restrict resource loading
        csp = (
            "default-src 'self'; "  # Only allow resources from same origin
            "script-src 'self' 'unsafe-inline'; "  # Scripts from self (unsafe-inline for Bootstrap)
            "style-src 'self' 'unsafe-inline'; "  # Styles from self (unsafe-inline for inline styles)
            "img-src 'self' data: https:; "  # Images from self, data URIs, and HTTPS
            "font-src 'self'; "  # Fonts from self only
            "connect-src 'self'; "  # AJAX/WebSocket to self only
            "frame-ancestors 'none'; "  # This frame cannot be embedded
            "base-uri 'self'; "  # Base tag points to same origin
            "form-action 'self'"  # Forms submit to same origin
        )
        resp.headers['Content-Security-Policy'] = csp

        # Referrer Policy - limit referrer info
        resp.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'

        # Permissions Policy - disable various browser features
        resp.headers['Permissions-Policy'] = (
            'geolocation=(), '
            'microphone=(), '
            'camera=(), '
            'payment=()'
        )

        # Prevent caching for dynamic pages (especially wallet dashboards)
        if request.path.startswith('/wallet/') or request.path == '/':
            resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            resp.headers['Pragma'] = 'no-cache'
            resp.headers['Expires'] = '0'

        return resp


def require_https(f):
    """Decorator to require HTTPS for a route."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from flask import request
        if request.scheme != 'https' and not request.environ.get('wsgi.url_scheme') == 'http://localhost':
            # Redirect to HTTPS (only if not localhost)
            url = request.url.replace('http://', 'https://', 1)
            return redirect(url, code=301)
        return f(*args, **kwargs)
    return decorated_function
