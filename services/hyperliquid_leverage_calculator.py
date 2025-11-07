"""Hyperliquid leverage calculation via totalMarginUsed tracking.

This module implements leverage calculation by tracking changes in the total
totalMarginUsed value from the Hyperliquid marginSummary API. When a position opens, 
the increase in totalMarginUsed equals the equity used by that position.

Algorithm:
    1. Detect if this is a new position (first snapshot with size > 0)
    2. Get previous totalMarginUsed from most recent equity snapshot
    3. Calculate delta: equity_used = current_margin_used - previous_margin_used
    4. Calculate leverage: position_size_usd / equity_used

This approach works identically to the Apex implementation but uses Hyperliquid's
totalMarginUsed field instead of initialMargin.
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
        symbol: Trading symbol (e.g., "BTC")
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


def get_previous_margin_used(
    session: Session,
    wallet_id: int,
    before_timestamp: datetime
) -> Optional[float]:
    """
    Get the most recent totalMarginUsed value before the given timestamp.
    
    Args:
        session: Database session
        wallet_id: Wallet ID
        before_timestamp: Get margin before this time
        
    Returns:
        Previous total margin used value, or None if not found
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
        logger.info(f"Found previous margin_used: ${snapshot.initial_margin:.2f} at {snapshot.timestamp}")
        return float(snapshot.initial_margin)
    
    logger.warning(f"No previous margin_used found before {before_timestamp}")
    return None


def calculate_leverage_from_margin_delta(
    session: Session,
    wallet_id: int,
    symbol: str,
    position_size_usd: float,
    current_margin_used: float,
    current_timestamp: datetime
) -> Tuple[Optional[float], Optional[float], str]:
    """
    Calculate leverage by tracking totalMarginUsed changes.
    
    This is the primary method for Hyperliquid leverage calculation. It works by:
    1. Detecting if this is a new position
    2. Finding the previous total totalMarginUsed
    3. Calculating the delta (equity used by this position)
    4. Computing leverage = position_size / equity_used
    
    Args:
        session: Database session
        wallet_id: Wallet ID
        symbol: Trading symbol
        position_size_usd: Notional value of position
        current_margin_used: Current total margin used from marginSummary
        current_timestamp: Timestamp of current snapshot
        
    Returns:
        (leverage, equity_used, calculation_method)
        - leverage: Calculated leverage (e.g., 5.0 for 5x)
        - equity_used: Margin allocated to this position
        - calculation_method: "margin_delta" | "unknown"
    """
    try:
        logger.info(f"\n{'='*60}")
        logger.info(f"Calculating Hyperliquid leverage for {symbol}")
        logger.info(f"Position size: ${position_size_usd:.2f}")
        logger.info(f"Current margin used: ${current_margin_used:.2f}")
        logger.info(f"{'='*60}")
    except Exception as e:
        logger.error(f"Error in initial logging for {symbol}: {e}")
        pass
    
    # Check if this is a new position
    if not is_new_position(session, wallet_id, symbol, current_timestamp):
        logger.info(f"[{symbol}] Existing position - not calculating via margin delta")
        return (None, None, "unknown")
    
    # Get previous margin used
    previous_margin = get_previous_margin_used(session, wallet_id, current_timestamp)
    
    if previous_margin is None:
        logger.warning(f"[{symbol}] No previous margin data - cannot calculate")
        return (None, None, "unknown")
    
    # Calculate margin delta
    margin_delta = current_margin_used - previous_margin
    
    logger.info(f"[{symbol}] Margin calculation:")
    logger.info(f"  Previous margin: ${previous_margin:.2f}" if previous_margin else "  Previous margin: None")
    logger.info(f"  Current margin: ${current_margin_used:.2f}")
    logger.info(f"  Delta (equity used): ${margin_delta:.2f}")
    
    # Validate delta
    if margin_delta <= 0:
        logger.warning(f"[{symbol}] Invalid margin delta ({margin_delta:.2f}) - cannot calculate")
        return (None, None, "unknown")
    
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

