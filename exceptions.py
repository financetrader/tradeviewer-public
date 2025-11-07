"""Custom exceptions for the wallet application."""
from typing import Optional


class WalletError(Exception):
    """Base exception for wallet-related errors."""
    pass


class WalletConnectionError(WalletError):
    """Raised when wallet connection fails."""
    
    def __init__(self, provider: str, message: Optional[str] = None):
        self.provider = provider
        self.message = message or f"Failed to connect to {provider} wallet"
        super().__init__(self.message)


class WalletNotFoundError(WalletError):
    """Raised when a wallet is not found."""
    
    def __init__(self, provider: str, message: Optional[str] = None):
        self.provider = provider
        self.message = message or f"No connected {provider} wallet found"
        super().__init__(self.message)


class WalletConfigurationError(WalletError):
    """Raised when wallet configuration is invalid."""
    
    def __init__(self, provider: str, message: Optional[str] = None):
        self.provider = provider
        self.message = message or f"Invalid configuration for {provider} wallet"
        super().__init__(self.message)


class DataProcessingError(WalletError):
    """Raised when data processing fails."""
    
    def __init__(self, operation: str, message: Optional[str] = None):
        self.operation = operation
        self.message = message or f"Data processing failed for operation: {operation}"
        super().__init__(self.message)


class DatabaseError(WalletError):
    """Raised when database operations fail."""
    
    def __init__(self, operation: str, message: Optional[str] = None):
        self.operation = operation
        self.message = message or f"Database operation failed: {operation}"
        super().__init__(self.message)

