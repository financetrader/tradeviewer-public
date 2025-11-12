"""
Migration: Create aggregated_trades table and populate from closed_trades

Date: 2025-11-12
Author: Claude

Purpose:
- Create aggregated_trades table for storing grouped fills
- Aggregate existing closed_trades by (wallet_id, timestamp, symbol)
- This allows cleaner display of what exchange APIs return as individual fills

What Changed:
- New table: aggregated_trades
- Indexes on wallet_id+timestamp, wallet_id+symbol+timestamp

Rollback:
DROP TABLE IF EXISTS aggregated_trades;

Testing:
1. Backup database: cp data/wallet.db data/wallet_backup_$(date +%Y%m%d_%H%M%S).db
2. Run migration: python db/migrations/create_aggregated_trades.py
3. Verify table created: sqlite3 data/wallet.db ".tables"
4. Check data: SELECT COUNT(*) FROM aggregated_trades;
5. Verify grouping: SELECT wallet_id, timestamp, symbol, COUNT(*) as fill_count, SUM(size) as total_size FROM closed_trades GROUP BY wallet_id, timestamp, symbol HAVING COUNT(*) > 1;
"""

import os
import sys
from datetime import datetime
from sqlalchemy import create_engine, text

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from db.database import DATABASE_URL

def run_migration():
    """Create aggregated_trades table and populate from closed_trades."""
    engine = create_engine(DATABASE_URL)

    with engine.connect() as conn:
        # Create table if not exists
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS aggregated_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wallet_id INTEGER,
                timestamp DATETIME NOT NULL,
                symbol VARCHAR(50) NOT NULL,
                side VARCHAR(10) NOT NULL,
                size FLOAT NOT NULL,
                avg_entry_price FLOAT NOT NULL,
                avg_exit_price FLOAT NOT NULL,
                trade_type VARCHAR(10) NOT NULL,
                total_pnl FLOAT NOT NULL,
                total_close_fee FLOAT,
                total_open_fee FLOAT,
                total_liquidate_fee FLOAT,
                exit_type VARCHAR(20),
                equity_used FLOAT,
                leverage FLOAT,
                strategy_id INTEGER,
                fill_count INTEGER DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """))

        # Create indexes
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_agg_wallet_timestamp
            ON aggregated_trades(wallet_id, timestamp)
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_agg_wallet_symbol_timestamp
            ON aggregated_trades(wallet_id, symbol, timestamp)
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_agg_timestamp
            ON aggregated_trades(timestamp)
        """))

        # Aggregate closed_trades into aggregated_trades
        # Group by wallet_id, timestamp, symbol and aggregate
        conn.execute(text("""
            INSERT INTO aggregated_trades
            (wallet_id, timestamp, symbol, side, size, avg_entry_price, avg_exit_price,
             trade_type, total_pnl, total_close_fee, total_open_fee, total_liquidate_fee,
             exit_type, equity_used, leverage, strategy_id, fill_count)
            SELECT
                wallet_id,
                timestamp,
                symbol,
                side,
                SUM(size) as size,
                CASE WHEN SUM(size) > 0
                    THEN SUM(entry_price * size) / SUM(size)
                    ELSE 0
                END as avg_entry_price,
                CASE WHEN SUM(size) > 0
                    THEN SUM(exit_price * size) / SUM(size)
                    ELSE 0
                END as avg_exit_price,
                trade_type,
                SUM(closed_pnl) as total_pnl,
                SUM(COALESCE(close_fee, 0)) as total_close_fee,
                SUM(COALESCE(open_fee, 0)) as total_open_fee,
                SUM(COALESCE(liquidate_fee, 0)) as total_liquidate_fee,
                exit_type,
                equity_used,
                leverage,
                strategy_id,
                COUNT(*) as fill_count
            FROM closed_trades
            WHERE ABS(closed_pnl) >= 0.01
            GROUP BY wallet_id, timestamp, symbol
        """))

        conn.commit()
        print("✓ Created aggregated_trades table")
        print("✓ Populated from existing closed_trades")

        # Show summary
        result = conn.execute(text("SELECT COUNT(*) FROM aggregated_trades"))
        count = result.scalar()
        print(f"✓ {count} aggregated trades created")

        result = conn.execute(text("""
            SELECT AVG(fill_count) as avg_fills, MAX(fill_count) as max_fills
            FROM aggregated_trades WHERE fill_count > 1
        """))
        row = result.fetchone()
        if row and row[0]:
            print(f"✓ Average fills per group: {row[0]:.1f}, Max fills: {int(row[1])}")

if __name__ == '__main__':
    try:
        run_migration()
        print("\n✓ Migration completed successfully")
    except Exception as e:
        print(f"\n✗ Migration failed: {e}")
        sys.exit(1)
