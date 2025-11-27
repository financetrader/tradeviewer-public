# Database Schema Map

**Complete reference guide for all database tables, fields, relationships, and data reuse opportunities.**

---

## 📋 Quick Reference

### Tables Overview

| Table | Purpose | Primary Key | Key Relationships |
|-------|---------|-------------|-------------------|
| `wallet_configs` | Wallet/exchange configurations | `id` | → All snapshot/trade tables |
| `equity_snapshots` | Historical equity & P&L snapshots | `id` | ← `wallet_configs` |
| `position_snapshots` | Historical position snapshots | `id` | ← `wallet_configs`, `strategies` |
| `closed_trades` | Raw individual fills/executions | `id` | ← `wallet_configs`, `strategies` |
| `aggregated_trades` | Complete trades (opening + closing) | `id` | ← `wallet_configs`, `strategies` |
| `strategies` | Strategy catalog/master list | `id` | → `strategy_assignments`, snapshots, trades |
| `strategy_assignments` | Time-bounded strategy assignments | `id` | ← `wallet_configs`, `strategies` |

### Relationship Diagram

```
┌─────────────────┐
│ wallet_configs  │
│   (id, name)    │
└────────┬────────┘
         │
         ├──────────────────┬──────────────────┬──────────────────┐
         │                  │                  │                  │
         ▼                  ▼                  ▼                  ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│equity_snapshots │ │position_snapshots│ │ closed_trades   │ │aggregated_trades│
│  (wallet_id)    │ │  (wallet_id)    │ │  (wallet_id)    │ │  (wallet_id)    │
└─────────────────┘ └────────┬────────┘ └─────────────────┘ └─────────────────┘
                             │
                             │ strategy_id
                             │
                             ▼
                    ┌─────────────────┐
                    │   strategies    │
                    │   (id, name)   │
                    └────────┬────────┘
                             │
                             │ strategy_id
                             │
                             ▼
                    ┌─────────────────┐
                    │strategy_assign- │
                    │    ments        │
                    │ (wallet_id,     │
                    │  strategy_id)   │
                    └─────────────────┘
```

---

## 📊 Table Details

### 1. `wallet_configs`

**Purpose**: Stores wallet/exchange account configurations and encrypted credentials.

**When to use**: 
- Lookup wallet information by ID
- Get wallet address for linking snapshots
- Check wallet connection status
- Access encrypted API credentials (via properties)

**Fields**:

| Field | Type | Null | Default | Description |
|-------|------|------|---------|-------------|
| `id` | `Integer` | NO | auto | **Primary key** - Unique identifier for this wallet configuration. Auto-incremented integer. Example: `1`, `2`, `3` |
| `name` | `String(255)` | NO | - | **User-friendly wallet name** - Display name shown in UI. Example: `"My Apex Account"`, `"Hyperliquid Main"`. Used for wallet selection and display. |
| `api_name` | `String(255)` | YES | - | **Optional friendly name for API credential** - Additional label for the API credential itself, separate from wallet name. Useful when one API key is used for multiple wallets. Example: `"Production Key"`, `"Test Account Key"` |
| `provider` | `String(50)` | NO | - | **Exchange/provider identifier** - Which exchange or platform this wallet connects to. Valid values: `'apex_omni'` (Apex Protocol), `'hyperliquid'` (Hyperliquid exchange), `'property'` (manual property tracking). Determines which API client to use. |
| `wallet_type` | `String(50)` | NO | - | **Asset type category** - Broad category of assets tracked. Valid values: `'crypto'` (cryptocurrency trading), `'stocks'` (stock trading), `'property'` (real estate or other property assets). Used for filtering and categorization. |
| `_api_key_encrypted` | `String(1000)` | YES | - | **Encrypted API key** - Exchange API key encrypted at rest using Fernet encryption. Stored encrypted in database, automatically decrypted when accessed via `wallet.api_key` property. Never access `_api_key_encrypted` directly. Example encrypted value: `"gAAAAABh..."` |
| `_api_secret_encrypted` | `String(1000)` | YES | - | **Encrypted API secret** - Exchange API secret key, encrypted at rest. Required for most exchanges. Automatically decrypted via `wallet.api_secret` property. Used for API authentication. |
| `_api_passphrase_encrypted` | `String(1000)` | YES | - | **Encrypted API passphrase** - Some exchanges (like Coinbase Pro) require a passphrase in addition to key/secret. Encrypted at rest, decrypted via `wallet.api_passphrase` property. Usually NULL for most exchanges. |
| `wallet_address` | `String(500)` | YES | - | **Wallet address/identifier** - The actual wallet address or account identifier from the exchange. Used as primary key for linking snapshots and trades. Example: `"0x1234..."` (Ethereum address), `"apex_account_123"`. **Preferred over `wallet_id` for new code** - use this to link equity/position snapshots. |
| `asset_name` | `String(255)` | YES | - | **Property asset name** - For property-type wallets, the name of the asset being tracked. Example: `"Downtown Office Building"`, `"Rental Property #1"`. NULL for crypto/stock wallets. |
| `asset_value` | `Float` | YES | - | **Property asset value** - For property-type wallets, the current estimated value of the asset in the base currency. Example: `250000.00` (for $250k property). NULL for crypto/stock wallets. |
| `asset_currency` | `String(10)` | YES | - | **Property asset currency** - Currency code for property value. Example: `"USD"`, `"EUR"`. NULL for crypto/stock wallets. |
| `status` | `String(50)` | YES | `'not_tested'` | **Connection status** - Current state of wallet connection. Values: `'not_tested'` (never tested, default), `'connected'` (successfully connected and working), `'error'` (connection failed, check `error_message`). Used to filter active wallets and show connection status in UI. |
| `last_test` | `DateTime` | YES | - | **Last connection test timestamp** - When the wallet connection was last tested. Updated when user clicks "Test Connection" button. Used to show "Last tested: 2 hours ago" in UI. NULL if never tested. |
| `error_message` | `String(500)` | YES | - | **Error message** - If `status` is `'error'`, this contains the error message explaining why connection failed. Example: `"Invalid API key"`, `"Connection timeout"`. NULL if status is not `'error'`. Displayed to user when connection fails. |
| `created_at` | `DateTime` | NO | `utcnow()` | **Record creation timestamp** - When this wallet configuration was first created in the database. Used for sorting and filtering wallets by creation date. Format: UTC datetime. |
| `updated_at` | `DateTime` | NO | `utcnow()` | **Last update timestamp** - Automatically updated whenever any field in this record changes. Used to track when wallet config was last modified. Auto-updated by SQLAlchemy. |

