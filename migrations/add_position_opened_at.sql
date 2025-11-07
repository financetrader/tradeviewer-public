-- Add opened_at column to track when positions were first opened
-- This is calculated from the first snapshot with size > 0 for each wallet+symbol combination

ALTER TABLE position_snapshots ADD COLUMN opened_at DATETIME;

-- Create index for efficient querying
CREATE INDEX IF NOT EXISTS idx_position_opened_at ON position_snapshots(opened_at);
CREATE INDEX IF NOT EXISTS idx_position_wallet_symbol_opened ON position_snapshots(wallet_id, symbol, opened_at);

