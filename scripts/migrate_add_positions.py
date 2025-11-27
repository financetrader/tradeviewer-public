#!/usr/bin/env python3
"""
Migration: Add positions table and position_id column to position_snapshots.

This migration:
1. Creates the 'positions' table to track position lifecycles
2. Adds 'position_id' column to position_snapshots table
3. Creates necessary indexes

Run with: python scripts/migrate_add_positions.py [db_path]
Default db_path: data/wallet.db
"""

import sqlite3
import sys
from datetime import datetime


def migrate(db_path='data/wallet.db'):
    """Run the migration."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("=" * 80)
    print("Migration: Add positions table and position_id column")
    print("=" * 80)
    print(f"Database: {db_path}")
    print(f"Started at: {datetime.now()}")
    print()
    
    try:
        # Step 1: Create positions table
        print("Step 1: Creating 'positions' table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wallet_id INTEGER NOT NULL,
                symbol VARCHAR(50) NOT NULL,
                side VARCHAR(10) NOT NULL,
                opened_at DATETIME NOT NULL,
                closed_at DATETIME,
                entry_price FLOAT,
                exit_price FLOAT,
                realized_pnl FLOAT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("  ✓ positions table created")
        
        # Step 2: Create indexes on positions table
        print("\nStep 2: Creating indexes on positions table...")
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_position_wallet_symbol_side 
            ON positions (wallet_id, symbol, side)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_position_wallet_open 
            ON positions (wallet_id, closed_at)
        """)
        print("  ✓ Indexes created")
        
        # Step 3: Add position_id column to position_snapshots
        print("\nStep 3: Adding position_id column to position_snapshots...")
        
        # Check if column already exists
        cursor.execute("PRAGMA table_info(position_snapshots)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'position_id' in columns:
            print("  ⓘ position_id column already exists, skipping")
        else:
            cursor.execute("""
                ALTER TABLE position_snapshots
                ADD COLUMN position_id INTEGER
            """)
            print("  ✓ position_id column added")
        
        # Step 4: Create index on position_id
        print("\nStep 4: Creating index on position_snapshots.position_id...")
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_position_snapshot_position_id 
            ON position_snapshots (position_id)
        """)
        print("  ✓ Index created")
        
        conn.commit()
        
        print("\n" + "=" * 80)
        print("✓ Migration completed successfully!")
        print("=" * 80)
        
        # Show table info
        print("\nNew 'positions' table structure:")
        cursor.execute("PRAGMA table_info(positions)")
        for col in cursor.fetchall():
            print(f"  {col[1]:20} {col[2]:15} {'NOT NULL' if col[3] else 'NULL':10}")
        
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"\n✗ Migration failed: {e}")
        return False
    finally:
        conn.close()


def rollback(db_path='data/wallet.db'):
    """Rollback the migration (for testing/recovery)."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("=" * 80)
    print("ROLLBACK: Removing positions table and position_id column")
    print("=" * 80)
    
    try:
        # Remove index first
        cursor.execute("DROP INDEX IF EXISTS idx_position_snapshot_position_id")
        print("  ✓ Dropped idx_position_snapshot_position_id")
        
        # SQLite doesn't support DROP COLUMN directly, but since position_id is nullable
        # and new, we can leave it (won't break anything) or recreate the table
        print("  ⓘ position_id column left in place (nullable, won't break anything)")
        
        # Drop positions table
        cursor.execute("DROP TABLE IF EXISTS positions")
        print("  ✓ Dropped positions table")
        
        conn.commit()
        print("\n✓ Rollback completed")
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"\n✗ Rollback failed: {e}")
        return False
    finally:
        conn.close()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == '--rollback':
        db_path = sys.argv[2] if len(sys.argv) > 2 else 'data/wallet.db'
        rollback(db_path)
    else:
        db_path = sys.argv[1] if len(sys.argv) > 1 else 'data/wallet.db'
        migrate(db_path)

