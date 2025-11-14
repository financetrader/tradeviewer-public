"""Database query helper functions."""
from typing import List, Dict, Any, Optional, TypedDict
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc, func, and_
from db.models import EquitySnapshot, PositionSnapshot, ClosedTrade
from utils.data_utils import normalize_symbol


# TypedDict definitions for structured return types
class EquityHistoryDict(TypedDict):
    timestamp: str
    total_equity: float
    unrealized_pnl: float
    available_balance: float
    realized_pnl: float


class PositionHistoryDict(TypedDict):
    timestamp: str
    pnl: float


class LeverageHistoryDict(TypedDict):
    timestamp: str
    leverage: Optional[float]


class ClosedTradeDict(TypedDict):
    timestamp: datetime
    createdAtFormatted: str
    side: str
    symbol: str
    size: float
    price: float  # For compatibility with app.py
    entryPrice: float
    exitPrice: float
    tradeType: str
    totalPnl: float  # For compatibility
    closedPnl: float
    closeFee: Optional[float]
    openFee: Optional[float]
    liquidateFee: Optional[float]
    exitType: Optional[str]
    equityUsed: float
    leverage: Optional[float]


class TotalRealizedPnlDict(TypedDict):
    timestamp: str
    pnl: float


class EquitySnapshotDataDict(TypedDict):
    wallet_id: Optional[int]
    timestamp: datetime
    total_equity: float
    unrealized_pnl: float
    available_balance: float
    realized_pnl: float


class PositionSnapshotDataDict(TypedDict):
    wallet_id: Optional[int]
    timestamp: datetime
    symbol: str
    side: str
    size: float
    entry_price: float
    current_price: Optional[float]
    position_size_usd: float
    leverage: Optional[float]
    unrealized_pnl: Optional[float]
    funding_fee: Optional[float]
    equity_used: Optional[float]


class ClosedTradeDataDict(TypedDict):
    wallet_id: Optional[int]
    timestamp: datetime
    side: str
    symbol: str
    size: float
    entry_price: float
    exit_price: float
    trade_type: str
    closed_pnl: float
    close_fee: Optional[float]
    open_fee: Optional[float]
    liquidate_fee: Optional[float]
    exit_type: Optional[str]
    equity_used: Optional[float]
    leverage: Optional[float]
def is_wallet_stale(last_update_timestamp: datetime, stale_hours: int = 2) -> bool:
    """
    Check if a wallet's last update is older than the staleness threshold.

    Args:
        last_update_timestamp: The timestamp of the wallet's last update
        stale_hours: Threshold in hours (default: 2 hours). If wallet hasn't updated in longer than this, it's stale.

    Returns:
        bool: True if wallet hasn't updated in >stale_hours, False otherwise

    Note:
        Used by the UI to show staleness warnings to users. This function does NOT filter data
        from queries - it's only for display purposes. See CLAUDE.md rule 6.
    """
    if last_update_timestamp is None:
        return True

    now = datetime.now()
    age_seconds = (now - last_update_timestamp).total_seconds()
    stale_seconds = stale_hours * 3600

    return age_seconds > stale_seconds


def get_equity_history(session: Session, wallet_id: Optional[int] = None, hours: Optional[int] = None) -> List[EquityHistoryDict]:
    """
    Get equity history snapshots.

    Args:
        session: Database session
        wallet_id: Optional wallet ID to filter by (None = aggregate across all connected wallets)
        hours: Optional filter for last N hours (None = all history)

    Returns:
        List of dicts with timestamp, total_equity, unrealized_pnl, available_balance, realized_pnl
        When wallet_id is None, returns aggregated totals per timestamp for connected wallets only
    """
    from db.models import WalletConfig
    
    if wallet_id:
        # Single wallet - return raw data
        query = session.query(EquitySnapshot).filter(
            EquitySnapshot.wallet_id == wallet_id
        ).order_by(EquitySnapshot.timestamp)

        if hours:
            cutoff = datetime.now() - timedelta(hours=hours)
            query = query.filter(EquitySnapshot.timestamp >= cutoff)

        results = []
        for snapshot in query.all():
            results.append({
                'timestamp': snapshot.timestamp.strftime("%Y-%m-%d %H:%M"),
                'total_equity': snapshot.total_equity,
                'unrealized_pnl': snapshot.unrealized_pnl,
                'available_balance': snapshot.available_balance,
                'realized_pnl': snapshot.realized_pnl
            })
        return results
    else:
        # Multiple wallets - build portfolio total by summing latest equity per wallet at each timestamp
        # Only include wallets with status == 'connected'
        from sqlalchemy import func
        from collections import defaultdict

        # Get connected wallet IDs
        connected_wallet_ids = session.query(WalletConfig.id).filter(
            WalletConfig.status == 'connected'
        ).subquery()

        # Get all equity snapshots for connected wallets only
        query = session.query(EquitySnapshot).filter(
            EquitySnapshot.wallet_id.in_(session.query(connected_wallet_ids.c.id)),
            EquitySnapshot.wallet_id.isnot(None)
        ).order_by(EquitySnapshot.timestamp)

        if hours:
            cutoff = datetime.now() - timedelta(hours=hours)
            query = query.filter(EquitySnapshot.timestamp >= cutoff)

        # Build a dictionary: timestamp -> {wallet_id -> equity_data}
        timestamp_data = defaultdict(dict)
        all_wallet_ids = set()

        for snapshot in query.all():
            if snapshot.wallet_id is None:
                continue
            ts_key = snapshot.timestamp.strftime("%Y-%m-%d %H:%M")
            wallet_key = snapshot.wallet_id  # Use wallet_id directly
            timestamp_data[ts_key][wallet_key] = {
                'total_equity': float(snapshot.total_equity or 0),
                'unrealized_pnl': float(snapshot.unrealized_pnl or 0),
                'available_balance': float(snapshot.available_balance or 0),
                'realized_pnl': float(snapshot.realized_pnl or 0)
            }
            all_wallet_ids.add(wallet_key)

        # For each timestamp, calculate portfolio total using latest data for each wallet
        # NOTE: Wallets are the source of truth. Aggregate ALL connected wallets' latest snapshots,
        # regardless of age. Staleness is shown in the UI, not filtered here. See CLAUDE.md rule 6.
        results = []
        latest_per_wallet = {}  # wallet_id -> (timestamp, equity_data)

        for ts_key in sorted(timestamp_data.keys()):
            # Update latest data for any wallets that have new snapshots at this timestamp
            for wallet_id, data in timestamp_data[ts_key].items():
                latest_per_wallet[wallet_id] = (ts_key, data)

            # Sum across ALL wallets using their latest data (no staleness filtering)
            portfolio_total = 0
            portfolio_unrealized = 0
            portfolio_available = 0
            portfolio_realized = 0

            for wallet_id, (ts_str, data) in latest_per_wallet.items():
                # Include ALL wallet data, regardless of age
                # Staleness is indicated to users via UI warnings, not by filtering data
                portfolio_total += data['total_equity']
                portfolio_unrealized += data['unrealized_pnl']
                portfolio_available += data['available_balance']
                portfolio_realized += data['realized_pnl']

            results.append({
                'timestamp': ts_key,
                'total_equity': portfolio_total,
                'unrealized_pnl': portfolio_unrealized,
                'available_balance': portfolio_available,
                'realized_pnl': portfolio_realized
            })

        return results


