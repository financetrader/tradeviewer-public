# Apex Omni Wallet Viewer

Multi-wallet portfolio monitoring application with SQLite database for tracking equity, positions, and trade history over time. Features portfolio overview dashboard, per-wallet detailed views, strategy management, automated logging, and comprehensive P&L analytics.

References:
- Apex Omni API docs: https://api-docs.pro.apex.exchange/#introduction
- Python SDK: https://github.com/ApeX-Protocol/apexpro-openapi

## Quick start

**Prerequisites:**
- Python 3.8 or higher
- pip (Python package manager)

**Setup Steps:**

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Create .env file**
   ```bash
   cp env.example .env
   # Edit .env and set FLASK_SECRET_KEY (generate with: python3 -c "import secrets; print(secrets.token_hex(32))")
   ```

3. **Start the application**
   ```bash
   python app.py
   ```

4. **Access the application**
   - **Portfolio Overview:** http://localhost:5000
   - **Wallets:** http://localhost:5000/admin
   - **Strategies:** http://localhost:5000/admin/strategies
   - **Exchange Logs:** http://localhost:5000/admin/exchange-logs

**To stop:**
Press `Ctrl+C` in the terminal

## Features

### Portfolio Overview (`/`)
- **Aggregate View**: Total equity across all connected wallets
- **Per-Wallet Metrics**: Equity, unrealized PnL, available balance, last update
- **Period Analytics**: Realized PnL, win rate, and trade count over selectable periods (24h/7d/30d/custom)
- **Quick Navigation**: Links to detailed wallet dashboards

### Wallet Management (`/admin`)
- **Multi-Wallet Support**: Manage multiple Apex Omni, Hyperliquid, or property wallets
- **Secure Credentials**: Database-stored API keys with connection testing
- **Wallet Types**: Crypto, stocks, property/fixed assets
- **Status Tracking**: Connection status and last test timestamp

### Strategy Management (`/admin/strategies`)
- **Strategy Catalog**: Define and name trading strategies with descriptions
- **Wallet+Pair Assignments**: Map strategies to specific wallet and symbol combinations
- **Time-Bounded Tracking**: Start/end timestamps for each strategy assignment
- **Active Management**: End assignments on-demand or let them run indefinitely
- **Performance Attribution**: Track which trades belong to which strategies

### Detailed Wallet View (`/wallet/<id>`)
- **Real-Time Data**: Current positions, balances, and open orders
- **Historical Charts**: Equity over time, per-symbol P&L tracking
- **Trade History**: Complete fill history with fees and position sizing
- **Closed P&L**: Detailed closed trade analysis with entry/exit prices

## Configuration

### Database-First Approach
Wallet credentials are now stored in the database via the wallets page. No `.env` file is required for wallet API keys.

**Note:** CSRF protection is currently disabled - all POST routes use `@csrf.exempt` decorator.

### Environment Variables

**Required for Production:**
```bash
FLASK_SECRET_KEY=your-secret-key-here  # For session security (auto-generated if not set)
```


**Optional:**
```bash
FLASK_ENV=production  # Set to 'production' for production deployment
ENCRYPTION_KEY=your-encryption-key  # For credential encryption (optional)
ADMIN_LOG_TAIL=200  # Number of log lines to show in admin panel
```

See `env.example` for a complete list of available environment variables.

### Adding Wallets
1. Navigate to `/admin`
2. Fill in wallet details (name, provider, API credentials)
3. Click "Test" to verify connection
4. Once connected, the wallet appears in the overview dashboard

### Supported Providers
- **Apex Omni**: API key, secret, and passphrase required
- **Hyperliquid**: Wallet address only (read-only via public API)
- **Property/Fixed Assets**: Manual entry for tracking real estate and other assets

## Project Structure

### Main Application
- `app.py` — Flask web app with all routes and integrated background logger
- `logger.py` — Equity logging functions (runs automatically in background thread)

### Services Layer
- `services/` — Business logic modules
  - `apex_client.py` — API client functions with logging wrapper
  - `data_service.py` — Data fetching and enrichment
  - `wallet_service.py` — Centralized wallet connection management
  - `wallet_manager.py` — Wallet testing and validation
  - `sync_service.py` — Data synchronization utilities
  - `exchange_logging.py` — Exchange traffic logging

