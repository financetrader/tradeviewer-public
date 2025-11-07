"""Apex Omni leverage calculation via initial margin tracking.

This module implements leverage calculation by tracking changes in the total
initialMargin value from the Apex balance API. When a position opens, the
increase in initialMargin equals the equity used by that position.

Algorithm:
    1. Detect if this is a new position (first snapshot with size > 0)
    2. Get previous initialMargin from most recent equity snapshot
    3. Calculate delta: equity_used = current_initial_margin - previous_initial_margin
    4. Calculate leverage: position_size_usd / equity_used

This approach works around the issue where customInitialMarginRate sometimes
returns 0 from the Apex API.
"""

from typing import Tuple, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
import logging

from db.models import PositionSnapshot, EquitySnapshot

logger = logging.getLogger(__name__)


def is_new_position(
    session: Session,
    wallet_id: int,
    symbol: str,
    current_timestamp: datetime
) -> bool:
    """
    Detect if this is a newly opened position.
    
    A position is considered "new" if this is the first snapshot with size > 0,
    or if the previous snapshot had size = 0 (position was closed and reopened).
    
    Args:
        session: Database session
        wallet_id: Wallet ID
        symbol: Trading symbol (e.g., "BTC-USDT")
        current_timestamp: Timestamp of current snapshot
        
    Returns:
        True if this is a new position opening
    """
    # Look for the most recent snapshot before current time
    lookback = current_timestamp - timedelta(minutes=5)
    
    previous = session.query(PositionSnapshot).filter(
        PositionSnapshot.wallet_id == wallet_id,
        PositionSnapshot.symbol == symbol,
        PositionSnapshot.timestamp < current_timestamp,
        PositionSnapshot.timestamp >= lookback
    ).order_by(PositionSnapshot.timestamp.desc()).first()
    
    # If no previous snapshot, this is a new position
    if not previous:
        logger.info(f"[{symbol}] No previous snapshot found - treating as new position")
        return True
    
    # If previous snapshot had size = 0, this is a reopened position
    if previous.size == 0 or abs(previous.size) < 0.0001:
        logger.info(f"[{symbol}] Previous snapshot had size=0 - position reopening")
        return True
    
    # Position already exists
    logger.info(f"[{symbol}] Position already exists (prev size={previous.size})")
    return False


def get_previous_initial_margin(
    session: Session,
    wallet_id: int,
    before_timestamp: datetime
) -> Optional[float]:
    """
    Get the most recent initialMargin value before the given timestamp.
    
    Args:
        session: Database session
        wallet_id: Wallet ID
        before_timestamp: Get margin before this time
        
    Returns:
        Previous initial margin value, or None if not found
    """
    # Look back up to 1 hour
    lookback = before_timestamp - timedelta(hours=1)
    
    snapshot = session.query(EquitySnapshot).filter(
        EquitySnapshot.wallet_id == wallet_id,
        EquitySnapshot.timestamp < before_timestamp,
        EquitySnapshot.timestamp >= lookback,
        EquitySnapshot.initial_margin.isnot(None)
    ).order_by(EquitySnapshot.timestamp.desc()).first()
    
    if snapshot:
        logger.info(f"Found previous initial_margin: ${snapshot.initial_margin:.2f} at {snapshot.timestamp}")
        return float(snapshot.initial_margin)
    
    logger.warning(f"No previous initial_margin found before {before_timestamp}")
    return None


def calculate_from_margin_rate(position_raw: dict) -> Tuple[Optional[float], Optional[float], str]:
    """
    Fallback: Calculate leverage from customInitialMarginRate.
    
    Args:
        position_raw: Raw position data from API
        
    Returns:
        (leverage, equity_used, method) or (None, None, "unknown")
    """
    margin_rate = float(position_raw.get('customInitialMarginRate', 0) or 0)
    
    if margin_rate > 0:
        leverage = 1.0 / margin_rate
        
        # Calculate equity used
        size = abs(float(position_raw.get('size', 0) or 0))
        entry_price = float(position_raw.get('entryPrice', 0) or 0)
        position_size_usd = size * entry_price
        equity_used = position_size_usd * margin_rate
        
        logger.info(f"Calculated from margin rate: leverage={leverage:.1f}x, equity=${equity_used:.2f}")
        return (leverage, equity_used, "margin_rate")
    
    logger.warning("Cannot calculate: margin_rate = 0")
    return (None, None, "unknown")


