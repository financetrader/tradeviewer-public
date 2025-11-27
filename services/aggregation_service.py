"""Service for aggregating individual fills into logical trades."""

from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from db.models import ClosedTrade, AggregatedTrade, Position
from db.queries import normalize_symbol


def close_position(
    session: Session,
    wallet_id: int,
    symbol: str,
    side: str,
    closed_at: datetime,
    exit_price: Optional[float] = None,
    realized_pnl: Optional[float] = None
) -> Optional[Position]:
    """
    Mark an open position as closed.
    
    Finds the open position for wallet+symbol+side and sets closed_at.
    
    Args:
        session: Database session
        wallet_id: Wallet ID
        symbol: Trading symbol
        side: Position side ("LONG" or "SHORT")
        closed_at: When position was closed
        exit_price: Exit price (optional)
        realized_pnl: Realized P&L (optional)
    
    Returns:
        Updated Position object, or None if no open position found
    """
    side = side.upper() if side else "LONG"
    
    position = session.query(Position).filter(
        Position.wallet_id == wallet_id,
        Position.symbol == symbol,
        Position.side == side,
        Position.closed_at.is_(None)
    ).first()
    
    if position:
        position.closed_at = closed_at
        if exit_price is not None:
            position.exit_price = exit_price
        if realized_pnl is not None:
            position.realized_pnl = realized_pnl
        return position
    
    return None


