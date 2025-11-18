"""Centralized wallet refresh service.

This module handles refreshing wallet data from exchange APIs and storing to database.
All wallets (Apex, Hyperliquid, etc.) refresh through this service.
"""

from typing import Tuple, Optional, Dict, Any, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from db.database import get_session
from db.models import WalletConfig, PositionSnapshot
from db import queries
from services.wallet_service import WalletService
from services.data_service import get_enriched_account_data
from services.apex_client import get_all_fills
from services.sync_service import sync_closed_trades_from_fills
from services.aggregation_service import sync_aggregated_trades
from utils.data_utils import normalize_symbol
from utils.validation import sanitize_string, sanitize_float
from sqlalchemy import func


def refresh_wallet_data(wallet_id: int) -> Tuple[bool, Optional[str], Optional[datetime]]:
    """
    Refresh wallet data from API and store to database.
    
    This function:
    1. Fetches fresh data from exchange API
    2. Calculates leverage using margin delta method
    3. Calculates time in trade from API timestamps
    4. Stores equity snapshots and position snapshots with raw_data
    5. Syncs closed trades (Apex only)
    
    Args:
        wallet_id: Wallet ID to refresh
        
    Returns:
        Tuple of (success: bool, error_message: Optional[str], last_refresh_time: Optional[datetime])
    """
    try:
        refresh_time = datetime.utcnow()
        
        # Get wallet configuration
        with get_session() as session:
            wallet = session.query(WalletConfig).filter(WalletConfig.id == wallet_id).first()
            if not wallet:
                return (False, f"Wallet {wallet_id} not found", None)
            
            if wallet.status != 'connected':
                return (False, f"Wallet '{wallet.name}' is not connected", None)
            
            provider = wallet.provider
            wallet_name = wallet.name
        
        # Get API client for this wallet
        try:
            client = WalletService.get_wallet_client_by_id(wallet_id, with_logging=False)
        except Exception as e:
            return (False, f"Failed to create API client: {str(e)}", None)
        
        # Fetch data based on provider
        if provider == 'hyperliquid':
            success, error_msg = _refresh_hyperliquid_wallet(wallet_id, client, refresh_time)
        elif provider == 'apex_omni':
            success, error_msg = _refresh_apex_wallet(wallet_id, client, refresh_time)
        else:
            return (False, f"Provider '{provider}' not supported for refresh", None)
        
        if not success:
            return (False, error_msg, None)
        
        print(f"[{refresh_time.strftime('%Y-%m-%d %H:%M:%S')}] ✓ Refreshed wallet '{wallet_name}' (ID: {wallet_id})")
        return (True, None, refresh_time)
        
    except Exception as e:
        error_msg = f"Unexpected error refreshing wallet {wallet_id}: {str(e)}"
        print(f"Error: {error_msg}")
        return (False, error_msg, None)


