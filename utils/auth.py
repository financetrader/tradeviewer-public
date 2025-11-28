"""Authentication utilities for Flask-Login."""
import os
from flask_login import LoginManager, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash


# Single admin user credentials from environment
ADMIN_USER = os.getenv('ADMIN_USER', 'admin')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'changeme')

# Hash the password at module load for secure comparison
_password_hash = generate_password_hash(ADMIN_PASSWORD)


class User(UserMixin):
    """Simple user class for Flask-Login.
    
    Single-user implementation - credentials from environment variables.
    """
    
    def __init__(self, user_id: str):
        self.id = user_id
    
    @staticmethod
    def validate_credentials(username: str, password: str) -> bool:
        """Validate username and password against environment credentials.
        
        Args:
            username: The submitted username
            password: The submitted password (plain text)
            
        Returns:
            True if credentials are valid, False otherwise
        """
        if username != ADMIN_USER:
            return False
        return check_password_hash(_password_hash, password)
    
    @staticmethod
    def get(user_id: str) -> 'User | None':
        """Get user by ID.
        
        Args:
            user_id: The user identifier
            
        Returns:
            User instance if valid, None otherwise
        """
        if user_id == ADMIN_USER:
            return User(user_id)
        return None


def init_login_manager(app):
    """Initialize Flask-Login with the app.
    
    Args:
        app: Flask application instance
        
    Returns:
        Configured LoginManager instance
    """
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'error'
    
    @login_manager.user_loader
    def load_user(user_id):
        """Load user by ID for Flask-Login."""
        return User.get(user_id)
    
    return login_manager

