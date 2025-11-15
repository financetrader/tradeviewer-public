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
- **Cached Data Display**: Current positions, balances, and open orders from database
- **Async Refresh**: Automatic refresh on page load and manual refresh button
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

## Data Logging & Synchronization

The application uses a database-centric, asynchronous refresh architecture. Dashboards read from the database immediately, then refresh data in the background.

### Data Refresh Architecture

**How It Works:**
1. **Page Load**: Dashboard routes read all data from the database (no blocking API calls)
2. **Async Refresh**: JavaScript automatically triggers refresh in background on page load
3. **Manual Refresh**: Each dashboard has a refresh button showing last update time
4. **Background Scheduler**: All wallets refresh every 30 minutes automatically
5. **Centralized Service**: All refresh logic in `services/wallet_refresh.py`

**Refresh Endpoints:**
- `POST /api/wallet/<id>/refresh` - Refresh single wallet
- `POST /api/wallets/refresh-all` - Refresh all wallets (from portfolio overview)

**Benefits:**
- Fast page loads (no waiting for API calls)
- Non-blocking UI (refresh happens in background)
- Always shows data (even if API is slow/down)
- Manual control (refresh button on each dashboard)

### Equity Snapshots
- Frequency: every 30 minutes (background logger) and on-demand via refresh button
- Data: total equity, unrealized PnL, available balance, realized PnL
- Source: live API balance data (fetched asynchronously, stored in database)
- Page load: Dashboard displays cached data from database immediately, then triggers async refresh in background
- When offline: no points are written → the equity chart shows visible gaps (broken lines) for missing periods

### Closed Trades / Realized PnL
- Frequency: every 30 minutes (background logger) and on-demand via refresh button
- Data: all historical fills (closed trades) fetched from the exchange
- Source: exchange historical trade API (fetched asynchronously, stored in database)
- Page load: Dashboard displays cached data from database immediately, then triggers async refresh in background
- When offline: no gaps; realized PnL only changes when trades close, so charts render a flat horizontal line until the next closed trade
- Recovery: when the server restarts, the next refresh/30‑minute cycle re-syncs all historical closed trades from the exchange

### Background Logger

The background logger runs automatically when you start the application. It:
- Refreshes all wallets every 30 minutes using `refresh_wallet_data()` (:00 and :30 past each hour)
- Writes equity snapshots and position data to database
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

### Strategy Management System
- **Strategy catalog**: Define and name trading strategies
- **Wallet+pair assignments**: Map strategies to specific symbols per wallet
- **Time-bounded tracking**: Start/end timestamps for performance attribution
- **Active management**: End assignments on-demand via UI

### Multi-Wallet Architecture
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
- **Multi-wallet support**: Complete multi-wallet dashboard with isolated data views
- **Portfolio overview**: Aggregate view across all connected wallets
- **Strategy management**: Track trading strategies and performance attribution

## New in v1.1
- By Symbol PnL tab with relative baseline, flat anchors, and sloped unrealized vs step realized combination.
- "All Trades (Realized)" option in the By Symbol dropdown (total realized PnL, relative to 0).
- Equity Used column in Positions and Closed P&L displays position sizing information.

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

