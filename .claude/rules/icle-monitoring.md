# ICLE UART Monitoring

The ICLE (In-Circuit Loop-back Equipment) device is an ESP32-based power monitoring tool connected via UART for development/testing.

## Hardware Connection

- **UART**: `/dev/ttyUSB0` (or `/dev/ttyACM0` on some systems)
- **Baud rate**: 115200
- **SD Card**: 32GB attached for log storage

## Serial Monitoring Setup

Use tmux + Python for non-blocking serial monitoring:

```bash
# Start tmux session for ICLE monitoring
tmux new-session -d -s icle-monitor

# Run Python serial monitor (non-blocking)
tmux send-keys -t icle-monitor 'python3 -m serial.tools.miniterm /dev/ttyUSB0 115200' Enter

# Attach to view output
tmux attach -t icle-monitor

# Detach with Ctrl+B, D (leaves running in background)
```

### Quick Commands

```bash
# Check if ICLE tmux session exists
tmux has-session -t icle-monitor 2>/dev/null && echo "Running" || echo "Not running"

# Kill the monitoring session
tmux kill-session -t icle-monitor

# List all tmux sessions
tmux list-sessions
```

## Important Notes

- **Never use `screen` or direct serial access** - it locks the port and can cause issues
- **Always use tmux** so monitoring continues in background while you work
- Python miniterm releases port cleanly on Ctrl+C
- If port is busy: `fuser -k /dev/ttyUSB0` (kills process holding the port)

## SD Card Operations

### Format SD Card (from Zephyr shell after boot)

```
fs format fat /SD:
```

### Create Log Directories

```
fs mkdir /SD:/icle
fs mkdir /SD:/icle/logs
fs mkdir /SD:/icle/config
```

### List Files

```
fs ls /SD:/
fs ls /SD:/icle/logs
```

### Check Free Space

The device reports free space in heartbeats. From shell:
```
fs statvfs /SD:
```

## Log File Locations

| Location | Contents |
|----------|----------|
| `/SD:/icle/logs/` | Power sampling CSV/binary logs |
| `/SD:/icle/config.json` | Config backup (read-only copy of ZMS config) |

## Log File Format

**CSV format** (log_format=1):
```csv
timestamp_ms,voltage_mv,current_ma,power_mw
0,3300,150,495
10,3301,148,489
...
```

**Binary format** (log_format=0):
```
[4 bytes timestamp_ms][2 bytes voltage_mv][2 bytes current_ma][2 bytes power_mw]
```

## Device States

| State | LED Pattern | Description |
|-------|-------------|-------------|
| BOOT | Fast blink | Device initializing |
| CONFIG | Slow blink | Waiting for WiFi/config |
| ONLINE | Solid on | Connected, idle |
| LOGGING | Pulse | Actively sampling power |
| OTA | Alternating | Firmware update in progress |
| OFFLINE | Off | Not connected |

## Troubleshooting

### No UART Output

1. Check USB connection
2. Verify correct port: `ls /dev/ttyUSB* /dev/ttyACM*`
3. Check permissions: `sudo usermod -a -G dialout $USER` (then re-login)
4. Ensure device is powered (USB provides power)

### WiFi Connection Issues

From Zephyr shell:
```
wifi scan
wifi connect "SSID" 0 "password"
wifi status
```

### Reset Device

- **Soft reset**: Send `reboot` command via shell
- **Hard reset**: Press reset button on ESP32 board

### Check Device ID

From Zephyr shell:
```
icle config show
```

The device_id is stored in ZMS and persists across reboots.
