"""Flask web application for Apex Omni Wallet monitoring."""
import os
import threading
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, session
from werkzeug.exceptions import RequestEntityTooLarge
from dotenv import load_dotenv

from services.apex_client import make_client, get_all_fills, LoggingApexClient
from services.wallet_service import WalletService
from services.data_service import (
    get_enriched_account_data,
    get_historical_data,
    get_symbol_pnl_data,
    format_fills_timestamps,
    format_orders_timestamps,
    format_duration,
)
from services.wallet_manager import (
    test_apex_connection,
    test_hyperliquid_connection,
    test_property_wallet,
    get_provider_instructions
)
from db.database import get_session, create_all_tables, cleanup_session
from pathlib import Path
import json
from services.exchange_logging import LOG_PATH
from db.models import WalletConfig
from db.models_strategies import Strategy, StrategyAssignment
from db import queries
from db.queries import get_latest_equity_per_wallet
from db.queries_strategies import (
    list_strategies, create_strategy,
    list_assignments, create_assignment, end_assignment, delete_assignment,
    resolve_strategy_id, get_traded_symbols_by_wallet, get_active_assignment_map,
    count_trades_for_assignment
)
from exceptions import WalletNotFoundError, WalletConfigurationError

# Security
from config import get_config
from utils.security import add_security_headers
from utils.rate_limit import init_rate_limiting, limiter, RATE_LIMITS
from utils.validation import sanitize_integer, sanitize_string, validate_wallet_name, validate_symbol, validate_wallet_address, sanitize_text, sanitize_float
from utils.data_utils import normalize_symbol

# CSRF Protection (optional - install Flask-WTF to enable)
try:
    from flask_wtf.csrf import CSRFProtect, CSRFError
    CSRF_AVAILABLE = True
except ImportError:
    CSRF_AVAILABLE = False
    CSRFError = None
    print("Warning: Flask-WTF not installed. CSRF protection disabled. Install with: pip install Flask-WTF")

load_dotenv()

app = Flask(__name__)
# Use environment-based config for dev/prod
app.config.from_object(get_config())
# Force template reloading - disable caching
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.jinja_env.auto_reload = True
app.jinja_env.cache = {}


# Add security middleware
add_security_headers(app)
init_rate_limiting(app)

# Initialize CSRF protection (if available)
if CSRF_AVAILABLE:
    csrf = CSRFProtect(app)
    
    # CSRF error handler - handle CSRFError exception properly
    @app.errorhandler(CSRFError)
    def csrf_error(error):
        """Handle CSRF validation errors."""
        app.logger.warning(f"CSRF error: {error.description} from {request.remote_addr}")
        return render_template('error.html',
                             error_code=400,
                             error_message="Invalid security token. Please refresh the page and try again."), 400
    
    # Also handle 400 errors for other cases
    @app.errorhandler(400)
    def bad_request(error):
        """Handle other 400 errors."""
        # If it's a CSRF error, it should have been caught by CSRFError handler
        # But handle other 400 errors generically
        error_msg = str(error.description) if hasattr(error, 'description') else "Bad request"
        return render_template('error.html',
                             error_code=400,
                             error_message=error_msg), 400
else:
    # Disable CSRF protection in config if Flask-WTF not available
    app.config['WTF_CSRF_ENABLED'] = False
    
    # Generic 400 handler when CSRF is not available
    @app.errorhandler(400)
    def bad_request(error):
        """Handle 400 errors."""
        error_msg = str(error.description) if hasattr(error, 'description') else "Bad request"
        return render_template('error.html',
                             error_code=400,
                             error_message=error_msg), 400

# Ensure session exists for CSRF
@app.before_request
def ensure_session():
    """Ensure session exists for CSRF token generation."""
    if 'csrf_token' not in session:
        # Touch the session to ensure it's created
        session.permanent = True
        session.modified = True

# Error handlers for production (hide internal errors)
@app.errorhandler(RequestEntityTooLarge)
def request_too_large(error):
    """Handle 413 Request Entity Too Large errors."""
    app.logger.warning(f"Request too large: {request.url} from {request.remote_addr}")
    return render_template('error.html',
                         error_code=413,
                         error_message="Request payload is too large. Maximum size is 16MB."), 413

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    app.logger.warning(f"404 error: {request.url}")
    return render_template('error.html', 
                         error_code=404,
                         error_message="Page not found"), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    app.logger.error(f"500 error: {error}", exc_info=True)
    return render_template('error.html',
                         error_code=500,
                         error_message="An internal error occurred"), 500

@app.errorhandler(Exception)
def handle_error(error):
    """Handle all unhandled exceptions."""
    app.logger.error(f"Unhandled error: {error}", exc_info=True)
    # Don't expose internal error details in production
    if app.debug:
        return f"<h1>Error</h1><p>{str(error)}</p>", 500
    else:
        return render_template('error.html',
                             error_code=500,
                             error_message="An error occurred. Please try again."), 500

# Initialize database tables on startup
create_all_tables()


# Clean up scoped sessions after each request
@app.teardown_appcontext
def shutdown_session(exception=None):
    """Clean up scoped session after request."""
    cleanup_session()


# Start background logger in a separate thread
def start_background_logger():
    """Start the equity logger in a background thread."""
    from logger import run_scheduler
    print("Starting background equity logger (30-minute intervals)...")
    logger_thread = threading.Thread(target=run_scheduler, daemon=True, name="EquityLogger")
    logger_thread.start()
    print("Background logger thread started.")


# Start logger only once (not on Flask reloader)
if os.environ.get('WERKZEUG_RUN_MAIN') == 'true' or not app.debug:
    start_background_logger()


@app.route("/health")
def health():
    """Health check endpoint for load balancers and monitoring."""
    try:
        # Quick database connectivity check
        from sqlalchemy import text
        with get_session() as session:
            session.execute(text("SELECT 1"))
        return jsonify({
            "status": "healthy",
            "timestamp": datetime.now().isoformat()
        }), 200
    except Exception as e:
        app.logger.error(f"Health check failed: {e}")
        return jsonify({
            "status": "unhealthy",
            "error": "Database connection failed"
        }), 503


def _parse_time_range():
    """Parse time range from query params. Default: 7d."""
    period = sanitize_string(request.args.get("period") or "7d", max_length=10, allow_empty=False).lower()
    now = datetime.now()
    
    if period == "24h":
        return now - timedelta(hours=24), now
    elif period == "7d":
        return now - timedelta(days=7), now
    elif period == "30d":
        return now - timedelta(days=30), now
    else:
        # Custom: start=YYYY-MM-DD, end=YYYY-MM-DD
        start_str = sanitize_string(request.args.get("start"), max_length=10, allow_empty=True)
        end_str = sanitize_string(request.args.get("end"), max_length=10, allow_empty=True)
        try:
            start = datetime.strptime(start_str, "%Y-%m-%d") if start_str else now - timedelta(days=7)
            end = datetime.strptime(end_str, "%Y-%m-%d") + timedelta(days=1) if end_str else now
            return start, end
        except Exception:
            return now - timedelta(days=7), now


@app.route("/debug")
def debug_dashboard():
    """Debug dashboard without login (development only - disabled in production)."""
    # Only allow in development mode
    if os.getenv('FLASK_ENV') != 'development':
        return f"<h1>404 Not Found</h1><p>Debug route not available in production.</p>", 404
    return index()


