"""Calculation utilities for position and P&L analysis."""
from typing import List, Dict, Any, Optional
from datetime import datetime


def estimate_equity_used(position_size_usd: float, leverage: Optional[float]) -> float:
    """Calculate equity used for a position given its size and leverage.
    
    Args:
        position_size_usd: Position size in USD
        leverage: Leverage multiplier
        
    Returns:
        Estimated equity used (position_size / leverage)
    """
    if not leverage or leverage == 0:
        return 0.0
    try:
        return round(float(position_size_usd) / float(leverage), 2)
    except Exception:
        return 0.0


def annotate_closed_pnl_equity_used(
    closed_pnl: List[Dict[str, Any]], 
    lev_history: Dict[str, List[Dict[str, Any]]]
) -> None:
    """Annotate each closed_pnl item with equityUsed using historical leverage data.
    
    We pick the latest leverage value for the symbol at or before the trade's close time.
    
    Args:
        closed_pnl: List of closed trade dicts to annotate (modified in-place)
        lev_history: Dict mapping symbol -> list of {timestamp, leverage} entries
    """
    def parse_ts(ts: str) -> Optional[datetime]:
        """Parse timestamp string to datetime object."""
        try:
            # createdAtFormatted is '%Y-%m-%d %H:%M'
            return datetime.strptime(ts, "%Y-%m-%d %H:%M")
        except Exception:
            try:
                return datetime.fromtimestamp(int(ts) / 1000)
            except Exception:
                return None

    for e in closed_pnl or []:
        sym: Optional[str] = e.get('symbol')
        ts: str = e.get('createdAtFormatted') or str(e.get('createdAt') or '')
        size: float = float(e.get('size', 0) or 0)
        price: float = float(e.get('price', 0) or 0)
        position_usd: float = round(abs(size) * price, 2)
        lev: Optional[float] = None
        series: List[Dict[str, Any]] = lev_history.get(sym) or [] if sym else []
        if series:
            t: Optional[datetime] = parse_ts(ts)
            latest: Optional[Dict[str, Any]] = None
            for item in series:
                it: Optional[datetime] = parse_ts(item.get('timestamp') or '')
                if t and it and it <= t:
                    latest = item
                elif t and it and it > t:
                    break
            if latest and latest.get('leverage'):
                lev = latest.get('leverage')
        e['equityUsed'] = estimate_equity_used(position_usd, lev if lev else 0)


def estimate_leverage_hyperliquid(
    position_size_usd: float,
    account_equity: float,
    position_value: Optional[float] = None,
    total_position_values: Optional[float] = None
) -> Optional[float]:
    """Estimate leverage for Hyperliquid positions.
    
    Hyperliquid uses cross-margin, so leverage calculation is:
    leverage = position_size_usd / equity_used
    
    Where equity_used is estimated from:
    - If we have position_value: equity_used ≈ position_value / leverage_estimate
    - Or: equity_used ≈ account_equity * (position_value / total_account_exposure)
    
    This function estimates leverage using position value when available,
    or falls back to estimating from position size relative to account equity.
    
    Args:
        position_size_usd: Position size in USD (size * entry_price)
        account_equity: Total account equity (accountValue from Hyperliquid)
        position_value: Position value from API (positionValue field, optional)
        total_position_values: Sum of all position values if multiple positions (optional)
        
    Returns:
        Estimated leverage (rounded to 1 decimal, capped at 50x), or None if cannot be calculated
        
    Note:
        Hyperliquid doesn't provide margin rate or leverage directly. This estimation
        uses account equity and position value to infer leverage. For cross-margin accounts,
        equity is shared across positions, so estimates may be less accurate with multiple positions.
    """
    if not position_size_usd or position_size_usd <= 0:
        return None
    
    if not account_equity or account_equity <= 0:
        return None
    
    # Method 1: Use position_value if available (most accurate)
    # position_value represents the notional value of the position
    if position_value and position_value > 0:
        # Estimate equity used based on position value relative to account equity
        # If position_value is larger than account_equity, it's leveraged
        if position_value >= account_equity:
            # Position is at least as large as account equity = leveraged
            # Estimate equity_used as portion of account_equity
            # For cross-margin, typically 50-80% of equity can be used
            estimated_equity_used = account_equity * 0.6  # Assume 60% of equity used
            leverage = position_size_usd / estimated_equity_used
        else:
            # Position smaller than account equity
            # Estimate equity_used based on position value
            # For cross-margin, equity_used is typically 70-90% of position_value
            estimated_equity_used = position_value * 0.8  # Assume 80% of position_value
            leverage = position_size_usd / estimated_equity_used
    
    # Method 2: Estimate from account equity and position size
    else:
        # Estimate based on position size relative to account equity
        position_ratio = position_size_usd / account_equity
        
        if position_ratio >= 1.0:
            # Position larger than equity = leveraged
            # Estimate equity_used as portion of equity
            estimated_equity_used = account_equity * 0.5  # Conservative estimate
            leverage = position_size_usd / estimated_equity_used
        else:
            # Position smaller than equity
            # Estimate equity_used ratio (typically 60-80% of position ratio for cross-margin)
            equity_used_ratio = max(0.1, position_ratio * 0.7)
            estimated_equity_used = account_equity * equity_used_ratio
            leverage = position_size_usd / estimated_equity_used
    
    # Cap at reasonable maximum (Hyperliquid typically allows up to 20-50x)
    leverage = min(leverage, 50.0)
    return round(leverage, 1)

