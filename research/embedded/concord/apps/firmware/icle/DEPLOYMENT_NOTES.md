# ICLE Deployment Notes

## Current Status

- **Firmware**: Built successfully (`build/zephyr/zephyr.bin`)
- **Backend API**: Running locally on port 9001
- **Serial Device**: Not connected - need to connect ICLE via USB

## WiFi Credentials (Updated)

```
SSID: ICLE_HERE
Password: icle4testing
```

## Kubernetes Deployment (IMPORTANT)

For the ICLE device to communicate with the backend over the network, you may need to deploy the HTTP API to Kubernetes:

```bash
# Build and deploy to staging
./deploy/ctl.sh staging deploy

# Or for local K3s cluster
kubectl apply -f deploy/helm/...
```

The backend must be accessible on the network for the ICLE heartbeat to work.

## Flashing the Firmware

When the ICLE is connected via USB:

```bash
# Check for serial device
ls /dev/ttyUSB* /dev/ttyACM*

# Flash firmware
cd /workspaces/concord/apps/firmware/icle
west flash

# Or manually with esptool
esptool.py --chip esp32 --port /dev/ttyUSB0 write_flash 0x0 build/zephyr/zephyr.bin
```

## Serial Monitoring

Use tmux for non-blocking serial monitoring:

```bash
tmux new-session -d -s icle-monitor 'python3 -m serial.tools.miniterm /dev/ttyUSB0 115200'
tmux attach -t icle-monitor
# Ctrl+B, D to detach
```

## Backend URL Configuration

Default backend URL in firmware: `http://concord.ad.corekinect.com/api`

Update in `include/icle/config.h`:
```c
#define ICLE_DEFAULT_BACKEND_URL "http://YOUR-SERVER:9001"
```

Or set at runtime via Zephyr shell:
```
icle config set backend_url http://YOUR-SERVER:9001
```

## Testing the Heartbeat

```bash
# Test heartbeat endpoint (no auth required)
curl -X POST http://localhost:9001/v2/icle/heartbeat \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "ICLE-TEST-001",
    "firmware_version": "1.0.0",
    "status": "online"
  }'
```
