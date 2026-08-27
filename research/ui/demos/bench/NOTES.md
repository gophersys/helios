# NOTES — what the framework could NOT decide (bench)

1. **The render is a snapshot, not a session.** The drill session runs at
   build time and the page shows its outcome; live interaction (drag ->
   seam -> device -> confirm animation) needs a JS runtime binding of
   ui.tree's semantics — a port, not a design gap: every behaviour is
   already specified and drilled in Python.
2. **The event log's prose is mine.** The framework decides which states
   exist (coerced, stale, reverted); the sentences describing them are
   authored. A production log format belongs to the census of whatever
   panel adopts it.
3. **Timing constants are demo-scaled.** 0.5 s staleness and the 0.6/0.4 s
   drill pattern are chosen to demonstrate the boundary; a real bench takes
   deadlines from its census (telemetry's census carries the real ones).
4. **No second transport.** Gate 3's "a second adapter drove the same panel
   unchanged" remains unrun — FakeSerial is one adapter; a WebSocket echo
   adapter would complete the drill and is P5-adjacent work.