### Database Layer
- `data/wallet.db` — SQLite database with all historical data
- `db/` — Database models, queries, and connection management
  - `models.py` — Core SQLAlchemy models (wallets, equity, positions, trades)
  - `models_strategies.py` — Strategy and assignment models
  - `queries.py` — Database query helpers (including overview analytics)
  - `queries_strategies.py` — Strategy-specific query helpers
  - `database.py` — Database connection and session management

### Templates
- `templates/` — Jinja2 HTML templates
  - `overview.html` — Portfolio overview dashboard (NEW)
  - `dashboard.html` — Per-wallet detailed view
  - `admin.html` — Wallet management panel
  - `admin_strategies.html` — Strategy management panel (RESTORED)
  - `admin_exchange_logs.html` — Exchange traffic logs
  - `edit_wallet.html` — Wallet editing form

### Utilities
- `utils/` — Helper functions
  - `calculations.py` — Position and P&L calculations
  - `data_utils.py` — Data normalization and formatting
  - `logging_utils.py` — Application logging utilities


### Migrations & Tests
- `docs/archive/migrations/` — Historical database migration scripts (archived)
- `tests/` — Comprehensive test suite
  - `test_overview_queries.py` — Unit tests for overview analytics
  - `test_overview_integration.py` — Integration tests for overview route
  - `test_calculations.py` — Position calculation tests
  - `test_data_service.py` — Data service tests
  - `test_wallet_service.py` — Wallet service tests
  - `test_integration.py` — End-to-end integration tests

### Documentation
- `README.md` — This file (project overview)
- `docs/GUIDE.md` — Complete setup, security, and deployment guide
- `docs/FRESH_SERVER_INSTALLATION.md` — Step-by-step installation guide for fresh Linux servers
- `docs/DOCUMENTATION_REVIEW.md` — Documentation review and verification report
- `docs/rules.md` — Folder structure rules and organization guidelines
- `docs/HYPERLIQUID_LEVERAGE_CALCULATION.md` — Hyperliquid leverage calculation methodology and implementation details
- `docs/archive/documentation/TESTING.md` — Comprehensive testing guide
- `docs/archive/documentation/PROJECT_RULES.md` — Development guidelines and AI collaboration rules
- `docs/archive/documentation/OVERVIEW_DASHBOARD_IMPLEMENTATION.md` — Overview feature documentation

## Database Schema

### Core Tables
- **wallet_configs** — Wallet credentials and connection status
- **equity_snapshots** — Historical equity and P&L snapshots (logged every 30 min)
- **position_snapshots** — Historical position data with leverage and unrealized PnL
- **closed_trades** — Historical closed trades with P&L, fees, and leverage (from position snapshots)

### Strategy Tables
- **strategies** — Strategy catalog (name, description)
- **strategy_assignments** — Time-bounded wallet+symbol → strategy mappings

### Indexes
- Composite indexes on `(wallet_id, timestamp)` for efficient time-series queries
- Indexes on `(wallet_id, symbol, timestamp)` for position lookups
- Strategy assignment indexes for active assignment lookups

## Testing

### Comprehensive Testing Document

**For major changes and regression testing, see `docs/archive/documentation/TESTING.md`** - a complete testing guide with:
- Quick 5-test checklist for core functionality
- Detailed API, database, and UI verification steps
- End-to-end workflow scenarios
- Performance monitoring (report-only)
- Troubleshooting guide

### Quick Verification After Changes

```bash
# Run unit tests
python -m pytest tests/ -v
```

### Unit Tests

Run unit tests to verify code functionality:

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test modules
python -m pytest tests/test_calculations.py -v
python -m pytest tests/test_overview_queries.py -v  # NEW: Overview analytics tests
python -m pytest tests/test_overview_integration.py -v  # NEW: Overview route tests

# Run with coverage
python -m pytest tests/ --cov=. --cov-report=html

# Run with coverage (if pytest-cov installed)
python -m pytest tests/ --cov=services --cov=utils
```

### When to Use Full Testing

- **Before major changes:** Run Quick Test Checklist from `docs/archive/documentation/TESTING.md`
- **After major changes:** Run relevant detailed test sections
- **Before deployment:** Complete the Regression Test Checklist
- **When issues arise:** Use the Troubleshooting Guide in `docs/archive/documentation/TESTING.md`

## Database

The application now uses SQLite for data persistence:

**View database:**
```bash
# Install DB Browser for SQLite
sudo apt install sqlitebrowser