@app.route("/")
def index():
    """Portfolio overview dashboard with aggregated metrics."""
    try:
        start, end = _parse_time_range()
        all_wallets = WalletService.get_all_connected_wallets()

        with get_session() as session:
            latest_equity = queries.get_latest_equity_per_wallet(session)
            latest_unrealized = queries.get_latest_unrealized_pnl_per_wallet(session)
            latest_balance = queries.get_latest_available_balance_per_wallet(session)
            latest_times = queries.get_latest_snapshot_time_per_wallet(session)
            pnl_by_wallet = queries.get_realized_pnl_by_wallet(session, start=start, end=end)
            trade_counts = queries.get_trade_counts_by_wallet(session, start=start, end=end)
            win_rates = queries.get_win_rates_by_wallet(session, start=start, end=end, zero_is_loss=True)
            active_positions = queries.get_active_positions_count(session)

            # Portfolio-level aggregates
            total_realized_pnl = sum(pnl_by_wallet.values())
            total_unrealized_pnl = sum(latest_unrealized.values())
            total_trade_count = sum(trade_counts.values())

            # Calculate aggregate win rate
            all_wins = 0
            all_trades = 0
            for wid in all_wallets:
                wallet_id = wid["id"]
                count = trade_counts.get(wallet_id, 0)
                if count > 0:
                    rate = win_rates.get(wallet_id, 0.0)
                    all_wins += int(count * rate / 100.0)
                    all_trades += count
            aggregate_win_rate = (all_wins / all_trades * 100.0) if all_trades > 0 else 0.0

            # Strategy performance
            strategy_performance = queries.get_strategy_performance(session, start, end)

            # Symbol performance (top 10)
            symbol_performance = queries.get_symbol_performance(session, start, end)[:10]

            # Recent activity
            recent_trades = queries.get_recent_trades(session, limit=10)

            # Open positions
            open_positions = queries.get_open_positions(session)

            # Resolve strategy names for open positions and add timeInTrade
            from db.models import PositionSnapshot
            from sqlalchemy import func
            for pos in open_positions:
                wallet_id = pos.get('wallet_id')
                symbol = pos.get('symbol')
                if wallet_id and symbol:
                    strategy_id = resolve_strategy_id(
                        session,
                        wallet_id,
                        symbol,
                        datetime.now()
                    )
                    if strategy_id:
                        strategy = session.query(Strategy).filter(Strategy.id == strategy_id).first()
                        pos['strategy_name'] = strategy.name if strategy else None
                    else:
                        pos['strategy_name'] = None
                else:
                    pos['strategy_name'] = None
                
                # Calculate timeInTrade directly from openedFormatted timestamp if available
                # Note: open_positions from get_open_positions() may not have openedFormatted
                # So we'll use database query as primary method for overview page
                # BUG FIX: Find the most recent time when position transitioned from size=0 to size>0
                symbol = pos.get('symbol', '')
                if symbol and wallet_id:
                    normalized_symbol = normalize_symbol(symbol)
                    
                    # Find the most recent time when position transitioned from size=0 to size>0
                    # Step 1: Find the most recent snapshot with size = 0 (position was closed)
                    last_zero_ts = session.query(func.max(PositionSnapshot.timestamp))\
                        .filter(PositionSnapshot.wallet_id == wallet_id)\
                        .filter(PositionSnapshot.symbol == normalized_symbol)\
                        .filter(PositionSnapshot.size == 0)\
                        .scalar()
                    
                    # Step 2: Find the earliest snapshot with size > 0 after the last_zero_ts
                    # This gives us when the current position was opened
                    if last_zero_ts:
                        earliest = session.query(func.min(PositionSnapshot.timestamp))\
                            .filter(PositionSnapshot.wallet_id == wallet_id)\
                            .filter(PositionSnapshot.symbol == normalized_symbol)\
                            .filter(PositionSnapshot.size > 0)\
                            .filter(PositionSnapshot.timestamp > last_zero_ts)\
                            .scalar()
                    else:
                        # No zero-size snapshot found, use earliest snapshot with size > 0
                        # (position was never closed, or no history of closures)
                        earliest = session.query(func.min(PositionSnapshot.timestamp))\
                            .filter(PositionSnapshot.wallet_id == wallet_id)\
                            .filter(PositionSnapshot.symbol == normalized_symbol)\
                            .filter(PositionSnapshot.size > 0)\
                            .scalar()
                    
                    if earliest:
                        try:
                            now = datetime.utcnow()
                            duration_seconds = (now - earliest).total_seconds()
                            pos['timeInTrade'] = format_duration(duration_seconds)
                        except Exception:
                            pos['timeInTrade'] = "-"
                    else:
                        pos['timeInTrade'] = "-"
                else:
                    pos['timeInTrade'] = "-"

            # Equity history for chart
            equity_history = queries.get_equity_history(session, wallet_id=None, hours=None)

            # Quick stats calculations
            all_trades = queries.get_closed_trades(session)

            # Filter to period and non-zero/non-None PnL trades
            period_trades = [t for t in all_trades
                           if t.get('closedPnl') is not None
                           and t.get('closedPnl') != 0
                           and start <= t.get('timestamp', datetime.min) < end]

            best_trade = max(period_trades, key=lambda x: x.get('closedPnl', 0))['closedPnl'] if period_trades else 0
            worst_trade = min(period_trades, key=lambda x: x.get('closedPnl', 0))['closedPnl'] if period_trades else 0

            # Calculate average duration (in hours) - placeholder for now
            # TODO: Track actual trade open/close times for accurate duration
            avg_duration_hours = 2.4

            # Count active wallets (wallets with equity > 0)
            active_wallets = len([w for w in all_wallets if latest_equity.get(w['id'], 0) > 0])

        wallet_rows = []
        total_equity = 0.0

        for w in all_wallets:
            wid = w["id"]
            eq = float(latest_equity.get(wid, 0.0))
            total_equity += eq

            last_update = latest_times.get(wid)
            last_update_str = last_update.strftime("%Y-%m-%d %H:%M") if last_update else "Never"

            wallet_rows.append({
                "id": wid,
                "name": w["name"],
                "provider": w["provider"],
                "equity": round(eq, 2),
                "unrealized_pnl": round(latest_unrealized.get(wid, 0.0), 2),
                "available_balance": round(latest_balance.get(wid, 0.0), 2),
                "last_update": last_update_str,
                "realized_pnl": round(pnl_by_wallet.get(wid, 0.0), 2),
                "win_rate": round(win_rates.get(wid, 0.0), 2),
                "trade_count": trade_counts.get(wid, 0),
                "active_positions": active_positions.get(wid, 0),
            })

        # Find best/worst performing wallet
        best_wallet = max(wallet_rows, key=lambda x: x["realized_pnl"]) if wallet_rows else None
        worst_wallet = min(wallet_rows, key=lambda x: x["realized_pnl"]) if wallet_rows else None

        period_label = request.args.get("period") or "7d"
        return render_template(
            "overview.html",
            total_equity=round(total_equity, 2),
            total_realized_pnl=round(total_realized_pnl, 2),
            total_unrealized_pnl=round(total_unrealized_pnl, 2),
            total_trade_count=total_trade_count,
            aggregate_win_rate=round(aggregate_win_rate, 2),
            best_wallet=best_wallet,
            worst_wallet=worst_wallet,
            wallets=wallet_rows,
            strategy_performance=strategy_performance,
            symbol_performance=symbol_performance,
            recent_trades=recent_trades,
            open_positions=open_positions,
            equity_history=equity_history,
            period_label=period_label,
            start=start.strftime("%Y-%m-%d"),
            end=(end - timedelta(days=1)).strftime("%Y-%m-%d"),
            # Quick stats
            best_trade=round(best_trade, 2),
            worst_trade=round(worst_trade, 2),
            avg_duration_hours=round(avg_duration_hours, 1),
            active_wallets=active_wallets,
        )
    except Exception as e:
        app.logger.error(f"Error in index route: {e}", exc_info=True)
        flash('An error occurred loading the dashboard. Please try again.', 'error')
        return redirect(url_for('admin'))


