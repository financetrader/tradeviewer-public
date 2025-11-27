# TradeViewer - Portfolio Monitor

A self-hosted portfolio monitoring dashboard for crypto traders. Track your equity, positions, and P&L across multiple wallets in one place.

### Why TradeViewer?

- **Multi-Wallet Support** - Monitor all your trading accounts from a single dashboard
- **Real-Time Sync** - Automatically fetches data from exchanges every 30 minutes
- **Historical Tracking** - See your equity growth over time with interactive charts
- **Strategy Attribution** - Tag positions with strategies to track what's actually working
- **Position Analytics** - Leverage, funding fees, time in trade, and entry/exit prices
- **Offline-First** - Data stored locally in SQLite - your data stays on your machine

### Supported Exchanges

| Exchange | Features |
|----------|----------|
| **Apex Omni** | Full support - positions, trades, equity, P&L |
| **Hyperliquid** | Read-only via public API - positions, equity |
| **Property/Assets** | Manual entry for real estate or other holdings |

### What You Can Track

- 📈 **Equity over time** - See your account growth with gap detection for offline periods
- 💰 **Open positions** - Size, leverage, entry price, unrealized P&L, funding fees
- 📊 **Closed trades** - Entry/exit prices, realized P&L, trade duration
- 🎯 **Strategy performance** - Win rate, total P&L, and trade count per strategy
- 📉 **Per-symbol breakdown** - Which pairs are making or losing money

---

## 🚀 Installation (Step-by-Step)

### What You Need First