**Special Properties**:
- `api_key`, `api_secret`, `api_passphrase`: Properties that automatically encrypt/decrypt credentials
- Access via `wallet.api_key` (not `wallet._api_key_encrypted`)

**Indexes**: None (primary key only)

**Notes**:
- ✅ **Use `wallet_address`** to link snapshots (preferred over `wallet_id` for new code)
- Property wallets use `asset_name`, `asset_value`, `asset_currency`
- Credentials are encrypted at rest using Fernet encryption

---

### 2. `equity_snapshots`

**Purpose**: Historical equity and P&L snapshots per wallet (time series data).

**When to use**:
- Display equity charts over time
- Calculate portfolio totals
- Track account balance changes
- Analyze equity trends

**Fields**:

| Field | Type | Null | Default | Description |
|-------|------|------|---------|-------------|
| `id` | `Integer` | NO | auto | **Primary key** - Unique identifier for this equity snapshot. Auto-incremented integer. Used internally for record identification. |
| `wallet_id` | `Integer` | YES | - | **Legacy wallet identifier** - Links to `wallet_configs.id`. Maintained for backward compatibility with older code. **For new code, use `wallet_address` instead.** Example: `1`, `2`, `3` |
| `wallet_address` | `String(500)` | YES | - | **Primary wallet identifier** - The wallet address from `wallet_configs.wallet_address`. Used to link snapshots to wallets. **Preferred identifier for new code.** Example: `"0x1234..."`, `"apex_account_123"` |
| `timestamp` | `DateTime` | NO | - | **Snapshot timestamp** - When this equity snapshot was taken. Typically every 5 minutes or on manual refresh. Used for time-series charts and historical analysis. Format: UTC datetime. Example: `2025-01-15 14:30:00` |
| `total_equity` | `Float` | NO | - | **Total account equity** - Complete account value including all positions, cash, and unrealized P&L. Formula: `available_balance + unrealized_pnl + margin_used`. This is the main equity value shown in charts. Example: `10000.50` (for $10,000.50 total equity) |
| `unrealized_pnl` | `Float` | NO | - | **Unrealized P&L from open positions** - Profit/loss from currently open positions that hasn't been realized yet. Changes as market prices move. Becomes `realized_pnl` when positions close. Can be negative. Example: `250.75` (profit), `-150.25` (loss) |
| `available_balance` | `Float` | NO | - | **Available balance for trading** - Cash balance available to open new positions. Excludes margin currently used by open positions. Formula: `total_equity - margin_used - unrealized_pnl`. Example: `5000.00` (for $5,000 available) |
| `realized_pnl` | `Float` | NO | - | **Cumulative realized P&L** - Total profit/loss from all closed trades since account creation. This is the sum of all `closed_pnl` values from `closed_trades` or `total_pnl` from `aggregated_trades`. Only increases when trades close. Example: `1250.50` (for $1,250.50 total realized profit) |
| `initial_margin` | `Float` | YES | - | **Total margin used (Apex only)** - Total initial margin currently used across all open positions. Apex-specific field. NULL for Hyperliquid and other exchanges. Used for margin calculations and risk analysis. Example: `2000.00` (for $2,000 margin used) |
| `created_at` | `DateTime` | NO | `utcnow()` | **Record creation timestamp** - When this snapshot record was inserted into the database. Usually very close to `timestamp` but may differ slightly due to processing time. Used for debugging and data integrity checks. |

**Indexes**:
- `idx_equity_wallet_timestamp` on (`wallet_address`, `timestamp`)
- `idx_equity_wallet_id_timestamp` on (`wallet_id`, `timestamp`)

**Data Flow**:
- Created every **5 minutes** (or on manual refresh)
- Fetched from exchange account balance API
- Used for equity charts and portfolio totals

**Notes**:
- ✅ **Use `wallet_address`** for new queries (legacy code may use `wallet_id`)
- `initial_margin` is Apex-specific (total margin across all positions)
- Missing snapshots create gaps in equity charts

**Example Query**:
```python
# Get latest equity for a wallet
latest = session.query(EquitySnapshot).filter(
    EquitySnapshot.wallet_address == wallet_address
).order_by(EquitySnapshot.timestamp.desc()).first()
```

---

### 3. `position_snapshots`

**Purpose**: Historical position snapshots with metrics per symbol (time series data).

**When to use**:
- Display open positions
- Track position history
- Calculate position metrics (leverage, P&L)
- Analyze position lifecycle

**Fields**:

