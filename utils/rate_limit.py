"""Rate limiting utilities."""
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
    strategy="fixed-window"
)


def init_rate_limiting(app):
    """Initialize rate limiter with the Flask app."""
    limiter.init_app(app)


# Predefined rate limit configurations
RATE_LIMITS = {
    'login': '5 per minute',  # Prevent brute force
    'api': '100 per hour',  # General API calls
    'admin': '30 per hour',  # Admin operations
    'export': '10 per hour',  # Data export
    'test_wallet': '10 per minute',  # Test wallet connections
}
