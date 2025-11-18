# Leverage Calculation Testing Plan

## Objective
Verify that the available_balance delta method correctly calculates leverage for NEW positions using automated mock data insertion.

## Test Method
- **Automated**: Insert mock BTC position data that simulates Apex API responses
- **Wallet**: Wallet 4 (Apex Omni)
- **Positions**: 2 BTC positions (1 SHORT, 1 LONG) opened 10 minutes apart
- **Data**: Uses only fields that would come from real Apex API (no synthetic fields)

---

## Test Files

### 1. `test_insert_mock_positions.py`
Inserts 2 mock BTC positions with supporting equity snapshots into the database.

**What it inserts:**
- 3 equity snapshots (baseline, after pos1, after pos2)
- 2 position snapshots (SHORT and LONG BTC)
- All data matches Apex API response structure

### 2. `test_remove_mock_positions.py`
Removes the test data after testing is complete.

**Safety features:**
- Only removes BTC-USDT positions from wallet 4
- Only removes snapshots from last 2 hours
- Only removes positions with `leverage = NULL` (test data)
- Requires manual confirmation

---

## Quick Test Execution

### Complete Test in 5 Commands:

```bash
# 1. Insert test data
./venv/bin/python test_insert_mock_positions.py

# 2. Run leverage calculation (simulates what logger does)
./venv/bin/python test_calculate_leverage.py

# 3. Verify results
./venv/bin/python test_verify_leverage.py

# 4. Check dashboard
curl -s http://91.99.142.197:5000/wallet/4 | grep -A 10 "BTC-USDT"

# 5. Cleanup (removes test data)
./venv/bin/python test_remove_mock_positions.py
```

---

## Detailed Test Steps

### Step 1: Pre-Test Verification

Check current state of database:

```bash
./venv/bin/python -c "
from db.database import get_session
from db.models import PositionSnapshot

with get_session() as session:
    btc_positions = session.query(PositionSnapshot).filter(
        PositionSnapshot.wallet_id == 4,
        PositionSnapshot.symbol == 'BTC-USDT'
    ).count()

    print(f'Existing BTC positions in wallet 4: {btc_positions}')
    if btc_positions > 0:
        print('WARNING: BTC positions already exist. Test may be affected.')
"
```

### Step 2: Insert Test Data

```bash
./venv/bin/python test_insert_mock_positions.py
```

**Expected output:**
```
=== Inserting Test Data ===

1. Inserting baseline equity snapshot...
   Timestamp: 2025-11-13 18:00:00
   Available Balance: $500.00

2. Inserting equity snapshot after Position 1...
   Timestamp: 2025-11-13 18:10:05
   Available Balance: $495.55
   Equity used: $4.45

3. Inserting equity snapshot after Position 2...
   Timestamp: 2025-11-13 18:20:05
   Available Balance: $486.65
   Equity used: $8.90

4. Inserting Position 1 snapshot (SHORT)...
   Symbol: BTC-USDT
   Side: SHORT
   Size: 0.001 BTC
   Entry: $89000.00
   Position Size: $89.00
   Opened at: 2025-11-13 18:10:00

5. Inserting Position 2 snapshot (LONG)...
   Symbol: BTC-USDT
   Side: LONG
   Size: 0.002 BTC
   Entry: $89100.00
   Position Size: $178.20
   Opened at: 2025-11-13 18:20:00

✓ Test data inserted successfully!

=== Expected Leverage Calculations ===
Position 1 (SHORT):
  Equity delta: $4.45
  Position size: $89.00
  Expected leverage: 20.0x

Position 2 (LONG):
  Equity delta: $8.90
  Position size: $178.20
  Expected leverage: 20.0x
```

### Step 3: Calculate Leverage

Now we need to manually trigger the leverage calculation for these positions:

