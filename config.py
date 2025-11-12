"""Flask application configuration for different environments."""
import os
from datetime import timedelta


class Config:
    """Base configuration."""
    # Flask
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'dev-key-change-in-production')

    # Request size limits (prevent DoS attacks)
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB limit

    # Session
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)
    SESSION_COOKIE_SECURE = False  # Set to True only when using HTTPS
    SESSION_COOKIE_HTTPONLY = True  # No JS access
    SESSION_COOKIE_SAMESITE = 'Lax'  # CSRF protection

    # Database
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Security
    ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY')
    ENCRYPTION_KEY_SEED = os.getenv('ENCRYPTION_KEY_SEED', 'default-dev-seed-change-in-production')

    # CSRF Protection
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600  # 1 hour token validity

    # Logging
    ADMIN_LOG_TAIL = int(os.getenv('ADMIN_LOG_TAIL', 200))

    # Portfolio Staleness Warnings
    STALE_WALLET_HOURS = int(os.getenv('STALE_WALLET_HOURS', 2))  # Show warning if wallet hasn't updated in N hours

    # Rate Limiting
    RATELIMIT_STORAGE_URL = 'memory://'


class DevelopmentConfig(Config):
    """Development environment configuration."""
    DEBUG = True
    TESTING = False
    SESSION_COOKIE_SECURE = False  # Allow HTTP in dev


class ProductionConfig(Config):
    """Production environment configuration."""
    DEBUG = False
    TESTING = False
    # Allow HTTP cookies when not using HTTPS (for port-based deployment)
    # Set to True when using HTTPS/TLS
    SESSION_COOKIE_SECURE = False


class TestingConfig(Config):
    """Testing environment configuration."""
    DEBUG = True
    TESTING = True
    SESSION_COOKIE_SECURE = False
    WTF_CSRF_ENABLED = False


def get_config():
    """Get appropriate config based on FLASK_ENV."""
    env = os.getenv('FLASK_ENV', 'development').lower()

    if env == 'production':
        # Validate production requirements
        if not os.getenv('FLASK_SECRET_KEY'):
            raise ValueError(
                'FLASK_SECRET_KEY environment variable is required in production. '
                'Generate with: python -c "import secrets; print(secrets.token_hex(32))"'
            )
        if not os.getenv('ENCRYPTION_KEY'):
            import warnings
            warnings.warn(
                'ENCRYPTION_KEY not set. Using ENCRYPTION_KEY_SEED fallback. '
                'This is NOT recommended for production. '
                'Set ENCRYPTION_KEY environment variable.'
            )
        return ProductionConfig()
    elif env == 'testing':
        return TestingConfig()
    else:
        return DevelopmentConfig()
