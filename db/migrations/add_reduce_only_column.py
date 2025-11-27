"""
Migration: Add reduce_only column to closed_trades table

Date: 2025-11-13
Author: Claude

Purpose:
- Add reduce_only column to track whether a fill is closing (true) or opening (false) a position
- This allows matching opening and closing legs to create logical trades
- Apex API provides reduceOnly field which indicates: true=closing, false=opening

Schema Changes:
- Add 'reduce_only' BOOLEAN column to closed_trades table
- Default value: NULL (for historical trades)
- Type: BOOLEAN

Rollback:
ALTER TABLE closed_trades DROP COLUMN reduce_only;

Testing:
1. Backup database: cp data/wallet.db data/wallet_backup_test.db
2. Run migration: python db/migrations/add_reduce_only_column.py
3. Verify column exists: sqlite3 data/wallet.db "PRAGMA table_info(closed_trades);"
4. Check new trades have reduce_only set: SELECT COUNT(*) FROM closed_trades WHERE reduce_only IS NOT NULL;
"""

import os
import sys
from sqlalchemy import create_engine, text

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from db.database import DATABASE_URL


def run_migration():
    """Add reduce_only column to closed_trades table."""
    engine = create_engine(DATABASE_URL)

    with engine.connect() as conn:
        try:
            # Check if column already exists
            result = conn.execute(text("PRAGMA table_info(closed_trades)"))
            columns = [row[1] for row in result.fetchall()]

            if 'reduce_only' in columns:
                print("✓ Column 'reduce_only' already exists")
                return

            # Add column if not exists
            conn.execute(text("""
                ALTER TABLE closed_trades
                ADD COLUMN reduce_only BOOLEAN
            """))

            conn.commit()
            print("✓ Added 'reduce_only' column to closed_trades table")

            # Show summary
            result = conn.execute(text("PRAGMA table_info(closed_trades)"))
            columns = {row[1]: row[2] for row in result.fetchall()}
            print(f"✓ Column type: {columns.get('reduce_only', 'NOT FOUND')}")

        except Exception as e:
            print(f"✗ Migration failed: {e}")
            raise


if __name__ == '__main__':
    try:
        run_migration()
        print("\n✓ Migration completed successfully")
    except Exception as e:
        print(f"\n✗ Migration failed: {e}")
        sys.exit(1)
