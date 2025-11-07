"""Input validation and sanitization utilities."""
import re
from typing import Optional, Union


def sanitize_integer(value: Union[str, int, None], default: int = 0, min_val: Optional[int] = None, max_val: Optional[int] = None) -> int:
    """
    Safely convert value to integer with defaults and bounds checking.
    
    Args:
        value: Value to convert (string, int, or None)
        default: Default value if conversion fails
        min_val: Minimum allowed value (inclusive)
        max_val: Maximum allowed value (inclusive)
    
    Returns:
        Integer value within bounds, or default if conversion fails
    """
    try:
        if value is None or value == '':
            return default
        
        # Handle both "123" and "123.0" strings
        result = int(float(str(value)))
        
        # Apply bounds
        if min_val is not None and result < min_val:
            return default
        if max_val is not None and result > max_val:
            return default
        
        return result
    except (ValueError, TypeError, OverflowError):
        return default


def sanitize_float(value: Union[str, float, None], default: float = 0.0, min_val: Optional[float] = None, max_val: Optional[float] = None) -> float:
    """
    Safely convert value to float with defaults and bounds checking.
    
    Args:
        value: Value to convert (string, float, or None)
        default: Default value if conversion fails
        min_val: Minimum allowed value (inclusive)
        max_val: Maximum allowed value (inclusive)
    
    Returns:
        Float value within bounds, or default if conversion fails
    """
    try:
        if value is None or value == '':
            return default
        
        result = float(str(value))
        
        # Apply bounds
        if min_val is not None and result < min_val:
            return default
        if max_val is not None and result > max_val:
            return default
        
        return result
    except (ValueError, TypeError, OverflowError):
        return default


def sanitize_string(value: Union[str, None], max_length: int = 255, allow_empty: bool = False) -> str:
    """
    Sanitize string input: strip whitespace, validate length, check for XSS patterns.
    
    Args:
        value: String to sanitize
        max_length: Maximum allowed length
        allow_empty: Whether empty strings are allowed
    
    Returns:
        Sanitized string, or empty string if validation fails
    """
    if value is None:
        return '' if allow_empty else ''
    
    # Strip whitespace
    sanitized = str(value).strip()
    
    # Check for empty
    if not sanitized and not allow_empty:
        return ''
    
    # Check for XSS patterns
    dangerous_patterns = [
        r'<script[^>]*>',
        r'javascript:',
        r'onerror\s*=',
        r'onload\s*=',
        r'onclick\s*=',
        r'<iframe[^>]*>',
        r'<object[^>]*>',
        r'<embed[^>]*>',
    ]
    
    for pattern in dangerous_patterns:
        if re.search(pattern, sanitized, re.IGNORECASE):
            return ''  # Reject dangerous content
    
    # Enforce length limit
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    
    return sanitized


def validate_wallet_name(name: str) -> Optional[str]:
    """
    Validate wallet name format.
    
    Rules:
    - 1-255 characters
    - Alphanumeric, spaces, dashes, underscores only
    
    Returns:
        Sanitized name if valid, None if invalid
    """
    sanitized = sanitize_string(name, max_length=255, allow_empty=False)
    if not sanitized:
        return None
    
    # Check format: alphanumeric, spaces, dashes, underscores only
    if not re.match(r'^[a-zA-Z0-9\s\-_]+$', sanitized):
        return None
    
    return sanitized


def validate_symbol(symbol: str) -> Optional[str]:
    """
    Validate trading symbol format.
    
    Rules:
    - 1-20 characters
    - Alphanumeric, uppercase preferred
    
    Returns:
        Uppercase sanitized symbol if valid, None if invalid
    """
    sanitized = sanitize_string(symbol, max_length=20, allow_empty=False)
    if not sanitized:
        return None
    
    # Check format: alphanumeric and hyphens allowed (e.g., BTC-USDT, SOL-USDT)
    if not re.match(r'^[a-zA-Z0-9\-]+$', sanitized):
        return None
    
    # Convert to uppercase
    return sanitized.upper()


def validate_wallet_address(address: str) -> Optional[str]:
    """
    Validate Ethereum-style wallet address format.
    
    Rules:
    - Exactly 42 characters
    - Starts with '0x'
    - Followed by 40 hex characters
    
    Returns:
        Lowercase address if valid, None if invalid
    """
    if not address:
        return None
    
    sanitized = address.strip()
    
    # Check format: 0x + 40 hex chars
    if not re.match(r'^0x[a-fA-F0-9]{40}$', sanitized):
        return None
    
    return sanitized.lower()


def sanitize_text(value: Union[str, None], max_length: int = 1000) -> str:
    """
    Sanitize longer text fields (notes, descriptions).
    
    Args:
        value: Text to sanitize
        max_length: Maximum allowed length
    
    Returns:
        Sanitized text
    """
    if value is None:
        return ''
    
    sanitized = str(value).strip()
    
    # Check for XSS patterns
    dangerous_patterns = [
        r'<script[^>]*>',
        r'javascript:',
        r'onerror\s*=',
        r'onload\s*=',
        r'onclick\s*=',
        r'<iframe[^>]*>',
        r'<object[^>]*>',
        r'<embed[^>]*>',
    ]
    
    for pattern in dangerous_patterns:
        if re.search(pattern, sanitized, re.IGNORECASE):
            # Strip dangerous content instead of rejecting
            sanitized = re.sub(pattern, '', sanitized, flags=re.IGNORECASE)
    
    # Enforce length limit
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    
    return sanitized


def validate_numeric(value: Union[str, int, float, None], min_val: Optional[float] = None, max_val: Optional[float] = None) -> Optional[float]:
    """
    Validate numeric value with optional bounds.
    
    Returns:
        Float value if valid, None if invalid
    """
    try:
        if value is None or value == '':
            return None
        
        result = float(str(value))
        
        if min_val is not None and result < min_val:
            return None
        if max_val is not None and result > max_val:
            return None
        
        return result
    except (ValueError, TypeError):
        return None

