-- Change modem firmware uniqueness from (boardRevisionId, version) to (boardRevisionId, filename)
-- This allows uploading without typing a version — the filename is the unique identifier.
DROP INDEX IF EXISTS "modem_firmwares_boardRevisionId_version_key";
CREATE UNIQUE INDEX "modem_firmwares_boardRevisionId_filename_key" ON "modem_firmwares"("boardRevisionId", "filename");