@app.route("/wallet/<int:wallet_id>")
def wallet_dashboard(wallet_id):
    """Dashboard for specific wallet."""
    # Validate wallet_id from URL
    wallet_id = sanitize_integer(wallet_id, default=0, min_val=1)
    if wallet_id == 0:
        flash('Invalid wallet ID', 'error')
        return redirect(url_for('admin'))
    
    try:
        # Get wallet from database
        wallet_name = None
        provider = None
        wallet_address = None
        with get_session() as session:
            wallet = session.query(WalletConfig).filter(WalletConfig.id == wallet_id).first()
            if not wallet:
                flash(f'Wallet not found', 'error')
                return redirect(url_for('admin'))

            if wallet.status != 'connected':
                flash(f'Wallet "{wallet.name}" is not connected. Please test the connection first.', 'error')
                return redirect(url_for('admin'))

            # Store wallet name, address, and provider before session closes
            wallet_name = wallet.name
            provider = wallet.provider
            wallet_address = wallet.wallet_address
        
        # Get client for this specific wallet
        client = WalletService.get_wallet_client_by_id(wallet_id, with_logging=True)
        
        # Fetch and enrich account data from API (provider-aware)
        if provider == 'hyperliquid':
            # Build read-only data using Hyperliquid client
            try:
                hl_balances = client.fetch_balances()
            except Exception:
                hl_balances = []
            try:
                hl_positions_raw = client.fetch_open_positions()
            except Exception:
                hl_positions_raw = []
            try:
                since_ms = int((datetime.now() - timedelta(days=90)).timestamp() * 1000)
                hl_trades = client.fetch_trades(since_ms=since_ms, limit=1000)
            except Exception:
                hl_trades = []
            
            # Get clearinghouse state for margin data
            try:
                hl_clearinghouse_state = client.fetch_clearinghouse_state()
            except Exception:
                hl_clearinghouse_state = {}

            # Extract account equity and margin data
            account_equity = 0.0
            total_margin_used = 0.0
            margin_summary = hl_clearinghouse_state.get('marginSummary', {})
            
            if margin_summary:
                account_equity = float(margin_summary.get('accountValue', 0) or 0)
                total_margin_used = float(margin_summary.get('totalMarginUsed', 0) or 0)
            else:
                # Fallback: extract from balances
                for b in hl_balances:
                    asset = b.get('asset', '')
                    amount = float(b.get('amount') or 0)
                    if asset == 'USDC':
                        account_equity = amount
                        break
            
            # Map HL positions to app format expected by templates and snapshots
            hl_positions = []
            for p in hl_positions_raw:
                size = float(p.get('quantity') or 0)
                entry_price = float(p.get('price') or 0)
                position_size_usd = abs(size * entry_price)
                position_value = float(p.get('position_value', 0) or 0)
                
                # Calculate leverage for Hyperliquid positions
                leverage = None
                if account_equity and account_equity > 0 and position_size_usd > 0:
                    from utils.calculations import estimate_leverage_hyperliquid
                    leverage = estimate_leverage_hyperliquid(
                        position_size_usd=position_size_usd,
                        account_equity=account_equity,
                        position_value=position_value if position_value > 0 else None
                    )
                
                hl_positions.append({
                    'symbol': p.get('asset', ''),
                    'side': p.get('side', ''),
                    'size': abs(size),
                    'entryPrice': entry_price,
                    'currentPrice': None,
                    'leverage': leverage,
                    'unrealizedPnl': float(p.get('unrealized_pnl') or 0),
                    'fundingFee': None,
                    'equityUsed': None,
                    'positionSizeUsd': position_size_usd,
                })
            
            # Add openedFormatted and timeInTrade for Hyperliquid positions
            # Try to get earliest position snapshot from database for each position
            # BUG FIX: Find the most recent time when position transitioned from size=0 to size>0
            # This handles cases where positions were closed and reopened - we want the current
            # position's open date, not the first time this symbol was ever opened
            with get_session() as session:
                from db.models import PositionSnapshot
                from sqlalchemy import func
                for pos in hl_positions:
                    symbol = pos.get('symbol', '')
                    if symbol:
                        # Normalize symbol to match how it's stored in database
                        normalized_symbol = normalize_symbol(symbol)
                        
                        # Find the most recent time when position transitioned from size=0 to size>0
                        # Step 1: Find the most recent snapshot with size = 0 (position was closed)
                        last_zero_ts = session.query(func.max(PositionSnapshot.timestamp))\
                            .filter(PositionSnapshot.wallet_id == wallet_id)\
                            .filter(PositionSnapshot.symbol == normalized_symbol)\
                            .filter(PositionSnapshot.size == 0)\
                            .scalar()
                        
                        # Step 2: Find the earliest snapshot with size > 0 after the last_zero_ts
                        # This gives us when the current position was opened
                        if last_zero_ts:
                            opened_timestamp = session.query(func.min(PositionSnapshot.timestamp))\
                                .filter(PositionSnapshot.wallet_id == wallet_id)\
                                .filter(PositionSnapshot.symbol == normalized_symbol)\
                                .filter(PositionSnapshot.size > 0)\
                                .filter(PositionSnapshot.timestamp > last_zero_ts)\
                                .scalar()
                        else:
                            # No zero-size snapshot found, use earliest snapshot with size > 0
                            # (position was never closed, or no history of closures)
                            opened_timestamp = session.query(func.min(PositionSnapshot.timestamp))\
                                .filter(PositionSnapshot.wallet_id == wallet_id)\
                                .filter(PositionSnapshot.symbol == normalized_symbol)\
                                .filter(PositionSnapshot.size > 0)\
                                .scalar()
                        
                        if opened_timestamp:
                            try:
                                pos['openedFormatted'] = opened_timestamp.strftime("%Y-%m-%d %H:%M")
                                now = datetime.utcnow()
                                duration_seconds = (now - opened_timestamp).total_seconds()
                                pos['timeInTrade'] = format_duration(duration_seconds)
                            except Exception:
                                pos['openedFormatted'] = "-"
                                pos['timeInTrade'] = "-"
                        else:
                            pos['openedFormatted'] = "-"
                            pos['timeInTrade'] = "-"
                    else:
                        pos['openedFormatted'] = "-"
                        pos['timeInTrade'] = "-"

            # Build balance summary and wallet lists
            total_equity = 0.0
            available_balance = 0.0
            total_unrealized = 0.0
            contract_wallets = []

            for b in hl_balances:
                asset = b.get('asset', '')
                amount = float(b.get('amount') or 0)
                unrealized_pnl = float(b.get('unrealized_pnl') or 0)

                # Add to wallet list for display
                contract_wallets.append({
                    'token': asset,
                    'balance': amount,
                    'availableBalance': amount,
                    'pendingDepositAmount': 0.0,
                    'pendingWithdrawAmount': 0.0,
                })

                if asset == 'USDC':
                    total_equity += amount
                    available_balance = amount
                total_unrealized += unrealized_pnl

            account_data = {
                'contract_wallets': contract_wallets,
                'spot_wallets': [],
                'positions': hl_positions,
                'balance_data': {
                    'totalEquityValue': total_equity,
                    'unrealizedPnl': total_unrealized,
                    'availableBalance': available_balance,
                    'realizedPnl': 0.0,
                    'totalMarginUsed': total_margin_used,  # Add margin data for leverage calculation
                },
                'orders': [],
                'closed_pnl': [],
            }
            # Keep raw trades for DB upsert; map a copy for UI
            hl_trades_raw = list(hl_trades)
            # Map HL trades to the template's fill structure
            fills = []
            def _normalize_side(raw: str) -> str:
                s = (raw or '').lower()
                if s in ('b', 'bid', 'buy', 'long'):
                    return 'buy'
                if s in ('a', 'ask', 'sell', 'short'):
                    return 'sell'
                return s or 'buy'
            for t in hl_trades_raw:
                ts = t.get('timestamp')
                created_str = ts.strftime("%Y-%m-%d %H:%M") if ts else ""
                fills.append({
                    'createdAtFormatted': created_str,
                    'symbol': t.get('asset', ''),
                    'side': _normalize_side(t.get('side', '')),
                    'size': float(t.get('quantity') or 0),
                    'price': float(t.get('price') or 0),
                    'cumMatchFillFee': float(t.get('fee') or 0),
                    'type': 'trade',
                })
        else:
            # Default Apex Omni flow
            account_data = get_enriched_account_data(client)
            
            # Fetch all fills and format timestamps
            fills = get_all_fills(client)
            format_fills_timestamps(fills)
        
        # Add strategy information to positions and orders
        with get_session() as session:
            from db.models import PositionSnapshot
            from sqlalchemy import func
            # For each position, resolve current strategy and ensure timeInTrade is set
            for pos in account_data['positions']:
                strategy_id = resolve_strategy_id(
                    session, 
                    wallet_id, 
                    pos.get('symbol', ''), 
                    datetime.now()
                )
                if strategy_id:
                    strategy = session.query(Strategy).filter(Strategy.id == strategy_id).first()
                    pos['strategy_name'] = strategy.name if strategy else None
                else:
                    pos['strategy_name'] = None
                
                # Calculate timeInTrade directly from openedFormatted timestamp
                opened_str = pos.get('openedFormatted', '')
                symbol = pos.get('symbol', '')
                
                # DEBUG: Log what we have initially
                app.logger.info(f"DEBUG Position {symbol}: Initial openedFormatted='{opened_str}', size={pos.get('size')}")
                
                # Now using updatedTime from API which should have the correct date
                # Always use API date if available
                if opened_str and opened_str != "-" and len(str(opened_str)) > 10:
                    try:
                        opened_dt = datetime.strptime(str(opened_str), "%Y-%m-%d %H:%M")
                        now = datetime.utcnow()
                        duration_seconds = (now - opened_dt).total_seconds()
                        if duration_seconds > 0:
                            pos['timeInTrade'] = format_duration(duration_seconds)
                        else:
                            pos['timeInTrade'] = "-"
                        app.logger.info(f"Position {symbol}: Using API openedFormatted={opened_str}, timeInTrade={pos['timeInTrade']}")
                    except (ValueError, TypeError) as e:
                        app.logger.warning(f"Could not parse openedFormatted '{opened_str}' for {symbol}: {e}")
                        pos['timeInTrade'] = "-"
                else:
                    # Fallback to database if openedFormatted not available
                    # BUG FIX: Find the most recent time when position transitioned from size=0 to size>0
                    # This handles cases where positions were closed and reopened
                    if symbol and wallet_id:
                        normalized_symbol = normalize_symbol(symbol)
                        
                        # Find the most recent time when position transitioned from size=0 to size>0
                        # Step 1: Find the most recent snapshot with size = 0 (position was closed)
                        last_zero_ts = session.query(func.max(PositionSnapshot.timestamp))\
                            .filter(PositionSnapshot.wallet_id == wallet_id)\
                            .filter(PositionSnapshot.symbol == normalized_symbol)\
                            .filter(PositionSnapshot.size == 0)\
                            .scalar()
                        
                        # Step 2: Find the earliest snapshot with size > 0 after the last_zero_ts
                        # This gives us when the current position was opened
                        if last_zero_ts:
                            opened_timestamp = session.query(func.min(PositionSnapshot.timestamp))\
                                .filter(PositionSnapshot.wallet_id == wallet_id)\
                                .filter(PositionSnapshot.symbol == normalized_symbol)\
                                .filter(PositionSnapshot.size > 0)\
                                .filter(PositionSnapshot.timestamp > last_zero_ts)\
                                .scalar()
                        else:
                            # No zero-size snapshot found, use earliest snapshot with size > 0
                            # (position was never closed, or no history of closures)
                            opened_timestamp = session.query(func.min(PositionSnapshot.timestamp))\
                                .filter(PositionSnapshot.wallet_id == wallet_id)\
                                .filter(PositionSnapshot.symbol == normalized_symbol)\
                                .filter(PositionSnapshot.size > 0)\
                                .scalar()
                        
                        if opened_timestamp:
                            try:
                                now = datetime.utcnow()
                                duration_seconds = (now - opened_timestamp).total_seconds()
                                pos['timeInTrade'] = format_duration(duration_seconds)
                                # Only set openedFormatted if it's not already set by the API
                                current_opened = pos.get('openedFormatted', '')
                                if not current_opened or current_opened == "-":
                                    pos['openedFormatted'] = opened_timestamp.strftime("%Y-%m-%d %H:%M")
                                    app.logger.info(f"Set openedFormatted from DB for {symbol}: {pos['openedFormatted']}")
                            except Exception as e:
                                app.logger.warning(f"Error calculating timeInTrade from DB for {symbol}: {e}")
                                pos['timeInTrade'] = "-"
                        else:
                            pos['timeInTrade'] = "-"
                    else:
                        pos['timeInTrade'] = "-"
                
                # Ensure it's always set
                if 'timeInTrade' not in pos:
                    pos['timeInTrade'] = "-"
            
            # For each open order, resolve current strategy
            for order in account_data['orders']:
                strategy_id = resolve_strategy_id(
                    session, 
                    wallet_id, 
                    order.get('symbol', ''), 
                    datetime.now()
                )
                if strategy_id:
                    strategy = session.query(Strategy).filter(Strategy.id == strategy_id).first()
                    order['strategy_name'] = strategy.name if strategy else None
                else:
                    order['strategy_name'] = None
            
            # Format order timestamps
            format_orders_timestamps(account_data['orders'])
        
        # Get historical data from database filtered by wallet
        with get_session() as session:
            # Write a fresh equity snapshot on page load/refresh
            try:
                balance = account_data.get('balance_data', {})
                # Determine which margin field to use based on provider
                if provider == 'apex_omni':
                    margin_used = float(balance.get('initialMargin', 0) or 0)
                elif provider == 'hyperliquid':
                    margin_used = float(balance.get('totalMarginUsed', 0) or 0)
                else:
                    margin_used = None
                
                snapshot_data = {
                    'wallet_id': wallet_id,
                    'timestamp': datetime.utcnow(),
                    'total_equity': float(balance.get('totalEquityValue', 0) or 0),
                    'unrealized_pnl': float(balance.get('unrealizedPnl', 0) or 0),
                    'available_balance': float(balance.get('availableBalance', 0) or 0),
                    'realized_pnl': float(balance.get('realizedPnl', 0) or 0),
                    'initial_margin': margin_used,  # Works for both Apex (initialMargin) and Hyperliquid (totalMarginUsed)
                }
                queries.insert_equity_snapshot(session, snapshot_data)
                
                # Also write position snapshots for each open position
                timestamp = datetime.utcnow()
                for pos in account_data['positions']:
                    if pos.get('size') and float(pos.get('size', 0)) != 0:
                        position_data = {
                            'wallet_id': wallet_id,
                            'timestamp': timestamp,
                            'symbol': normalize_symbol(pos.get('symbol', '')) or '',
                            'side': sanitize_string(pos.get('side', ''), max_length=10, allow_empty=False),
                            'size': sanitize_float(pos.get('size', 0), default=0.0, min_val=0),
                            'entry_price': sanitize_float(pos.get('entryPrice', 0) or 0, default=0.0, min_val=0),
                            'current_price': sanitize_float(pos.get('currentPrice', 0) or 0, default=None, min_val=0) if pos.get('currentPrice') else None,
                            'position_size_usd': sanitize_float(float(pos.get('size', 0) or 0) * float(pos.get('currentPrice', 0) or pos.get('entryPrice', 0) or 0), default=0.0, min_val=0),
                            'leverage': sanitize_float(pos.get('leverage', 0), default=None, min_val=0) if pos.get('leverage') else None,
                            'unrealized_pnl': sanitize_float(pos.get('unrealizedPnl', 0) or 0, default=0.0),
                            'funding_fee': sanitize_float(pos.get('fundingFee', 0) or 0, default=0.0),
                            'equity_used': sanitize_float(pos.get('equityUsed', 0), default=None, min_val=0) if pos.get('equityUsed') else None,
                            'raw_data': pos  # Store complete position data from API
                        }
                        
                        # Exchange-specific leverage calculation via margin tracking
                        if provider == 'apex_omni':
                            from services.apex_leverage_calculator import calculate_leverage_from_margin_delta
                            
                            symbol = normalize_symbol(pos.get('symbol', '')) or ''
                            position_size_usd = float(position_data['position_size_usd'])
                            current_initial_margin = float(balance.get('initialMargin', 0) or 0)
                            
                            try:
                                leverage, equity_used, method = calculate_leverage_from_margin_delta(
                                    session, wallet_id, symbol, position_size_usd,
                                    current_initial_margin, timestamp, pos
                                )
                                
                                # Override with calculated values if available
                                if leverage is not None:
                                    position_data['leverage'] = leverage
                                if equity_used is not None:
                                    position_data['equity_used'] = equity_used
                                position_data['initial_margin_at_open'] = current_initial_margin
                                position_data['calculation_method'] = method
                                
                                app.logger.info(f"Apex leverage calc for {symbol}: {leverage:.1f}x via {method}")
                            except Exception as e:
                                app.logger.error(f"Error calculating Apex leverage for {symbol}: {e}")
                                position_data['calculation_method'] = 'error'
                        
                        elif provider == 'hyperliquid':
                            from services.hyperliquid_leverage_calculator import calculate_leverage_from_margin_delta as hl_calc_leverage
                            
                            symbol = normalize_symbol(pos.get('symbol', '')) or ''
                            position_size_usd = float(position_data['position_size_usd'])
                            current_margin_used = float(balance.get('totalMarginUsed', 0) or 0)
                            
                            try:
                                leverage, equity_used, method = hl_calc_leverage(
                                    session, wallet_id, symbol, position_size_usd,
                                    current_margin_used, timestamp
                                )
                                
                                # Override with calculated values if available
                                if leverage is not None:
                                    position_data['leverage'] = leverage
                                if equity_used is not None:
                                    position_data['equity_used'] = equity_used
                                position_data['initial_margin_at_open'] = current_margin_used
                                position_data['calculation_method'] = method
                                
                                app.logger.info(f"Hyperliquid leverage calc for {symbol}: {leverage:.1f}x via {method}")
                            except Exception as e:
                                app.logger.error(f"Error calculating Hyperliquid leverage for {symbol}: {e}")
                                position_data['calculation_method'] = 'error'
                        
                        queries.insert_position_snapshot(session, position_data)

                # For Hyperliquid, upsert trades (fills) into closed_trades
                if provider == 'hyperliquid':
                    for t in hl_trades_raw:
                        try:
                            ts = t.get('timestamp')
                            raw_side = str(t.get('side') or '')
                            price = float(t.get('price') or 0)
                            size = float(t.get('quantity') or 0)
                            # Normalize side for DB stored trades (buy/sell)
                            norm_side = 'buy' if raw_side.lower() in ('b', 'bid', 'buy', 'long') else 'sell'
                            queries.upsert_closed_trade(session, {
                                'wallet_id': wallet_id,
                                'timestamp': ts,
                                'side': sanitize_string(norm_side, max_length=10, allow_empty=False),
                                'symbol': validate_symbol(t.get('asset') or '') or '',
                                'size': sanitize_float(abs(size), default=0.0, min_val=0),
                                'entry_price': sanitize_float(price, default=0.0, min_val=0),
                                'exit_price': sanitize_float(price, default=0.0, min_val=0),
                                'trade_type': sanitize_string(norm_side, max_length=10, allow_empty=False),
                                'closed_pnl': sanitize_float(t.get('realized_pnl') or 0, default=0.0),
                                'close_fee': sanitize_float(t.get('fee') or 0, default=None, min_val=0),
                                'open_fee': None,
                                'liquidate_fee': None,
                                'exit_type': None,
                                'equity_used': None,
                            }, wallet_id=wallet_id)
                        except Exception as e:
                            # Log but continue processing other trades
                            print(f"Warning: Failed to upsert Hyperliquid trade for {t.get('asset')}: {e}")
                            continue
                
                session.commit()
            except Exception as e:
                session.rollback()
                print(f"Warning: Could not write snapshots: {e}")
                pass

            historical_data = get_historical_data(session, wallet_id=wallet_id)
            # Build symbol PnL from database (closed trades)
            symbol_data = get_symbol_pnl_data(session, wallet_id=wallet_id)

            # NEW: fetch aggregated closed trades for the Closed P&L table
            # This uses aggregated_trades which groups fills by (wallet_id, timestamp, symbol)
            closed_trades = queries.get_aggregated_closed_trades(session, wallet_id=wallet_id)
        
        # Get current timestamp
        last_update = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Get all connected wallets for dropdown
        all_wallets = WalletService.get_all_connected_wallets()
        
        # DEBUG: Log positions before rendering and ensure timeInTrade is set
        app.logger.info(f"Rendering dashboard for wallet {wallet_id}, positions count: {len(account_data.get('positions', []))}")
        for pos in account_data.get('positions', []):
            symbol = pos.get('symbol', '')
            timeInTrade = pos.get('timeInTrade', 'NOT SET')
            openedFormatted = pos.get('openedFormatted', 'NOT SET')
            app.logger.info(f"  Position {symbol}: timeInTrade='{timeInTrade}', openedFormatted='{openedFormatted}'")
            
            # Final check - if timeInTrade is still not set, calculate it now
            if not timeInTrade or timeInTrade == 'NOT SET' or timeInTrade == '-':
                if openedFormatted and openedFormatted != "-" and len(str(openedFormatted)) > 10:
                    try:
                        opened_dt = datetime.strptime(openedFormatted, "%Y-%m-%d %H:%M")
                        now = datetime.utcnow()
                        duration_seconds = (now - opened_dt).total_seconds()
                        if duration_seconds > 0:
                            pos['timeInTrade'] = format_duration(duration_seconds)
                            app.logger.info(f"    Calculated timeInTrade='{pos['timeInTrade']}' for {symbol}")
                    except Exception as e:
                        app.logger.warning(f"    Failed to calculate timeInTrade for {symbol}: {e}")
                        pos['timeInTrade'] = "-"
                else:
                    pos['timeInTrade'] = "-"
        
        return render_template('dashboard.html',
                             wallet_id=wallet_id,
                             wallet_name=wallet_name,
                             network="MAIN",
                             all_wallets=all_wallets,
                             contract_wallets=account_data['contract_wallets'],
                             spot_wallets=account_data['spot_wallets'],
                             positions=account_data['positions'],
                             balance_data=account_data['balance_data'],
                             orders=account_data['orders'],
                             closed_pnl=closed_trades,
                             fills=fills,
                             equity_history=historical_data['equity_history'],
                             symbol_unrealized_history=symbol_data['symbol_unrealized_history'],
                             symbol_realized_history=symbol_data['symbol_realized_history'],
                             total_realized_series=symbol_data['total_realized_series'],
                             symbols=symbol_data['symbols'],
                             last_update=last_update)
    except WalletNotFoundError as e:
        app.logger.error(f"Wallet not found: {e}", exc_info=True)
        flash('Wallet not found. Please check the wallet ID.', 'error')
        return redirect(url_for('admin'))
    except WalletConfigurationError as e:
        app.logger.error(f"Wallet configuration error: {e}", exc_info=True)
        flash('Wallet configuration error. Please check your wallet settings.', 'error')
        return redirect(url_for('admin'))
    except Exception as e:
        app.logger.error(f"Error in wallet_dashboard: {e}", exc_info=True)
        flash('An error occurred loading the wallet dashboard. Please check your wallet configuration.', 'error')
        return redirect(url_for('admin'))