def calculate_leverage_from_margin_delta(
    session: Session,
    wallet_id: int,
    symbol: str,
    position_size_usd: float,
    current_initial_margin: float,
    current_timestamp: datetime,
    position_raw: dict
) -> Tuple[Optional[float], Optional[float], str]:
    """
    Calculate leverage by tracking initialMargin changes.
    
    This is the primary method for Apex leverage calculation. It works by:
    1. Detecting if this is a new position
    2. Finding the previous total initialMargin
    3. Calculating the delta (equity used by this position)
    4. Computing leverage = position_size / equity_used
    
    Args:
        session: Database session
        wallet_id: Wallet ID
        symbol: Trading symbol
        position_size_usd: Notional value of position
        current_initial_margin: Current total initial margin from balance API
        current_timestamp: Timestamp of current snapshot
        position_raw: Raw position data from API (for fallback)
        
    Returns:
        (leverage, equity_used, calculation_method)
        - leverage: Calculated leverage (e.g., 5.0 for 5x)
        - equity_used: Margin allocated to this position
        - calculation_method: "margin_delta" | "margin_rate" | "unknown"
    """
    try:
        logger.info(f"\n{'='*60}")
        logger.info(f"Calculating leverage for {symbol}")
        logger.info(f"Position size: ${position_size_usd:.2f}")
        logger.info(f"Current initial margin: ${current_initial_margin:.2f}")
        logger.info(f"{'='*60}")
    except Exception as e:
        logger.error(f"Error in initial logging for {symbol}: {e}")
        pass
    
    # Check if this is a new position
    if not is_new_position(session, wallet_id, symbol, current_timestamp):
        logger.info(f"[{symbol}] Existing position - not calculating via margin delta")
        # For existing positions, try margin rate fallback
        return calculate_from_margin_rate(position_raw)
    
    # Get previous initial margin
    previous_margin = get_previous_initial_margin(session, wallet_id, current_timestamp)
    
    if previous_margin is None:
        logger.warning(f"[{symbol}] No previous margin data - trying margin rate fallback")
        return calculate_from_margin_rate(position_raw)
    
    # Calculate margin delta
    margin_delta = current_initial_margin - previous_margin
    
    logger.info(f"[{symbol}] Margin calculation:")
    logger.info(f"  Previous margin: ${previous_margin:.2f}" if previous_margin else "  Previous margin: None")
    logger.info(f"  Current margin: ${current_initial_margin:.2f}")
    logger.info(f"  Delta (equity used): ${margin_delta:.2f}")
    
    # Validate delta
    if margin_delta <= 0:
        logger.warning(f"[{symbol}] Invalid margin delta ({margin_delta:.2f}) - using fallback")
        return calculate_from_margin_rate(position_raw)
    
    if margin_delta > position_size_usd:
        logger.warning(f"[{symbol}] Margin delta (${margin_delta:.2f}) > position size (${position_size_usd:.2f})")
        logger.warning(f"  This may indicate multiple positions opened simultaneously")
        # Still calculate, but log the anomaly
    
    # Calculate leverage
    equity_used = margin_delta
    leverage = position_size_usd / equity_used
    
    logger.info(f"[{symbol}] RESULT:")
    logger.info(f"  Equity used: ${equity_used:.2f}")
    logger.info(f"  Leverage: {leverage:.1f}x")
    logger.info(f"  Method: margin_delta")
    logger.info(f"{'='*60}\n")
    
    return (leverage, equity_used, "margin_delta")

