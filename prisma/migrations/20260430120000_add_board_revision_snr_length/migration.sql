-- ============================================================================
-- add_board_revision_snr_length
--
-- Add `snrLength` (nullable INTEGER) to `board_revisions`. Per-revision
-- expected serial number length, used by the manufacturing scan UI to
-- enforce exact-length input before allowing a panel run to start.
--
-- Nullable on purpose: existing rows have no enforced length, so the
-- frontend falls back to current behavior (no length validation) when
-- the value is NULL.
-- ============================================================================

ALTER TABLE "board_revisions"
    ADD COLUMN "snrLength" INTEGER;
