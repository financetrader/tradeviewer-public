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
    # Look back up to 24 hours (increased from 1 hour to handle positions opened longer ago)
    lookback = before_timestamp - timedelta(hours=24)
    
    snapshot = session.query(EquitySnapshot).filter(
        EquitySnapshot.wallet_id == wallet_id,
        EquitySnapshot.timestamp < before_timestamp,
        EquitySnapshot.timestamp >= lookback,
        EquitySnapshot.initial_margin.isnot(None)
    ).order_by(EquitySnapshot.timestamp.desc()).first()
    
    if snapshot:
        logger.info(f"Found previous margin_used: ${snapshot.initial_margin:.2f} at {snapshot.timestamp}")
        return float(snapshot.initial_margin)
    
    logger.warning(f"No previous margin_used found before {before_timestamp} (looked back 24 hours)")
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
    
    # Check if this is a new position OR if we need to calculate leverage for an existing position
    is_new = is_new_position(session, wallet_id, symbol, current_timestamp)
    
    # Also check if the latest snapshot doesn't have leverage yet, or has invalid leverage
    from db.models import PositionSnapshot
    from sqlalchemy import desc
    latest_snapshot = session.query(PositionSnapshot).filter(
        PositionSnapshot.wallet_id == wallet_id,
        PositionSnapshot.symbol == symbol,
        PositionSnapshot.timestamp < current_timestamp
    ).order_by(desc(PositionSnapshot.timestamp)).first()
    
    # Check if we have an opened_at timestamp - if so, use it for lookup even if is_new=True
    # (is_new might be True if no snapshot within 5 minutes, but position actually opened earlier)
    first_snapshot = None
    if latest_snapshot:
        first_snapshot = session.query(PositionSnapshot).filter(
            PositionSnapshot.wallet_id == wallet_id,
            PositionSnapshot.symbol == symbol,
            PositionSnapshot.size > 0
        ).order_by(PositionSnapshot.timestamp).first()
    
    # CRITICAL: Leverage should be calculated ONCE when position first opens
    # Check the FIRST snapshot - if it has leverage, use it for ALL future snapshots
    if first_snapshot and first_snapshot.leverage is not None and first_snapshot.leverage <= 100.0:
        logger.info(f"[{symbol}] Position already has leverage from first snapshot ({first_snapshot.leverage:.2f}x) - preserving it")
        return (
            float(first_snapshot.leverage),
            float(first_snapshot.equity_used) if first_snapshot.equity_used else None,
            first_snapshot.calculation_method or "margin_delta"
        )
    
    # Only calculate leverage if the FIRST snapshot doesn't have it
    # This means this is truly a new position opening, or leverage was never calculated
    needs_leverage_calc = (first_snapshot is None) or (first_snapshot.leverage is None) or (first_snapshot.leverage > 100.0)
    
    if not needs_leverage_calc:
        # Shouldn't reach here, but keep as safety check
        logger.info(f"[{symbol}] Existing position with valid leverage ({latest_snapshot.leverage:.2f}x) - returning existing values")
        return (
            float(latest_snapshot.leverage),
            float(latest_snapshot.equity_used) if latest_snapshot.equity_used else None,
            latest_snapshot.calculation_method or "margin_delta"
        )
    
    # If we need to calculate leverage, use opened_at timestamp if available (even if is_new=True)
    # This handles cases where position opened earlier but is_new=True due to 5-minute lookback window
    lookup_timestamp = current_timestamp
    if first_snapshot and first_snapshot.opened_at:
        lookup_timestamp = first_snapshot.opened_at
        logger.info(f"[{symbol}] Using opened_at timestamp ({lookup_timestamp}) for margin lookup")
    
    # For existing positions OR positions with opened_at timestamp, get margin at open time
    if (not is_new and latest_snapshot) or (first_snapshot and first_snapshot.opened_at):
        if first_snapshot and first_snapshot.opened_at:
            # Get margin at the time position was opened
            equity_at_open = session.query(EquitySnapshot).filter(
                EquitySnapshot.wallet_id == wallet_id,
                EquitySnapshot.timestamp <= first_snapshot.opened_at
            ).order_by(EquitySnapshot.timestamp.desc()).first()
            
            # Get margin BEFORE position opened (right before opened_at)
            equity_before_open = session.query(EquitySnapshot).filter(
                EquitySnapshot.wallet_id == wallet_id,
                EquitySnapshot.timestamp < first_snapshot.opened_at
            ).order_by(EquitySnapshot.timestamp.desc()).first()
            
            if equity_at_open and equity_at_open.initial_margin is not None:
                margin_at_open = float(equity_at_open.initial_margin)
                margin_before_open = float(equity_before_open.initial_margin) if equity_before_open and equity_before_open.initial_margin is not None else 0.0
                # Calculate delta from before open to at open
                margin_delta = margin_at_open - margin_before_open
                logger.info(f"[{symbol}] Using margin at open (${margin_at_open:.2f}) - before open (${margin_before_open:.2f}) = ${margin_delta:.2f}")
                # Skip validation and calculation below, use this delta directly
                if margin_delta > 0:
                    equity_used = margin_delta
                    leverage = position_size_usd / equity_used
                    logger.info(f"[{symbol}] RESULT:")
                    logger.info(f"  Equity used: ${equity_used:.2f}")
                    logger.info(f"  Leverage: {leverage:.1f}x")
                    logger.info(f"  Method: margin_delta")
                    logger.info(f"{'='*60}\n")
                    return (leverage, equity_used, "margin_delta")
                else:
                    logger.warning(f"[{symbol}] Invalid margin delta ({margin_delta:.2f}) - margin at open <= margin before open")
            else:
                # Fallback: get previous margin used (before position opened)
                previous_margin = get_previous_margin_used(session, wallet_id, lookup_timestamp)
                if previous_margin is None:
                    logger.warning(f"[{symbol}] No previous margin data - cannot calculate")
                    return (None, None, "unknown")
                margin_delta = current_margin_used - previous_margin
        else:
            # Fallback: get previous margin used
            previous_margin = get_previous_margin_used(session, wallet_id, lookup_timestamp)
            if previous_margin is None:
                logger.warning(f"[{symbol}] No previous margin data - cannot calculate")
                return (None, None, "unknown")
            margin_delta = current_margin_used - previous_margin
    else:
        # For new positions, get previous margin used and use current margin delta
        previous_margin = get_previous_margin_used(session, wallet_id, lookup_timestamp)
        if previous_margin is None:
            logger.warning(f"[{symbol}] No previous margin data - cannot calculate")
            return (None, None, "unknown")
        margin_delta = current_margin_used - previous_margin
    
    logger.info(f"[{symbol}] Margin calculation:")
    logger.info(f"  Margin delta (equity used): ${margin_delta:.2f}")
    
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