def sync_aggregated_trades(session: Session, wallet_id: Optional[int] = None) -> int:
    """
    Sync aggregated_trades from closed_trades.

    Matches opening and closing legs of trades using the reduce_only flag:
    - reduce_only=false: Opening leg (increases position size)
    - reduce_only=true: Closing leg (decreases position size)

    For each closing leg, finds the most recent matching opening leg with:
    - Same wallet_id, symbol, and side (LONG/SHORT)
    - Matching size (±0.1%)
    - Opening timestamp before closing timestamp

    Creates one aggregated trade per closing leg, showing the complete round trip
    from opening to closing.

    Args:
        session: Database session
        wallet_id: Optional wallet_id to sync specific wallet only

    Returns:
        Number of aggregated trades upserted
    """
    from sqlalchemy import and_, or_

    # Get all closed_trades
    query = session.query(ClosedTrade)

    if wallet_id:
        query = query.filter(ClosedTrade.wallet_id == wallet_id)

    closed_trades = query.all()

    # Separate opening and closing legs
    # For trades with explicit reduce_only flag use it, otherwise infer from context
    closing_legs_explicit = [t for t in closed_trades if t.reduce_only is True]
    opening_legs_explicit = [t for t in closed_trades if t.reduce_only is False]
    unknown_legs = [t for t in closed_trades if t.reduce_only is None]

    # For unknown legs, infer based on pairing: typically first leg opens, second closes
    # We'll handle these during the matching process
    closing_legs = closing_legs_explicit + unknown_legs  # Will filter unknown during matching
    opening_legs = opening_legs_explicit

    # Build lookup for opening legs by (wallet_id, symbol)
    # Don't group by side since SHORT positions have different sides for open/close
    from collections import defaultdict
    opening_lookup = defaultdict(list)
    for trade in opening_legs:
        key = (trade.wallet_id, normalize_symbol(str(trade.symbol)))
        opening_lookup[key].append(trade)

    # Sort each group by timestamp (descending) for "most recent" matching
    for key in opening_lookup:
        opening_lookup[key].sort(key=lambda t: t.timestamp, reverse=True)

    # Match closing legs with opening legs and create aggregated trades
    count = 0
    matched_closing_ids = set()

    for closing_leg in closing_legs:
        # Skip if already matched
        if closing_leg.id in matched_closing_ids:
            continue

        # Find matching opening leg
        # For SHORT positions: opening=SELL, closing=BUY
        # For LONG positions: opening=BUY, closing=SELL
        lookup_key = (closing_leg.wallet_id, normalize_symbol(str(closing_leg.symbol)))
        opening_candidates = opening_lookup.get(lookup_key, [])

        opening_leg = None
        for candidate in opening_candidates:
            # Opening must be before closing
            if candidate.timestamp >= closing_leg.timestamp:
                continue

            # Size must match within ±0.1%
            if candidate.size == 0:
                continue
            size_diff_pct = abs(candidate.size - closing_leg.size) / candidate.size
            if size_diff_pct > 0.001:  # ±0.1%
                continue

            # Found matching opening leg
            opening_leg = candidate
            break

        if opening_leg is None:
            # No matching opening leg found, skip this closing leg
            continue

        matched_closing_ids.add(closing_leg.id)

        # Infer position side from opening leg
        # If opening leg is BUY (reduce_only=False), it's a LONG position
        # If opening leg is SELL (reduce_only=False), it's a SHORT position
        position_side = "LONG" if opening_leg.side == "BUY" else "SHORT"

        # Calculate PnL from opening and closing prices
        size = abs(closing_leg.size)
        if position_side == 'LONG':
            # LONG: profit when exit > entry
            pnl = (closing_leg.exit_price - opening_leg.entry_price) * size
        else:  # SHORT
            # SHORT: profit when entry > exit
            pnl = (opening_leg.entry_price - closing_leg.exit_price) * size

        # Subtract all fees
        total_fees = (opening_leg.open_fee or 0) + (closing_leg.close_fee or 0) + (closing_leg.liquidate_fee or 0)
        total_pnl = pnl - total_fees

        # Check if aggregated trade already exists for this closing leg
        existing = session.query(AggregatedTrade).filter(
            and_(
                AggregatedTrade.wallet_id == closing_leg.wallet_id,
                AggregatedTrade.timestamp == closing_leg.timestamp,
                AggregatedTrade.symbol == lookup_key[1],
            )
        ).first()

        # Mark the position as closed
        close_position(
            session=session,
            wallet_id=closing_leg.wallet_id,
            symbol=lookup_key[1],
            side=position_side,
            closed_at=closing_leg.timestamp,
            exit_price=closing_leg.exit_price,
            realized_pnl=total_pnl
        )

        if existing:
            # Update existing
            existing.side = position_side
            existing.size = size
            existing.avg_entry_price = opening_leg.entry_price
            existing.avg_exit_price = closing_leg.exit_price
            existing.trade_type = closing_leg.trade_type
            existing.total_pnl = total_pnl
            existing.total_open_fee = opening_leg.open_fee if (opening_leg.open_fee or 0) > 0 else None
            existing.total_close_fee = closing_leg.close_fee if (closing_leg.close_fee or 0) > 0 else None
            existing.total_liquidate_fee = closing_leg.liquidate_fee if (closing_leg.liquidate_fee or 0) > 0 else None
            existing.exit_type = closing_leg.exit_type
            existing.equity_used = closing_leg.equity_used
            existing.leverage = closing_leg.leverage
            existing.strategy_id = closing_leg.strategy_id
            existing.fill_count = 2  # Opening + Closing leg
        else:
            # Insert new
            agg_trade = AggregatedTrade(
                wallet_id=closing_leg.wallet_id,
                timestamp=closing_leg.timestamp,  # Use closing timestamp as the trade completion time
                symbol=lookup_key[1],
                side=position_side,
                size=size,
                avg_entry_price=opening_leg.entry_price,
                avg_exit_price=closing_leg.exit_price,
                trade_type=closing_leg.trade_type,
                total_pnl=total_pnl,
                total_open_fee=opening_leg.open_fee if (opening_leg.open_fee or 0) > 0 else None,
                total_close_fee=closing_leg.close_fee if (closing_leg.close_fee or 0) > 0 else None,
                total_liquidate_fee=closing_leg.liquidate_fee if (closing_leg.liquidate_fee or 0) > 0 else None,
                exit_type=closing_leg.exit_type,
                equity_used=closing_leg.equity_used,
                leverage=closing_leg.leverage,
                strategy_id=closing_leg.strategy_id,
                fill_count=2,  # Opening + Closing leg
            )
            session.add(agg_trade)

        count += 1

    return count
