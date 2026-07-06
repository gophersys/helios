# cipher-go

Go implementation of the CoreKinect **iface** (transport abstraction) and
**cipher** (networking protocol) libraries — wire-compatible with the Zephyr
firmware implementations (`gophersys/zephyr-iface`, `gophersys/zephyr-cipher`).

## Packages
- `iface` — socket transport with the same contract as the C library
  (create / connect / accept / send / recv with explicit timeout +
  connection-closed signaling / close). UART transport TBD.
- `cipher` — the protocol: 12-byte network-byte-order header with serdes-exact
  bit packing, version handshake, service-discovery broadcasts, a goroutine
  daemon (uplink/downlink roles), and an analyzer that logs decoded packets
  and ships ck_analyzer-schema JSON to a UDP collector.

## Commands
- `cmd/cipher-uplink` — client node: dials a downlink, handshakes, exchanges SD.
- `cmd/cipher-downlink` — server node: accepts uplinks, advertises services.

## Verified interop (2026-07-06)
Go uplink (Linux) ↔ Zephyr cipher downlink on a Nucleo-H743ZI over real
ethernet: handshake success, bidirectional SD broadcast, byte-exact decode
(`demo-echo` id 42 learned from device 0x0001). Golden-vector unit tests pin
the wire format against bytes captured live from the firmware.

## Test
    go test ./...
