#!/usr/bin/env python3
"""Remove mock BTC test positions from database.

This script removes the test data inserted by test_insert_mock_positions.py
"""

from datetime import datetime, timedelta
from db.database import get_session
from db.models import EquitySnapshot, PositionSnapshot

WALLET_ID = 4


def remove_test_data():
    """Remove all test position and equity snapshots."""

    with get_session() as session:
        print("=== Removing Test Data ===\n")

        # Calculate the time range for test data (last 2 hours)
        cutoff_time = datetime.utcnow() - timedelta(hours=2)

        # 1. Find and remove test position snapshots
        print("1. Removing test position snapshots...")
        positions_deleted = session.query(PositionSnapshot).filter(
            PositionSnapshot.wallet_id == WALLET_ID,
            PositionSnapshot.symbol == 'BTC-USDT',
            PositionSnapshot.timestamp >= cutoff_time,
            PositionSnapshot.leverage.is_(None)  # Only remove those without calculated leverage (test data)
        ).delete()

        print(f"   Deleted {positions_deleted} position snapshot(s)\n")

        # 2. Find and remove test equity snapshots
        print("2. Removing test equity snapshots...")

        # We need to be more careful with equity snapshots
        # Only delete if they're in our test time range AND there are multiple snapshots
        # (to avoid deleting real production data)

        test_equity_snapshots = session.query(EquitySnapshot).filter(
            EquitySnapshot.wallet_id == WALLET_ID,
            EquitySnapshot.timestamp >= cutoff_time
        ).all()

        # Count total equity snapshots to ensure we don't delete ALL data
        total_equity_count = session.query(EquitySnapshot).filter(
            EquitySnapshot.wallet_id == WALLET_ID
        ).count()

        if total_equity_count > len(test_equity_snapshots) + 5:
            # Safe to delete - there's plenty of other data
            equity_deleted = 0
            for snap in test_equity_snapshots:
                # Additional safety: only delete if total_equity is exactly 500.00 or 499.xx
                # (our test data range)
                if 499.0 <= snap.total_equity <= 500.5:
                    session.delete(snap)
                    equity_deleted += 1

            print(f"   Deleted {equity_deleted} equity snapshot(s)")
            print(f"   (Kept {total_equity_count - equity_deleted} production equity snapshots)\n")
        else:
            print(f"   Skipped equity deletion - insufficient production data")
            print(f"   (Only {total_equity_count} total equity snapshots exist)")
            print(f"   This prevents accidental deletion of all equity data\n")

        # Commit deletions
        session.commit()

        # 3. Verify deletion
        print("3. Verifying deletion...")
        remaining_test_positions = session.query(PositionSnapshot).filter(
            PositionSnapshot.wallet_id == WALLET_ID,
            PositionSnapshot.symbol == 'BTC-USDT',
            PositionSnapshot.timestamp >= cutoff_time,
            PositionSnapshot.leverage.is_(None)
        ).count()

        if remaining_test_positions == 0:
            print("   ✓ All test position snapshots removed\n")
        else:
            print(f"   ⚠ Warning: {remaining_test_positions} test position snapshots remain\n")

        print("=== Cleanup Complete ===\n")


if __name__ == '__main__':
    # Ask for confirmation before deleting
    print("This will remove test BTC position data from wallet 4.")
    print("Test data is identified by:")
    print("  - Symbol: BTC-USDT")
    print("  - Wallet ID: 4")
    print("  - Timestamp: Within last 2 hours")
    print("  - Leverage: NULL (not yet calculated)")
    print()

    confirm = input("Continue? (yes/no): ").lower().strip()

    if confirm == 'yes':
        remove_test_data()
    else:
        print("Cancelled.")