```bash
./venv/bin/python -c "
from db.database import get_session
from db.models import PositionSnapshot
from services.apex_leverage_calculator import calculate_leverage_from_margin_delta
from datetime import datetime, timedelta

with get_session() as session:
    # Get recent BTC positions without leverage
    recent_time = datetime.utcnow() - timedelta(hours=2)

    positions = session.query(PositionSnapshot).filter(
        PositionSnapshot.wallet_id == 4,
        PositionSnapshot.symbol == 'BTC-USDT',
        PositionSnapshot.timestamp >= recent_time,
        PositionSnapshot.leverage.is_(None)
    ).order_by(PositionSnapshot.timestamp.asc()).all()

    print(f'Found {len(positions)} positions to calculate leverage for\n')

    for pos in positions:
        print(f'=== Calculating leverage for {pos.symbol} {pos.side} ===')
        print(f'Opened at: {pos.timestamp}')
        print(f'Size: {pos.size} BTC')
        print(f'Position USD: ${pos.position_size_usd:.2f}')

        # Calculate leverage
        try:
            leverage, equity_used, method = calculate_leverage_from_margin_delta(
                session=session,
                wallet_id=pos.wallet_id,
                symbol=pos.symbol,
                position_size_usd=pos.position_size_usd,
                current_initial_margin=0.0,  # Not used in available_balance method
                current_timestamp=pos.timestamp,
                position_raw=pos.raw_data or {}
            )

            if leverage:
                # Update position
                pos.leverage = leverage
                pos.equity_used = equity_used
                pos.calculation_method = method

                print(f'✓ Calculated: {leverage:.1f}x leverage, ${equity_used:.2f} equity used')
                print(f'  Method: {method}\n')
            else:
                print(f'✗ Failed to calculate leverage (method: {method})\n')

        except Exception as e:
            print(f'✗ Error: {e}\n')

    session.commit()
    print('Leverage calculation complete.')
"
```

### Step 4: Verify Results

```bash
./venv/bin/python -c "
from db.database import get_session
from db.models import PositionSnapshot
from datetime import datetime, timedelta

with get_session() as session:
    recent_time = datetime.utcnow() - timedelta(hours=2)

    positions = session.query(PositionSnapshot).filter(
        PositionSnapshot.wallet_id == 4,
        PositionSnapshot.symbol == 'BTC-USDT',
        PositionSnapshot.timestamp >= recent_time
    ).order_by(PositionSnapshot.timestamp.asc()).all()

    print('=== VERIFICATION RESULTS ===\n')

    passed = 0
    failed = 0

    for i, pos in enumerate(positions, 1):
        print(f'Position {i}: {pos.side}')
        print(f'  Opened: {pos.timestamp}')
        print(f'  Size: {pos.size} BTC')
        print(f'  Position USD: ${pos.position_size_usd:.2f}')
        print(f'  Leverage: {pos.leverage:.1f}x' if pos.leverage else '  Leverage: None')
        print(f'  Equity Used: ${pos.equity_used:.2f}' if pos.equity_used else '  Equity Used: None')
        print(f'  Method: {pos.calculation_method}')

        # Check if calculation succeeded
        if pos.leverage and pos.equity_used and pos.calculation_method == 'margin_delta':
            # Check if leverage is reasonable (15-25x range)
            if 15.0 <= pos.leverage <= 25.0:
                print('  Status: ✓ PASS')
                passed += 1
            else:
                print(f'  Status: ✗ FAIL (leverage {pos.leverage:.1f}x out of range)')
                failed += 1
        else:
            print('  Status: ✗ FAIL (no leverage calculated)')
            failed += 1

        print()

    print(f'=== SUMMARY ===')
    print(f'Passed: {passed}/{len(positions)}')
    print(f'Failed: {failed}/{len(positions)}')

    if failed == 0:
        print('\n🎉 ALL TESTS PASSED!')
    else:
        print(f'\n⚠️  {failed} TEST(S) FAILED')
"
```

### Step 5: Check Dashboard

Verify the positions display correctly on the dashboard:

```bash
echo "Visit: http://91.99.142.197:5000/wallet/4"
echo ""
echo "Look for BTC-USDT positions with leverage displayed (not '-')"
```

### Step 6: Cleanup Test Data

After verification, remove the test data:

```bash
./venv/bin/python test_remove_mock_positions.py
```

Type `yes` when prompted to confirm deletion.

---

## Expected Test Results

### ✓ Pass Criteria

1. **Position 1 (SHORT 0.001 BTC)**
   - Leverage: ~20.0x
   - Equity used: ~$4.45
   - Method: `margin_delta`

2. **Position 2 (LONG 0.002 BTC)**
   - Leverage: ~20.0x
   - Equity used: ~$8.90
   - Method: `margin_delta`

3. **Dashboard Display**
   - Both BTC positions show leverage (not "-")
   - Equity used displays correctly

### ✗ Fail Indicators

- Leverage = `None` or `-`
- Method = `unknown` or `margin_rate`
- Leverage outside 15-25x range
- Equity used = `None`

---

