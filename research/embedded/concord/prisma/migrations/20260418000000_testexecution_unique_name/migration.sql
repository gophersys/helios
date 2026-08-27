-- Add @@unique([targetId, name]) to TestExecution.
-- Prevents duplicate execution rows caused by a reporter regression (e.g. a
-- run that drops slotIndex and falls through to the wrong target). Any race
-- now surfaces as a unique-constraint violation which the handler converts
-- to a 409, rather than silently corrupting the data.
--
-- Non-destructive: adds constraint + index only. If the target environment
-- has existing duplicate (targetId, name) rows this migration will fail at
-- deploy time; resolve those duplicates manually before retrying.

CREATE UNIQUE INDEX IF NOT EXISTS "test_executions_targetId_name_key"
    ON "test_executions"("targetId", "name");
