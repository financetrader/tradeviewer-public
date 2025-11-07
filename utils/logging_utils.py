"""Centralized logging utilities for consistent application logging."""
import logging
import sys
from typing import Optional
from datetime import datetime


class AppLogger:
    """Centralized application logger with consistent formatting."""
    
    _instance: Optional['AppLogger'] = None
    _logger: Optional[logging.Logger] = None
    
    def __new__(cls) -> 'AppLogger':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._logger is None:
            self._setup_logger()
    
    def _setup_logger(self) -> None:
        """Set up the application logger with consistent formatting."""
        self._logger = logging.getLogger('wallet_app')
        self._logger.setLevel(logging.INFO)
        
        # Clear any existing handlers
        self._logger.handlers.clear()
        
        # Create console handler with custom formatting
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        
        # Custom formatter
        formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(formatter)
        
        self._logger.addHandler(console_handler)
        
        # Prevent duplicate logs
        self._logger.propagate = False
    
    def info(self, message: str, **kwargs) -> None:
        """Log info message."""
        self._logger.info(message, **kwargs)
    
    def warning(self, message: str, **kwargs) -> None:
        """Log warning message."""
        self._logger.warning(message, **kwargs)
    
    def error(self, message: str, **kwargs) -> None:
        """Log error message."""
        self._logger.error(message, **kwargs)
    
    def debug(self, message: str, **kwargs) -> None:
        """Log debug message."""
        self._logger.debug(message, **kwargs)
    
    def log_wallet_operation(self, operation: str, provider: str, success: bool, details: Optional[str] = None) -> None:
        """Log wallet-specific operations with consistent format."""
        status = "SUCCESS" if success else "FAILED"
        message = f"Wallet {operation} [{provider}] - {status}"
        if details:
            message += f": {details}"
        
        if success:
            self.info(message)
        else:
            self.error(message)
    
    def log_data_operation(self, operation: str, success: bool, details: Optional[str] = None) -> None:
        """Log data processing operations with consistent format."""
        status = "SUCCESS" if success else "FAILED"
        message = f"Data {operation} - {status}"
        if details:
            message += f": {details}"
        
        if success:
            self.info(message)
        else:
            self.error(message)


def get_app_logger() -> AppLogger:
    """Get the singleton application logger instance."""
    return AppLogger()

