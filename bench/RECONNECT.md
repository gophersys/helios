# Reconnect investigation

## Symptom
A **freshly-booted** board serves the FIRST client connection perfectly every
time (deterministic). The **Nth** connection (after a client disconnects and a
new one connects) fails: the client connects + handshakes OK but never learns
the board's service (no SD), so RPC/stream can't route.

## Method
The 115200 UART **drops lines under load**, so board-side tracing is unreliable
over serial. Added a UDP debug channel (`src/interface/netdbg.*`, `-DCK_NETDBG`)
that ships trace strings to a node-side collector — reliable. Reachability was
also pinned with a static ARP entry to remove L2 noise.

## Root causes found + fixed
1. **Listening-socket churn.** `socket_close()` closed the server's *listening*
   socket on every client disconnect, and the connection thread re-created it
   each reconnect. The STM32 has a tiny socket/context pool; the churn starved
   it. **Fixed:** the listening socket is created once and persists; only the
   per-connection client socket is recycled.
2. **Send thread parked on K_FOREVER.** The send thread polled its queues with
   `K_FOREVER`. A disconnect sets `iface->connected=false` but queues nothing to
   wake the poll, so the thread never re-armed (`k_sem_take`) for the next
   client. **Fixed:** poll with a 200 ms timeout and re-check `connected`.

## Open item
With reliable UDP tracing, on the 2nd connection the board **does** `ACCEPT`,
**does** run `conn_event` and **does** `BCAST` the SD, and the send thread
**does** re-arm and dequeue/send — yet the client still doesn't receive the SD.
Leading hypothesis: the SD send lands on a stale/mismatched socket fd after the
accept()/close() recycle on the persistent listener, or an fd-reuse aliasing
between the closed conn-1 client socket and the conn-2 accept. Needs a couple
more traced iterations on a STABLE board.

## Hardware caveat
After many hours of flash/reset cycles the board's ethernet became
intermittently unreachable (ARP fails even with a static entry) — consistent
with a marginal PHY (slot 4's PHY is already dead). Reliable reconnect debugging
needs a power-cycled/known-good board.

## Deterministic path today
A single connection per board-boot is 100% deterministic. The benchmark harness
therefore does its FULL suite (RPC latency loop + stream size sweep) on ONE
persistent connection per invocation, which needs no reconnects.

## Measured so far (single connection, healthy board)
- Go stream -> board: 200000 B / 200 chunks reassembled, FNV-1a checksum MATCH.
- Go RPC  -> board: 1000 calls, 0 failures; latency min 34.2ms mean 35.0ms
  p99 41.4ms — dominated by TCP Nagle + delayed-ACK (client-side TCP_NODELAY is
  the fix; Zephyr supports it, verified it does NOT break the server when set on
  the client connect() path only).
