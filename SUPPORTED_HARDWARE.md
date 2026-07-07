# Supported hardware

cipher is an application-level networking library: it **consumes** connectivity,
it never seizes it. The link (WiFi, Ethernet, …) is owned by the Zephyr
connection manager; `cipher_daemon_start()` just waits for `NET_EVENT_L4_CONNECTED`.
The application is transport-agnostic — the *same* `main` and the *same* cipher
run on every target below, differing only by a board overlay. It coexists with
any other networking on the node.

## The application (identical everywhere)

```c
cipher_daemon_init(&cfg, &d);
cipher_register_local_services(&d, services, n);
cipher_daemon_start(&d);   // waits for the platform's link internally
```

No `#ifdef`, no WiFi/DHCP code, no credentials in the image.

## Verified targets

| Target | Transport | Connectivity | Status | Evidence (measured) |
|---|---|---|---|---|
| **STM32 Nucleo-H743ZI** | Ethernet (100 Mbit) | conn_mgr + DHCP | ✅ verified | RPC 200/200, **0.34 ms** mean; stream 256 KB–4 MB checksum-OK @ ~2.8 MB/s; on-device CPU/heap/stack sampling |
| **ESP32 DevKitC (orig. ESP32, rev v1.0)** | WiFi 2.4 GHz WPA2 | conn_mgr + `CONNECTIVITY_WIFI_MGMT` (iface lib) reading NVS creds | ✅ verified | associates from NVS on boot; RPC 100/100 @ ~12.5 ms; stream 256 KB checksum-OK @ ~144 KiB/s; double-sided via streamctl |
| **native_sim (64-bit host)** | loopback | direct | ✅ verified | two full daemons in one process (multi-instance) stream + checksum-OK |
| **Go (Linux/macOS)** | LAN | host OS | ✅ verified | wire-compatible reference impl; C↔Go RPC + stream interop, golden vectors |

## Notes per transport

- **Ethernet**: nothing to provision; `conn_mgr` + DHCP bring the link up, cipher
  waits for L4. (Nucleo slot 4's PHY is hardware-dead — confirmed by bare-metal
  MDIO scan — so only one H743 is an active Ethernet node.)
- **WiFi (ESP32)**: original ESP32 is **2.4 GHz only**. Credentials live in **NVS**,
  provisioned **once** with `samples/wifi_provision` (or `wifi cred add`); the
  application firmware carries no credentials and survives reflashes. Requires
  `west blobs fetch hal_espressif` once and `CONFIG_ESP32_USE_UNSUPPORTED_REVISION=y`
  for rev-v1.0 boards. Power-save is disabled on association (203 ms → ~7 ms RTT).

## Adding a target

1. Add a `boards/<board>.conf` overlay enabling the transport + `conn_mgr`
   (Ethernet: `NET_L2_ETHERNET` + DHCP; WiFi: `NET_L2_WIFI_MGMT` +
   `NET_CONNECTION_MANAGER_CONNECTIVITY_WIFI_MGMT` + `WIFI_CREDENTIALS` — the
   iface lib supplies the connectivity backend).
2. Build `samples/matrix_node` for it — no code changes.
3. Run the interop matrix; record the row here with its numbers.
