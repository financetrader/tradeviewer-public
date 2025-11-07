-- Add raw_data column to position_snapshots table
ALTER TABLE position_snapshots ADD COLUMN raw_data JSON;

-- This column will store the complete API response for each position
-- It's nullable so existing records won't be affected
