"""Service for aggregating individual fills into logical trades."""

from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from db.models import ClosedTrade, AggregatedTrade
from db.queries import normalize_symbol


def sync_aggregated_trades(session: Session, wallet_id: Optional[int] = None) -> int:
    """
    Sync aggregated_trades from closed_trades.

    Groups all closed_trades with |PnL| >= $0.01 by (wallet_id, timestamp, symbol)
    and upserts into aggregated_trades table.

    Args:
        session: Database session
        wallet_id: Optional wallet_id to sync specific wallet only

    Returns:
        Number of aggregated trades upserted
    """
    from sqlalchemy import and_

    # Get all closed_trades with meaningful PnL
    query = session.query(ClosedTrade).filter(
        (ClosedTrade.closed_pnl >= 0.01) | (ClosedTrade.closed_pnl <= -0.01)
    )

    if wallet_id:
        query = query.filter(ClosedTrade.wallet_id == wallet_id)

    closed_trades = query.all()

    # Group by (wallet_id, timestamp, symbol)
    from collections import defaultdict
    grouped = defaultdict(list)

    for trade in closed_trades:
        key = (trade.wallet_id, trade.timestamp, normalize_symbol(str(trade.symbol)))
        grouped[key].append(trade)

    # Upsert into aggregated_trades
    count = 0
    for (wallet_id_val, ts, symbol), trades in grouped.items():
        # Calculate aggregates
        total_size = sum(float(t.size or 0) for t in trades)
        total_pnl = sum(float(t.closed_pnl or 0) for t in trades)
        total_close_fee = sum(float(t.close_fee or 0) for t in trades if t.close_fee)
        total_open_fee = sum(float(t.open_fee or 0) for t in trades if t.open_fee)
        total_liquidate_fee = sum(float(t.liquidate_fee or 0) for t in trades if t.liquidate_fee)

        # Weighted average entry price
        total_entry_value = sum(float(t.entry_price or 0) * float(t.size or 0) for t in trades)
        avg_entry_price = total_entry_value / total_size if total_size > 0 else 0

        # Weighted average exit price
        total_exit_value = sum(float(t.exit_price or 0) * float(t.size or 0) for t in trades)
        avg_exit_price = total_exit_value / total_size if total_size > 0 else 0

        # Get data from first trade
        primary = trades[0]

        # Check if aggregated trade already exists
        existing = session.query(AggregatedTrade).filter(
            and_(
                AggregatedTrade.wallet_id == wallet_id_val,
                AggregatedTrade.timestamp == ts,
                AggregatedTrade.symbol == symbol,
            )
        ).first()

        if existing:
            # Update existing
            existing.side = primary.side
            existing.size = total_size
            existing.avg_entry_price = avg_entry_price
            existing.avg_exit_price = avg_exit_price
            existing.trade_type = primary.trade_type
            existing.total_pnl = total_pnl
            existing.total_close_fee = total_close_fee if total_close_fee > 0 else None
            existing.total_open_fee = total_open_fee if total_open_fee > 0 else None
            existing.total_liquidate_fee = total_liquidate_fee if total_liquidate_fee > 0 else None
            existing.exit_type = primary.exit_type
            existing.equity_used = primary.equity_used
            existing.leverage = primary.leverage
            existing.strategy_id = primary.strategy_id
            existing.fill_count = len(trades)
        else:
            # Insert new
            agg_trade = AggregatedTrade(
                wallet_id=wallet_id_val,
                timestamp=ts,
                symbol=symbol,
                side=primary.side,
                size=total_size,
                avg_entry_price=avg_entry_price,
                avg_exit_price=avg_exit_price,
                trade_type=primary.trade_type,
                total_pnl=total_pnl,
                total_close_fee=total_close_fee if total_close_fee > 0 else None,
                total_open_fee=total_open_fee if total_open_fee > 0 else None,
                total_liquidate_fee=total_liquidate_fee if total_liquidate_fee > 0 else None,
                exit_type=primary.exit_type,
                equity_used=primary.equity_used,
                leverage=primary.leverage,
                strategy_id=primary.strategy_id,
                fill_count=len(trades),
            )
            session.add(agg_trade)

        count += 1

    return count