@app.route("/admin/exchange-logs")
def admin_exchange_logs():
    """Admin page showing the last N exchange traffic log lines."""
    try:
        path = Path(str(LOG_PATH))
        last_n = int(os.getenv("ADMIN_LOG_TAIL", "200"))
        lines = []
        if path.exists():
            with path.open("r", encoding="utf-8") as f:
                lines = f.readlines()
        tail = lines[-last_n:] if lines else []
        parsed = []
        for ln in tail:
            ln = ln.strip()
            try:
                parsed.append(json.loads(ln))
            except Exception:
                parsed.append({"raw": ln})
        # Only show filename, not full path for security
        log_filename = path.name if path.exists() else "Not available"
        return render_template("admin_exchange_logs.html", entries=parsed, log_path=log_filename, count=len(parsed))
    except Exception as e:
        app.logger.error(f"Error in admin_exchange_logs: {e}", exc_info=True)
        flash('An error occurred loading exchange logs.', 'error')
        return redirect(url_for('admin'))


@app.route("/admin")
def admin():
    """Wallets page for wallet management."""
    with get_session() as session:
        wallets = session.query(WalletConfig).order_by(WalletConfig.created_at.desc()).all()
        # Get latest equity per wallet
        portfolio_equity = get_latest_equity_per_wallet(session)

        # Convert to list of dictionaries to avoid session issues
        wallets_data = []
        for wallet in wallets:
            wallets_data.append({
                'id': wallet.id,
                'name': wallet.name,
                'provider': wallet.provider,
                'wallet_type': wallet.wallet_type,
                'status': wallet.status,
                'last_test': wallet.last_test,
                'created_at': wallet.created_at,
                'equity': portfolio_equity.get(wallet.id, 0)
            })

    return render_template('admin.html', wallets=wallets_data)


