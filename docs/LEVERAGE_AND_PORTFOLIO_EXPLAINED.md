# Leverage & Portfolio Tracking Explained

A simple guide to how TradeViewer calculates leverage and tracks your portfolio.

---

## Leverage Calculation

**The Core Idea**: Leverage tells you how much "buying power" you're using with your actual money (margin).

**Formula**: 
```
Leverage = Position Size / Equity Used
```

For example: If you open a $10,000 position using $1,000 of your own money (equity), your leverage is **10x**.

### How It's Calculated (Margin Delta Method)

1. **When you open a position**, the system tracks how much total margin you were using *before* and *after*
2. The **difference** (delta) is the equity used for that position
3. Leverage = `Position Size USD ÷ Equity Used`

**Key Point**: Leverage is calculated **once when the position opens** and stored. It doesn't recalculate every time—once calculated, it's preserved for the life of that position.

### Example

```
Before opening position:
  Total Margin Used = $500

After opening $5,000 BTC-LONG position:
  Total Margin Used = $1,000

Margin Delta (Equity Used) = $1,000 - $500 = $500
Leverage = $5,000 ÷ $500 = 10x
```

---

## Portfolio Tracking

### Three Main Tables

| What's Tracked | Table | Purpose |
|----------------|-------|---------|
| Wallet Balance | `equity_snapshots` | Total equity, unrealized P&L, available balance (taken every 30 min) |
| Open Positions | `position_snapshots` | Current positions with size, entry price, leverage, unrealized P&L |
| Closed Trades | `aggregated_trades` | Complete trade round-trips with final P&L |

### How It Works

1. **Every 30 minutes**, a background logger takes a "snapshot" of:
   - Your total equity (account balance)
   - All open positions (entry price, size, leverage, unrealized P&L)

2. **When you close a trade**, it's stored in `aggregated_trades` with the final realized P&L

3. **Portfolio View**: Sums up all wallet snapshots at each timestamp to show your total portfolio equity over time

### Visual Flow

```
Position Opens
    ↓
Logger takes snapshots (every 30 min while position is open)
├─ Stores position data + calculated leverage
└─ Stores wallet equity snapshot
    ↓
Position Closes
    ↓
Final P&L stored in aggregated_trades
```

### What's Stored in Each Snapshot

**Equity Snapshot** (wallet-level):
- Total equity (account value)
- Unrealized P&L
- Available balance
- Realized P&L
- Initial margin used

**Position Snapshot** (per-position):
- Symbol (e.g., BTC-USDT)
- Side (LONG or SHORT)
- Size
- Entry price
- Current price
- Position size in USD
- Leverage
- Unrealized P&L
- Funding fees
- Equity used

---

## TL;DR

- **Leverage** = Position Size ÷ Money You Put In (calculated once at open)
- **Portfolio** = Regular snapshots of balances + positions every 30 mins, plus a log of all completed trades