def get_position_history_by_symbol(session: Session, wallet_id: Optional[int] = None) -> Dict[str, List[PositionHistoryDict]]:
    """
    Get position snapshot history grouped by symbol.

    Args:
        session: Database session
        wallet_id: Optional wallet ID to filter by (None = all wallets)

    Returns:
        Dict mapping symbol -> list of {timestamp, pnl} for unrealized PnL
    """
    query = session.query(PositionSnapshot).order_by(PositionSnapshot.timestamp)
    if wallet_id:
        query = query.filter(PositionSnapshot.wallet_id == wallet_id)
    snapshots = query.all()
    
    symbol_history: Dict[str, List[PositionHistoryDict]] = {}
    for snapshot in snapshots:
        if snapshot.symbol not in symbol_history:
            symbol_history[snapshot.symbol] = []
        
        symbol_history[snapshot.symbol].append({
            'timestamp': snapshot.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            'pnl': round(snapshot.unrealized_pnl or 0, 2)
        })
    
    return symbol_history


def get_leverage_history(session: Session, wallet_id: Optional[int] = None) -> Dict[str, List[LeverageHistoryDict]]:
    """
    Get leverage history per symbol from position snapshots.

    Args:
        session: Database session
        wallet_id: Optional wallet ID to filter by (None = all wallets)

    Returns:
        Dict mapping symbol -> list of {timestamp, leverage}
    """
    query = session.query(PositionSnapshot).order_by(PositionSnapshot.timestamp)
    if wallet_id:
        query = query.filter(PositionSnapshot.wallet_id == wallet_id)
    snapshots = query.all()
    
    leverage_history: Dict[str, List[LeverageHistoryDict]] = {}
    for snapshot in snapshots:
        if snapshot.symbol not in leverage_history:
            leverage_history[snapshot.symbol] = []
        
        leverage_history[snapshot.symbol].append({
            'timestamp': snapshot.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            'leverage': snapshot.leverage
        })
    
    return leverage_history


def get_account_equity_at_timestamp(
    session: Session,
    wallet_id: Optional[int],
    timestamp: datetime
) -> Optional[float]:
    """Get account equity at or before a specific timestamp.
    
    This function queries equity_snapshots for the most recent equity value
    at or before the given timestamp. Used when logging positions to get
    current account equity for leverage calculations.
    
    Args:
        session: Database session
        wallet_id: Wallet ID to filter by
        timestamp: Timestamp to look up equity at
        
    Returns:
        Total equity value if found, None otherwise
    """
    if not wallet_id:
        return None
    
    query = (
        session.query(EquitySnapshot.total_equity)
        .filter(EquitySnapshot.wallet_id == wallet_id)
        .filter(EquitySnapshot.timestamp <= timestamp)
        .order_by(desc(EquitySnapshot.timestamp))
        .first()
    )
    
    if query and query[0] is not None:
        return float(query[0])
    
    return None


def get_leverage_at_timestamp(
    session: Session,
    wallet_id: Optional[int],
    symbol: str,
    timestamp: datetime
) -> Optional[float]:
    """Get leverage for a symbol/wallet at a specific timestamp from position snapshots.
    
    This looks up leverage that was calculated and stored when the position was open.
    Used when syncing closed trades to get the leverage that was calculated for the position.
    
    Args:
        session: Database session
        wallet_id: Wallet ID to filter by
        symbol: Symbol to look up
        timestamp: Timestamp to look up leverage at or before
        
    Returns:
        Leverage value if found, None otherwise
    """
    query = (
        session.query(PositionSnapshot.leverage)
        .filter(PositionSnapshot.symbol == normalize_symbol(symbol))
        .filter(PositionSnapshot.timestamp <= timestamp)
        .filter(PositionSnapshot.leverage.isnot(None))
        .filter(PositionSnapshot.size > 0)
    )
    
    if wallet_id:
        query = query.filter(PositionSnapshot.wallet_id == wallet_id)
    
    # Get the most recent leverage value before or at the trade timestamp
    result = query.order_by(desc(PositionSnapshot.timestamp)).first()
    
    if result and result[0] is not None:
        return float(result[0])
    
    return None


