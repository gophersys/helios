# `libs/embedded` — knowledge

Zephyr-RTOS building blocks shared across CoreKinect firmware projects:
board definitions, helper libraries. Today it carries two pieces: a Zephyr
board family (`ck_board`) and a WiFi helper library (`ck_wifi`).

Refresh this file when: a board overlay or revision is added; a new helper
library is added under `libs/embedded/`; the Zephyr module manifest
(`zephyr/module.yml`) is changed; consumer firmware repos add a new
dependency from this tree.

## Location

```
libs/embedded/
├── ck_board/
│   └── testing/
│       └── icle_v1_0/        # ESP32-based board for ICLE power-monitor firmware
│           ├── board.cmake
│           ├── board.yml
│           ├── Kconfig.defconfig
│           ├── Kconfig.icle_v1_0
│           ├── icle_v1_0-pinctrl.dtsi
│           ├── icle_v1_0_procpu.dts
│           ├── icle_v1_0_procpu.yaml
│           └── icle_v1_0_procpu_defconfig
└── ck_wifi/                  # Zephyr WiFi helper library
    ├── ck_wifi.c
    ├── ck_wifi.h
    ├── CMakeLists.txt        # standalone library build
    ├── Kconfig               # CK_WIFI menuconfig
    └── zephyr/
        ├── CMakeLists.txt    # zephyr_library wrapper
        └── module.yml        # Zephyr module manifest
```

## What it covers

- **Zephyr board definitions** under `ck_board/`. Each board is a normal
  Zephyr board layout (DTS, defconfig, Kconfig, pinctrl, board.yml). The
  `testing/` subdir holds boards used only by lab/test firmware (vs.
  product firmware boards which live in each firmware repo's own
  `ck_boards/` tree).
- **Helper libraries** that are firmware-agnostic and shared between
  firmware projects. `ck_wifi` is the first.

## What's intentionally outside

- **Product board definitions for Alpha / Sigma5 / Theta.** Those live in
  each product's firmware repo under `ck_boards/current/boards/corekinect/`
  (e.g. `firmware/alpha_fw/ck_boards/`), not here. This tree only carries
  shared/lab boards.
- **Sigma vendor drivers** (e.g. `accel_drv`, `lsm6dso_drv`). Those live
  in `firmware/<product>_fw/` repos with their own `west` manifest.
- **Application code.** ICLE firmware itself lives at
  `apps/firmware/icle/`; this directory only ships the *board* that ICLE
  builds against.

## Consumers

| Consumer | Pulls in |
|---|---|
| `apps/firmware/icle/` | `ck_board/testing/icle_v1_0/` board target + `ck_wifi/` (WiFi connectivity for the ESP32). |
| `firmware/alpha_fw/`, `firmware/sigma5_fw/`, `firmware/theta_fw/` | Today: nothing direct from `libs/embedded`. (Their boards live in-repo under `ck_boards/`.) Shared helper code lands here when promoted out of a single firmware repo. |
| `firmware/*_mfg_fw/` | Same as above. |

The Zephyr module manifest at `ck_wifi/zephyr/module.yml` is the binding —
adding `ck_wifi` (and the parent `libs/embedded`) to a firmware project's
`west.yml` as a Zephyr module makes the library available via Kconfig
(`CONFIG_CK_WIFI=y`).

## ck_board/testing/icle_v1_0

ESP32-WROOM-32UE board variant. Targets `SOC_ESP32_WROOM_32UE` via the SoC
series `esp32`. Standard Zephyr board layout:

| File | Role |
|---|---|
| `board.yml` | `name: icle_v1_0`, `vendor: corekinect`, `socs: [esp32]`. |
| `board.cmake` | Includes `${ZEPHYR_BASE}/boards/common/esp32.board.cmake`. |
| `icle_v1_0_procpu.dts` | DTS for the protocol CPU core. |
| `icle_v1_0-pinctrl.dtsi` | Pin mux. |
| `icle_v1_0_procpu_defconfig` | Default Kconfig. |
| `icle_v1_0_procpu.yaml` | Test/twister metadata. |
| `Kconfig.icle_v1_0` | `BOARD_ICLE_V1_0` symbol, selects the ESP32 SoC option. |
| `Kconfig.defconfig` | Board-level Kconfig defaults. |

Build target name (passed to `west`): `icle_v1_0/esp32/procpu`.

## ck_wifi

Thin wrapper over Zephyr's `WIFI` + `NET_L2_WIFI_MGMT` subsystems. Provides
an async connect with a callback, a blocking wait helper, and a status
enum. Used by the ICLE firmware for STA-mode connectivity.

Public API (from `ck_wifi.h`):