def _refresh_hyperliquid_wallet(wallet_id: int, client, refresh_time: datetime) -> Tuple[bool, Optional[str]]:
    """Refresh Hyperliquid wallet data."""
    try:
        # Fetch clearinghouse state (full API response) first to get raw data
        clearinghouse_state = client.fetch_clearinghouse_state()
        
        # Extract raw position objects from clearinghouse state
        raw_positions_dict = {}
        asset_positions = clearinghouse_state.get("assetPositions", [])
        for ap in asset_positions:
            if isinstance(ap, dict):
                pos = ap.get("position", {})
                if isinstance(pos, dict):
                    coin = pos.get("coin", "")
                    size = float(pos.get("szi", 0) or 0)
                    if size != 0 and coin:
                        raw_positions_dict[coin] = pos
        
        # Get processed positions
        positions_raw = client.fetch_open_positions()
        
        # Get balances
        balances = client.fetch_balances()
        
        # Get margin data
        margin_summary = clearinghouse_state.get('marginSummary', {})
        current_margin_used = float(margin_summary.get('totalMarginUsed', 0) or 0)
        account_equity = float(margin_summary.get('accountValue', 0) or 0)
        
        # Fetch historical trades (last 90 days)
        try:
            since_ms = int((datetime.now() - timedelta(days=90)).timestamp() * 1000)
            hl_trades = client.fetch_trades(since_ms=since_ms, limit=1000)
        except Exception:
            hl_trades = []
        
        with get_session() as session:
            # Get account equity from DB for leverage calculation
            account_equity_db = queries.get_account_equity_at_timestamp(session, wallet_id, refresh_time)
            if not account_equity_db or account_equity_db <= 0:
                account_equity_db = account_equity  # Use API value
            
            # Store equity snapshot
            total_equity = 0.0
            total_unrealized = 0.0
            for b in balances:
                asset = b.get('asset', '')
                amount = float(b.get('amount') or 0)
                if asset == 'USDC':
                    total_equity = amount
                total_unrealized += float(b.get('unrealized_pnl') or 0)
            
            equity_data = {
                'wallet_id': wallet_id,
                'timestamp': refresh_time,
                'total_equity': total_equity,
                'unrealized_pnl': total_unrealized,
                'available_balance': total_equity,
                'realized_pnl': 0.0,
                'initial_margin': current_margin_used,
            }
            queries.insert_equity_snapshot(session, equity_data)
            
            # Process and store positions
            positions_stored = 0
            for p in positions_raw:
                asset = p.get('asset', '')
                size = float(p.get('quantity') or 0)
                entry_price = float(p.get('price') or 0)
                position_size_usd = abs(size * entry_price)
                
                # Get raw API position data
                raw_position_data = raw_positions_dict.get(asset, {})
                
                # Extract current price (mark price) from raw position data
                current_price = None
                if raw_position_data:
                    # Try to get mark price directly (Hyperliquid may provide markPx or similar)
                    mark_px = raw_position_data.get('markPx') or raw_position_data.get('markPrice') or raw_position_data.get('mark_price')
                    if mark_px:
                        try:
                            current_price = float(mark_px)
                        except (ValueError, TypeError):
                            pass
                    
                    # Fallback: calculate from positionValue and size
                    if current_price is None and abs(size) > 0:
                        position_value = raw_position_data.get('positionValue')
                        if position_value:
                            try:
                                position_value_float = float(position_value)
                                if position_value_float > 0:
                                    current_price = position_value_float / abs(size)
                            except (ValueError, TypeError):
                                pass
                
                # Calculate leverage using margin delta
                leverage = None
                equity_used = None
                calculation_method = 'unknown'
                
                if position_size_usd > 0:
                    from services.hyperliquid_leverage_calculator import calculate_leverage_from_margin_delta
                    leverage, equity_used, calculation_method = calculate_leverage_from_margin_delta(
                        session, wallet_id, asset,
                        position_size_usd, current_margin_used, refresh_time
                    )
                
                # Store position snapshot with raw API data
                position_data = {
                    'wallet_id': wallet_id,
                    'timestamp': refresh_time,
                    'symbol': asset,
                    'side': p.get('side', '').upper(),
                    'size': abs(size),
                    'entry_price': entry_price,
                    'current_price': current_price,
                    'position_size_usd': position_size_usd,
                    'leverage': leverage,
                    'unrealized_pnl': float(p.get('unrealized_pnl') or 0),
                    'funding_fee': None,
                    'equity_used': equity_used,
                    'calculation_method': calculation_method,
                    'raw_data': raw_position_data,  # Store ALL raw API data
                }
                queries.insert_position_snapshot(session, position_data)
                positions_stored += 1
            
            # Log zero-position marker if no positions
            if positions_stored == 0:
                position_data = {
                    'wallet_id': wallet_id,
                    'timestamp': refresh_time,
                    'symbol': 'NO_POSITIONS',
                    'side': 'NONE',
                    'size': 0.0,
                    'entry_price': 0.0,
                    'current_price': None,
                    'position_size_usd': 0.0,
                    'leverage': None,
                    'unrealized_pnl': 0.0,
                    'funding_fee': 0.0,
                    'equity_used': None,
                }
                queries.insert_position_snapshot(session, position_data)
            
            # Sync closed trades (upsert fills into closed_trades)
            if hl_trades:
                from db.queries_strategies import resolve_strategy_id
                trades_synced = 0
                for t in hl_trades:
                    try:
                        side_raw = t.get('side', '')
                        side = 'BUY' if side_raw.lower() in ('buy', 'b', 'long') else 'SELL'
                        asset = t.get('asset', '')
                        
                        # Resolve strategy
                        strategy_id = None
                        if asset:
                            trade_time = t.get('timestamp')
                            if isinstance(trade_time, datetime):
                                strategy_id = resolve_strategy_id(session, wallet_id, asset, trade_time)
                        
                        price = float(t.get('price') or 0)
                        trade_data = {
                            'wallet_id': wallet_id,
                            'timestamp': t.get('timestamp'),
                            'symbol': asset,
                            'side': side,
                            'size': float(t.get('quantity') or 0),
                            'price': price,
                            'entry_price': price,  # For Hyperliquid, use same price as entry
                            'exit_price': price,   # For Hyperliquid, use same price as exit
                            'trade_type': side,
                            'closed_pnl': 0.0,  # Will be calculated later if needed
                            'close_fee': float(t.get('fee') or 0),
                            'open_fee': 0.0,
                            'liquidate_fee': 0.0,
                            'exit_type': 'TRADE',
                            'strategy_id': strategy_id,
                        }
                        queries.upsert_closed_trade(session, trade_data, wallet_id=wallet_id)
                        trades_synced += 1
                    except Exception as e:
                        print(f"Warning: Failed to upsert Hyperliquid trade for {t.get('asset')}: {e}")
                        continue
                
                print(f"  Synced {trades_synced} Hyperliquid trades")
            
            session.commit()
        
        return (True, None)
        
    except Exception as e:
        return (False, f"Hyperliquid refresh error: {str(e)}")


