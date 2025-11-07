"""Data fetching and processing service."""
from typing import List, Dict, Any, TypedDict, Optional, Set
from datetime import datetime
from collections import defaultdict

from apexomni.http_private_v3 import HttpPrivate_v3
from sqlalchemy.orm import Session

from db import queries
from utils.calculations import estimate_equity_used, annotate_closed_pnl_equity_used


# TypedDict definitions for structured data types
class AccountDataDict(TypedDict):
    contract_wallets: List[Dict[str, Any]]
    spot_wallets: List[Dict[str, Any]]
    positions: List[Dict[str, Any]]
    balance_data: Dict[str, Any]
    orders: List[Dict[str, Any]]
    closed_pnl: List[Dict[str, Any]]


class HistoricalDataDict(TypedDict):
    equity_history: List[Dict[str, Any]]


class SymbolPnlDataDict(TypedDict):
    symbol_unrealized_history: Dict[str, List[Dict[str, Any]]]
    symbol_realized_history: Dict[str, List[Dict[str, Any]]]
    total_realized_series: List[Dict[str, Any]]
    symbols: List[str]


class RealizedPnlPointDict(TypedDict):
    timestamp: str
    pnl: float


def fetch_symbol_prices(client: HttpPrivate_v3, symbols: Set[str]) -> Dict[str, float]:
    """Fetch current prices for given symbols.
    
    Args:
        client: Authenticated Apex Omni API client
        symbols: Set of symbol strings to fetch prices for
        
    Returns:
        Dict mapping symbol -> current price
    """
    symbol_prices: Dict[str, float] = {}
    
    for symbol in symbols:
        if not symbol:
            continue
        try:
            ticker_result = client.ticker_v3(symbol=symbol)
            if ticker_result and isinstance(ticker_result, dict) and "data" in ticker_result:
                ticker_data = ticker_result["data"]
                if isinstance(ticker_data, list) and len(ticker_data) > 0:
                    ticker = ticker_data[0]
                    if isinstance(ticker, dict):
                        price_str = ticker.get("markPrice") or ticker.get("lastPrice") or "0"
                        try:
                            price = float(price_str) if price_str else 0.0
                            if price > 0:
                                symbol_prices[symbol] = price
                        except (ValueError, TypeError):
                            pass
        except Exception as e:
            print(f"Warning: Could not fetch ticker for {symbol}: {e}")
    
    return symbol_prices


def format_fills_timestamps(fills: List[Dict[str, Any]]) -> None:
    """Format timestamps for fill orders (modifies in-place).
    
    Args:
        fills: List of fill order dicts
    """
    for fill in fills:
        timestamp_ms = fill.get("createdAt")
        if timestamp_ms:
            try:
                dt = datetime.utcfromtimestamp(int(timestamp_ms) / 1000)
                fill["createdAtFormatted"] = dt.strftime("%Y-%m-%d %H:%M")
            except Exception:
                fill["createdAtFormatted"] = str(timestamp_ms)
        else:
            fill["createdAtFormatted"] = "-"


def format_orders_timestamps(orders: List[Dict[str, Any]]) -> None:
    """Format timestamps for open orders (modifies in-place).
    
    Args:
        orders: List of order dicts
    """
    for order in orders:
        timestamp_ms = order.get("createdAt") or order.get("createdTime")
        if timestamp_ms:
            try:
                dt = datetime.utcfromtimestamp(int(timestamp_ms) / 1000)
                order["createdAtFormatted"] = dt.strftime("%Y-%m-%d %H:%M")
            except Exception:
                order["createdAtFormatted"] = str(timestamp_ms)
        else:
            order["createdAtFormatted"] = "-"