def get_aggregated_closed_trades(session: Session, symbol: Optional[str] = None, wallet_id: Optional[int] = None) -> List[ClosedTradeDict]:
    """
    Get closed trades history using aggregated_trades table.

    Exchange APIs return individual fills. This function queries aggregated_trades which
    groups fills by (wallet_id, timestamp, symbol) for cleaner display.

    Args:
        session: Database session
        symbol: Optional symbol filter
        wallet_id: Optional wallet ID to filter by

    Returns:
        List of closed trade dicts with strategy_name field
    """
    from db.models import AggregatedTrade, WalletConfig
    from db.models_strategies import Strategy
    from sqlalchemy.exc import OperationalError

    def _normalize_side(raw: Optional[str]) -> str:
        s = str(raw or '').lower()
        if s in ('b', 'bid', 'buy', 'long'):
            return 'buy'
        if s in ('a', 'ask', 'sell', 'short'):
            return 'sell'
        return s or 'buy'

    try:
        # Query aggregated_trades instead of closed_trades
        query = (
            session.query(AggregatedTrade, Strategy.name, WalletConfig.name)
            .outerjoin(Strategy, AggregatedTrade.strategy_id == Strategy.id)
            .outerjoin(WalletConfig, AggregatedTrade.wallet_id == WalletConfig.id)
            .order_by(desc(AggregatedTrade.timestamp))
        )

        if wallet_id:
            query = query.filter(AggregatedTrade.wallet_id == wallet_id)

        if symbol:
            query = query.filter(AggregatedTrade.symbol == symbol)

        trades = query.all()

    except OperationalError:
        # aggregated_trades table doesn't exist yet - fall back to closed_trades
        app.logger.warning("aggregated_trades table not found, falling back to get_closed_trades")
        return get_closed_trades(session, symbol=symbol, wallet_id=wallet_id)

    # Convert aggregated trades to result dicts
    from db.models import PositionSnapshot

    results = []
    for agg_trade, strategy_name, wallet_name in trades:
        side_norm = _normalize_side(agg_trade.side)
        trade_type_norm = _normalize_side(agg_trade.trade_type)

        leverage = None
        try:
            leverage = float(agg_trade.leverage) if agg_trade.leverage is not None else None
        except (AttributeError, TypeError):
            leverage = None

        # If leverage or equity_used is missing, look it up from position snapshots
        # ONLY use snapshots that were recorded while the position was open during this trade
        # Match: snapshot within 5 minutes after trade + similar position size (within 10%)
        equity_used = agg_trade.equity_used
        if (leverage is None or equity_used is None or equity_used == 0.0) and agg_trade.wallet_id and agg_trade.symbol:
            try:
                pos_snap = (
                    session.query(PositionSnapshot.leverage, PositionSnapshot.size, PositionSnapshot.equity_used)
                    .filter(PositionSnapshot.wallet_id == agg_trade.wallet_id)
                    .filter(PositionSnapshot.symbol == normalize_symbol(str(agg_trade.symbol)))
                    .filter(PositionSnapshot.timestamp >= agg_trade.timestamp)
                    .filter(PositionSnapshot.timestamp <= agg_trade.timestamp + timedelta(minutes=5))
                    .filter(PositionSnapshot.size > 0)
                    .order_by(asc(PositionSnapshot.timestamp))
                    .first()
                )
                if pos_snap:
                    pos_leverage, pos_size, pos_equity_used = pos_snap
                    # Verify the position size matches (same position, not a different one opened later)
                    # Allow 10% size difference to account for rounding/liquidations
                    if agg_trade.size > 0 and abs(pos_size - agg_trade.size) / agg_trade.size < 0.1:
                        if leverage is None and pos_leverage is not None:
                            leverage = float(pos_leverage)
                        if (equity_used is None or equity_used == 0.0) and pos_equity_used is not None:
                            equity_used = float(pos_equity_used)
            except Exception:
                pass  # If lookup fails, values stay as they are

        results.append({
            'timestamp': agg_trade.timestamp,
            'createdAtFormatted': agg_trade.timestamp.strftime("%Y-%m-%d %H:%M"),
            'side': side_norm,
            'symbol': normalize_symbol(str(agg_trade.symbol)),
            'size': agg_trade.size,
            'price': agg_trade.avg_entry_price,
            'entryPrice': agg_trade.avg_entry_price,
            'exitPrice': agg_trade.avg_exit_price,
            'tradeType': trade_type_norm,
            'totalPnl': agg_trade.total_pnl,
            'closedPnl': agg_trade.total_pnl,
            'closeFee': agg_trade.total_close_fee,
            'openFee': agg_trade.total_open_fee,
            'liquidateFee': agg_trade.total_liquidate_fee,
            'exitType': agg_trade.exit_type,
            'equityUsed': equity_used or 0.0,
            'leverage': leverage,
            'strategy_name': strategy_name,
            'wallet_id': agg_trade.wallet_id,
            'wallet_name': wallet_name,
        })

    return results


def get_closed_trades(session: Session, symbol: Optional[str] = None, wallet_id: Optional[int] = None) -> List[ClosedTradeDict]:
    """
    Get closed trades history with strategy names.

    Args:
        session: Database session
        symbol: Optional symbol filter
        wallet_id: Optional wallet ID to filter by

    Returns:
        List of closed trade dicts with strategy_name field
    """
    from db.models_strategies import Strategy
    from sqlalchemy.exc import OperationalError
    from sqlalchemy import text

    # Check if leverage column exists
    try:
        result = session.execute(text("PRAGMA table_info(closed_trades)"))
        columns = [row[1] for row in result]
        has_leverage_column = 'leverage' in columns
    except Exception:
        has_leverage_column = False

    try:
        query = session.query(ClosedTrade, Strategy.name).outerjoin(
            Strategy, ClosedTrade.strategy_id == Strategy.id
        ).order_by(desc(ClosedTrade.timestamp))

        if wallet_id:
            query = query.filter(ClosedTrade.wallet_id == wallet_id)
        
        if symbol:
            query = query.filter(ClosedTrade.symbol == symbol)
        
        trades = query.all()
    except OperationalError as e:
        # Handle case where leverage column doesn't exist yet
        if 'no such column' in str(e).lower() and 'leverage' in str(e).lower():
            # Column doesn't exist - need to run migration
            print(f"Warning: leverage column not found in closed_trades table. Please run migration: python db/migrations/add_leverage_to_closed_trades.py")
            # Try to continue without leverage - use raw SQL
            sql = """
                SELECT ct.*, s.name as strategy_name
                FROM closed_trades ct
                LEFT JOIN strategies s ON ct.strategy_id = s.id
            """
            conditions = []
            if wallet_id:
                conditions.append(f"ct.wallet_id = {wallet_id}")
            if symbol:
                # Escape single quotes in symbol for SQL
                escaped_symbol = symbol.replace("'", "''")
                conditions.append(f"ct.symbol = '{escaped_symbol}'")
            if conditions:
                sql += " WHERE " + " AND ".join(conditions)
            sql += " ORDER BY ct.timestamp DESC"
            
            result = session.execute(text(sql))
            trades = []
            for row in result:
                trade_dict = dict(row._mapping)
                strategy_name = trade_dict.pop('strategy_name', None)
                # Create a simple object-like dict for compatibility
                class TradeObj:
                    def __init__(self, d):
                        for k, v in d.items():
                            setattr(self, k, v)
                trade = TradeObj(trade_dict)
                trades.append((trade, strategy_name))
        else:
            raise
    
    def _normalize_side(raw: Optional[str]) -> str:
        s = str(raw or '').lower()
        if s in ('b', 'bid', 'buy', 'long'):
            return 'buy'
        if s in ('a', 'ask', 'sell', 'short'):
            return 'sell'
        return s or 'buy'

    results = []
    for trade, strategy_name in trades:
        side_norm = _normalize_side(trade.side)
        trade_type_norm = _normalize_side(trade.trade_type)
        
        # Handle leverage field - may not exist in database yet
        leverage = None
        if has_leverage_column:
            try:
                leverage = float(trade.leverage) if trade.leverage is not None else None
            except (AttributeError, TypeError):
                leverage = None
        
        results.append({
            'timestamp': trade.timestamp,
            'createdAtFormatted': trade.timestamp.strftime("%Y-%m-%d %H:%M"),
            'side': side_norm,
            'symbol': normalize_symbol(str(trade.symbol)),
            'size': trade.size,
            'price': trade.entry_price,  # For compatibility with app.py
            'entryPrice': trade.entry_price,
            'exitPrice': trade.exit_price,
            'tradeType': trade_type_norm,
            'totalPnl': trade.closed_pnl,  # For compatibility
            'closedPnl': trade.closed_pnl,
            'closeFee': trade.close_fee,
            'openFee': trade.open_fee,
            'liquidateFee': trade.liquidate_fee,
            'exitType': trade.exit_type,
            'equityUsed': trade.equity_used or 0.0,
            'leverage': leverage,
            'strategy_name': strategy_name  # Add strategy name
        })
    
    return results