## Manual Calculation Verification

Calculate expected leverage manually:

```bash
./venv/bin/python -c "
# Position 1
pos1_size = 89.00  # USD
equity1 = 4.45     # USD
lev1 = pos1_size / equity1
print(f'Position 1: ${pos1_size} / ${equity1} = {lev1:.1f}x')

# Position 2
pos2_size = 178.20  # USD
equity2 = 8.90      # USD
lev2 = pos2_size / equity2
print(f'Position 2: ${pos2_size} / ${equity2} = {lev2:.1f}x')
"
```

**Expected:**
```
Position 1: $89.0 / $4.45 = 20.0x
Position 2: $178.2 / $8.9 = 20.0x
```

---

## Troubleshooting

### Issue: Leverage shows as `None`

**Check 1: Is position detected as "new"?**
```bash
./venv/bin/python -c "
from db.database import get_session
from db.models import PositionSnapshot
from services.apex_leverage_calculator import is_new_position
from datetime import datetime, timedelta

with get_session() as session:
    pos = session.query(PositionSnapshot).filter(
        PositionSnapshot.wallet_id == 4,
        PositionSnapshot.symbol == 'BTC-USDT'
    ).order_by(PositionSnapshot.timestamp.desc()).first()

    if pos:
        is_new = is_new_position(session, 4, 'BTC-USDT', pos.timestamp)
        print(f'Position opened at: {pos.timestamp}')
        print(f'is_new_position(): {is_new}')
        print()
        print('Expected: True')
        print('If False: Position was not detected as new (check lookback window)')
"
```

**Check 2: Do equity snapshots exist?**
```bash
./venv/bin/python -c "
from db.database import get_session
from db.models import EquitySnapshot, PositionSnapshot
from datetime import timedelta

with get_session() as session:
    pos = session.query(PositionSnapshot).filter(
        PositionSnapshot.wallet_id == 4,
        PositionSnapshot.symbol == 'BTC-USDT'
    ).order_by(PositionSnapshot.timestamp.desc()).first()

    if pos:
        # Check for equity snapshot BEFORE position
        before = session.query(EquitySnapshot).filter(
            EquitySnapshot.wallet_id == 4,
            EquitySnapshot.timestamp < pos.timestamp,
            EquitySnapshot.available_balance.isnot(None)
        ).order_by(EquitySnapshot.timestamp.desc()).first()

        # Check for equity snapshot AFTER position
        after = session.query(EquitySnapshot).filter(
            EquitySnapshot.wallet_id == 4,
            EquitySnapshot.timestamp >= pos.timestamp,
            EquitySnapshot.timestamp <= pos.timestamp + timedelta(minutes=5),
            EquitySnapshot.available_balance.isnot(None)
        ).order_by(EquitySnapshot.timestamp.asc()).first()

        print(f'Position opened: {pos.timestamp}')
        print(f'Equity before: {before.timestamp if before else \"NOT FOUND\"}')
        print(f'Equity after: {after.timestamp if after else \"NOT FOUND\"}')
        print()

        if before and after:
            delta = float(before.available_balance) - float(after.available_balance)
            print(f'Available balance before: ${before.available_balance:.2f}')
            print(f'Available balance after: ${after.available_balance:.2f}')
            print(f'Delta: ${delta:.2f}')
        else:
            print('ERROR: Missing equity snapshots')
"
```

**Check 3: Review calculation logs**
```bash
# Check if any errors occurred during calculation
tail -100 logs/app.log | grep -i "BTC\|leverage\|equity"
```

---

## Success Checklist

- [ ] Test data inserted successfully
- [ ] 2 positions created (1 SHORT, 1 LONG)
- [ ] 3 equity snapshots created
- [ ] Leverage calculated for both positions
- [ ] Leverage values are ~20.0x (within 15-25x range)
- [ ] Equity used matches expected values
- [ ] `calculation_method = "margin_delta"`
- [ ] Dashboard displays leverage correctly
- [ ] Test data cleaned up

---

## Time Required

- **Setup & Insert**: 1 minute
- **Calculate Leverage**: 30 seconds
- **Verification**: 1 minute
- **Cleanup**: 30 seconds
- **Total**: ~3 minutes

---

## Notes

- Test uses mock data that simulates real Apex API responses
- No actual trading required
- Test data is isolated to BTC-USDT on wallet 4
- Cleanup script has safety checks to prevent deleting production data
- All timestamps are relative to current time (test works at any time)