| Field | Type | Null | Default | Description |
|-------|------|------|---------|-------------|
| `id` | `Integer` | NO | auto | **Primary key** - Unique identifier for this position snapshot. Auto-incremented integer. Used internally for record identification. |
| `wallet_id` | `Integer` | YES | - | **Legacy wallet identifier** - Links to `wallet_configs.id`. Maintained for backward compatibility. **For new code, use `wallet_address` instead.** Example: `1`, `2`, `3` |
| `wallet_address` | `String(500)` | YES | - | **Primary wallet identifier** - The wallet address from `wallet_configs.wallet_address`. Used to link position snapshots to wallets. **Preferred identifier for new code.** Example: `"0x1234..."`, `"apex_account_123"` |
| `position_id` | `Integer` | YES | - | **Foreign key to positions** - Links to `positions.id`. Identifies which position lifecycle this snapshot belongs to. All snapshots for the same position share the same `position_id`. When a position closes and reopens, a new `position_id` is assigned. NULL for legacy data not yet backfilled. |
| `timestamp` | `DateTime` | NO | - | **Snapshot timestamp** - When this position snapshot was taken. Typically every 5 minutes or on manual refresh. Used for time-series analysis and position history. Format: UTC datetime. Example: `2025-01-15 14:30:00` |
| `symbol` | `String(50)` | NO | - | **Trading symbol** - The trading pair or instrument identifier. Format varies by exchange. Examples: `"BTC/USD"`, `"ETH-PERP"`, `"SOL/USD"`. Used to identify which asset this position is for. |
| `side` | `String(10)` | NO | - | **Position side** - Direction of the position. Values: `'LONG'` (betting price goes up, buying), `'SHORT'` (betting price goes down, selling). Determines P&L calculation direction. |
| `size` | `Float` | NO | - | **Position size (absolute value)** - The size of the position in the base asset units. Always stored as positive number regardless of side. Example: `0.5` (for 0.5 BTC), `100.0` (for 100 SOL). Zero-size positions are not stored (position is closed). |
| `entry_price` | `Float` | NO | - | **Average entry price** - The weighted average price at which the position was opened. Used to calculate unrealized P&L. Example: `45000.00` (for $45,000 entry price). May change if position is added to (averaged up/down). |
| `current_price` | `Float` | YES | - | **Current market price** - The current market price of the asset at snapshot time. Used to calculate `position_size_usd` and `unrealized_pnl`. Can be NULL if price unavailable. Example: `46000.00` (for $46,000 current price). |
| `position_size_usd` | `Float` | NO | - | **Position size in USD** - The dollar value of the position. Calculated as `size * current_price`. Used for position sizing and risk analysis. Example: `23000.00` (for $23,000 position value). |
| `leverage` | `Float` | YES | - | **Calculated leverage** - The leverage multiplier used for this position. Calculated **once** when position first opens, then **preserved** for all future snapshots. Example: `5.0` (for 5x leverage), `10.0` (for 10x leverage). NULL if calculation failed or unavailable. |
| `unrealized_pnl` | `Float` | YES | - | **Unrealized P&L for this position** - Current profit/loss for this specific position that hasn't been realized yet. Formula: `(current_price - entry_price) * size * side_multiplier`. Can be negative (loss). Example: `500.00` (profit), `-250.00` (loss). |
| `funding_fee` | `Float` | YES | - | **Cumulative funding fee since position opened** - Total funding fees paid/received since position opened. Perpetual futures contracts charge funding fees periodically. Can be positive (received) or negative (paid). Example: `-12.50` (paid $12.50 in fees), `5.25` (received $5.25). |
| `equity_used` | `Float` | YES | - | **Equity/margin used for this position** - How much equity (collateral) is locked up for this position. Calculated from leverage and position size. Formula: `position_size_usd / leverage`. Used for margin calculations. Example: `2300.00` (for $2,300 equity used on 10x leverage). |
| `strategy_id` | `Integer` | YES | - | **Foreign key to strategies** - Which strategy was active when this snapshot was taken. Links to `strategies.id`. NULL if no strategy assigned. Used for strategy performance analysis. Populated from `strategy_assignments` at insert time. |
| `raw_data` | `JSON` | YES | - | **Complete API response** - Stores the entire raw JSON response from the exchange API for this position. Useful for debugging, data recovery, and extracting additional fields in the future. Format: JSON object with all API fields. Example: `{"symbol": "BTC/USD", "size": 0.5, ...}` |
| `initial_margin_at_open` | `Float` | YES | - | **Total margin when position opened** - The total initial margin that was used when this position first opened. Preserved for historical analysis. Apex-specific. Example: `2000.00` (for $2,000 initial margin). |
| `calculation_method` | `String(20)` | YES | - | **Leverage calculation method** - Records how the leverage was calculated. Values: `'margin_delta'` (calculated from margin changes), `'margin_rate'` (calculated from margin rate), `'unknown'` (calculation failed or unavailable). Used for debugging and understanding calculation accuracy. |
| `created_at` | `DateTime` | NO | `utcnow()` | **Record creation timestamp** - When this snapshot record was inserted into the database. Usually very close to `timestamp` but may differ slightly due to processing time. Used for debugging and data integrity checks. |
| `opened_at` | `DateTime` | YES | - | **When position was first opened** - Calculated from the first snapshot where `size > 0`. Tracks when position lifecycle began. Used for position duration analysis and lifetime metrics. Example: `2025-01-15 10:00:00` (position opened at 10 AM). NULL if position was already open when tracking started. |

**Indexes**:
- `idx_position_wallet_symbol_timestamp` on (`wallet_address`, `symbol`, `timestamp`)
- `idx_position_wallet_timestamp` on (`wallet_address`, `timestamp`)
- `idx_position_wallet_id_symbol_timestamp` on (`wallet_id`, `symbol`, `timestamp`)
- `idx_position_wallet_id_timestamp` on (`wallet_id`, `timestamp`)
- `idx_position_symbol_timestamp` on (`symbol`, `timestamp`)
- `idx_position_timestamp` on (`timestamp`)
- `idx_position_snapshot_position_id` on (`position_id`) - For joining to positions table

**Data Flow**:
- Created every **5 minutes** (or on manual refresh) for each **open position**
- Zero-size positions are **not stored**
- Used for position display and historical analysis

