# esp32_wifi_node

A cipher daemon running over **WiFi** on an ESP32 (original, rev v1.0). Associates
to a 2.4 GHz WPA2 AP, disables WiFi power-save, waits for DHCP, then runs a cipher
stream-sink node so a peer can stream to it over WiFi. Reports completed streams
(bytes/chunks/KiB-s/checksum) over UDP to the node collector.

## Repeatable build+flash (survives a continuous reflash loop)

WiFi credentials are NOT committed and do NOT need re-injecting per flash. They
live once in a PVC-backed overlay on the devbox and a helper wires them into
every build:

    # one-time (already done): /workspace/ck-wifi.conf  (mode 600, on the PVC)
    #   CONFIG_WIFI_SSID="..."   CONFIG_WIFI_PSK="..."   CONFIG_ESP32_USE_UNSUPPORTED_REVISION=y

    # every reflash — one command:
    /workspace/ck-esp32.sh /workspace/ck-libs/cipher/samples/esp32_wifi_node /dev/ttyUSB0

Prerequisites (one-time on the devbox): `west blobs fetch hal_espressif` (the WiFi
driver needs the proprietary Espressif blobs).

## WiFi robustness

- **Board rev v1.0** → `CONFIG_ESP32_USE_UNSUPPORTED_REVISION=y` (in the overlay).
- **Power-save disabled** at association → LAN RTT drops ~203 ms → ~7 ms.
- **Exponential-backoff retry**: the first association after a boot/reflash
  routinely returns `CONN_TIMEOUT` (status 3); the node retries with 5/10/15/20/25/30s
  backoff so it always comes up without hammering (and rate-limiting) the AP.
- **DRAM**: memory trimmed to fit the ESP32 (WiFi ~50 KB + cipher static heaps);
  heap pool 16 KB, net buffers halved.

Verified: Go client streamed 256 KB over WiFi, ESP32 reassembled, checksum OK
(~144 KiB/s); WiFi comes up on every fresh flash via backoff retry.