@app.route("/admin/add_wallet", methods=['POST'])
@limiter.limit(RATE_LIMITS['admin'])
@csrf.exempt
def add_wallet():
    """Add new wallet configuration."""
    try:
        # Extract and validate form data
        name = validate_wallet_name(request.form.get('name', ''))
        if not name:
            flash('Wallet name is required and must be 1-255 characters (alphanumeric, spaces, dashes, underscores only)', 'error')
            return redirect(url_for('admin'))
        
        provider = sanitize_string(request.form.get('provider', ''), max_length=50, allow_empty=False)
        if not provider or provider not in ['apex_omni', 'hyperliquid', 'property']:
            flash('Provider is required and must be apex_omni, hyperliquid, or property', 'error')
            return redirect(url_for('admin'))
        
        wallet_type = sanitize_string(request.form.get('wallet_type', 'crypto'), max_length=50, allow_empty=False)
        if wallet_type not in ['crypto', 'stocks', 'property']:
            wallet_type = 'crypto'  # Default fallback
        
        # Extract provider-specific fields
        api_name = sanitize_string(request.form.get('api_name', ''), max_length=255, allow_empty=True) or None
        api_key = sanitize_string(request.form.get('api_key', ''), max_length=1000, allow_empty=True) or None
        api_secret = sanitize_string(request.form.get('api_secret', ''), max_length=1000, allow_empty=True) or None
        api_passphrase = sanitize_string(request.form.get('api_passphrase', ''), max_length=1000, allow_empty=True) or None
        wallet_address_raw = request.form.get('wallet_address', '').strip()
        wallet_address = validate_wallet_address(wallet_address_raw) if wallet_address_raw else None
        
        # Property-specific fields
        asset_name = sanitize_string(request.form.get('asset_name', ''), max_length=255, allow_empty=True) or None
        asset_value_raw = request.form.get('asset_value', '').strip()
        asset_value = sanitize_float(asset_value_raw, default=None, min_val=0) if asset_value_raw else None
        asset_currency = sanitize_string(request.form.get('asset_currency', 'USD'), max_length=10, allow_empty=False).upper()
        
        # Create wallet configuration
        wallet_config = WalletConfig(
            name=name,
            api_name=api_name,
            provider=provider,
            wallet_type=wallet_type,
            api_key=api_key,
            api_secret=api_secret,
            api_passphrase=api_passphrase,
            wallet_address=wallet_address,
            asset_name=asset_name,
            asset_value=asset_value,
            asset_currency=asset_currency,
            status='not_tested'
        )
        
        # Save to database
        with get_session() as session:
            session.add(wallet_config)
            session.commit()
        
        flash(f'Wallet "{name}" added successfully!', 'success')
        return redirect(url_for('admin'))
        
    except Exception as e:
        app.logger.error(f"Error adding wallet: {e}", exc_info=True)
        flash('An error occurred adding the wallet. Please check your input.', 'error')
        return redirect(url_for('admin'))