**Key Behaviors**:
- ✅ **`leverage`**: Calculated **once** when position opens, then **preserved** for all future snapshots
- ✅ **`opened_at`**: Tracks when position first opened (for position lifetime analysis)
- ✅ **`raw_data`**: Stores complete API response (useful for debugging and data recovery)
- ✅ **`calculation_method`**: Records how leverage was calculated (`margin_delta`, `margin_rate`, or `unknown`)

**Example Query**:
```python
# Get latest open positions for a wallet
positions = session.query(PositionSnapshot).filter(
    PositionSnapshot.wallet_address == wallet_address
).order_by(PositionSnapshot.timestamp.desc()).all()

# Get position history for a specific symbol
history = session.query(PositionSnapshot).filter(
    PositionSnapshot.wallet_address == wallet_address,
    PositionSnapshot.symbol == 'BTC/USD'
).order_by(PositionSnapshot.timestamp).all()
```

---

### 4. `positions`

**Purpose**: Track position lifecycles with unique IDs. Each record represents one open→close cycle.

**When to use**:
- Link multiple position snapshots to the same position lifecycle
- Track when positions were opened and closed
- Query historical positions (both open and closed)
- Get authoritative `opened_at` timestamp for time-in-trade calculations

**Fields**:

| Field | Type | Null | Default | Description |
|-------|------|------|---------|-------------|
| `id` | `Integer` | NO | auto | **Primary key** - Unique position ID. Referenced by `position_snapshots.position_id`. Displayed in UI as "#1", "#2", etc. |
| `wallet_id` | `Integer` | NO | - | **Foreign key to wallet_configs** - Which wallet owns this position. |
| `symbol` | `String(50)` | NO | - | **Trading symbol** - The trading pair. Example: `"BTC-USDT"`, `"SOL-USDT"`. |
| `side` | `String(10)` | NO | - | **Position side** - `"LONG"` or `"SHORT"`. |
| `opened_at` | `DateTime` | NO | - | **When position was first opened** - Authoritative timestamp for this position lifecycle. Used for time-in-trade calculation. |
| `closed_at` | `DateTime` | YES | - | **When position was fully closed** - NULL if position is still open. Set when a closing trade is detected. |
| `entry_price` | `Float` | YES | - | **Entry price when opened** - Price at which position was opened. |
| `exit_price` | `Float` | YES | - | **Exit price when closed** - Price at which position was closed. NULL if still open. |
| `realized_pnl` | `Float` | YES | - | **Final realized P&L** - Total profit/loss when position closed. NULL if still open. |
| `created_at` | `DateTime` | NO | `utcnow()` | **Record creation timestamp** |

**Indexes**:
- `idx_position_wallet_symbol_side` on (`wallet_id`, `symbol`, `side`)
- `idx_position_wallet_open` on (`wallet_id`, `closed_at`) - For finding open positions

**Key Behaviors**:
- ✅ **One position per lifecycle**: When a position closes and reopens, a NEW position record is created
- ✅ **Open positions**: `closed_at IS NULL` means position is still open
- ✅ **Side flips**: LONG closing + SHORT opening = two separate position records
- ⚠️ **Partial closes**: Position ID stays same during partial closes (not tested extensively)

**Example Query**:
```python
# Get all open positions for a wallet
open_positions = session.query(Position).filter(
    Position.wallet_id == wallet_id,
    Position.closed_at.is_(None)
).all()

# Get position history (all positions ever opened)
all_positions = session.query(Position).filter(
    Position.wallet_id == wallet_id
).order_by(Position.opened_at.desc()).all()
```

---

### 5. `closed_trades`

**Purpose**: Raw individual fills/executions from exchange APIs.

**When to use**:
- Internal processing and aggregation
- Fallback when `aggregated_trades` doesn't exist
- Detailed fill-level analysis
- Debugging trade execution issues

**Fields**:

