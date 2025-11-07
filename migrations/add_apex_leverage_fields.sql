-- Add fields for Apex leverage calculation via initial margin tracking
-- Run date: 2025-11-07

-- Add initial_margin to equity_snapshots table
ALTER TABLE equity_snapshots ADD COLUMN initial_margin FLOAT;

-- Add initial_margin_at_open and calculation_method to position_snapshots table
ALTER TABLE position_snapshots ADD COLUMN initial_margin_at_open FLOAT;
ALTER TABLE position_snapshots ADD COLUMN calculation_method VARCHAR(20);

-- These columns track:
-- - initial_margin: Total margin used across all positions (from Apex balance API)
-- - initial_margin_at_open: Snapshot of total margin when position was opened
-- - calculation_method: How leverage was calculated (margin_delta, margin_rate, unknown)