def get_total_realized_pnl_series(session: Session) -> List[TotalRealizedPnlDict]:
    """
    Get cumulative realized PnL across all trades.
    
    Returns:
        List of {timestamp, pnl} where pnl is cumulative
    """
    trades = session.query(ClosedTrade).order_by(ClosedTrade.timestamp).all()
    
    cumulative = 0.0
    series = []
    for trade in trades:
        cumulative += trade.closed_pnl
        series.append({
            'timestamp': trade.timestamp.strftime("%Y-%m-%d %H:%M"),
            'pnl': round(cumulative, 2)
        })
    
    return series


def insert_equity_snapshot(session: Session, data: EquitySnapshotDataDict) -> EquitySnapshot:
    """
    Insert a new equity snapshot.

    Args:
        session: Database session
        data: Dict with keys: wallet_id, timestamp, total_equity, unrealized_pnl, available_balance, realized_pnl

    Returns:
        Created EquitySnapshot object
    """
    snapshot = EquitySnapshot(
        wallet_id=data.get('wallet_id'),
        wallet_address=None,  # No longer used as identifier
        timestamp=data['timestamp'] if isinstance(data['timestamp'], datetime) else datetime.fromisoformat(data['timestamp']),
        total_equity=float(data['total_equity']),  # type: ignore
        unrealized_pnl=float(data['unrealized_pnl']),  # type: ignore
        available_balance=float(data['available_balance']),  # type: ignore
        realized_pnl=float(data['realized_pnl']),  # type: ignore
        initial_margin=float(data['initial_margin']) if data.get('initial_margin') is not None else None  # type: ignore
    )
    session.add(snapshot)
    return snapshot


def insert_position_snapshot(session: Session, data: PositionSnapshotDataDict) -> PositionSnapshot:
    """
    Insert a new position snapshot.

    Args:
        session: Database session
        data: Dict with position data including wallet_id

    Returns:
        Created PositionSnapshot object
    """
    current_timestamp = data['timestamp'] if isinstance(data['timestamp'], datetime) else datetime.fromisoformat(data['timestamp'])
    wallet_id = data.get('wallet_id')
    symbol = data['symbol']
    current_size = float(data['size'])
    
    # Calculate opened_at: when this position was first opened
    opened_at = None
    if wallet_id and current_size > 0:
        # Check if this position already exists (has previous snapshots with size > 0)
        prev_snapshot = (
            session.query(PositionSnapshot)
            .filter(PositionSnapshot.wallet_id == wallet_id)
            .filter(PositionSnapshot.symbol == symbol)
            .filter(PositionSnapshot.size > 0)
            .filter(PositionSnapshot.timestamp < current_timestamp)
            .order_by(desc(PositionSnapshot.timestamp))
            .first()
        )
        
        if prev_snapshot and prev_snapshot.opened_at:
            # Position continues - use existing opened_at
            opened_at = prev_snapshot.opened_at
        else:
            # New position - set opened_at to current timestamp
            opened_at = current_timestamp
    
    snapshot = PositionSnapshot(
        wallet_id=wallet_id,
        wallet_address=None,  # No longer used as identifier
        timestamp=current_timestamp,
        symbol=symbol,
        side=data['side'],
        size=current_size,
        entry_price=float(data['entry_price']),  # type: ignore
        current_price=float(data['current_price']) if data.get('current_price') else None,  # type: ignore
        position_size_usd=float(data['position_size_usd']),  # type: ignore
        leverage=float(data['leverage']) if data.get('leverage') else None,  # type: ignore
        unrealized_pnl=float(data['unrealized_pnl']) if data.get('unrealized_pnl') else None,  # type: ignore
        funding_fee=float(data['funding_fee']) if data.get('funding_fee') else None,  # type: ignore
        equity_used=float(data['equity_used']) if data.get('equity_used') else None,  # type: ignore
        raw_data=data.get('raw_data'),  # Store complete API response
        initial_margin_at_open=float(data['initial_margin_at_open']) if data.get('initial_margin_at_open') is not None else None,  # type: ignore
        calculation_method=data.get('calculation_method'),  # How leverage was calculated
        opened_at=opened_at  # When position was first opened
    )
    session.add(snapshot)
    return snapshot