| Field | Type | Null | Default | Description |
|-------|------|------|---------|-------------|
| `id` | `Integer` | NO | auto | **Primary key** - Unique identifier for this closed trade fill. Auto-incremented integer. Used internally for record identification. |
| `wallet_id` | `Integer` | YES | - | **Legacy wallet identifier** - Links to `wallet_configs.id`. Maintained for backward compatibility. **For new code, use `wallet_address` instead.** Example: `1`, `2`, `3` |
| `wallet_address` | `String(500)` | YES | - | **Primary wallet identifier** - The wallet address from `wallet_configs.wallet_address`. Used to link trades to wallets. **Preferred identifier for new code.** Example: `"0x1234..."`, `"apex_account_123"` |
| `timestamp` | `DateTime` | NO | - | **Trade execution timestamp** - When this fill/execution occurred on the exchange. Used for chronological ordering and time-series analysis. Format: UTC datetime. Example: `2025-01-15 14:30:00` |
| `side` | `String(10)` | NO | - | **Position side** - The side of the position this fill relates to. Values: `'LONG'` (long position), `'SHORT'` (short position). Used to determine trade direction. |
| `symbol` | `String(50)` | NO | - | **Trading symbol** - The trading pair or instrument identifier. Must match format used in `position_snapshots`. Examples: `"BTC/USD"`, `"ETH-PERP"`, `"SOL/USD"`. |
| `size` | `Float` | NO | - | **Trade size** - The size of this fill in base asset units. Always positive. Example: `0.5` (for 0.5 BTC filled), `100.0` (for 100 SOL filled). Multiple fills from same order create multiple rows. |
| `entry_price` | `Float` | NO | - | **Entry price for this fill** - The price at which this fill executed when opening the position. Used for P&L calculation. Example: `45000.00` (for $45,000 entry). |
| `exit_price` | `Float` | NO | - | **Exit price for this fill** - The price at which this fill executed when closing the position. Used for P&L calculation. Example: `46000.00` (for $46,000 exit). |
| `trade_type` | `String(10)` | NO | - | **Trade type** - The action taken. Values: `'BUY'` (buying/longing), `'SELL'` (selling/shorting). Determines if this is opening or closing a position. |
| `closed_pnl` | `Float` | NO | - | **P&L for this individual fill** - Profit/loss realized from this specific fill. Formula: `(exit_price - entry_price) * size * side_multiplier - fees`. Can be negative (loss). Example: `500.00` (profit), `-250.00` (loss). Sum of all fills makes up total trade P&L. |
| `close_fee` | `Float` | YES | - | **Fee paid on close** - Trading fee charged when closing this fill. Usually a percentage of trade value. Example: `2.50` (for $2.50 fee). NULL if fee not available. |
| `open_fee` | `Float` | YES | - | **Fee paid on open** - Trading fee charged when opening this fill. Usually a percentage of trade value. Example: `2.50` (for $2.50 fee). NULL if fee not available. |
| `liquidate_fee` | `Float` | YES | - | **Liquidation fee (if applicable)** - Additional fee charged if position was liquidated (forced closed due to margin call). Usually higher than normal fees. NULL if not a liquidation. Example: `50.00` (for $50 liquidation fee). |
| `exit_type` | `String(20)` | YES | - | **Exit type** - How the position was closed. Values: `'Trade'` (normal trade execution), `'Liquidation'` (forced closure due to margin call). Used to identify liquidations in analysis. |
| `equity_used` | `Float` | YES | - | **Equity used for this trade** - How much equity (collateral) was allocated to this trade. Estimated from position snapshots. Used for risk analysis. Example: `2300.00` (for $2,300 equity used). |
| `leverage` | `Float` | YES | - | **Estimated leverage from position snapshots** - The leverage multiplier used for this trade. Estimated by looking up position snapshots at trade time. Example: `5.0` (for 5x leverage), `10.0` (for 10x leverage). NULL if unavailable. |
| `strategy_id` | `Integer` | YES | - | **Foreign key to strategies** - Which strategy was active when this trade executed. Links to `strategies.id`. NULL if no strategy assigned. Used for strategy performance analysis. Populated from `strategy_assignments` at insert time. |
| `reduce_only` | `Boolean` | YES | - | **Position direction indicator** - Indicates whether this fill closes or opens a position. Values: `True` (closes/reduces position), `False` (opens/increases position), `None` (unknown). Used in aggregation logic to group fills into complete trades. |
| `created_at` | `DateTime` | NO | `utcnow()` | **Record creation timestamp** - When this trade record was inserted into the database. Usually very close to `timestamp` but may differ due to processing time. Used for debugging and data integrity checks. |

**Indexes**:
- `idx_closed_wallet_symbol_timestamp` on (`wallet_address`, `symbol`, `timestamp`)
- `idx_closed_wallet_timestamp` on (`wallet_address`, `timestamp`)
- `idx_closed_wallet_id_symbol_timestamp` on (`wallet_id`, `symbol`, `timestamp`)
- `idx_closed_wallet_id_timestamp` on (`wallet_id`, `timestamp`)
- `idx_closed_symbol_timestamp` on (`symbol`, `timestamp`)
- `idx_closed_timestamp` on (`timestamp`)

**Data Flow**:
- Fetched every **30 minutes** from exchange historical trade APIs
- One row per fill/execution
- Used internally to populate `aggregated_trades`

**Notes**:
- ⚠️ **Not for UI display** - use `aggregated_trades` instead
- `reduce_only` indicates if trade closes or opens a position
- Multiple fills from same order create multiple rows

**Example Query**:
```python
# Get all fills for aggregation
fills = session.query(ClosedTrade).filter(
    ClosedTrade.wallet_address == wallet_address
).order_by(ClosedTrade.timestamp).all()
```

---

### 6. `aggregated_trades` ⭐ **PRIMARY TABLE FOR DISPLAY**

**Purpose**: Complete trades (opening + closing leg combined) for UI display.

**When to use**:
- **Wallet dashboards** (`/wallet/<id>`) - Closed P&L tab
- **Strategy performance** calculations
- **Recent trades** display
- **Portfolio overview** - Recent activity

**Fields**:

| Field | Type | Null | Default | Description |
|-------|------|------|---------|-------------|
| `id` | `Integer` | NO | auto | **Primary key** - Unique identifier for this aggregated trade. Auto-incremented integer. Used internally for record identification. |
| `wallet_id` | `Integer` | YES | - | **Wallet identifier** - Links to `wallet_configs.id`. Used to filter trades by wallet. Example: `1`, `2`, `3`. Note: This table uses `wallet_id` (not `wallet_address`) for linking. |
| `timestamp` | `DateTime` | NO | - | **Trade timestamp** - When the trade was executed (typically the closing timestamp). Used for chronological ordering and time-series analysis. Format: UTC datetime. Example: `2025-01-15 14:30:00` |
| `symbol` | `String(50)` | NO | - | **Trading symbol** - The trading pair or instrument identifier. Must match format used in other tables. Examples: `"BTC/USD"`, `"ETH-PERP"`, `"SOL/USD"`. |
| `side` | `String(10)` | NO | - | **Trade side** - The side of the trade. Values: `'buy'` (buying/longing), `'sell'` (selling/shorting). Lowercase format (different from `closed_trades` which uses uppercase). |
| `size` | `Float` | NO | - | **Total size from all fills** - The sum of all fill sizes that make up this complete trade. Example: If order had 3 fills of 0.1, 0.2, 0.2 BTC, this would be `0.5`. Used for position sizing analysis. |
| `avg_entry_price` | `Float` | NO | - | **Average entry price across fills** - Weighted average of all entry prices from fills that opened the position. Formula: `sum(size * entry_price) / sum(size)`. Example: `45000.00` (for $45,000 average entry). |
| `avg_exit_price` | `Float` | NO | - | **Average exit price across fills** - Weighted average of all exit prices from fills that closed the position. Formula: `sum(size * exit_price) / sum(size)`. Example: `46000.00` (for $46,000 average exit). |
| `trade_type` | `String(10)` | NO | - | **Trade type** - The action taken. Values: `'BUY'` or `'SELL'`. Determines trade direction. |
| `total_pnl` | `Float` | NO | - | **Sum of all fill P&Ls** - Total profit/loss from this complete trade. This is the sum of `closed_pnl` from all fills that make up this trade. **This is the primary P&L value for UI display.** Example: `500.00` (profit), `-250.00` (loss). |
| `total_close_fee` | `Float` | YES | - | **Sum of all close fees** - Total of all `close_fee` values from fills that closed the position. Example: If 3 fills had fees of $2, $2, $1, this would be `5.00`. NULL if fees not available. |
| `total_open_fee` | `Float` | YES | - | **Sum of all open fees** - Total of all `open_fee` values from fills that opened the position. Example: If 2 fills had fees of $2.50 each, this would be `5.00`. NULL if fees not available. |
| `total_liquidate_fee` | `Float` | YES | - | **Sum of all liquidation fees** - Total of all `liquidate_fee` values if position was liquidated. Usually NULL unless position was liquidated. Example: `50.00` (for $50 total liquidation fees). |
| `exit_type` | `String(20)` | YES | - | **Exit type** - How the position was closed. Values: `'Trade'` (normal trade execution), `'Liquidation'` (forced closure due to margin call). Used to identify liquidations in analysis. |
| `equity_used` | `Float` | YES | - | **Equity used for trade** - How much equity (collateral) was allocated to this trade. Estimated from position snapshots. Used for risk analysis and position sizing. Example: `2300.00` (for $2,300 equity used). |
| `leverage` | `Float` | YES | - | **Leverage used** - The leverage multiplier used for this trade. Estimated from position snapshots. Example: `5.0` (for 5x leverage), `10.0` (for 10x leverage). NULL if unavailable. |
| `strategy_id` | `Integer` | YES | - | **Foreign key to strategies** - Which strategy was active when this trade executed. Links to `strategies.id`. NULL if no strategy assigned. **Used for strategy performance calculations.** Populated from `strategy_assignments` at insert time. |
| `fill_count` | `Integer` | YES | `1` | **Number of fills aggregated** - How many individual fills from `closed_trades` were combined to create this aggregated trade. Example: `3` (if 3 fills were aggregated), `1` (if single fill). Used to understand trade complexity. |
| `created_at` | `DateTime` | NO | `utcnow()` | **Record creation timestamp** - When this aggregated trade record was created by the aggregation service. Usually after the trade closes. Used for debugging and data integrity checks. |

**Indexes**:
- `idx_agg_wallet_timestamp` on (`wallet_id`, `timestamp`)
- `idx_agg_wallet_symbol_timestamp` on (`wallet_id`, `symbol`, `timestamp`)
- `idx_agg_timestamp` on (`timestamp`)

**Data Flow**:
- Generated by `services/aggregation_service.py` from `closed_trades`
- One row per complete trade round-trip
- Aggregates multiple fills into logical trades

**Notes**:
- ✅ **Use this table for UI display** (not `closed_trades`)
- `total_pnl` is sum of all fill P&Ls that make up this trade
- `fill_count` indicates how many fills were aggregated

**Example Query**:
```python
# Get closed trades for wallet dashboard
trades = session.query(AggregatedTrade).filter(
    AggregatedTrade.wallet_id == wallet_id
).order_by(AggregatedTrade.timestamp.desc()).all()

# Calculate strategy performance
strategy_pnl = session.query(func.sum(AggregatedTrade.total_pnl)).filter(
    AggregatedTrade.strategy_id == strategy_id
).scalar()
```

---

### 7. `strategies`

**Purpose**: Strategy catalog/master list.

**When to use**:
- List all available strategies
- Create new strategies
- Reference strategy by ID

**Fields**:

| Field | Type | Null | Default | Description |
|-------|------|------|---------|-------------|
| `id` | `Integer` | NO | auto | **Primary key** - Unique identifier for this strategy. Auto-incremented integer. Referenced by `strategy_assignments`, `position_snapshots`, `closed_trades`, and `aggregated_trades`. Example: `1`, `2`, `3` |
| `name` | `String(255)` | NO | - | **Strategy name (unique)** - Human-readable name for the strategy. Must be unique across all strategies. Used for display and selection in UI. Examples: `"Mean Reversion BTC"`, `"Trend Following ETH"`, `"Scalping Strategy"`. |
| `description` | `String(1000)` | YES | - | **Strategy description** - Optional detailed description of the strategy, its logic, parameters, or notes. Used for documentation and understanding strategy purpose. Example: `"Mean reversion strategy for BTC/USD with RSI < 30 entry signal"`. NULL if no description provided. |
| `created_at` | `DateTime` | NO | `utcnow()` | **Record creation timestamp** - When this strategy was first created in the database. Used for sorting and filtering strategies by creation date. Format: UTC datetime. |

**Indexes**: None (primary key only)

**Relationships**:
- Referenced by `strategy_assignments`, `position_snapshots`, `closed_trades`, `aggregated_trades`

**Example Query**:
```python
# Get all strategies
strategies = session.query(Strategy).order_by(Strategy.name).all()

# Get strategy by name
strategy = session.query(Strategy).filter(Strategy.name == 'My Strategy').first()
```

---

### 8. `strategy_assignments`

**Purpose**: Time-bounded strategy assignments per wallet and symbol.

**When to use**:
- Assign strategies to wallet/symbol pairs
- Determine which strategy was active at trade time
- Track strategy assignment history

