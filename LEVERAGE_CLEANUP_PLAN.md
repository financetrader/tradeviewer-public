# Leverage Calculation Cleanup Plan

**Objective**: Remove all deprecated estimation code and ensure ONLY margin delta method is used everywhere.

**Status**: Ready for cleanup

---

## What Needs to be Done

### 1. Replace logger.py (CRITICAL)
**File**: `logger.py` lines 81-86

**Current Code** (OLD - estimation):
```python
from utils.calculations import estimate_leverage_hyperliquid
leverage = estimate_leverage_hyperliquid(
    position_size_usd=position_size_usd,
    account_equity=account_equity,
    position_value=position_value if position_value > 0 else None
)
```

**Replace With** (NEW - margin delta):
```python
from services.hyperliquid_leverage_calculator import calculate_leverage_from_margin_delta

# Get previous margin used from database
leverage, equity_used, method = calculate_leverage_from_margin_delta(
    session, wallet_id, symbol, position_size_usd,
    total_margin_used, timestamp_dt
)
```

**Why**: Logger needs to use same accurate margin delta method as dashboard

**Testing After**:
- Run logger manually: `python logger.py`
- Check database: `SELECT * FROM position_snapshots WHERE wallet_id=X AND calculation_method='margin_delta'`

---

### 2. Remove app.py Temp Display (CLEANUP)
**File**: `app.py` lines 500-515

**Current Code** (OLD - estimation for temporary display):
```python
from utils.calculations import estimate_leverage_hyperliquid
leverage = estimate_leverage_hyperliquid(
    position_size_usd=position_size_usd,
    account_equity=account_equity,
    position_value=position_value if position_value > 0 else None
)

hl_positions.append({
    ...
    'leverage': leverage,
    ...
})
```

**Replace With** (OPTION A - Remove from temp display):
```python
hl_positions.append({
    ...
    # 'leverage': leverage,  # Will be calculated when storing to DB
    ...
})
```

**OR OPTION B** (Replace with margin delta):
Get from equity snapshots context already available at line 489-497

**Why**: Temp API display doesn't need leverage. Real leverage calculated when stored to DB.

**Testing After**:
- Load dashboard: `http://91.99.142.197:5000/wallet/X`
- Verify no errors
- Check positions display correctly

---

### 3. Delete Deprecated Function (CLEANUP)
**File**: `utils/calculations.py` lines 69-144

**Remove**:
```python
def estimate_leverage_hyperliquid(position_size_usd, account_equity, position_value=None):
    """OLD DEPRECATED METHOD - DELETE THIS"""
    # ... entire function ...
```

**Why**: Not used anymore after steps 1 & 2. Keeping dead code causes confusion.

**Verification**:
```bash
grep -r "estimate_leverage_hyperliquid" --include="*.py"
# Should return: 0 results
```

---

## Testing Checklist

### Before Cleanup
- [ ] Backup database: `cp data/wallet.db data/wallet_backup_pre_cleanup.db`
- [ ] Note current position snapshot count
- [ ] Verify dashboard currently works

### During Cleanup - Step 1 (Logger)
- [ ] Replace logger.py lines 81-86
- [ ] Run logger: `python logger.py`
- [ ] Check for errors in logs
- [ ] Query DB: Verify new position_snapshots have `calculation_method='margin_delta'`

### During Cleanup - Step 2 (App.py temp)
- [ ] Remove/replace app.py lines 500-515
- [ ] Load dashboard page
- [ ] Check for JavaScript errors (F12 DevTools)
- [ ] Verify positions display without errors

### During Cleanup - Step 3 (Delete function)
- [ ] Delete estimate_leverage_hyperliquid()
- [ ] Search for any remaining imports: `grep -r "estimate_leverage_hyperliquid"`
- [ ] Should find ZERO results

### After Cleanup - Integration Tests
- [ ] Run test suite: `python tests/test_leverage_cleanup.py`
- [ ] Test dashboard:
  - Load wallet page
  - Verify positions show correctly
  - Check position_snapshots in DB have leverage
- [ ] Test logger:
  - Run logger manually
  - Verify new snapshots have margin_delta method
- [ ] Test trade closing:
  - Close a position on exchange
  - Run logger sync
  - Verify closed_trade has leverage from position_snapshot
- [ ] Test aggregated trades:
  - Verify aggregated trades have correct leverage

### After Cleanup - Manual Verification
```sql
-- All position snapshots should have margin_delta method
SELECT COUNT(*) FROM position_snapshots
WHERE calculation_method != 'margin_delta';
-- Result should be: 0

-- All new leverage values should be non-null
SELECT COUNT(*) FROM position_snapshots
WHERE leverage IS NULL AND calculation_method = 'margin_delta';
-- Result should be: 0 (or very small for edge cases)

-- Aggregated trades should have leverage from position snapshots
SELECT COUNT(*) FROM aggregated_trades
WHERE leverage IS NOT NULL;
-- Result should be > 0
```

---

## Rollback Plan

If anything breaks:

1. **Stop the app**: `pkill -f app.py`
2. **Restore database**: `cp data/wallet_backup_pre_cleanup.db data/wallet.db`
3. **Revert code changes**: `git checkout HEAD~ logger.py app.py utils/calculations.py`
4. **Restart app**: `python app.py`

---

## Expected Results

### Before Cleanup
- ⚠️ Mixed methods: margin_delta (dashboard) + estimation (logger, temp display)
- ⚠️ Deprecated code still present
- ⚠️ Inconsistent leverage values

### After Cleanup
- ✅ All methods use margin_delta
- ✅ No deprecated code
- ✅ Consistent leverage values everywhere
- ✅ Tests pass
- ✅ Database clean

---

## Cleanup Order

**MUST BE DONE IN THIS ORDER**:

1. **Step 1**: Replace logger.py (test)
2. **Step 2**: Remove app.py temp display (test)
3. **Step 3**: Delete deprecated function (test)
4. **Run full integration tests**
5. **Manual verification on running server**
6. **Delete this plan file when complete**

---

## Notes

- **Database Backup**: Keep the pre-cleanup backup for 24 hours in case issues arise
- **Testing**: Each step should be tested before moving to next
- **Git Commits**: Create one commit per cleanup step with clear messages
- **No Production Risk**: Dashboard/logger will still work during cleanup, just using new method
- **Consistency**: After cleanup, all leverage is calculated the same way (margin delta)

---

## Success Criteria

- ✅ Zero references to `estimate_leverage_hyperliquid` in code
- ✅ All leverage calculations use margin delta
- ✅ Test suite passes (100%)
- ✅ Dashboard works without errors
- ✅ Logger runs successfully
- ✅ Database queries confirm no NULL leverage values (where expected)
- ✅ Documentation updated
