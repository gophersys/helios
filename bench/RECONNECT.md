# Reconnect investigation

## Symptom
A freshly-booted board serves the FIRST client connection perfectly. Later
connections (client disconnects, a new one connects) could fail: the client
connects + handshakes but never learns the board's service (no SD), so nothing
routes.

## Method
The 115200 UART drops lines under load, so board-side tracing is unreliable over
serial. Added a UDP debug channel (`src/interface/netdbg.*`, build with
`-DCK_NETDBG`) that ships trace strings to a node-side collector — reliable.
Reachability was pinned with a static ARP entry to remove L2 noise. Every claim
below was confirmed by UDP trace, not inferred.

## Root causes found + fixed (reconnect went 1/N -> 6 consecutive)
1. **Listening-socket churn.** `socket_close()` closed the server's *listening*
   socket on every client disconnect; the connection thread re-created it each
   reconnect, starving the STM32 socket pool. Fix: create the listener once, let
   it persist; only recycle the per-connection client socket. (iface lib)
2. **Send thread parked on K_FOREVER.** After a disconnect (which sets
   `connected=false` but queues nothing) the send thread never woke to re-arm.
   Fix: poll with a 200 ms timeout and re-check `connected`. (cipher send.c)
3. **THE big one — local services wiped on disconnect.** `update_registry()`
   removed EVERY registry entry on any client disconnect (the per-interface
   guard was commented out `// fix me`). So the first disconnect deleted our own
   local `math` service and every later client found nothing to discover. Fix:
   never remove local services; for remote services drop only the endpoints
   reachable via the interface that disconnected. Verified by UDP trace: BCAST
   now fires on conn 2+. (cipher disconn_event.c)
4. **Same iface on two k_fifos.** `cipher_iface_t`'s first field is `id`, not a
   reserved fifo node, yet the CONNECTED/DISCONNECTED events `k_fifo_put` the
   raw iface onto two different queues. When connect/disconnect overlap the two
   lists fight over that one word and corrupt. Fix: `k_fifo_alloc_put` (wraps
   the pointer in its own node) + a `CONFIG_HEAP_MEM_POOL_SIZE` for the nodes.
   (cipher controller.c)

## Remaining (characterised, not cipher-level)
- **Hard cap at ~6 consecutive reconnects.** UDP trace proves the service
  registry stays clean across reconnects (`used_services=1, endpoints=1`) and
  the math service is still advertised — so this is NOT a daemon/registry leak.
  It is a lower-level Zephyr net-stack resource limit: bumping
  `NET_MAX_CONN`/`NET_MAX_CONTEXTS` to 24 and `TCP_TIME_WAIT_DELAY` to 250 ms
  did not move the ceiling, pointing at net-pkt/context recycling under rapid
  connection cycling. Needs net-stack-level tuning, tracked separately.
- **Rapid back-to-back reconnects** (no gap) fail after conn 1: the daemon
  accepts the next client before it has finished tearing down the previous
  connection. Needs a "server ready" gate between accept cycles.

## Deterministic path for the benchmark
A single connection per board-boot is 100% deterministic (verified repeatedly:
1000 RPCs + large streams all succeed on one connection). The benchmark harness
runs its FULL suite (RPC latency loop + stream size sweep) on ONE persistent
connection per invocation, so it needs no reconnects and is fully repeatable.

## Verified interop (single connection, healthy board)
- Go stream -> board: 200000 B / 200 chunks reassembled, FNV-1a checksum MATCH.
- Go RPC  -> board: 1000 calls, 0 failures, every add() result correct.
- RPC latency (post-fix, single conn): min 6.5ms mean 7.0ms p99 7.3ms.
