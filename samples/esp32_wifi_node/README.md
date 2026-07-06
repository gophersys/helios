# esp32_wifi_node

A cipher daemon running over **WiFi** on an ESP32 (original, rev v1.0). Associates
to a 2.4 GHz WPA2 AP, waits for DHCP, then runs a cipher stream-sink node so a peer
can stream to it over WiFi. Reports completed streams (bytes/chunks/KiB-s/checksum)
over UDP to the node collector.

WiFi credentials are NOT committed. Supply them at build time via an overlay:

    # secret.conf (do not commit)
    CONFIG_WIFI_SSID="your-ssid"
    CONFIG_WIFI_PSK="your-psk"
    CONFIG_ESP32_USE_UNSUPPORTED_REVISION=y   # these boards are rev v1.0

    west build -b esp32_devkitc/esp32/procpu . -- -DEXTRA_CONF_FILE=secret.conf

Verified: Go client streamed 256 KB over WiFi, ESP32 reassembled with checksum OK
(~144 KiB/s).