**Fields**:

| Field | Type | Null | Default | Description |
|-------|------|------|---------|-------------|
| `id` | `Integer` | NO | auto | **Primary key** - Unique identifier for this strategy assignment. Auto-incremented integer. Used internally for record identification. |
| `wallet_id` | `Integer` | NO | - | **Wallet identifier** - Links to `wallet_configs.id`. Identifies which wallet this assignment applies to. Example: `1`, `2`, `3`. Used to filter assignments by wallet. |
| `symbol` | `String(50)` | NO | - | **Trading symbol** - The trading pair or instrument this assignment applies to. Must match format used in other tables. Examples: `"BTC/USD"`, `"ETH-PERP"`, `"SOL/USD"`. Used to scope strategy to specific symbols. |
| `strategy_id` | `Integer` | NO | - | **Foreign key to strategies** - Links to `strategies.id`. Identifies which strategy is assigned. Example: `1`, `2`, `3`. Used to populate `strategy_id` in snapshots and trades. |
| `start_at` | `DateTime` | NO | `utcnow()` | **Assignment start time** - When this strategy assignment becomes active. Used for time-bounded assignments and historical tracking. Format: UTC datetime. Example: `2025-01-15 10:00:00` (strategy active from 10 AM). |
| `end_at` | `DateTime` | YES | - | **Assignment end time** - When this strategy assignment ends. NULL means assignment is still active (no end date). Used to support strategy changes over time. Example: `2025-01-20 15:00:00` (strategy ended at 3 PM). NULL = currently active. |
| `active` | `Boolean` | YES | `True` | **Active flag** - Whether this assignment is currently active. Used for filtering active assignments. `True` = active, `False` = inactive (archived). Allows soft-deletion of assignments. |
| `is_current` | `Boolean` | YES | `True` | **Current usage indicator** - Whether this wallet/symbol pair is currently using this strategy. Used to identify the active strategy for a pair. `True` = currently in use, `False` = historical assignment. Multiple assignments can exist for same pair with different time ranges. |
| `notes` | `String(500)` | YES | - | **User comments/notes** - Optional user-provided notes about this assignment. Used for documentation, reminders, or strategy notes. Example: `"Testing new parameters"`, `"Paused due to market conditions"`. NULL if no notes. |
| `created_at` | `DateTime` | NO | `utcnow()` | **Record creation timestamp** - When this assignment was first created. Used for audit trail and sorting. Format: UTC datetime. |
| `modified_at` | `DateTime` | NO | `utcnow()` | **Last modification timestamp** - Automatically updated whenever any field in this record changes. Used to track when assignment was last modified. Auto-updated by SQLAlchemy. |

**Indexes**:
- `idx_assign_wallet_symbol_time` on (`wallet_id`, `symbol`, `start_at`, `end_at`)
- `idx_assign_active` on (`active`)

**Relationships**:
- `strategy` relationship to `Strategy` model

**Notes**:
- Supports time-bounded assignments (historical tracking)
- Used to determine which strategy was active at trade time
- `is_current` indicates if assignment is currently active

**Example Query**:
```python
# Get active strategy for wallet/symbol at a specific time
assignment = session.query(StrategyAssignment).filter(
    StrategyAssignment.wallet_id == wallet_id,
    StrategyAssignment.symbol == 'BTC/USD',
    StrategyAssignment.start_at <= trade_time,
    or_(
        StrategyAssignment.end_at.is_(None),
        StrategyAssignment.end_at >= trade_time
    )
).first()
```

---

## 🔄 Data Reuse Opportunities

### 1. Position Data Reuse

**`position_snapshots.raw_data` (JSON)**:
- Stores complete API response
- **Reuse for**: Data recovery, debugging, future field extraction
- **Example**: If API adds new fields, can extract from `raw_data` without re-fetching

**`position_snapshots.opened_at`**:
- Calculated once from first snapshot with size > 0
- **Reuse for**: Position lifetime analysis, duration calculations
- **Example**: Calculate how long position was open: `closed_at - opened_at`

**`position_snapshots.leverage`**:
- Calculated once when position opens, then preserved
- **Reuse for**: All future snapshots of same position
- **Example**: Don't recalculate leverage for existing positions

### 2. Trade Data Reuse

**`closed_trades` → `aggregated_trades`**:
- Aggregation service reuses raw fills
- **Reuse for**: Creating logical trades from multiple fills
- **Example**: Group fills by timestamp + symbol to create complete trades

**`closed_trades.reduce_only`**:
- Indicates if trade opens or closes position
- **Reuse for**: Determining trade direction in aggregation logic

### 3. Strategy Assignment Reuse

**`strategy_assignments`**:
- Used to populate `strategy_id` in snapshots/trades
- **Reuse for**: Historical strategy attribution
- **Example**: Look up strategy active at trade time to populate `strategy_id`

### 4. Wallet Linking

**`wallet_address` vs `wallet_id`**:
- Both fields maintained for backward compatibility
- ✅ **Use `wallet_address`** for new code (preferred)
- **Reuse for**: Linking snapshots without foreign key constraints

### 5. Leverage Calculation Reuse

**`calculation_method`**:
- Stores how leverage was calculated
- **Reuse for**: Understanding calculation method, debugging
- **Example**: Know if leverage came from `margin_delta` or `margin_rate`

**`initial_margin_at_open`**:
- Preserved for historical analysis
- **Reuse for**: Position analysis, margin calculations

---

## 🔍 Common Query Patterns

### 1. Latest Equity Per Wallet

```python
# Get latest equity snapshot for each wallet
latest_equity = session.query(
    EquitySnapshot.wallet_address,
    func.max(EquitySnapshot.timestamp).label('latest_ts')
).group_by(EquitySnapshot.wallet_address).subquery()

equity = session.query(EquitySnapshot).join(
    latest_equity,
    and_(
        EquitySnapshot.wallet_address == latest_equity.c.wallet_address,
        EquitySnapshot.timestamp == latest_equity.c.latest_ts
    )
).all()
```