def _refresh_apex_wallet(wallet_id: int, client, refresh_time: datetime) -> Tuple[bool, Optional[str]]:
    """Refresh Apex Omni wallet data."""
    try:
        # Fetch enriched account data from API
        account_data = get_enriched_account_data(client)
        balance = account_data.get('balance_data', {})
        positions = account_data.get('positions', [])
        
        with get_session() as session:
            # Store equity snapshot
            margin_used = float(balance.get('initialMargin', 0) or 0)
            
            equity_data = {
                'wallet_id': wallet_id,
                'timestamp': refresh_time,
                'total_equity': float(balance.get('totalEquityValue', 0) or 0),
                'unrealized_pnl': float(balance.get('unrealizedPnl', 0) or 0),
                'available_balance': float(balance.get('availableBalance', 0) or 0),
                'realized_pnl': float(balance.get('realizedPnl', 0) or 0),
                'initial_margin': margin_used,
            }
            queries.insert_equity_snapshot(session, equity_data)
            
            # Process and store positions
            positions_stored = 0
            for pos in positions:
                size = float(pos.get('size', 0) or 0)
                if size == 0:
                    continue
                
                symbol = normalize_symbol(pos.get('symbol', '')) or ''
                position_size_usd = abs(size) * float(pos.get('currentPrice', 0) or pos.get('entryPrice', 0) or 0)
                
                # Calculate leverage using margin delta
                leverage = None
                equity_used = None
                calculation_method = 'unknown'
                
                if position_size_usd > 0:
                    from services.apex_leverage_calculator import calculate_leverage_from_margin_delta
                    try:
                        current_initial_margin = float(balance.get('initialMargin', 0) or 0)
                        leverage, equity_used, calculation_method = calculate_leverage_from_margin_delta(
                            session, wallet_id, symbol, position_size_usd,
                            current_initial_margin, refresh_time, pos
                        )
                    except Exception as e:
                        print(f"Warning: Leverage calc failed for {symbol}: {e}")
                
                # Store position snapshot with raw API data
                position_data = {
                    'wallet_id': wallet_id,
                    'timestamp': refresh_time,
                    'symbol': symbol,
                    'side': sanitize_string(pos.get('side', ''), max_length=10, allow_empty=False),
                    'size': sanitize_float(size, default=0.0, min_val=0),
                    'entry_price': sanitize_float(pos.get('entryPrice', 0) or 0, default=0.0, min_val=0),
                    'current_price': sanitize_float(pos.get('currentPrice', 0) or 0, default=None, min_val=0) if pos.get('currentPrice') else None,
                    'position_size_usd': sanitize_float(position_size_usd, default=0.0, min_val=0),
                    'leverage': leverage,
                    'unrealized_pnl': sanitize_float(pos.get('unrealizedPnl', 0) or 0, default=0.0),
                    'funding_fee': sanitize_float(pos.get('fundingFee', 0) or 0, default=0.0),
                    'equity_used': equity_used,
                    'initial_margin_at_open': float(balance.get('initialMargin', 0) or 0) if leverage else None,
                    'calculation_method': calculation_method,
                    'raw_data': pos,  # Store complete position data from API
                }
                queries.insert_position_snapshot(session, position_data)
                positions_stored += 1
            
            # Log zero-position marker if no positions
            if positions_stored == 0:
                position_data = {
                    'wallet_id': wallet_id,
                    'timestamp': refresh_time,
                    'symbol': 'NO_POSITIONS',
                    'side': 'NONE',
                    'size': 0.0,
                    'entry_price': 0.0,
                    'current_price': None,
                    'position_size_usd': 0.0,
                    'leverage': None,
                    'unrealized_pnl': 0.0,
                    'funding_fee': 0.0,
                    'equity_used': None,
                }
                queries.insert_position_snapshot(session, position_data)
            
            # Sync closed trades from API
            try:
                fills = get_all_fills(client)
                trades_synced = sync_closed_trades_from_fills(session, fills, wallet_id)
                # Aggregate closed trades
                agg_count = sync_aggregated_trades(session, wallet_id=wallet_id)
                print(f"  Synced {trades_synced} closed trades, aggregated into {agg_count} trades")
            except Exception as e:
                print(f"Warning: Could not sync closed trades for Apex wallet {wallet_id}: {e}")
            
            session.commit()
        
        return (True, None)
        
    except Exception as e:
        return (False, f"Apex refresh error: {str(e)}")


def get_wallet_last_refresh_time(wallet_id: int) -> Optional[datetime]:
    """
    Get the last refresh time for a wallet.
    Uses the latest equity snapshot timestamp.
    
    Args:
        wallet_id: Wallet ID
        
    Returns:
        Last refresh datetime, or None if never refreshed
    """
    with get_session() as session:
        latest_snapshot = queries.get_latest_snapshot_time_per_wallet(session)
        return latest_snapshot.get(wallet_id)

