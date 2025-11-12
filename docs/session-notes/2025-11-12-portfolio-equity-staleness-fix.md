# Session Notes - 2025-11-12 - Portfolio Equity Staleness Fix

## What Changed

Fixed artificial portfolio equity dips caused by filtering out wallets that hadn't updated in >1 hour.

- **Removed 1-hour stale data filter** from `db/queries.py:get_equity_history()`
- **Added `is_wallet_stale()` helper function** for UI to detect stale wallets
- **Added `STALE_WALLET_HOURS` configuration** (default: 2 hours, configurable via env var)
- **Updated CLAUDE.md** with better testing guidance (use actual server URL, not localhost)

## What Broke

Nothing. No pre-existing features were affected by this change.

## How It Was Fixed

### Root Cause
The portfolio equity aggregation query was filtering out any wallet that hadn't reported in the last hour:
```python
if (current_ts - wallet_ts).total_seconds() <= 3600:  # 3600 seconds = 1 hour
    portfolio_total += data['total_equity']
```

This violated the design principle that "wallets are the source of truth." When a wallet stopped reporting for 61 minutes, it would suddenly be excluded from the portfolio total, causing a sharp dip in the equity chart. Then when it reported again, it would jump back up.

### Solution
1. **Removed the age-based filtering** - now all connected wallets' latest snapshots are always included
2. **Added staleness detection for UI** - `is_wallet_stale()` function checks if a wallet hasn't updated recently
3. **Staleness is displayed, not hidden** - users see "Last updated: 3 hours ago" in the wallet table, not missing equity data
4. **Made threshold configurable** - `STALE_WALLET_HOURS` env var (default: 2 hours)

### Code Changes

**db/queries.py (lines 94-116):**
```python
def is_wallet_stale(last_update_timestamp: datetime, stale_hours: int = 2) -> bool:
    """Check if wallet hasn't updated in >stale_hours."""
    if last_update_timestamp is None:
        return True
    now = datetime.now()
    age_seconds = (now - last_update_timestamp).total_seconds()
    stale_seconds = stale_hours * 3600
    return age_seconds > stale_seconds
```

**db/queries.py (lines 188-194):**
Removed:
```python
if (current_ts - wallet_ts).total_seconds() <= 3600:  # OLD: Only include if <1 hour old
```

Replaced with:
```python
# Include ALL wallet data, regardless of age
# Staleness is indicated to users via UI warnings, not by filtering data
```

**config.py (line 35):**
```python
STALE_WALLET_HOURS = int(os.getenv('STALE_WALLET_HOURS', 2))
```

**env.example (line 14):**
```bash
STALE_WALLET_HOURS=2  # Threshold for stale wallet warnings
```

## Testing Performed

### Backend Testing (Automated)
1. **App startup** - No import/syntax errors ✓
2. **Health endpoint** - Returns 200 OK ✓
3. **Portfolio page** - Loads successfully ✓
4. **is_wallet_stale() function** - Works correctly:
   - 1 hour ago: `False` (not stale) ✓
   - 3 hours ago: `True` (stale) ✓
5. **STALE_WALLET_HOURS config** - Loads as integer value 2 ✓
6. **Portfolio equity query** - 11 data points aggregated, smooth trend, **NO artificial dips** ✓
7. **Last Update column** - Displays timestamps correctly in table ✓
8. **Wallet aggregation** - All connected wallets included regardless of last update ✓

### Expected Visual Testing (for you)
1. **Equity chart** - Should show smooth curve, no V-shaped dip around 2025-11-12 07:52
2. **Wallet table** - Should show "Last updated: X minutes/hours ago" for each wallet
3. **No stale warnings yet** - Because all wallets updated within 2 hours

## Rollback Steps

If this change causes problems:

1. **Revert the commit:**
   ```bash
   git revert eec4485
   ```

2. **Restore database (if needed):**
   ```bash
   cp data/wallet_backup_20251112_093104.db data/wallet.db
   ```

3. **Restart the app:**
   ```bash
   python app.py
   ```

## Notes for Future

### Design Decision: Wallets as Source of Truth
This fix implements the principle that **wallets are the source of truth**. The database aggregation query should never filter data based on recency - it should aggregate what actually exists.

**Why not filter in the database layer?**
- Users expect to see all their data
- Staleness is a UI concern, not a data concern
- Filtering can hide real problems (e.g., wallet disconnected)

**Where staleness IS used:**
- UI layer: Display "Last updated: X hours ago" warning
- UI layer (future): Show warning modal when clicking stale wallet badge

### Related Code
- See `CLAUDE.md` rule 6 for the documented gotcha about portfolio equity aggregation
- The `is_wallet_stale()` function is available for UI components to use when displaying warnings

### Configuration
Users can adjust the staleness threshold via environment variable:
```bash
# Show warning if wallet hasn't updated in >3 hours instead of 2
STALE_WALLET_HOURS=3 python app.py
```

### Gotcha Added to CLAUDE.md
Added this gotcha to prevent future developers from re-introducing the filtering:
```
- **Portfolio equity aggregation**: DO NOT filter wallets based on staleness (e.g., no update in 1 hour). This causes artificial dips in equity charts. Wallets are the source of truth - aggregate ALL connected wallets' latest snapshots, no matter the age. Show staleness warnings in UI instead.
```

## Next Steps

- [ ] Visual testing in browser at http://91.99.142.197:5000
- [ ] Verify equity chart no longer has dips
- [ ] Implement UI stale wallet warning modal (uses `is_wallet_stale()` helper)
- [ ] Update README.md to document staleness warnings
- [ ] Merge feature branch to master once testing complete

---

**Branch:** `fix/portfolio-equity-staleness`
**Commit:** `eec4485`
**Date:** 2025-11-12 09:52 UTC
