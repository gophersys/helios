-- Add a unique constraint on (targetId, name) for TestExecution. A given
-- test function should run at most once per RunTarget. Before this
-- change, a reporter bug that dropped slotIndex attribution could create
-- duplicate rows on the first-slot target silently; the DB-level unique
-- makes that failure mode impossible — concurrent double-creates surface
-- as a 409 instead of corrupt data.
--
-- Verified before authoring: production has 0 existing duplicates
-- (`SELECT COUNT(*) FROM (... GROUP BY targetId, name HAVING COUNT(*) > 1) d;`).
-- If a future deploy finds duplicates, add a dedup step here before the
-- CREATE UNIQUE INDEX.

-- CreateIndex
CREATE UNIQUE INDEX IF NOT EXISTS "test_executions_targetId_name_key"
  ON "test_executions"("targetId", "name");
