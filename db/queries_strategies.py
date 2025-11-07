"""Strategy query helpers and resolver."""
from typing import List, Optional, Dict, Set
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import distinct, func

from utils.data_utils import normalize_symbol
from db.models_strategies import Strategy, StrategyAssignment
from db.models import PositionSnapshot, ClosedTrade


def count_trades_for_assignment(session: Session, assignment_id: int) -> int:
    """
    Count the number of closed trades for a specific strategy assignment.

    Args:
        session: Database session
        assignment_id: ID of the strategy assignment

    Returns:
        Number of trades taken under this assignment
    """
    a = session.query(StrategyAssignment).filter(StrategyAssignment.id == assignment_id).first()
    if not a:
        return 0

    # Count trades where:
    # - wallet_id matches
    # - symbol matches (normalized)
    # - strategy_id matches
    # - timestamp is between start_at and end_at (or after start_at if no end_at)
    query = session.query(func.count(ClosedTrade.id)).filter(
        ClosedTrade.wallet_id == a.wallet_id,
        ClosedTrade.symbol == a.symbol,
        ClosedTrade.strategy_id == a.strategy_id,
        ClosedTrade.timestamp >= a.start_at,
    )

    if a.end_at:
        query = query.filter(ClosedTrade.timestamp <= a.end_at)

    count = query.scalar()
    return count or 0


def list_strategies(session: Session) -> List[Strategy]:
    return session.query(Strategy).order_by(Strategy.name).all()


def create_strategy(session: Session, name: str, description: Optional[str] = None) -> Strategy:
    s = Strategy(name=name.strip(), description=(description or '').strip() or None)
    session.add(s)
    return s


def list_assignments(session: Session, wallet_id: Optional[int] = None) -> List[StrategyAssignment]:
    q = session.query(StrategyAssignment).order_by(StrategyAssignment.wallet_id, StrategyAssignment.symbol, StrategyAssignment.start_at.desc())
    if wallet_id:
        q = q.filter(StrategyAssignment.wallet_id == wallet_id)
    return q.all()


def create_assignment(session: Session, wallet_id: int, symbol: str, strategy_id: int, start_at: Optional[datetime] = None, notes: Optional[str] = None, is_current: bool = True) -> StrategyAssignment:
    sym = normalize_symbol(symbol)
    a = StrategyAssignment(
        wallet_id=wallet_id,
        symbol=sym,
        strategy_id=strategy_id,
        start_at=start_at or datetime.utcnow(),
        end_at=None,
        active=True,
        notes=notes,
        is_current=is_current,
    )
    session.add(a)
    return a


def end_assignment(session: Session, assignment_id: int, end_time: Optional[datetime] = None) -> Optional[StrategyAssignment]:
    a = session.query(StrategyAssignment).filter(StrategyAssignment.id == assignment_id).first()
    if not a:
        return None
    a.end_at = end_time or datetime.utcnow()
    a.active = False
    return a


def delete_assignment(session: Session, assignment_id: int) -> bool:
    """Delete a strategy assignment completely."""
    result = session.query(StrategyAssignment).filter(StrategyAssignment.id == assignment_id).delete()
    return result > 0


def resolve_strategy_id(session: Session, wallet_id: int, symbol: str, ts: datetime) -> Optional[int]:
    sym = normalize_symbol(symbol)
    a = (
        session.query(StrategyAssignment)
        .filter(
            StrategyAssignment.wallet_id == wallet_id,
            StrategyAssignment.symbol == sym,
            StrategyAssignment.start_at <= ts,
            (StrategyAssignment.end_at.is_(None) | (StrategyAssignment.end_at >= ts)),
        )
        .order_by(StrategyAssignment.start_at.desc())
        .first()
    )
    return a.strategy_id if a else None


def get_traded_symbols_by_wallet(session: Session) -> Dict[int, Set[str]]:
    """
    Get currently open position symbols per wallet from the latest position snapshots.
    Only includes positions with non-zero size and symbol != 'NO_POSITIONS'.

    Returns:
        Dict mapping wallet_id to set of symbols
    """
    result: Dict[int, Set[str]] = {}

    # Get the latest timestamp
    latest_ts = session.query(func.max(PositionSnapshot.timestamp)).scalar()

    if not latest_ts:
        return result

    # Get latest positions per wallet, excluding NO_POSITIONS and zero-size positions
    latest_positions = session.query(
        PositionSnapshot.wallet_id,
        PositionSnapshot.symbol
    ).filter(
        PositionSnapshot.timestamp == latest_ts,
        PositionSnapshot.wallet_id.isnot(None),
        PositionSnapshot.symbol != 'NO_POSITIONS',
        PositionSnapshot.size > 0  # Only open positions
    ).all()

    for wallet_id, symbol in latest_positions:
        if wallet_id not in result:
            result[wallet_id] = set()
        result[wallet_id].add(symbol)

    return result


def get_active_assignment_map(session: Session) -> Dict[tuple, int]:
    """
    Get a map of (wallet_id, symbol) -> strategy_id for all active assignments.

    Returns:
        Dict mapping (wallet_id, symbol) tuple to strategy_id
    """
    assignments = session.query(StrategyAssignment).filter(
        StrategyAssignment.active == True
    ).all()

    result = {}
    for a in assignments:
        key = (a.wallet_id, a.symbol)
        result[key] = a.strategy_id

    return result