@app.route("/admin/test_wallet/<int:wallet_id>")
@limiter.limit(RATE_LIMITS['test_wallet'])
def test_wallet(wallet_id):
    """Test wallet connection and return JSON result."""
    # Validate wallet_id from URL
    wallet_id = sanitize_integer(wallet_id, default=0, min_val=1)
    if wallet_id == 0:
        return jsonify({"success": False, "message": "Invalid wallet ID"})
    
    try:
        with get_session() as session:
            wallet = session.query(WalletConfig).filter(WalletConfig.id == wallet_id).first()
            if not wallet:
                return jsonify({"success": False, "message": "Wallet not found"})
            
            # Test connection based on provider
            if wallet.provider == 'apex_omni':
                success, message = test_apex_connection(
                    wallet.api_key or '',
                    wallet.api_secret or '',
                    wallet.api_passphrase or ''
                )
            elif wallet.provider == 'hyperliquid':
                success, message = test_hyperliquid_connection(wallet.wallet_address or '')
            elif wallet.provider == 'property':
                success, message = test_property_wallet(
                    wallet.asset_name or '',
                    wallet.asset_value or 0,
                    wallet.asset_currency or 'USD'
                )
            else:
                success, message = False, f"Unknown provider: {wallet.provider}"
            
            # Update wallet status
            wallet.status = 'connected' if success else 'error'
            wallet.last_test = datetime.utcnow()
            wallet.error_message = None if success else message
            session.commit()
            
            return jsonify({"success": success, "message": message})
            
    except Exception as e:
        return jsonify({"success": False, "message": f"Test failed: {str(e)}"})


@app.route("/admin/edit_wallet/<int:wallet_id>", methods=['GET', 'POST'])
@limiter.limit(RATE_LIMITS['admin'], methods=['POST'])
@csrf.exempt
def edit_wallet(wallet_id):
    """Edit wallet configuration."""
    # Validate wallet_id from URL
    wallet_id = sanitize_integer(wallet_id, default=0, min_val=1)
    if wallet_id == 0:
        flash('Invalid wallet ID', 'error')
        return redirect(url_for('admin'))
    
    try:
        with get_session() as session:
            wallet = session.query(WalletConfig).filter(WalletConfig.id == wallet_id).first()
            if not wallet:
                flash('Wallet not found', 'error')
                return redirect(url_for('admin'))
            
            if request.method == 'POST':
                # Update wallet fields with validation
                credentials_changed = False

                if 'name' in request.form:
                    new_name = validate_wallet_name(request.form.get('name'))
                    if new_name:
                        wallet.name = new_name

                if 'api_name' in request.form:
                    wallet.api_name = sanitize_string(request.form.get('api_name', ''), max_length=255, allow_empty=True) or None

                if 'provider' in request.form:
                    new_provider = sanitize_string(request.form.get('provider', ''), max_length=50, allow_empty=False)
                    if new_provider in ['apex_omni', 'hyperliquid', 'property']:
                        wallet.provider = new_provider

                if 'wallet_type' in request.form:
                    new_wallet_type = sanitize_string(request.form.get('wallet_type', ''), max_length=50, allow_empty=False)
                    if new_wallet_type in ['crypto', 'stocks', 'property']:
                        wallet.wallet_type = new_wallet_type

                # Provider-specific fields (track if credentials changed)
                if 'api_key' in request.form:
                    new_api_key = sanitize_string(request.form.get('api_key', ''), max_length=1000, allow_empty=True) or None
                    if new_api_key != wallet.api_key:
                        credentials_changed = True
                    wallet.api_key = new_api_key
                if 'api_secret' in request.form:
                    new_api_secret = sanitize_string(request.form.get('api_secret', ''), max_length=1000, allow_empty=True) or None
                    if new_api_secret != wallet.api_secret:
                        credentials_changed = True
                    wallet.api_secret = new_api_secret
                if 'api_passphrase' in request.form:
                    new_api_passphrase = sanitize_string(request.form.get('api_passphrase', ''), max_length=1000, allow_empty=True) or None
                    if new_api_passphrase != wallet.api_passphrase:
                        credentials_changed = True
                    wallet.api_passphrase = new_api_passphrase
                if 'wallet_address' in request.form:
                    wallet_address_raw = request.form.get('wallet_address', '').strip()
                    new_wallet_address = validate_wallet_address(wallet_address_raw) if wallet_address_raw else None
                    if new_wallet_address != wallet.wallet_address:
                        credentials_changed = True
                    wallet.wallet_address = new_wallet_address

                # Property-specific fields
                if 'asset_name' in request.form:
                    wallet.asset_name = sanitize_string(request.form.get('asset_name', ''), max_length=255, allow_empty=True) or None
                if 'asset_value' in request.form:
                    asset_value_raw = request.form.get('asset_value', '').strip()
                    wallet.asset_value = sanitize_float(asset_value_raw, default=None, min_val=0) if asset_value_raw else None
                if 'asset_currency' in request.form:
                    wallet.asset_currency = sanitize_string(request.form.get('asset_currency', 'USD'), max_length=10, allow_empty=False).upper()

                # Only reset status if credentials changed, not just name/metadata
                if credentials_changed:
                    wallet.status = 'not_tested'
                    wallet.error_message = None
                    wallet.last_test = None
                
                session.commit()
                flash(f'Wallet "{wallet.name}" updated successfully!', 'success')
                return redirect(url_for('admin'))
            
            # GET request - show edit form
            return render_template('edit_wallet.html', wallet=wallet)
            
    except Exception as e:
        flash(f'Error editing wallet: {str(e)}', 'error')
        return redirect(url_for('admin'))


@app.route("/admin/delete_wallet/<int:wallet_id>", methods=['POST'])
@limiter.limit(RATE_LIMITS['admin'])
@csrf.exempt
def delete_wallet(wallet_id):
    """Delete wallet and all related historical data."""
    # Validate wallet_id from URL
    wallet_id = sanitize_integer(wallet_id, default=0, min_val=1)
    if wallet_id == 0:
        flash('Invalid wallet ID', 'error')
        return redirect(url_for('admin'))
    
    try:
        with get_session() as session:
            wallet = session.query(WalletConfig).filter(WalletConfig.id == wallet_id).first()
            if wallet:
                wallet_name = wallet.name

                # Delete all related historical data
                from db.models import EquitySnapshot, PositionSnapshot, ClosedTrade

                session.query(EquitySnapshot).filter(EquitySnapshot.wallet_id == wallet_id).delete()
                session.query(PositionSnapshot).filter(PositionSnapshot.wallet_id == wallet_id).delete()
                session.query(ClosedTrade).filter(ClosedTrade.wallet_id == wallet_id).delete()

                # Delete strategy assignments for this wallet
                from db.models_strategies import StrategyAssignment
                session.query(StrategyAssignment).filter(StrategyAssignment.wallet_id == wallet_id).delete()

                # Delete wallet config
                session.delete(wallet)

                flash(f'Wallet "{wallet_name}" and all associated data deleted successfully!', 'success')
            else:
                flash('Wallet not found', 'error')
    except Exception as e:
        flash(f'Error deleting wallet: {str(e)}', 'error')

    return redirect(url_for('admin'))


@app.route("/api/provider_instructions/<provider>")
def get_provider_instructions_api(provider):
    """Get provider setup instructions via API."""
    instructions = get_provider_instructions(provider)
    return jsonify(instructions)