| Symbol | Purpose |
|---|---|
| `enum ck_wifi_status` | `DISCONNECTED / CONNECTING / CONNECTED / ERROR`. |
| `ck_wifi_callback_t` | Callback signature for connect events. |
| `int ck_wifi_init(void)` | Init the WiFi subsystem. |
| `int ck_wifi_connect(ssid, psk, callback, user_data)` | Connect. NULL ssid/psk = use Kconfig values. |
| `int ck_wifi_disconnect(void)` | Disconnect. |
| `enum ck_wifi_status ck_wifi_get_status(void)` | Current status. |
| `int ck_wifi_wait_connected(k_timeout_t)` | Block until connected or timeout. |
| `struct net_if *ck_wifi_get_iface(void)` | Net iface handle (NULL if not init). |

Kconfig (`libs/embedded/ck_wifi/Kconfig`):

```
CK_WIFI                       bool, menuconfig, depends on WIFI && NET_L2_WIFI_MGMT
  CK_WIFI_SSID                string
  CK_WIFI_PSK                 string
  CK_WIFI_CONNECT_TIMEOUT_MS  int, default 30000
  CK_WIFI_LOG_LEVEL           int, default 3 (inf)
```

Zephyr module wiring (`zephyr/module.yml`):

```yaml
build:
  cmake: .
  kconfig: ../Kconfig
```

The inner `zephyr/CMakeLists.txt` calls `zephyr_library()` and adds
`../ck_wifi.c` only when `CONFIG_CK_WIFI` is set.

## How to add a new board overlay

A "board overlay" in the Zephyr sense (a `.overlay` file that tweaks an
existing board for an application) belongs in the *consumer* firmware
repo, not here.

Adding a brand new **board** (a new ICLE revision, a new lab fixture
target) follows the standard Zephyr layout:

1. `mkdir libs/embedded/ck_board/testing/<board_name>/`.
2. Copy the `icle_v1_0/` files as a starting template.
3. Edit `board.yml` (name, socs), `board.cmake` (include path for the SoC
   family), DTS + pinctrl + defconfig, and the two Kconfig files.
4. Update `Kconfig.<board_name>` so its symbol matches `BOARD_<NAME_UPPER>`.
5. Build target string becomes `<board_name>/<soc>/<core>` (or just
   `<board_name>/<soc>` for single-core SoCs).
6. Add a row to this knowledge file's structure block.

A board for a **production** product (Alpha, Sigma5, Theta) does not go
here — it goes in that firmware repo's `ck_boards/` tree. Production
firmware repos pin their own boards.

## How to add a new helper library

1. `mkdir libs/embedded/<libname>/` with the C/H sources at the root.
2. Add a top-level `Kconfig` declaring a `menuconfig <LIBNAME>` symbol.
3. Add a `zephyr/` subdir with:
   - `module.yml` pointing at `cmake: .` and `kconfig: ../Kconfig`.
   - `CMakeLists.txt` calling `zephyr_library()` guarded by your config.
4. Add it to the `west.yml` of each firmware repo that should pick it up.
5. Document the public API + Kconfig surface in this file.

## Common failure modes

- **`west build` fails with "board not found: icle_v1_0".** The firmware
  repo's `west.yml` doesn't reference `libs/embedded` as a Zephyr module,
  so the board search path doesn't include this tree. Add an entry under
  `manifest.projects` pointing here.
- **`CONFIG_CK_WIFI=y` but the library doesn't link.** The Zephyr module
  is registered but `WIFI` / `NET_L2_WIFI_MGMT` are not enabled. Check
  the board's defconfig — `ck_wifi` depends on both.
- **`ck_wifi_init` returns -ENODEV.** The board has no WiFi-capable SoC
  configured at the DT level. ESP32 boards expose it via the `esp32-wifi`
  binding; other SoCs need their own.
- **Board DTS errors after an SDK bump.** Zephyr's board layout
  conventions (`board.yml`, hwmv2) change between LTS releases. Re-check
  the `boards/common/<soc>.board.cmake` include in `board.cmake` and the
  shape of `board.yml`.
- **Two firmware repos drift on the same ck_wifi version.** `libs/embedded`
  is a monorepo path, not a versioned artifact. Each firmware repo's
  `west.yml` pins a commit of the parent `concord` repo (or this tree
  directly). Bumps need to land in each consumer's manifest.

## Related knowledge

- [`../glossary.md`](../glossary.md) — Verdin, MTIB, DUT, ICLE
  definitions.
- [`../apps/firmware/icle.md`](../apps/firmware/icle.md) — ICLE firmware
  consumer.
- [`../../../firmware/`](../../../firmware/) (sibling repos) — each
  product's firmware repo declares its own boards; this tree is shared
  infrastructure.