- **Python 3.8 or higher** - [Download Python](https://www.python.org/downloads/)
- **Git** (optional) - [Download Git](https://git-scm.com/downloads)

**Not sure if you have Python?** Open a terminal and type:
```bash
python3 --version
```
If you see `Python 3.8` or higher, you're good!

---

### Step 1: Download the Code

**Option A: Using Git (Recommended)**
```bash
# Open terminal and navigate to where you want the app
cd ~

# Clone the repository
git clone https://github.com/financetrader/tradeviewer-public.git

# Go into the folder
cd tradeviewer-public
```

**Option B: Download ZIP (No Git Required)**
1. Go to https://github.com/financetrader/tradeviewer-public
2. Click the green **"Code"** button
3. Click **"Download ZIP"**
4. Extract the ZIP file to a folder (e.g., `tradeviewer-public`)
5. Open terminal and navigate to that folder:
   ```bash
   cd ~/Downloads/tradeviewer-public-main
   ```

---

### Step 2: Install Dependencies

```bash
pip install -r requirements.txt
```

**If that doesn't work, try:**
```bash
pip3 install -r requirements.txt
```

---

### Step 3: Create Configuration File

```bash
cp env.example .env
```

This creates your local configuration file. The defaults work fine for testing.

**For production**, edit `.env` and set a secure secret key:
```bash
# Generate a secret key
python3 -c "import secrets; print(secrets.token_hex(32))"

# Copy the output and paste it into .env as FLASK_SECRET_KEY=your-key-here
```

---

### Step 4: Start the Application

```bash
python app.py
```

**If that doesn't work, try:**
```bash
python3 app.py
```

You should see output like:
```
* Running on http://0.0.0.0:5000
```

---

### Step 5: Open in Browser

Open your web browser and go to: **http://localhost:5000**

🎉 **You should see the Portfolio Overview dashboard!**

---

### Step 6: Add Your First Wallet

1. Go to **http://localhost:5000/admin**
2. Click **"Add Wallet"**
3. Choose your exchange (Apex Omni or Hyperliquid)
4. Enter your credentials
5. Click **"Test"** to verify the connection
6. Click **"Add Wallet"**

Your wallet data will start syncing automatically!

---

## 📱 Quick Links

| Page | URL |
|------|-----|
| Portfolio Overview | http://localhost:5000 |
| Manage Wallets | http://localhost:5000/admin |
| Manage Strategies | http://localhost:5000/admin/strategies |
| Exchange Logs | http://localhost:5000/admin/exchange-logs |

---

## ⏹️ How to Stop

Press `Ctrl+C` in the terminal where the app is running.

---

## 🔧 Troubleshooting

**"Command not found: python"**
- Try `python3` instead of `python`
- Make sure Python is installed and in your PATH

**"No module named X"**
- Run `pip install -r requirements.txt` again
- Try `pip3` instead of `pip`

**"Address already in use"**
- Another app is using port 5000
- Stop the other app, or change the port in `app.py`

**Can't connect to exchange**
- Double-check your API credentials
- Make sure your API key has read permissions

---

## 📚 References

- [Apex Omni API Docs](https://api-docs.pro.apex.exchange/#introduction)
- [Apex Python SDK](https://github.com/ApeX-Protocol/apexpro-openapi)

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
- **Position Details**: 
  - **Funding Fee**: Cumulative funding fee since position opened (from `position_snapshots.funding_fee`)
  - **Opened Time**: Exact timestamp when position opened (from `position_snapshots.opened_at`)
  - **Time in Trade**: Duration calculated from `opened_at` to current time

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
- **Enhanced Logging**: Detailed file logging for debugging gaps and failures
  - `logs/refresh_operations.log` - Refresh operations, errors, and scheduler activity
  - `logs/exchange_traffic.log` - API call details (when logging enabled)
  - Scheduler resilience: Continues running even if individual refreshes fail

### Equity Snapshots
- Frequency: every 30 minutes (background logger) and on-demand via refresh button
- Data: total equity, unrealized PnL, available balance, realized PnL
- Source: live API balance data (fetched asynchronously, stored in database)
- Page load: Dashboard displays cached data from database immediately, then triggers async refresh in background
- When offline: no points are written → the equity chart shows visible gaps (broken lines) for missing periods
- **Logging**: All refresh operations logged to `logs/refresh_operations.log` with detailed error tracking and stack traces

### Closed Trades / Realized PnL
- Frequency: every 30 minutes (background logger) and on-demand via refresh button
- Data: all historical fills (closed trades) fetched from the exchange
- Source: exchange historical trade API (fetched asynchronously, stored in database)
- Page load: Dashboard displays cached data from database immediately, then triggers async refresh in background
- When offline: no gaps; realized PnL only changes when trades close, so charts render a flat horizontal line until the next closed trade
- Recovery: when the server restarts, the next refresh/30‑minute cycle re-syncs all historical closed trades from the exchange

## Database Schema & Table Usage

**IMPORTANT**: Understanding which table to use prevents bugs and ensures data consistency.

### Trade Tables: `closed_trades` vs `aggregated_trades`

The application uses two tables for storing trade data:

#### `closed_trades` Table
- **Purpose**: Raw individual fills from exchange APIs
- **Structure**: One row per fill/execution
- **Use Cases**: 
  - Internal processing and aggregation
  - Fallback when `aggregated_trades` doesn't exist
  - Detailed fill-level analysis
- **Key Fields**:
  - `closed_pnl` (Float): PNL for this individual fill
  - `strategy_id` (Integer): Strategy assignment at time of fill
  - `wallet_id` (Integer): Wallet that executed the trade
  - `reduce_only` (Boolean): True if closing position, False if opening

#### `aggregated_trades` Table ⭐ **PRIMARY TABLE FOR DISPLAY**
- **Purpose**: Complete trades (opening + closing leg combined)
- **Structure**: One row per complete trade round-trip
- **Use Cases**: 
  - **Wallet dashboards** (`/wallet/<id>`) - Closed P&L tab
  - **Strategy performance** calculations
  - **Recent trades** display
  - **Portfolio overview** - Recent activity
- **Key Fields**:
  - `total_pnl` (Float): **Sum of PNL from all fills** that make up this trade
  - `strategy_id` (Integer): Strategy assignment (copied from closing leg)
  - `wallet_id` (Integer): Wallet that executed the trade
  - `avg_entry_price` (Float): Weighted average entry price
  - `avg_exit_price` (Float): Weighted average exit price
  - `leverage` (Float): Leverage used for this trade
  - `equity_used` (Float): Equity allocated to this trade

**Why Two Tables?**
- Exchange APIs return individual fills (e.g., partial fills, multiple executions)
- `closed_trades` stores raw fills for accuracy
- `aggregated_trades` groups fills into logical trades for cleaner UI display
- Each aggregated trade represents one complete position open→close cycle

### Strategy Performance Calculations

**CRITICAL**: Always use `aggregated_trades` table for strategy performance.

**Function**: `get_strategy_performance()`
- **Table**: `aggregated_trades` (with fallback to `closed_trades` if table doesn't exist)
- **Fields Used**:
  - `strategy_id`: Group trades by strategy
  - `total_pnl`: Sum per strategy (already aggregated per trade)
  - `timestamp`: Filter by date range
- **Calculations**:
  - Total PnL: `SUM(total_pnl)` grouped by `strategy_id`
  - Trade Count: `COUNT(*)` grouped by `strategy_id`
  - Win Rate: `SUM(CASE WHEN total_pnl > 0 THEN 1 ELSE 0 END) / COUNT(*) * 100`
  - Avg PnL: `SUM(total_pnl) / COUNT(*)`

**Why `aggregated_trades`?**
- Each row = one complete trade (not individual fills)
- `total_pnl` already contains the sum of all fills
- Matches what wallet dashboards display
- Avoids double-counting when multiple fills make up one trade

### Symbol Performance Calculations

**CRITICAL**: Always use `aggregated_trades` table for symbol performance.

**Function**: `get_symbol_performance()`
- **Table**: `aggregated_trades` (with fallback to `closed_trades` if table doesn't exist)
- **Fields Used**:
  - `symbol`: Group trades by symbol
  - `total_pnl`: Sum per symbol (already aggregated per trade)
  - `timestamp`: Filter by date range
- **Calculations**:
  - Total PnL: `SUM(total_pnl)` grouped by `symbol`
  - Trade Count: `COUNT(*)` grouped by `symbol`
  - Win Rate: `SUM(CASE WHEN total_pnl > 0 THEN 1 ELSE 0 END) / COUNT(*) * 100`
  - Avg PnL: `SUM(total_pnl) / COUNT(*)`

**Why `aggregated_trades`?**
- Each row = one complete trade (not individual fills)
- `total_pnl` already contains the sum of all fills
- Matches what wallet dashboards display
- Avoids double-counting when multiple fills make up one trade
- Same pattern as strategy performance for consistency

### Wallet Win Rate Calculations

**CRITICAL**: Always use `aggregated_trades` table for wallet win rate.

**Function**: `get_win_rates_by_wallet()`
- **Table**: `aggregated_trades` (no fallback - table always exists)
- **Fields Used**:
  - `wallet_id`: Group trades by wallet
  - `total_pnl`: P&L per complete trade (already aggregated)
  - `timestamp`: Filter by date range
- **Calculations**:
  - Win Rate: `SUM(CASE WHEN total_pnl > 0 THEN 1 ELSE 0 END) / COUNT(*) * 100` grouped by `wallet_id`
  - Counts complete trades, not individual fills
- **Parameters**:
  - `zero_is_loss`: If `True`, count zero PnL as a loss (default). If `False`, count zero PnL as a win.

**Why `aggregated_trades`?**
- Each row = one complete trade (not individual fills)
- `total_pnl` already contains the sum of all fills
- Matches what wallet dashboards display
- Avoids double-counting when multiple fills make up one trade
- Consistent with strategy and symbol performance calculations

### Other Key Tables

#### `equity_snapshots`
- **Purpose**: Historical equity and balance data
- **Frequency**: Every 30 minutes
- **Key Fields**: `total_equity`, `unrealized_pnl`, `available_balance`, `realized_pnl`, `initial_margin`

#### `position_snapshots`
- **Purpose**: Historical open position data
- **Frequency**: Every 30 minutes (when positions are open)
- **Key Fields**: 
  - `size` (Float): Position size
  - `entry_price` (Float): Average entry price
  - `current_price` (Float): Current market price
  - `unrealized_pnl` (Float): Unrealized profit/loss
  - `leverage` (Float): Leverage used (calculated once at position open)
  - `equity_used` (Float): Equity/margin allocated to position
  - `funding_fee` (Float): **Cumulative funding fee since position opened** (Hyperliquid: `cumFunding.sinceOpen` from API)
  - `opened_at` (DateTime): **Timestamp when position was first opened** (used for "Opened" column and time-in-trade calculation)
  - `strategy_name` (String): Strategy assigned to this position
  - `calculation_method` (String): Method used to calculate leverage (`margin_delta`, `margin_rate`, or `unknown`)
- **Leverage Storage**: Leverage is calculated ONCE when position first opens and stored in `leverage` field. The system checks the FIRST snapshot - if it has valid leverage, that value is used for ALL future snapshots (not recalculated) to ensure consistency.
- **Funding Fee Storage**: 
  - Extracted from exchange API on each refresh (Hyperliquid: `cumFunding.sinceOpen`)
  - Stored in `funding_fee` field as cumulative total since position opened
  - Updated on every snapshot refresh (every 30 minutes)
  - Displayed in wallet dashboard "Positions" table with color coding (red for negative, green for positive)
- **Opened Time Display**:
  - `opened_at` field stores the exact timestamp when position was first opened
  - Displayed in wallet dashboard "Opened" column as `YYYY-MM-DD HH:MM:SS`
  - Time-in-trade duration calculated from `opened_at` to current time, displayed below timestamp (e.g., "17h 31m")
- **Position ID Tracking**:
  - `position_id` (Integer): Links snapshot to a position lifecycle in the `positions` table
  - All snapshots for the same position share the same `position_id`
  - When a position closes and reopens, it gets a NEW `position_id`

#### `positions`
- **Purpose**: Track position lifecycles with unique IDs
- **Key Fields**:
  - `id` (Integer): Unique position ID (displayed as "#1", "#2", etc.)
  - `wallet_id` (Integer): Which wallet owns this position
  - `symbol` (String): Trading pair (e.g., "BTC-USDT")
  - `side` (String): "LONG" or "SHORT"
  - `opened_at` (DateTime): **Authoritative timestamp** for when position opened
  - `closed_at` (DateTime): When position closed (NULL if still open)
  - `entry_price`, `exit_price`, `realized_pnl`: Trade details
- **Lifecycle Tracking**:
  - Open positions: `closed_at IS NULL`
  - Closed positions: `closed_at IS NOT NULL`
  - Side flips: LONG closing + SHORT opening = two separate positions
  - Partial closes: Same `position_id` until fully closed (untested)

#### `strategies` & `strategy_assignments`
- **Purpose**: Strategy catalog and wallet+symbol assignments
- **Key Fields**: `name`, `description`, `start_at`, `end_at`, `wallet_id`, `symbol`

### Query Functions Reference

| Function | Table Used | Purpose |
|----------|-----------|---------|
| `get_aggregated_closed_trades()` | `aggregated_trades` | Wallet dashboard Closed P&L tab |
| `get_recent_trades()` | `aggregated_trades` | Portfolio overview Recent Trades |
| `get_open_positions()` | `position_snapshots` + `positions` | Wallet dashboard Positions table (includes `position_id`, `funding_fee`, `opened_at`, `timeInTrade`) |
| `get_strategy_performance()` | `aggregated_trades` | Strategy Performance card |
| `get_symbol_performance()` | `aggregated_trades` | Top Symbols by PnL card |
| `get_closed_trades()` | `closed_trades` | Fallback, detailed fill analysis |
| `get_realized_pnl_by_wallet()` | `closed_trades` | Wallet-level PnL sums (uses fills) |

**Note**: There's a known inconsistency where `get_realized_pnl_by_wallet()` uses `closed_trades` (individual fills) while display uses `aggregated_trades` (complete trades). This may cause slight discrepancies in totals.

### Leverage Calculation & Storage

**How Leverage is Calculated:**
- **Hyperliquid**: Uses margin delta method - tracks `totalMarginUsed` changes when position opens
- **Apex**: Uses margin delta method - tracks `initialMargin` changes when position opens
- Leverage = `position_size_usd / equity_used` where `equity_used` is the margin delta

**When Leverage is Calculated:**
- **CRITICAL**: Leverage is calculated ONCE when position first opens, then preserved for all future snapshots
- Checks the FIRST snapshot (when position was first opened) - if it has leverage, uses it for ALL future snapshots
- Only calculates if the FIRST snapshot doesn't have leverage (or has invalid leverage >100x)
- **Preserved if valid**: If first snapshot has valid leverage, it's returned from database (not recalculated) for all subsequent refreshes

**Storage:**
- Stored in `position_snapshots.leverage` field
- Also stored in `closed_trades.leverage` and `aggregated_trades.leverage` when trades close
- `calculation_method` field indicates how leverage was calculated (`margin_delta`, `margin_rate`, or `unknown`)

**Display:**
- Wallet dashboard reads leverage from `position_snapshots` entry
- If latest snapshot has `leverage=None`, the system looks for the most recent snapshot with valid leverage (≤100x) and uses that
- If leverage is `None` in database, displays as "-" (empty)
- Leverage is calculated once when position first opens (stored in first snapshot), then preserved for all future snapshots

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