@app.route("/admin/strategies")
def admin_strategies():
    """Manage strategies and assignments."""
    with get_session() as session:
        strategies = list_strategies(session)
        assignments = list_assignments(session)
        wallets = session.query(WalletConfig).filter(WalletConfig.status == 'connected').order_by(WalletConfig.name).all()

        # Get latest equity per wallet
        portfolio_equity = get_latest_equity_per_wallet(session)

        # Serialize to plain dicts to avoid lazy loading after session close
        strategies_data = [{
            'id': s.id,
            'name': s.name,
            'description': s.description,
            'created_at': s.created_at,
        } for s in strategies]

        # Build strategy id -> name map
        name_by_id = {s['id']: s['name'] for s in strategies_data}

        assignments_data = [{
            'id': a.id,
            'wallet_id': a.wallet_id,
            'symbol': a.symbol,
            'strategy_id': a.strategy_id,
            'strategy_name': name_by_id.get(a.strategy_id),
            'start_at': a.start_at,
            'end_at': a.end_at,
            'active': a.active,
        } for a in assignments]

        wallets_data = [{
            'id': w.id,
            'name': w.name,
            'provider': w.provider,
            'equity': portfolio_equity.get(w.id, 0)
        } for w in wallets]

        # Get traded symbols per wallet
        traded_symbols_map = get_traded_symbols_by_wallet(session)

        # Get active assignments map
        active_assignments = get_active_assignment_map(session)

        # Build matrix data structure
        # Merge traded symbols with assigned symbols (to show manually added symbols)
        # Helper: intelligently merge symbols by checking if one is a base/subset of another
        from utils.data_utils import normalize_symbol as norm_sym
        def merge_symbols(traded_set, assignment_symbol):
            """Merge an assignment symbol with traded symbols, handling variants like BTC vs BTC-USDT"""
            norm_assign = norm_sym(assignment_symbol)
            # Check if this symbol variant already exists in traded symbols
            for traded in traded_set:
                # Direct match
                if traded == norm_assign:
                    return traded_set
                # Check if assignment is a base of traded (e.g., BTC is in BTC-USDT)
                if traded.startswith(norm_assign + '-') or traded.startswith(norm_assign + '_'):
                    return traded_set
                # Check if traded is a base of assignment
                if norm_assign.startswith(traded + '-') or norm_assign.startswith(traded + '_'):
                    traded_set.discard(traded)
                    traded_set.add(norm_assign)
                    return traded_set
            # No variant found, add as-is
            traded_set.add(norm_assign)
            return traded_set

        combined_symbols_map = {}
        for w in wallets:
            wallet_id = w.id
            symbols = set(traded_symbols_map.get(wallet_id, set()))

            # Add symbols from active assignments (even if not traded yet)
            for (assign_wallet_id, assign_symbol), _ in active_assignments.items():
                if assign_wallet_id == wallet_id:
                    symbols = merge_symbols(symbols, assign_symbol)

            combined_symbols_map[wallet_id] = symbols

        # Build matrix: list of wallet rows with their symbol assignments
        matrix_data = []
        for w in wallets:
            wallet_symbols = sorted(list(combined_symbols_map.get(w.id, set())))
            row = {
                'wallet_id': w.id,
                'wallet_name': w.name,
                'equity': portfolio_equity.get(w.id, 0),
                'symbols': []
            }
            for symbol in wallet_symbols:
                # Try to find assignment, handling symbol variants (e.g., BTC vs BTC-USDT)
                assigned_strategy_id = active_assignments.get((w.id, symbol))
                # If not found, try looking up assignments with any symbol that matches
                if not assigned_strategy_id:
                    for (assign_wallet_id, assign_symbol), strategy_id in active_assignments.items():
                        if assign_wallet_id == w.id:
                            assign_norm = norm_sym(assign_symbol)
                            # Direct match
                            if assign_norm == symbol:
                                assigned_strategy_id = strategy_id
                                break
                            # Check symbol variants (BTC matches BTC-USDT)
                            if symbol.startswith(assign_norm + '-') or symbol.startswith(assign_norm + '_'):
                                assigned_strategy_id = strategy_id
                                break
                            if assign_norm.startswith(symbol + '-') or assign_norm.startswith(symbol + '_'):
                                assigned_strategy_id = strategy_id
                                break
                assigned_strategy_name = name_by_id.get(assigned_strategy_id) if assigned_strategy_id else None

                # Get notes, is_current, assignment_id, modified_at, and trade count from assignment
                assignment_notes = None
                assignment_is_current = True
                assignment_id = None
                assignment_modified_at = None
                assignment_trade_count = 0
                for a in assignments:
                    if a.wallet_id == w.id and a.active:
                        a_norm = norm_sym(a.symbol)
                        # Check for direct match or symbol variants
                        if (a_norm == symbol or
                            symbol.startswith(a_norm + '-') or symbol.startswith(a_norm + '_') or
                            a_norm.startswith(symbol + '-') or a_norm.startswith(symbol + '_')):
                            assignment_notes = a.notes
                            assignment_is_current = a.is_current if hasattr(a, 'is_current') else True
                            assignment_id = a.id
                            assignment_modified_at = a.modified_at if hasattr(a, 'modified_at') else a.created_at
                            # Count trades for this assignment
                            try:
                                assignment_trade_count = count_trades_for_assignment(session, a.id)
                            except Exception:
                                assignment_trade_count = 0
                            break

                row['symbols'].append({
                    'symbol': symbol,
                    'strategy_id': assigned_strategy_id,
                    'strategy_name': assigned_strategy_name,
                    'notes': assignment_notes,
                    'is_current': assignment_is_current,
                    'assignment_id': assignment_id,
                    'modified_at': assignment_modified_at,
                    'trade_count': assignment_trade_count,
                })

            # Only include wallet row if it has at least one symbol with an assignment
            has_assignment = any(sym['assignment_id'] for sym in row['symbols'])
            if has_assignment:
                matrix_data.append(row)

    return render_template("admin_strategies.html",
                         strategies=strategies_data,
                         assignments=assignments_data,
                         wallets=wallets_data,
                         matrix_data=matrix_data)


@app.route("/admin/strategies/add", methods=['POST'])
@limiter.limit(RATE_LIMITS['admin'])
@csrf.exempt
def admin_add_strategy():
    name = (request.form.get('name') or '').strip()
    desc = (request.form.get('description') or '').strip()
    if not name:
        flash('Strategy name is required', 'error')
        return redirect(url_for('admin_strategies'))
    try:
        with get_session() as session:
            create_strategy(session, name, desc)
        flash(f'Strategy "{name}" added.', 'success')
    except Exception as e:
        flash(f'Error adding strategy: {e}', 'error')
    return redirect(url_for('admin_strategies'))


@app.route("/admin/strategies/edit/<int:strategy_id>", methods=['POST'])
@limiter.limit(RATE_LIMITS['admin'])
@csrf.exempt
def admin_edit_strategy(strategy_id):
    # Validate strategy_id from URL
    strategy_id = sanitize_integer(strategy_id, default=0, min_val=1)
    if strategy_id == 0:
        flash('Invalid strategy ID', 'error')
        return redirect(url_for('admin_strategies'))
    
    name = (request.form.get('name') or '').strip()
    desc = (request.form.get('description') or '').strip()
    if not name:
        flash('Strategy name is required', 'error')
        return redirect(url_for('admin_strategies'))
    try:
        with get_session() as session:
            strategy = session.query(Strategy).filter(Strategy.id == strategy_id).first()
            if not strategy:
                flash('Strategy not found', 'error')
                return redirect(url_for('admin_strategies'))
            strategy.name = name
            strategy.description = desc if desc else None
            session.commit()
        flash(f'Strategy "{name}" updated.', 'success')
    except Exception as e:
        flash(f'Error updating strategy: {e}', 'error')
    return redirect(url_for('admin_strategies'))


@app.route("/admin/strategies/delete/<int:strategy_id>", methods=['POST'])
@limiter.limit(RATE_LIMITS['admin'])
@csrf.exempt
def admin_delete_strategy(strategy_id):
    # Validate strategy_id from URL
    strategy_id = sanitize_integer(strategy_id, default=0, min_val=1)
    if strategy_id == 0:
        flash('Invalid strategy ID', 'error')
        return redirect(url_for('admin_strategies'))
    
    try:
        with get_session() as session:
            strategy = session.query(Strategy).filter(Strategy.id == strategy_id).first()
            if not strategy:
                flash('Strategy not found', 'error')
                return redirect(url_for('admin_strategies'))

            strategy_name = strategy.name
            session.delete(strategy)
            session.commit()
        flash(f'Strategy "{strategy_name}" deleted.', 'success')
    except Exception as e:
        flash(f'Error deleting strategy: {e}', 'error')
    return redirect(url_for('admin_strategies'))