### 2. Open Positions

```python
# Get latest position snapshot for each symbol (open positions only)
latest_positions = session.query(
    PositionSnapshot.wallet_address,
    PositionSnapshot.symbol,
    func.max(PositionSnapshot.timestamp).label('latest_ts')
).filter(PositionSnapshot.size > 0).group_by(
    PositionSnapshot.wallet_address,
    PositionSnapshot.symbol
).subquery()

positions = session.query(PositionSnapshot).join(
    latest_positions,
    and_(
        PositionSnapshot.wallet_address == latest_positions.c.wallet_address,
        PositionSnapshot.symbol == latest_positions.c.symbol,
        PositionSnapshot.timestamp == latest_positions.c.latest_ts
    )
).filter(PositionSnapshot.size > 0).all()
```

### 3. Closed Trades (Use Aggregated)

```python
# Get closed trades for wallet dashboard
trades = session.query(AggregatedTrade).filter(
    AggregatedTrade.wallet_id == wallet_id
).order_by(AggregatedTrade.timestamp.desc()).limit(100).all()

# Fallback to closed_trades if aggregated_trades doesn't exist
if not trades:
    trades = session.query(ClosedTrade).filter(
        ClosedTrade.wallet_id == wallet_id
    ).order_by(ClosedTrade.timestamp.desc()).limit(100).all()
```

### 4. Strategy Attribution

```python
# Get strategy active at trade time
def get_strategy_at_time(wallet_id, symbol, trade_time):
    assignment = session.query(StrategyAssignment).filter(
        StrategyAssignment.wallet_id == wallet_id,
        StrategyAssignment.symbol == symbol,
        StrategyAssignment.start_at <= trade_time,
        or_(
            StrategyAssignment.end_at.is_(None),
            StrategyAssignment.end_at >= trade_time
        )
    ).first()
    return assignment.strategy_id if assignment else None
```

### 5. Historical Equity Chart

```python
# Get equity time series for chart
equity_series = session.query(EquitySnapshot).filter(
    EquitySnapshot.wallet_address == wallet_address,
    EquitySnapshot.timestamp >= start_date,
    EquitySnapshot.timestamp <= end_date
).order_by(EquitySnapshot.timestamp).all()

# Format for chart
chart_data = [{
    'timestamp': e.timestamp.isoformat(),
    'equity': e.total_equity,
    'unrealized_pnl': e.unrealized_pnl,
    'realized_pnl': e.realized_pnl
} for e in equity_series]
```

### 6. Position History

```python
# Get position history for symbol
position_history = session.query(PositionSnapshot).filter(
    PositionSnapshot.wallet_address == wallet_address,
    PositionSnapshot.symbol == symbol
).order_by(PositionSnapshot.timestamp).all()

# Calculate position metrics
for snapshot in position_history:
    duration = snapshot.timestamp - snapshot.opened_at if snapshot.opened_at else None
    # ... analyze position lifecycle
```

---

## 📝 Field Naming Conventions

### Wallet Identification
- ✅ **Use `wallet_address`** for new code (preferred)
- ⚠️ `wallet_id` maintained for legacy compatibility

### Timestamps
- `timestamp`: When the event occurred (snapshot time, trade time)
- `created_at`: When record was inserted into database
- `updated_at`: When record was last modified (auto-updated)
- `opened_at`: When position was first opened (calculated)

### Price Fields
- `entry_price`: Average entry price
- `current_price`: Current market price
- `exit_price`: Exit price for closed trades
- `avg_entry_price`: Average entry price (aggregated trades)
- `avg_exit_price`: Average exit price (aggregated trades)

### P&L Fields
- `unrealized_pnl`: Unrealized P&L from open positions
- `realized_pnl`: Cumulative realized P&L
- `closed_pnl`: P&L for individual fill
- `total_pnl`: Sum of P&Ls for aggregated trade

### Fee Fields
- `close_fee`: Fee paid on close
- `open_fee`: Fee paid on open
- `liquidate_fee`: Liquidation fee
- `total_close_fee`: Sum of close fees (aggregated)
- `total_open_fee`: Sum of open fees (aggregated)
- `total_liquidate_fee`: Sum of liquidation fees (aggregated)

---

## ⚠️ Important Notes

### Table Selection Guidelines

1. **For UI Display**:
   - ✅ Use `aggregated_trades` for closed trades
   - ✅ Use `position_snapshots` for open positions
   - ✅ Use `equity_snapshots` for equity charts

2. **For Internal Processing**:
   - Use `closed_trades` for aggregation
   - Use `raw_data` JSON for data recovery

3. **For Strategy Attribution**:
   - Use `strategy_assignments` to determine active strategy
   - Populate `strategy_id` in snapshots/trades at insert time

### Data Consistency

- **Leverage**: Calculated once, preserved for all future snapshots
- **Strategy ID**: Populated from `strategy_assignments` at insert time
- **Wallet Linking**: Use `wallet_address` (preferred) or `wallet_id` (legacy)

### Performance Considerations

- Indexes exist on common query patterns (wallet + timestamp, symbol + timestamp)
- Use `wallet_address` for queries (indexed)
- Filter by timestamp ranges for large datasets

---

## 🔗 Related Documentation

- [README.md](../README.md) - Database schema overview
- [GUIDE.md](GUIDE.md) - Complete application guide
- [leverage/LEVERAGE_CALCULATION.md](leverage/LEVERAGE_CALCULATION.md) - Leverage calculation details

---

**Last Updated**: 2025-01-XX  
**Database Version**: SQLite (wallet.db)