def insert_closed_trade(session: Session, data: ClosedTradeDataDict) -> ClosedTrade:
    """
    Insert a new closed trade.

    Args:
        session: Database session
        data: Dict with trade data including wallet_id

    Returns:
        Created ClosedTrade object
    """
    trade = ClosedTrade(
        wallet_id=data.get('wallet_id'),
        wallet_address=None,  # No longer used as identifier
        timestamp=data['timestamp'] if isinstance(data['timestamp'], datetime) else datetime.fromisoformat(data['timestamp']),
        side=data['side'],
        symbol=data['symbol'],
        size=float(data['size']),
        entry_price=float(data['entry_price']),
        exit_price=float(data['exit_price']),
        trade_type=data['trade_type'],
        closed_pnl=float(data['closed_pnl']),
        close_fee=float(data['close_fee']) if data.get('close_fee') else None,
        open_fee=float(data['open_fee']) if data.get('open_fee') else None,
        liquidate_fee=float(data['liquidate_fee']) if data.get('liquidate_fee') else None,
        exit_type=data.get('exit_type'),
        equity_used=float(data['equity_used']) if data.get('equity_used') else None,
        leverage=float(data['leverage']) if data.get('leverage') else None
    )
    session.add(trade)
    return trade


def upsert_closed_trade(session: Session, data: ClosedTradeDataDict, wallet_id: Optional[int] = None) -> ClosedTrade:
    """
    Insert or update a closed trade uniquely identified by wallet_id, symbol, timestamp, and size.
    If a matching row exists, update numeric fields; otherwise insert a new one.
    """
    # Normalize input
    ts = data['timestamp'] if isinstance(data['timestamp'], datetime) else datetime.fromisoformat(data['timestamp'])
    symbol = normalize_symbol(str(data['symbol']))
    size = float(data['size'])

    # Build filter for existing trade
    existing = session.query(ClosedTrade).filter(
        ClosedTrade.wallet_id == wallet_id if wallet_id is not None else ClosedTrade.wallet_id.is_(None),
        ClosedTrade.symbol == symbol,
        ClosedTrade.timestamp == ts,
        ClosedTrade.size == size,
    ).first()

    if existing:
        existing.side = data['side']  # type: ignore
        existing.entry_price = float(data['entry_price'])  # type: ignore
        existing.exit_price = float(data['exit_price'])  # type: ignore
        existing.trade_type = data['trade_type']  # type: ignore
        existing.closed_pnl = float(data['closed_pnl'])  # type: ignore
        existing.close_fee = float(data['close_fee']) if data.get('close_fee') else existing.close_fee  # type: ignore
        existing.open_fee = float(data['open_fee']) if data.get('open_fee') else existing.open_fee  # type: ignore
        existing.liquidate_fee = float(data['liquidate_fee']) if data.get('liquidate_fee') else existing.liquidate_fee  # type: ignore
        existing.exit_type = data.get('exit_type', existing.exit_type)  # type: ignore
        existing.equity_used = float(data['equity_used']) if data.get('equity_used') else existing.equity_used  # type: ignore
        existing.leverage = float(data['leverage']) if data.get('leverage') is not None else getattr(existing, 'leverage', None)  # type: ignore
        existing.strategy_id = data.get('strategy_id')  # type: ignore  # Update strategy_id
        existing.reduce_only = data.get('reduce_only')  # type: ignore  # Update reduce_only flag
        return existing

    trade = ClosedTrade(
        wallet_id=wallet_id,
        wallet_address=None,  # No longer used as identifier
        timestamp=ts,
        side=data['side'],
        symbol=symbol,
        size=size,
        entry_price=float(data['entry_price']),  # type: ignore
        exit_price=float(data['exit_price']),  # type: ignore
        trade_type=data['trade_type'],
        closed_pnl=float(data['closed_pnl']),  # type: ignore
        close_fee=float(data['close_fee']) if data.get('close_fee') else None,  # type: ignore
        open_fee=float(data['open_fee']) if data.get('open_fee') else None,  # type: ignore
        liquidate_fee=float(data['liquidate_fee']) if data.get('liquidate_fee') else None,  # type: ignore
        exit_type=data.get('exit_type'),
        equity_used=float(data['equity_used']) if data.get('equity_used') else None,  # type: ignore
        leverage=float(data['leverage']) if data.get('leverage') is not None else None,  # type: ignore
        strategy_id=data.get('strategy_id')
    )
    session.add(trade)
    return trade


def get_latest_equity_per_wallet(session: Session, wallet_id: Optional[int] = None) -> Dict[int, float]:
    """Get latest total_equity per wallet_id.

    Args:
        session: Database session
        wallet_id: Optional wallet_id to filter by

    Returns:
        Dict mapping wallet_id to latest total_equity
    """
    subq = (
        session.query(
            EquitySnapshot.wallet_id.label("wid"),
            func.max(EquitySnapshot.timestamp).label("max_ts"),
        )
        .filter(EquitySnapshot.wallet_id.isnot(None))
    )

    if wallet_id:
        subq = subq.filter(EquitySnapshot.wallet_id == wallet_id)

    subq = subq.group_by(EquitySnapshot.wallet_id).subquery()

    query = (
        session.query(EquitySnapshot.wallet_id, EquitySnapshot.total_equity)
        .join(subq, and_(
            EquitySnapshot.wallet_id == subq.c.wid,
            EquitySnapshot.timestamp == subq.c.max_ts
        ))
    )

    if wallet_id:
        query = query.filter(EquitySnapshot.wallet_id == wallet_id)

    rows = query.all()
    return {int(wid): float(equity or 0.0) for wid, equity in rows if wid is not None}


def get_latest_unrealized_pnl_per_wallet(session: Session, wallet_id: Optional[int] = None) -> Dict[int, float]:
    """Get latest unrealized_pnl per wallet_id.

    Args:
        session: Database session
        wallet_id: Optional wallet_id to filter by

    Returns:
        Dict mapping wallet_id to latest unrealized_pnl
    """
    subq = (
        session.query(
            EquitySnapshot.wallet_id.label("wid"),
            func.max(EquitySnapshot.timestamp).label("max_ts"),
        )
        .filter(EquitySnapshot.wallet_id.isnot(None))
    )

    if wallet_id:
        subq = subq.filter(EquitySnapshot.wallet_id == wallet_id)

    subq = subq.group_by(EquitySnapshot.wallet_id).subquery()

    query = (
        session.query(EquitySnapshot.wallet_id, EquitySnapshot.unrealized_pnl)
        .join(subq, and_(
            EquitySnapshot.wallet_id == subq.c.wid,
            EquitySnapshot.timestamp == subq.c.max_ts
        ))
    )

    if wallet_id:
        query = query.filter(EquitySnapshot.wallet_id == wallet_id)

    rows = query.all()
    return {int(wid): float(upnl or 0.0) for wid, upnl in rows if wid is not None}