# Open database
sqlitebrowser data/wallet.db
```

**Query from command line:**
```bash
sqlite3 data/wallet.db
.tables                    # List all tables
.schema equity_snapshots   # View table structure
SELECT * FROM equity_snapshots ORDER BY timestamp DESC LIMIT 10;
.quit
```

**Tables:**
- `equity_snapshots` - Historical account balance data
- `position_snapshots` - Position history with equity_used tracking
- `closed_trades` - Closed trade history with P&L


## Data Logging & Synchronization

The application automatically logs and synchronizes data so the dashboard stays current.

### Equity Snapshots
- Frequency: every 30 minutes (background logger) and on every dashboard page load/refresh
- Data: total equity, unrealized PnL, available balance, realized PnL
- Source: live API balance data
- When offline: no points are written → the equity chart shows visible gaps (broken lines) for missing periods

### Closed Trades / Realized PnL
- Frequency: every 30 minutes (background logger) and on every dashboard page load/refresh
- Data: all historical fills (closed trades) fetched from the exchange
- Source: exchange historical trade API
- When offline: no gaps; realized PnL only changes when trades close, so charts render a flat horizontal line until the next closed trade
- Recovery: when the server restarts, the next refresh/30‑minute cycle re-syncs all historical closed trades from the exchange

### Background Logger

The background logger runs automatically when you start the application. It:
- Writes equity snapshots every 30 minutes (:00 and :30 past each hour)
- Syncs closed trades from exchange API every 30 minutes
- Runs in a separate background thread (non-blocking)
- Starts automatically with the application

```bash
# The logger starts automatically when you run:
python app.py