@app.route("/admin/strategies/bulk_add", methods=['POST'])
@limiter.limit(RATE_LIMITS['admin'])
@csrf.exempt
def admin_bulk_add_strategies():
    """Bulk add strategies from textarea (one per line)."""
    strategies_text = sanitize_text(request.form.get('strategies', ''), max_length=10000)
    if not strategies_text:
        flash('No strategies provided', 'error')
        return redirect(url_for('admin_strategies'))

    # Split by newlines and filter out empty lines
    strategy_names = [line.strip() for line in strategies_text.split('\n') if line.strip()]

    if not strategy_names:
        flash('No valid strategy names found', 'error')
        return redirect(url_for('admin_strategies'))

    added_count = 0
    skipped_count = 0
    errors = []

    try:
        with get_session() as session:
            for name in strategy_names:
                try:
                    create_strategy(session, name, '')  # Empty description for bulk add
                    added_count += 1
                except Exception as e:
                    skipped_count += 1
                    errors.append(f'{name}: {str(e)}')

        # Show summary message
        if added_count > 0:
            flash(f'Successfully added {added_count} strategies.', 'success')
        if skipped_count > 0:
            flash(f'Skipped {skipped_count} strategies (duplicates or errors).', 'error')

    except Exception as e:
        flash(f'Error during bulk add: {e}', 'error')

    return redirect(url_for('admin_strategies'))


@app.route("/admin/strategies/assign", methods=['POST'])
@limiter.limit(RATE_LIMITS['admin'])
@csrf.exempt
def admin_assign_strategy():
    """
    Handle both single-pair (legacy form) and multi-pair assignments.
    Multi-pair form sends arrays: symbols[], strategy_ids[], notes_list[]
    Legacy form sends single values: symbol, strategy_id, notes
    """
    try:
        wallet_id = sanitize_integer(request.form.get('wallet_id'), default=0, min_val=1)
        is_current = request.form.get('is_current') == '1'
    except Exception:
        wallet_id = 0
        is_current = True

    if not wallet_id:
        app.logger.warning(f"Missing required wallet_id")
        flash('Wallet is required', 'error')
        return redirect(url_for('admin_strategies'))

    # Check if this is multi-pair form (arrays) or legacy single-pair form
    symbols_list = request.form.getlist('symbols')
    strategy_ids_list = request.form.getlist('strategy_ids')
    notes_list = request.form.getlist('notes_list')

    # If no arrays provided, try legacy single-pair format
    if not symbols_list:
        symbol = sanitize_string(request.form.get('symbol', ''), max_length=20, allow_empty=False)
        strategy_id = sanitize_integer(request.form.get('strategy_id'), default=0, min_val=1)
        notes = sanitize_text(request.form.get('notes', ''), max_length=1000) or None

        if not symbol or not strategy_id:
            app.logger.warning(f"Missing required fields: wallet_id={wallet_id}, symbol={symbol}, strategy_id={strategy_id}")
            flash('Wallet, Symbol and Strategy are required', 'error')
            return redirect(url_for('admin_strategies'))

        symbols_list = [symbol]
        strategy_ids_list = [str(strategy_id)]
        notes_list = [notes]

    # Validate that arrays have matching lengths
    if not (len(symbols_list) == len(strategy_ids_list)):
        app.logger.warning(f"Array length mismatch: symbols={len(symbols_list)}, strategies={len(strategy_ids_list)}")
        flash('Symbols and strategies must have matching counts', 'error')
        return redirect(url_for('admin_strategies'))

    # Pad notes_list to match if needed
    if len(notes_list) < len(symbols_list):
        notes_list.extend([''] * (len(symbols_list) - len(notes_list)))

    # Process all pairs
    assignment_count = 0
    errors = []

    try:
        with get_session() as session:
            for i, symbol in enumerate(symbols_list):
                # Sanitize inputs
                symbol = sanitize_string(symbol, max_length=20, allow_empty=False).strip()
                strategy_id = sanitize_integer(strategy_ids_list[i], default=0, min_val=1)
                notes = sanitize_text(notes_list[i] if i < len(notes_list) else '', max_length=1000) or None

                # Validate required fields
                if not symbol or not strategy_id:
                    errors.append(f"Pair {i + 1}: Missing symbol or strategy")
                    continue

                # Validate symbol format
                normalized_symbol = validate_symbol(symbol)
                if not normalized_symbol:
                    errors.append(f"Pair {i + 1}: Invalid symbol format '{symbol}'")
                    continue

                try:
                    # Deactivate existing assignments for this wallet/symbol combo
                    existing = session.query(StrategyAssignment).filter(
                        StrategyAssignment.wallet_id == wallet_id,
                        StrategyAssignment.symbol == normalized_symbol,
                        StrategyAssignment.active == True
                    ).all()

                    for assignment in existing:
                        assignment.active = False
                        assignment.end_at = datetime.utcnow()

                    # Create new assignment
                    app.logger.info(f"Creating assignment {i + 1}/{len(symbols_list)}: wallet_id={wallet_id}, symbol={normalized_symbol}, strategy_id={strategy_id}")
                    create_assignment(session, wallet_id, normalized_symbol, strategy_id, None, notes, is_current)
                    assignment_count += 1

                except Exception as e:
                    errors.append(f"Pair {i + 1} ({symbol}): {str(e)}")
                    app.logger.error(f"Error creating assignment for pair {i + 1}: {e}", exc_info=True)
                    continue

            # Commit all successful assignments
            if assignment_count > 0:
                session.commit()
                app.logger.info(f"Successfully created {assignment_count} assignments")

    except Exception as e:
        app.logger.error(f"Error in transaction: {e}", exc_info=True)
        flash(f'Error creating assignments: {e}', 'error')
        return redirect(url_for('admin_strategies'))

    # Report results
    if assignment_count > 0:
        message = f'Successfully created {assignment_count} strategy assignment{"s" if assignment_count != 1 else ""}.'
        if errors:
            message += f' {len(errors)} pair(s) failed.'
        flash(message, 'success')
    else:
        flash(f'No assignments created. Errors: {"; ".join(errors)}', 'error')

    if errors:
        app.logger.warning(f"Assignment errors: {errors}")

    return redirect(url_for('admin_strategies'))


@app.route("/api/symbol-suggestions", methods=['GET'])
@limiter.limit(RATE_LIMITS['api'])
def get_symbol_suggestions():
    """
    Get symbol suggestions for autocomplete based on existing assignments.
    Returns list of unique symbols from strategy assignments.

    Query params:
    - q: Optional search query to filter symbols (e.g., "BTC" returns "BTC-USDT", "BTC-USD")
    """
    try:
        query = request.args.get('q', '').strip().upper()

        with get_session() as session:
            # Get all unique symbols from active assignments
            all_symbols = session.query(StrategyAssignment.symbol).filter(
                StrategyAssignment.active == True
            ).distinct().all()

            # Extract symbol strings and deduplicate
            symbols = sorted(list(set([s[0] for s in all_symbols if s[0]])))

            # Filter by query if provided
            if query:
                symbols = [s for s in symbols if query in s]

            # Return top 15 suggestions
            return jsonify({'symbols': symbols[:15]})

    except Exception as e:
        app.logger.error(f"Error fetching symbol suggestions: {e}", exc_info=True)
        return jsonify({'symbols': [], 'error': str(e)}), 500


@app.route("/admin/strategies/end/<int:assignment_id>", methods=['POST'])
@limiter.limit(RATE_LIMITS['admin'])
@csrf.exempt
def admin_end_assignment(assignment_id):
    # Validate assignment_id from URL
    assignment_id = sanitize_integer(assignment_id, default=0, min_val=1)
    if assignment_id == 0:
        flash('Invalid assignment ID', 'error')
        return redirect(url_for('admin_strategies'))
    
    try:
        with get_session() as session:
            a = end_assignment(session, assignment_id, None)
            if not a:
                flash('Assignment not found', 'error')
            else:
                flash('Assignment ended.', 'success')
    except Exception as e:
        flash(f'Error ending assignment: {e}', 'error')
    return redirect(url_for('admin_strategies'))


@app.route("/admin/strategies/assignment/<int:assignment_id>/delete", methods=['POST'])
@limiter.limit(RATE_LIMITS['admin'])
@csrf.exempt
def admin_delete_assignment(assignment_id):
    # Validate assignment_id from URL
    assignment_id = sanitize_integer(assignment_id, default=0, min_val=1)
    if assignment_id == 0:
        flash('Invalid assignment ID', 'error')
        return redirect(url_for('admin_strategies'))
    
    try:
        with get_session() as session:
            result = delete_assignment(session, assignment_id)
            if result:
                flash('Strategy pairing deleted.', 'success')
            else:
                flash('Assignment not found', 'error')
    except Exception as e:
        flash(f'Error deleting assignment: {e}', 'error')
    return redirect(url_for('admin_strategies'))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=app.debug)
