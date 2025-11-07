"""Data transformation and normalization utilities."""
from typing import Optional


def normalize_symbol(symbol: Optional[str]) -> str:
    """
    Normalize trading symbols to consistent DASH format (e.g., BTC-USDT).
    
    Handles:
    - Already-dashed symbols: BTC-USDT → BTC-USDT
    - Compact forms: BTCUSDT → BTC-USDT
    - Underscore separators: BTC_USDT → BTC-USDT
    
    Args:
        symbol: Trading pair symbol in any format
        
    Returns:
        Normalized symbol in DASH format (BASE-QUOTE)
        
    Examples:
        >>> normalize_symbol("BTCUSDT")
        "BTC-USDT"
        >>> normalize_symbol("BTC-USDT")
        "BTC-USDT"
        >>> normalize_symbol("ETH_USDC")
        "ETH-USDC"
    """
    if not symbol:
        return symbol or ""
    
    # Replace underscores with dashes
    s = symbol.replace('_', '-').upper()
    
    # If already has dash, return as-is
    if '-' in s:
        return s
    
    # Try to split common quote assets
    for quote in ("USDT", "USDC", "USD"):
        if s.endswith(quote) and len(s) > len(quote):
            base = s[:-len(quote)]
            return f"{base}-{quote}"
    
    return s