# Logger output appears in the console or log files
```

### Chart Behavior
- Equity charts: show gaps (broken lines) for missing 30+ minute periods
- PnL charts: extend horizontally to now when there are no recent closed trades (flat line = no change)
- Symbol normalization: symbols are stored as dashed pairs (e.g., `BTC-USDT`, `ETH-USDC`) to avoid duplicates

### Wallet Staleness Warnings

**Important**: Wallets are the source of truth. The dashboard aggregates ALL connected wallets' data, regardless of how recently they updated. Staleness is displayed as a warning, not by hiding data.

**Staleness Behavior:**
- **Threshold**: Configurable via `STALE_WALLET_HOURS` environment variable (default: 2 hours)
- **Display**: Each wallet shows "Last updated: X minutes/hours ago" in the portfolio table
- **Warning**: If a wallet hasn't updated in >threshold hours, a warning indicator appears
- **Portfolio Total**: Includes stale wallets (they are still valid data, just old)
- **No Gaps**: Unlike missing data periods, stale wallet data does NOT create gaps in the equity chart

**Example:**
```bash
# Show warning if wallet is older than 4 hours
STALE_WALLET_HOURS=4 python app.py
```

**Why This Design?**
- Wallets are the ultimate source of truth for portfolio equity
- Filtering out stale data would create artificial dips in equity charts
- Better UX: show stale data with a warning than hide it from users
- Users can see if a wallet is disconnected and take action

## Notes
- If you hit a dependency import error, run the `pip install` line shown in Quick start; versions are pinned in `requirements.txt`.
- To switch between mainnet and testnet, set `APEX_NETWORK` accordingly.
- Historical CSV data archived in `archive/` directory

## Recent Updates (October 2025)

### Portfolio Overview Dashboard
- **New default route (`/`)**: Aggregate view across all wallets
- **Period analytics**: 24h/7d/30d/custom date range selection
- **Per-wallet metrics**: Equity, unrealized PnL, available balance, last update
- **Performance tracking**: Realized PnL, win rate %, and trade count per period
- **17 comprehensive tests**: Unit and integration tests for all query helpers

### Strategy Management System
- **Strategy catalog**: Define and name trading strategies
- **Wallet+pair assignments**: Map strategies to specific symbols per wallet
- **Time-bounded tracking**: Start/end timestamps for performance attribution
- **Active management**: End assignments on-demand via UI
- **Database schema**: New `strategies` and `strategy_assignments` tables

### Multi-Wallet Architecture
- **Centralized wallet service**: Unified connection management
- **Database-stored credentials**: No more `.env` files for API keys
- **Connection testing**: Verify wallet connectivity before activation
- **Isolated data views**: Per-wallet equity, positions, and trade history

## Multi-Wallet Support

### Accessing Wallets
- **Portfolio overview (`/`)**: Aggregate view across all connected wallets
- **Direct wallet access**: `/wallet/<wallet_id>` - Detailed dashboard for specific wallet
- **Switch between wallets**: Use the dropdown in wallet dashboard headers
- **Wallets page**: Manage all wallets, view connection status

### URL Structure
- `/` - Portfolio overview dashboard (aggregate metrics)
- `/wallet/<id>` - Detailed wallet dashboard
- `/admin` - Wallet management panel

### Data Isolation
Each wallet maintains its own:
- Equity history snapshots
- Position snapshots  
- Closed trades
- Performance metrics
- Charts and analytics

### Adding Multiple Wallets
1. Go to Wallets (`/admin`)
2. Add new wallet configuration
3. Test the connection
4. Access via Dashboard link or direct URL
5. Switch between wallets using the dropdown selector

## New in v1.2
- **Complete code refactoring**: Broke down monolithic `app.py` into modular structure
- **New modular architecture**: 
  - `services/` - API client and data processing logic
  - `db/` - Database models, queries, and connection management
  - `utils/` - Utility functions for calculations
  - `tests/` - Comprehensive unit and integration tests
- **Enhanced database integration**: Full SQLite integration with proper models and queries
- **Comprehensive testing**: Added `TESTING.md` with detailed testing procedures
- **Migration documentation**: Complete migration plans and verification procedures
- **Improved maintainability**: Clean separation of concerns and better code organization
- **Multi-wallet support**: Complete multi-wallet dashboard with isolated data views

## New in v1.1
- By Symbol PnL tab with relative baseline, flat anchors, and sloped unrealized vs step realized combination.
- "All Trades (Realized)" option in the By Symbol dropdown (total realized PnL, relative to 0).
- Equity Used column in Positions and Closed P&L (italics), computed as `positionSizeUsd / leverage`. `positions_log.csv` now logs Equity Used.

## Data Gap Visualization

The dashboard automatically detects and visualizes missing data periods when the logger is offline:

### How It Works
- **Expected data frequency**: Every 30 minutes
- **Gap detection**: Automatically detects gaps > 30 minutes between data points
- **Visual representation**: Inserts null values to break chart lines at missing data periods
- **Real-time processing**: Gap detection happens on every chart update (refresh, filter changes)

### Example Scenarios
- **Logger offline for 24 hours**: Chart shows a 24-hour gap with broken lines
- **Server restart**: Missing data period clearly visible on next dashboard refresh
- **Network issues**: Any interruption in data collection will show as visual gaps

### Benefits
- **Clear visibility** of when the system was down or had errors
- **Accurate timeline** representation of data availability
- **No manual intervention** required - gaps appear automatically
- **Historical tracking** of system reliability and uptime

This feature helps monitor system health and ensures data integrity by making any missing data periods immediately obvious in the charts.

## Branching
- Active development branch: `master`.
- Feature branches should be created with `feature/` prefix and merged back to `master`.
- See [CLAUDE.md](CLAUDE.md) for complete branching workflow guidelines.
- Do not perform git operations unless explicitly requested by the project owner.

## By Symbol PnL & All Trades (Realized)

- The By Symbol tab has two modes:
  - Select a specific symbol to plot unrealized PnL history from `position_snapshots` (snapshots are written each time a wallet dashboard loads and by the background logger).
  - Select "All Trades (Realized)" to plot the cumulative realized PnL across all symbols using `closed_trades` stored in the database (relative baseline at 0 over the selected range).
- Important: Realized PnL must come from the exchange's Closed P&L endpoint (NOT from raw fills). Fills typically do not contain a PnL field.
- Manual sync example (replace `wallet_id` as needed):

```python
from db.database import get_session
from services.wallet_service import WalletService
from services.data_service import get_enriched_account_data
from services.sync_service import sync_closed_trades_from_fills

wallet_id = 2
client = WalletService.get_wallet_client_by_id(wallet_id, with_logging=False)
account_data = get_enriched_account_data(client)
closed_pnl = account_data.get('closed_pnl', [])

with get_session() as session:
    count = sync_closed_trades_from_fills(session, closed_pnl, wallet_id=wallet_id)
    session.commit()
print(f"Synced {count} closed P&L rows")
```

- Schema notes:
  - `position_snapshots` includes `wallet_id` and is inserted via `insert_position_snapshot` in `db/queries.py`.
  - `closed_trades` includes `strategy_id` when an assignment was active at the trade timestamp.

## Database Backup

Create a backup before migrations or bulk syncs:

```bash
cp data/wallet.db data/wallet_backup_$(date +%Y%m%d_%H%M%S).db
```
