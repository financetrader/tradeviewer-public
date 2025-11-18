import os
import time
from datetime import datetime
from dotenv import load_dotenv

# Database imports
from db.database import get_session
from db.models import WalletConfig
from db import queries
from services.apex_client import make_client
from services.wallet_service import WalletService

# Optional: direct Apex client creation for admin wallet
try:
    from apexomni.http_private_v3 import HttpPrivate_v3
    from apexomni.constants import APEX_OMNI_HTTP_MAIN, NETWORKID_OMNI_MAIN_ARB
except Exception:
    HttpPrivate_v3 = None
    APEX_OMNI_HTTP_MAIN = None
    NETWORKID_OMNI_MAIN_ARB = None

load_dotenv()


def log_positions_for_all_wallets():
    """Fetch and log position snapshots for all connected wallets"""
    try:
        from services.wallet_service import WalletService
        from services.data_service import get_enriched_account_data

        timestamp_dt = datetime.utcnow()
        timestamp_str = timestamp_dt.strftime("%Y-%m-%d %H:%M:%S")

        # Get all wallets
        wallets = WalletService.get_all_connected_wallets()

        total_positions_logged = 0

        with get_session() as session:
            for wallet in wallets:
                try:
                    wallet_id = wallet['id']
                    provider = wallet['provider']

                    # Get client for this wallet
                    client = WalletService.get_wallet_client_by_id(wallet_id, with_logging=False)

                    if provider == 'apex_omni':
                        account_data = get_enriched_account_data(client)
                        positions = account_data.get('positions', [])
                    elif provider == 'hyperliquid':
                        # Fetch clearinghouse state (full API response) first to get raw data
                        clearinghouse_state = client.fetch_clearinghouse_state()
                        
                        # Extract raw position objects from clearinghouse state
                        # Map asset -> raw position object for storage
                        raw_positions_dict = {}
                        asset_positions = clearinghouse_state.get("assetPositions", [])
                        for ap in asset_positions:
                            if isinstance(ap, dict):
                                pos = ap.get("position", {})
                                if isinstance(pos, dict):
                                    coin = pos.get("coin", "")
                                    size = float(pos.get("szi", 0) or 0)
                                    if size != 0 and coin:
                                        # Store the full raw position object from API
                                        raw_positions_dict[coin] = pos
                        
                        # Get processed positions for leverage calculation
                        positions_raw = client.fetch_open_positions()
                        
                        # Get current account equity for leverage calculation
                        account_equity = queries.get_account_equity_at_timestamp(session, wallet_id, timestamp_dt)
                        
                        # Fallback: if no equity in DB (e.g., first run), fetch from API
                        if not account_equity or account_equity <= 0:
                            try:
                                balances = client.fetch_balances()
                                # Extract account equity from USDC balance (same logic as log_equity_and_pnl)
                                for b in balances:
                                    asset = b.get('asset', '')
                                    amount = float(b.get('amount') or 0)
                                    if asset == 'USDC':
                                        account_equity = amount
                                        break
                            except Exception as e:
                                print(f"Warning: Failed to fetch balances for leverage calculation: {e}")
                        
                        # Get margin data from clearinghouse state
                        margin_summary = clearinghouse_state.get('marginSummary', {})
                        current_margin_used = float(margin_summary.get('totalMarginUsed', 0) or 0)

                        # Map to standard format and calculate leverage
                        positions = []
                        for p in positions_raw:
                            asset = p.get('asset', '')
                            size = float(p.get('quantity') or 0)
                            entry_price = float(p.get('price') or 0)
                            position_size_usd = abs(size * entry_price)

                            # Get raw API position data (full position object from clearinghouse state)
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

                            # Calculate leverage for Hyperliquid positions using margin delta
                            leverage = None
                            equity_used = None
                            calculation_method = 'unknown'

                            if position_size_usd > 0:
                                from services.hyperliquid_leverage_calculator import calculate_leverage_from_margin_delta
                                leverage, equity_used, calculation_method = calculate_leverage_from_margin_delta(
                                    session, wallet_id, asset,
                                    position_size_usd, current_margin_used, timestamp_dt
                                )
                            
                            positions.append({
                                'symbol': asset,
                                'side': p.get('side', ''),
                                'size': abs(size),
                                'entryPrice': entry_price,
                                'currentPrice': current_price,
                                'leverage': leverage,
                                'unrealizedPnl': float(p.get('unrealized_pnl') or 0),
                                'fundingFee': None,
                                'equityUsed': equity_used,
                                'positionSizeUsd': position_size_usd,
                                'calculationMethod': calculation_method,
                                '_raw_api_data': raw_position_data,  # Store ALL raw API position data
                            })
                    else:
                        continue

                    # Log each position, or log a zero-position snapshot if no positions
                    has_open_positions = False
                    if positions and len(positions) > 0:
                        for pos in positions:
                            if pos.get('size') and float(pos.get('size', 0)) > 0:
                                position_data = {
                                    'wallet_id': wallet_id,
                                    'timestamp': timestamp_dt,
                                    'symbol': pos.get('symbol', ''),
                                    'side': pos.get('side', ''),
                                    'size': float(pos.get('size', 0)),
                                    'entry_price': float(pos.get('entryPrice', 0) or 0),
                                    'current_price': float(pos.get('currentPrice', 0) or 0) if pos.get('currentPrice') else None,
                                    'position_size_usd': float(pos.get('size', 0)) * float(pos.get('currentPrice', 0) or pos.get('entryPrice', 0) or 0),
                                    'leverage': float(pos.get('leverage', 0)) if pos.get('leverage') else None,
                                    'unrealized_pnl': float(pos.get('unrealizedPnl', 0) or 0),
                                    'funding_fee': float(pos.get('fundingFee', 0) or 0),
                                    'equity_used': float(pos.get('equityUsed', 0)) if pos.get('equityUsed') else None,
                                    'calculation_method': pos.get('calculationMethod', 'unknown'),
                                    'raw_data': pos.get('_raw_api_data', {}),  # Store ALL raw API position data
                                }
                                queries.insert_position_snapshot(session, position_data)
                                total_positions_logged += 1
                                has_open_positions = True

                    if not has_open_positions:
                        # No positions - write a marker snapshot with size=0 to indicate no open positions
                        position_data = {
                            'wallet_id': wallet_id,
                            'timestamp': timestamp_dt,
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

                except Exception as wallet_error:
                    print(f"[{timestamp_str}] ⚠ Error logging positions for wallet {wallet.get('name', wallet_id)}: {wallet_error}")

            session.commit()

        print(f"[{timestamp_str}] ✓ Logged {total_positions_logged} position snapshots across {len(wallets)} wallets")

    except Exception as e:
        print(f"Error logging positions: {e}")


def log_equity_and_pnl():
    """Fetch and log equity and unrealized PnL for all wallets"""
    try:
        timestamp_dt = datetime.utcnow()
        timestamp_str = timestamp_dt.strftime("%Y-%m-%d %H:%M:%S")

        # Get all wallets
        wallets = WalletService.get_all_connected_wallets()

        total_wallets_logged = 0

        with get_session() as session:
            for wallet in wallets:
                try:
                    wallet_id = wallet['id']
                    provider = wallet['provider']

                    # Get client for this wallet
                    client = WalletService.get_wallet_client_by_id(wallet_id, with_logging=False)

                    # Get balance data based on provider
                    if provider == 'apex_omni':
                        balances = client.get_account_balance_v3()
                        balance_data = balances.get("data", {})

                        total_equity = round(float(balance_data.get("totalEquityValue", 0) or 0), 2)
                        unrealized_pnl = round(float(balance_data.get("unrealizedPnl", 0) or 0), 2)
                        available_balance = round(float(balance_data.get("availableBalance", 0) or 0), 2)
                        realized_pnl = round(float(balance_data.get("realizedPnl", 0) or 0), 2)

                    elif provider == 'hyperliquid':
                        balances = client.fetch_balances()
                        # For Hyperliquid, calculate equity from balance data
                        total_equity = 0.0
                        available_balance = 0.0
                        unrealized_pnl = 0.0
                        for b in balances:
                            asset = b.get('asset', '')
                            amount = float(b.get('amount') or 0)
                            if asset == 'USDC':
                                total_equity = amount
                                available_balance = amount
                            unrealized_pnl += float(b.get('unrealized_pnl') or 0)
                        realized_pnl = 0.0  # Not available from Hyperliquid API directly

                    else:
                        continue

                    # Write to database
                    data = {
                        'wallet_id': wallet_id,
                        'timestamp': timestamp_dt,
                        'total_equity': total_equity,
                        'unrealized_pnl': unrealized_pnl,
                        'available_balance': available_balance,
                        'realized_pnl': realized_pnl
                    }
                    queries.insert_equity_snapshot(session, data)
                    total_wallets_logged += 1

                    print(f"[{timestamp_str}] {wallet.get('name')}: Equity=${total_equity:.2f}, Unrealized PnL=${unrealized_pnl:.2f}")

                except Exception as wallet_error:
                    print(f"[{timestamp_str}] ⚠ Error logging equity for wallet {wallet.get('name', wallet_id)}: {wallet_error}")

            session.commit()

        print(f"[{timestamp_str}] ✓ Logged equity for {total_wallets_logged}/{len(wallets)} wallets")

    except Exception as e:
        print(f"Error logging equity: {e}")


def run_scheduler():
    """Run wallet refresh at :00 and :30 past each hour"""
    print("Starting wallet refresh scheduler (synced to :00 and :30 past each hour)...")
    print(f"Logging to: Database (data/wallet.db)")
    
    # Calculate time until next :00 or :30
    now = datetime.utcnow()
    current_minute = now.minute
    current_second = now.second
    
    # Determine next target minute (0 or 30)
    if current_minute < 30:
        target_minute = 30
        wait_minutes = 30 - current_minute
    else:
        target_minute = 0
        wait_minutes = 60 - current_minute
    
    wait_seconds = wait_minutes * 60 - current_second
    
    if wait_seconds > 0:
        print(f"Waiting {wait_minutes} minutes until :{target_minute:02d} to start refreshing...")
        time.sleep(wait_seconds)
    
    # Refresh immediately at the synchronized time
    refresh_all_wallets()

    # Then refresh every 30 minutes
    interval = 30 * 60  # 30 minutes in seconds

    while True:
        time.sleep(interval)
        refresh_all_wallets()


def refresh_all_wallets():
    """Refresh data for all connected wallets."""
    try:
        from services.wallet_refresh import refresh_wallet_data
        
        timestamp_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        wallets = WalletService.get_all_connected_wallets()
        
        print(f"\n[{timestamp_str}] Starting refresh for {len(wallets)} wallet(s)...")
        
        success_count = 0
        error_count = 0
        
        for wallet in wallets:
            wallet_id = wallet['id']
            wallet_name = wallet['name']
            
            try:
                success, error_msg, refresh_time = refresh_wallet_data(wallet_id)
                
                if success:
                    success_count += 1
                    print(f"[{timestamp_str}] ✓ {wallet_name}")
                else:
                    error_count += 1
                    print(f"[{timestamp_str}] ✗ {wallet_name}: {error_msg}")
                    
            except Exception as e:
                error_count += 1
                print(f"[{timestamp_str}] ✗ {wallet_name}: {str(e)}")
        
        print(f"[{timestamp_str}] Refresh complete: {success_count} succeeded, {error_count} failed\n")
        
    except Exception as e:
        print(f"Error in refresh_all_wallets: {e}")


if __name__ == "__main__":
    run_scheduler()