def get_latest_available_balance_per_wallet(session: Session, wallet_id: Optional[int] = None) -> Dict[int, float]:
    """Get latest available_balance per wallet_id.

    Args:
        session: Database session
        wallet_id: Optional wallet_id to filter by

    Returns:
        Dict mapping wallet_id to latest available_balance
    """
    subq = (
        session.query(
            EquitySnapshot.wallet_id.label("wid"),
            func.max(EquitySnapshot.timestamp).label("max_ts"),
        )
        .filter(EquitySnapshot.wallet_id.isnot(None))
    )

    if wallet_id:
        subq = subq.filter(EquitySnapshot.wallet_id == wallet_id)

    subq = subq.group_by(EquitySnapshot.wallet_id).subquery()

    query = (
        session.query(EquitySnapshot.wallet_id, EquitySnapshot.available_balance)
        .join(subq, and_(
            EquitySnapshot.wallet_id == subq.c.wid,
            EquitySnapshot.timestamp == subq.c.max_ts
        ))
    )

    if wallet_id:
        query = query.filter(EquitySnapshot.wallet_id == wallet_id)

    rows = query.all()
    return {int(wid): float(bal or 0.0) for wid, bal in rows if wid is not None}


def get_latest_snapshot_time_per_wallet(session: Session, wallet_id: Optional[int] = None) -> Dict[int, datetime]:
    """Get latest snapshot timestamp per wallet_id.

    Args:
        session: Database session
        wallet_id: Optional wallet_id to filter by

    Returns:
        Dict mapping wallet_id to latest snapshot timestamp
    """
    query = (
        session.query(
            EquitySnapshot.wallet_id,
            func.max(EquitySnapshot.timestamp).label("max_ts")
        )
        .filter(EquitySnapshot.wallet_id.isnot(None))
    )

    if wallet_id:
        query = query.filter(EquitySnapshot.wallet_id == wallet_id)

    rows = query.group_by(EquitySnapshot.wallet_id).all()
    return {int(wid): ts for wid, ts in rows if wid is not None and ts is not None}


def get_realized_pnl_by_wallet(session: Session, start: datetime, end: datetime, wallet_id: Optional[int] = None) -> Dict[int, float]:
    """Sum realized PnL per wallet in [start, end) interval.

    Args:
        session: Database session
        start: Start of time range (inclusive)
        end: End of time range (exclusive)
        wallet_id: Optional wallet_id to filter by

    Returns:
        Dict mapping wallet_id to total realized PnL in period
    """
    query = (
        session.query(ClosedTrade.wallet_id, func.sum(ClosedTrade.closed_pnl))
        .filter(ClosedTrade.wallet_id.isnot(None))
        .filter(ClosedTrade.timestamp >= start)
        .filter(ClosedTrade.timestamp < end)
    )

    if wallet_id:
        query = query.filter(ClosedTrade.wallet_id == wallet_id)

    rows = query.group_by(ClosedTrade.wallet_id).all()
    return {int(wid): float(pnl or 0.0) for wid, pnl in rows if wid is not None}


def get_trade_counts_by_wallet(session: Session, start: datetime, end: datetime, wallet_id: Optional[int] = None) -> Dict[int, int]:
    """Count closed trades per wallet in [start, end) interval.

    Args:
        session: Database session
        start: Start of time range (inclusive)
        end: End of time range (exclusive)
        wallet_id: Optional wallet_id to filter by

    Returns:
        Dict mapping wallet_id to trade count in period
    """
    query = (
        session.query(ClosedTrade.wallet_id, func.count(ClosedTrade.id))
        .filter(ClosedTrade.wallet_id.isnot(None))
        .filter(ClosedTrade.timestamp >= start)
        .filter(ClosedTrade.timestamp < end)
    )

    if wallet_id:
        query = query.filter(ClosedTrade.wallet_id == wallet_id)

    rows = query.group_by(ClosedTrade.wallet_id).all()
    return {int(wid): int(cnt) for wid, cnt in rows if wid is not None}


def get_win_rates_by_wallet(session: Session, start: datetime, end: datetime, zero_is_loss: bool = True, wallet_id: Optional[int] = None) -> Dict[int, float]:
    """Calculate win rate per wallet in [start, end). Win = closed_pnl > 0.

    Args:
        session: Database session
        start: Start of time range (inclusive)
        end: End of time range (exclusive)
        zero_is_loss: If True, count zero PnL as a loss
        wallet_id: Optional wallet_id to filter by

    Returns:
        Dict mapping wallet_id to win rate percentage
    """
    query = (
        session.query(ClosedTrade.wallet_id, ClosedTrade.closed_pnl)
        .filter(ClosedTrade.wallet_id.isnot(None))
        .filter(ClosedTrade.timestamp >= start)
        .filter(ClosedTrade.timestamp < end)
    )

    if wallet_id:
        query = query.filter(ClosedTrade.wallet_id == wallet_id)

    trades = query.all()

    wallet_stats: Dict[int, tuple[int, int]] = {}  # wallet_id -> (wins, total)
    for wid, pnl in trades:
        if wid is None:
            continue
        wid = int(wid)
        if wid not in wallet_stats:
            wallet_stats[wid] = (0, 0)
        wins, total = wallet_stats[wid]
        total += 1
        if pnl > 0 or (not zero_is_loss and pnl == 0):
            wins += 1
        wallet_stats[wid] = (wins, total)

    return {wid: (wins / total * 100.0 if total > 0 else 0.0) for wid, (wins, total) in wallet_stats.items()}