def format_duration(seconds: float) -> str:
    """Format duration in seconds to human-readable string (e.g., '2d 5h', '3h 15m', '45m').
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        Formatted string like '2d 5h', '3h 15m', '45m', or '0m'
    """
    if seconds < 0:
        return "0m"
    
    days = int(seconds // 86400)
    hours = int((seconds % 86400) // 3600)
    minutes = int((seconds % 3600) // 60)
    
    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0 or not parts:
        parts.append(f"{minutes}m")
    
    return " ".join(parts) if parts else "0m"


def format_closed_pnl(closed_pnl: List[Dict[str, Any]]) -> None:
    """Format closed P&L data with timestamps and trade types (modifies in-place).
    
    Args:
        closed_pnl: List of closed P&L dicts
    """
    for pnl in closed_pnl:
        timestamp_ms = pnl.get("createdAt")
        if timestamp_ms:
            try:
                dt = datetime.utcfromtimestamp(int(timestamp_ms) / 1000)
                pnl["createdAtFormatted"] = dt.strftime("%Y-%m-%d %H:%M")
            except Exception:
                pnl["createdAtFormatted"] = str(timestamp_ms)
        else:
            pnl["createdAtFormatted"] = "-"
        
        # Derive trade type from side (LONG closes with SELL, SHORT closes with BUY)
        side = pnl.get("side", "").upper()
        pnl["tradeType"] = "SELL" if side == "LONG" else "BUY" if side == "SHORT" else "-"


def enrich_positions(positions: List[Dict[str, Any]], symbol_prices: Dict[str, float]) -> None:
    """Enrich positions with calculated fields (modifies in-place).
    
    Adds: leverage, positionSizeUsd, equityUsed, currentPrice, unrealizedPnl, openedFormatted, timeInTrade
    
    Args:
        positions: List of position dicts
        symbol_prices: Dict mapping symbol -> current price
    """
    for pos in positions:
        # Calculate leverage from margin rate
        margin_rate = float(pos.get("customInitialMarginRate", 0) or 0)
        pos["leverage"] = round(1.0 / margin_rate, 1) if margin_rate > 0 else None
        # Optional: log leverage snapshot per position
        try:
            from services.exchange_logging import get_exchange_logger, jlog
            jlog(get_exchange_logger(), {
                "exchange": "ApexOmni",
                "method": "positions_snapshot",
                "symbol": pos.get("symbol"),
                "side": pos.get("side"),
                "size": pos.get("size"),
                "entryPrice": pos.get("entryPrice"),
                "markPrice": pos.get("markPrice"),
                "customInitialMarginRate": pos.get("customInitialMarginRate"),
                "computedLeverage": pos.get("leverage"),
            })
        except Exception:
            pass
        
        # Get basic position info
        entry_price = float(pos.get("entryPrice", 0) or 0)
        size = float(pos.get("size", 0) or 0)
        symbol = pos.get("symbol", "")
        side = pos.get("side", "").upper()
        
        # Calculate position size in USD (Entry Price × Size)
        pos["positionSizeUsd"] = round(entry_price * abs(size), 2)
        
        # Estimate equity used = position size USD / leverage
        if pos["positionSizeUsd"] and pos.get("leverage"):
            pos["equityUsed"] = estimate_equity_used(pos["positionSizeUsd"], pos.get("leverage"))
        else:
            pos["equityUsed"] = None
        
        # Get current price from ticker or position's mark price
        current_price = symbol_prices.get(symbol, 0.0)
        if current_price == 0:
            # Try to get mark price from position itself
            mark_price_str = pos.get("markPrice", "0")
            try:
                current_price = float(mark_price_str) if mark_price_str else 0.0
            except (ValueError, TypeError):
                current_price = 0.0
        
        pos["currentPrice"] = round(current_price, 2) if current_price > 0 else None
        
        # Calculate unrealized PnL
        # First try to use API-provided value
        unrealized_pnl_str = pos.get("unrealizedPnl", "0")
        try:
            api_pnl = float(unrealized_pnl_str) if unrealized_pnl_str else 0.0
        except (ValueError, TypeError):
            api_pnl = 0.0
        
        # If API doesn't provide PnL or it's zero, calculate manually
        if api_pnl == 0.0 and current_price > 0 and entry_price > 0 and size != 0:
            if side == "LONG":
                # For LONG: profit when price goes up
                calculated_pnl = (current_price - entry_price) * abs(size)
            elif side == "SHORT":
                # For SHORT: profit when price goes down
                calculated_pnl = (entry_price - current_price) * abs(size)
            else:
                calculated_pnl = 0.0
            pos["unrealizedPnl"] = round(calculated_pnl, 2)
        else:
            pos["unrealizedPnl"] = round(api_pnl, 2)
        
        # Format timestamp
        # Use updatedTime (when position was last modified) instead of createdAt (original creation)
        # This gives us the actual open date when positions are closed and reopened
        timestamp_ms = pos.get("updatedTime") or pos.get("createdAt")
        if timestamp_ms:
            try:
                dt = datetime.utcfromtimestamp(int(timestamp_ms) / 1000)
                pos["openedFormatted"] = dt.strftime("%Y-%m-%d %H:%M")
                # Calculate time in trade
                now = datetime.utcnow()
                duration_seconds = (now - dt).total_seconds()
                pos["timeInTrade"] = format_duration(duration_seconds)
            except Exception:
                pos["openedFormatted"] = str(timestamp_ms)
                pos["timeInTrade"] = "-"
        else:
            # Don't set timeInTrade here if openedFormatted might be set elsewhere
            # Let the calling code handle it
            if "openedFormatted" not in pos:
                pos["openedFormatted"] = "-"
            # Don't set timeInTrade to "-" here - let it be calculated later
            if "timeInTrade" not in pos:
                pos["timeInTrade"] = None  # Use None instead of "-" so we know it wasn't set


def build_realized_pnl_series(closed_pnl: List[Dict[str, Any]]) -> Dict[str, List[RealizedPnlPointDict]]:
    """Build cumulative realized PnL time series per symbol from closed_pnl entries.
    
    Args:
        closed_pnl: List of closed P&L dicts
        
    Returns:
        Dict mapping symbol -> list of {timestamp: str, pnl: float} where pnl is cumulative
    """
    symbol_to_points: Dict[str, List[RealizedPnlPointDict]] = defaultdict(list)
    
    def to_ts(p):
        """Extract timestamp string for sorting."""
        ts = p.get("createdAtFormatted") or p.get("createdAt") or ""
        return ts
    
    # Group entries by symbol and sort within symbol by createdAtFormatted
    by_symbol: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for p in closed_pnl or []:
        sym = p.get("symbol")
        if not sym:
            continue
        by_symbol[sym].append(p)
    
    for sym, entries in by_symbol.items():
        # Sort by createdAt (formatted string) which is chronological
        entries_sorted = sorted(entries, key=lambda e: to_ts(e))
        cumulative = 0.0
        for e in entries_sorted:
            try:
                # Handle both API format (totalPnl) and database format (closed_pnl)
                pnl_val = float(e.get("totalPnl") or e.get("closed_pnl") or e.get("closedPnl") or 0)
            except (ValueError, TypeError):
                pnl_val = 0.0
            cumulative += pnl_val
            symbol_to_points[sym].append({
                'timestamp': e.get('createdAtFormatted') or to_ts(e),
                'pnl': round(cumulative, 2)
            })
    
    return symbol_to_points


def build_total_realized_series(closed_pnl: List[Dict[str, Any]]) -> List[RealizedPnlPointDict]:
    """Build cumulative total realized PnL across all symbols.
    
    Args:
        closed_pnl: List of closed P&L dicts (from database or API)
        
    Returns:
        List of {timestamp: str, pnl: float} where pnl is cumulative total
    """
    def to_ts(p):
        """Extract timestamp string for sorting."""
        return p.get("createdAtFormatted") or p.get("createdAt") or ""
    
    entries = sorted((closed_pnl or []), key=lambda e: to_ts(e))
    total: float = 0.0
    series: List[RealizedPnlPointDict] = []
    for e in entries:
        try:
            # Handle both API format (totalPnl) and database format (closed_pnl)
            pnl_val = float(e.get("totalPnl") or e.get("closed_pnl") or e.get("closedPnl") or 0)
        except (ValueError, TypeError):
            pnl_val = 0.0
        total += pnl_val
        series.append({
            'timestamp': e.get('createdAtFormatted') or to_ts(e),
            'pnl': round(total, 2)
        })
    return series


def get_enriched_account_data(client: HttpPrivate_v3) -> AccountDataDict:
    """Fetch and enrich all account data from the API.
    
    Args:
        client: Authenticated Apex Omni API client
        
    Returns:
        Dict containing enriched account data with keys:
        - contract_wallets, spot_wallets, positions, balance_data, orders, closed_pnl
    """
    # Fetch data from API
    account = client.get_account_v3()
    balances = client.get_account_balance_v3()
    open_orders = client.open_orders_v3()
    
    # Fetch closed positions P&L
    closed_pnl = []
    try:
        pnl_result = client.historical_pnl_v3(limit=100)
        if pnl_result and isinstance(pnl_result, dict) and "data" in pnl_result:
            pnl_data = pnl_result["data"]
            closed_pnl = pnl_data.get("historicalPnl", [])
            format_closed_pnl(closed_pnl)
    except Exception as e:
        print(f"Warning: Could not fetch historical P&L: {e}")
    
    # Extract key info
    balance_data = balances.get("data", {})
    contract_wallets = account.get("contractWallets", [])
    spot_wallets = account.get("spotWallets", [])
    positions = account.get("positions", [])
    orders_data = open_orders.get("data", [])
    
    # Fetch current prices for active positions
    position_symbols = set()
    for pos in positions:
        size = float(pos.get("size", 0) or 0)
        if abs(size) > 0.0001:
            position_symbols.add(pos.get("symbol", ""))
    
    symbol_prices = fetch_symbol_prices(client, position_symbols)
    
    # Enrich positions with calculated fields
    enrich_positions(positions, symbol_prices)
    
    return {
        'contract_wallets': contract_wallets,
        'spot_wallets': spot_wallets,
        'positions': positions,
        'balance_data': balance_data,
        'orders': orders_data,
        'closed_pnl': closed_pnl,
    }


def get_historical_data(session: Session, wallet_id: Optional[int] = None) -> HistoricalDataDict:
    """Get all historical data from database filtered by wallet.

    Args:
        session: Database session
        wallet_id: Optional wallet ID to filter by

    Returns:
        Dict containing historical data with keys:
        - equity_history
    """
    try:
        equity_history = queries.get_equity_history(session, wallet_id=wallet_id)
    except Exception as e:
        print(f"Warning: Could not read equity history from database: {e}")
        equity_history = []

    return {
        'equity_history': equity_history,
    }


def get_symbol_pnl_data(session: Session, closed_pnl: Optional[List[Dict[str, Any]]] = None, wallet_id: Optional[int] = None) -> SymbolPnlDataDict:
    """Get symbol-specific P&L data from database and closed trades.

    Args:
        session: Database session
        closed_pnl: Optional list of closed P&L dicts (if None, fetched from database)
        wallet_id: Optional wallet ID to filter by

    Returns:
        Dict containing symbol P&L data with keys:
        - symbol_unrealized_history, symbol_realized_history, total_realized_series, symbols
    """
    # Get unrealized PnL history from position snapshots
    try:
        symbol_unrealized_history = queries.get_position_history_by_symbol(session, wallet_id=wallet_id)
    except Exception as e:
        print(f"Warning: Could not read symbol PnL history from database: {e}")
        symbol_unrealized_history = {}

    # Always use database data for consistency, ignore API closed_pnl
    try:
        db_closed_pnl = queries.get_closed_trades(session, wallet_id=wallet_id)
    except Exception as e:
        print(f"Warning: Could not read closed trades from database: {e}")
        db_closed_pnl = []
    
    # Build realized PnL series from database data
    symbol_realized_history = build_realized_pnl_series(db_closed_pnl)
    total_realized_series = build_total_realized_series(db_closed_pnl)
    
    # Get leverage history and annotate closed_pnl with equity used
    try:
        lev_history = queries.get_leverage_history(session, wallet_id=wallet_id)
        annotate_closed_pnl_equity_used(db_closed_pnl, lev_history)
    except Exception as e:
        print(f"Warning: Could not annotate equity used: {e}")
    
    # Collect all traded symbols
    traded_symbols = set(symbol_unrealized_history.keys())
    traded_symbols.update(symbol_realized_history.keys())
    symbols = sorted(s for s in traded_symbols if s)
    
    return {
        'symbol_unrealized_history': symbol_unrealized_history,
        'symbol_realized_history': symbol_realized_history,
        'total_realized_series': total_realized_series,
        'symbols': symbols,
    }