def get_strategy_performance(session: Session, start: datetime, end: datetime, wallet_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Get performance metrics per strategy.

    Args:
        session: Database session
        start: Start of time range (inclusive)
        end: End of time range (exclusive)
        wallet_id: Optional wallet_id to filter by

    Returns:
        List of dicts with strategy_id, strategy_name, total_pnl, trade_count, win_rate, avg_pnl
    """
    from db.models_strategies import Strategy

    query = (
        session.query(ClosedTrade.strategy_id, ClosedTrade.closed_pnl, Strategy.name)
        .outerjoin(Strategy, ClosedTrade.strategy_id == Strategy.id)
        .filter(ClosedTrade.timestamp >= start)
        .filter(ClosedTrade.timestamp < end)
    )

    if wallet_id:
        query = query.filter(ClosedTrade.wallet_id == wallet_id)

    trades = query.all()

    strategy_stats: Dict[Optional[int], Dict[str, Any]] = {}
    for strategy_id, pnl, strategy_name in trades:
        if strategy_id not in strategy_stats:
            strategy_stats[strategy_id] = {
                'strategy_id': strategy_id,
                'strategy_name': strategy_name or 'Unassigned',
                'total_pnl': 0.0,
                'trade_count': 0,
                'wins': 0,
                'pnls': []
            }

        strategy_stats[strategy_id]['total_pnl'] += float(pnl or 0)
        strategy_stats[strategy_id]['trade_count'] += 1
        strategy_stats[strategy_id]['pnls'].append(float(pnl or 0))
        if pnl > 0:
            strategy_stats[strategy_id]['wins'] += 1

    results = []
    for sid, stats in strategy_stats.items():
        trade_count = stats['trade_count']
        wins = stats['wins']
        win_rate = (wins / trade_count * 100.0) if trade_count > 0 else 0.0
        avg_pnl = stats['total_pnl'] / trade_count if trade_count > 0 else 0.0

        results.append({
            'strategy_id': sid,
            'strategy_name': stats['strategy_name'],
            'total_pnl': round(stats['total_pnl'], 2),
            'trade_count': trade_count,
            'win_rate': round(win_rate, 2),
            'avg_pnl': round(avg_pnl, 2),
        })

    # Sort by total PnL descending
    results.sort(key=lambda x: x['total_pnl'], reverse=True)
    return results


def get_symbol_performance(session: Session, start: datetime, end: datetime, wallet_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Get performance metrics per symbol.

    Returns:
        List of dicts with symbol, total_pnl, trade_count, win_rate, avg_pnl
    """
    query = session.query(ClosedTrade.symbol, ClosedTrade.closed_pnl)

    if wallet_id:
        query = query.filter(ClosedTrade.wallet_id == wallet_id)

    trades = query.filter(ClosedTrade.timestamp >= start).filter(ClosedTrade.timestamp < end).all()

    symbol_stats: Dict[str, Dict[str, Any]] = {}
    for symbol, pnl in trades:
        if symbol not in symbol_stats:
            symbol_stats[symbol] = {
                'symbol': symbol,
                'total_pnl': 0.0,
                'trade_count': 0,
                'wins': 0,
            }

        symbol_stats[symbol]['total_pnl'] += float(pnl or 0)
        symbol_stats[symbol]['trade_count'] += 1
        if pnl > 0:
            symbol_stats[symbol]['wins'] += 1

    results = []
    for symbol, stats in symbol_stats.items():
        trade_count = stats['trade_count']
        wins = stats['wins']
        win_rate = (wins / trade_count * 100.0) if trade_count > 0 else 0.0
        avg_pnl = stats['total_pnl'] / trade_count if trade_count > 0 else 0.0

        results.append({
            'symbol': symbol,
            'total_pnl': round(stats['total_pnl'], 2),
            'trade_count': trade_count,
            'win_rate': round(win_rate, 2),
            'avg_pnl': round(avg_pnl, 2),
        })

    # Sort by total PnL descending
    results.sort(key=lambda x: x['total_pnl'], reverse=True)
    return results


def get_active_positions_count(session: Session, wallet_id: Optional[int] = None) -> Dict[int, int]:
    """Get count of active positions per wallet from latest snapshots.

    Args:
        session: Database session
        wallet_id: Optional wallet_id to filter by

    Returns:
        Dict mapping wallet_id to active position count
    """
    # Get latest timestamp per wallet
    subq = (
        session.query(
            PositionSnapshot.wallet_id.label("wid"),
            func.max(PositionSnapshot.timestamp).label("max_ts"),
        )
        .filter(PositionSnapshot.wallet_id.isnot(None))
    )

    if wallet_id:
        subq = subq.filter(PositionSnapshot.wallet_id == wallet_id)

    subq = subq.group_by(PositionSnapshot.wallet_id).subquery()

    # Count positions at latest timestamp where size > 0
    query = (
        session.query(PositionSnapshot.wallet_id, func.count(PositionSnapshot.id))
        .join(subq, and_(
            PositionSnapshot.wallet_id == subq.c.wid,
            PositionSnapshot.timestamp == subq.c.max_ts
        ))
        .filter(PositionSnapshot.size > 0)
    )

    if wallet_id:
        query = query.filter(PositionSnapshot.wallet_id == wallet_id)

    rows = query.group_by(PositionSnapshot.wallet_id).all()

    return {int(wid): int(cnt) for wid, cnt in rows if wid is not None}


def get_recent_trades(session: Session, limit: int = 10, wallet_id: Optional[int] = None) -> List[ClosedTradeDict]:
    """Get most recent trades.

    Args:
        session: Database session
        limit: Maximum number of trades to return
        wallet_id: Optional wallet_id to filter by

    Returns:
        List of closed trade dicts
    """
    from db.models_strategies import Strategy
    from db.models import WalletConfig
    from sqlalchemy.exc import OperationalError
    from sqlalchemy import text

    # Check if leverage column exists
    try:
        result = session.execute(text("PRAGMA table_info(closed_trades)"))
        columns = [row[1] for row in result]
        has_leverage_column = 'leverage' in columns
    except Exception:
        has_leverage_column = False

    try:
        from db.models import AggregatedTrade
        query = (
            session.query(AggregatedTrade, Strategy.name, WalletConfig.name)
            .outerjoin(Strategy, AggregatedTrade.strategy_id == Strategy.id)
            .outerjoin(WalletConfig, AggregatedTrade.wallet_id == WalletConfig.id)
        )

        if wallet_id:
            query = query.filter(AggregatedTrade.wallet_id == wallet_id)

        query = query.order_by(desc(AggregatedTrade.timestamp)).limit(limit)
        trades = query.all()
    except OperationalError as e:
        # Handle case where leverage column doesn't exist yet
        if 'no such column' in str(e).lower() and 'leverage' in str(e).lower():
            # Column doesn't exist - need to run migration
            print(f"Warning: leverage column not found in closed_trades table. Please run migration: python db/migrations/add_leverage_to_closed_trades.py")
            # Try to continue without leverage - use raw SQL
            sql = """
                SELECT ct.*, s.name as strategy_name, wc.name as wallet_name
                FROM closed_trades ct
                LEFT JOIN strategies s ON ct.strategy_id = s.id
                LEFT JOIN wallet_configs wc ON ct.wallet_id = wc.id
            """
            conditions = []
            if wallet_id:
                conditions.append(f"ct.wallet_id = {wallet_id}")
            if conditions:
                sql += " WHERE " + " AND ".join(conditions)
            # Fetch more trades initially to account for filtering out zero PnL trades
            fetch_limit = limit * 3
            sql += f" ORDER BY ct.timestamp DESC LIMIT {fetch_limit}"
            
            result = session.execute(text(sql))
            trades = []
            for row in result:
                trade_dict = dict(row._mapping)
                strategy_name = trade_dict.pop('strategy_name', None)
                wallet_name = trade_dict.pop('wallet_name', None)
                # Create a simple object-like dict for compatibility
                class TradeObj:
                    def __init__(self, d):
                        for k, v in d.items():
                            setattr(self, k, v)
                trade = TradeObj(trade_dict)
                trades.append((trade, strategy_name, wallet_name))
        else:
            raise

    def _normalize_side(raw: Optional[str]) -> str:
        s = str(raw or '').lower()
        if s in ('b', 'bid', 'buy', 'long'):
            return 'buy'
        if s in ('a', 'ask', 'sell', 'short'):
            return 'sell'
        return s or 'buy'

    # Convert aggregated trades to result dicts
    results = []
    for agg_trade, strategy_name, wallet_name in trades:
        side_norm = _normalize_side(agg_trade.side)
        trade_type_norm = _normalize_side(agg_trade.trade_type)

        leverage = None
        if has_leverage_column:
            try:
                leverage = float(agg_trade.leverage) if agg_trade.leverage is not None else None
            except (AttributeError, TypeError):
                leverage = None

        equity_used = None
        try:
            equity_used = float(agg_trade.equity_used) if agg_trade.equity_used is not None else None
        except (AttributeError, TypeError):
            equity_used = None

        results.append({
            'timestamp': agg_trade.timestamp,
            'createdAtFormatted': agg_trade.timestamp.strftime("%Y-%m-%d %H:%M"),
            'side': side_norm,
            'symbol': normalize_symbol(str(agg_trade.symbol)),
            'size': agg_trade.size,
            'price': agg_trade.avg_entry_price,
            'entryPrice': agg_trade.avg_entry_price,
            'exitPrice': agg_trade.avg_exit_price,
            'tradeType': trade_type_norm,
            'totalPnl': agg_trade.total_pnl,
            'closedPnl': agg_trade.total_pnl,
            'closeFee': agg_trade.total_close_fee,
            'openFee': agg_trade.total_open_fee,
            'liquidateFee': agg_trade.total_liquidate_fee,
            'exitType': agg_trade.exit_type,
            'equityUsed': equity_used or 0.0,
            'leverage': leverage,
            'strategy_name': strategy_name,
            'wallet_id': agg_trade.wallet_id,
            'wallet_name': wallet_name,
        })

    return results


def get_open_positions(session: Session, wallet_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Get all open positions from latest position snapshots.

    Args:
        session: Database session
        wallet_id: Optional wallet_id to filter by

    Returns:
        List of dicts with wallet_id, wallet_name, symbol, side, size, entry_price,
        current_price, unrealized_pnl, position_size_usd, strategy_name
    """
    from db.models import WalletConfig
    from db.models_strategies import Strategy

    # Get latest timestamp per wallet
    subq = (
        session.query(
            PositionSnapshot.wallet_id.label("wid"),
            func.max(PositionSnapshot.timestamp).label("max_ts"),
        )
        .filter(PositionSnapshot.wallet_id.isnot(None))
    )

    if wallet_id:
        subq = subq.filter(PositionSnapshot.wallet_id == wallet_id)

    subq = subq.group_by(PositionSnapshot.wallet_id).subquery()

    # Get positions at latest timestamp where size > 0
    query = (
        session.query(
            PositionSnapshot,
            WalletConfig.name.label("wallet_name"),
            Strategy.name.label("strategy_name")
        )
        .join(subq, and_(
            PositionSnapshot.wallet_id == subq.c.wid,
            PositionSnapshot.timestamp == subq.c.max_ts
        ))
        .join(WalletConfig, PositionSnapshot.wallet_id == WalletConfig.id)
        .outerjoin(Strategy, PositionSnapshot.strategy_id == Strategy.id)
        .filter(PositionSnapshot.size > 0)
    )

    if wallet_id:
        query = query.filter(PositionSnapshot.wallet_id == wallet_id)

    # Sort by opened_at (when position was first opened) DESC - newest positions first
    query = query.order_by(desc(PositionSnapshot.opened_at))

    results = []
    for pos, wallet_name, strategy_name in query.all():
        results.append({
            'wallet_id': pos.wallet_id,
            'wallet_name': wallet_name,
            'symbol': normalize_symbol(str(pos.symbol)),
            'side': pos.side,
            'size': float(pos.size),
            'entry_price': float(pos.entry_price or 0),
            'current_price': float(pos.current_price or 0) if pos.current_price else None,
            'unrealized_pnl': float(pos.unrealized_pnl or 0),
            'position_size_usd': float(pos.position_size_usd or 0),
            'leverage': float(pos.leverage) if pos.leverage else None,
            'equity_used': float(pos.equity_used) if pos.equity_used is not None else None,
            'strategy_name': strategy_name,
            'timestamp': pos.timestamp,
        })

    return results

