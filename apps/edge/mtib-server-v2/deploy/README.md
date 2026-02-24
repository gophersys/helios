# MTIB Server V2 - Deployment

Multi-container architecture with Saleae Logic 2 sidecar support.

## Architecture

```
┌─────────────────────────────────────────────────┐
│  Pod / Docker Compose Stack                     │
│                                                  │
│  ┌──────────────────────┐  ┌─────────────────┐ │
│  │  mtib-server         │  │  logic2-sidecar │ │
│  │  (ARM64 native)      │  │  (x86_64+QEMU)  │ │
│  │                      │  │                 │ │
│  │  ✓ All handlers      │  │  ✓ Logic 2 app  │ │
│  │  ✓ Native perf       │  │  ✓ Port 10430   │ │
│  │  ✓ Port 50052    ────┼──┼─>Automation API │ │
│  └──────────────────────┘  └─────────────────┘ │
│           localhost:10430 (microsecond latency)  │
└──────────────────────────────────────────────────┘
```

**Key Features:**
- ✅ **Main server runs ARM64 native** - zero emulation overhead
- ✅ **Logic 2 sidecar runs x86_64** - only emulates what needs it
- ✅ **Graceful degradation** - works with or without Saleae hardware
- ✅ **Localhost communication** - ultra-low latency gRPC

## Building

### Build Both Containers (Recommended)

```bash
# Build main server (ARM64) + Logic 2 sidecar (x86_64)
nx run mtib-server-v2:build-all -c production

# Push both to registry
nx run mtib-server-v2:push-all
```

### Build Individually

```bash
# Main server only (ARM64)
nx run mtib-server-v2:containerize -c production

# Logic 2 sidecar only (x86_64)
nx run mtib-server-v2:containerize-logic2 -c production
```

## Running Locally

```bash
# Start both containers with docker-compose
nx run mtib-server-v2:start

# Check status
docker compose -f apps/edge/mtib-server-v2/deploy/docker-compose.yaml ps

# View logs
docker compose -f apps/edge/mtib-server-v2/deploy/docker-compose.yaml logs -f

# Stop
nx run mtib-server-v2:stop
```

## Kubernetes Deployment

The pod spec automatically includes both containers. Update your deployment YAML:

```yaml
apiVersion: v1
kind: Pod
spec:
  containers:
  # Logic 2 sidecar (starts first, provides automation API)
  - name: logic2-sidecar
    image: containers.ad.corekinect.com/logic2-sidecar:latest
    imagePullPolicy: Always
    securityContext:
      privileged: true
    volumeMounts:
    - name: usb
      mountPath: /dev/bus/usb
    env:
    - name: DISPLAY
      value: ":99"

  # Main MTIB server (connects to sidecar's port 10430)
  - name: mtib-server
    image: containers.ad.corekinect.com/concord-mtib-server-v2:latest
    imagePullPolicy: Always
    ports:
    - containerPort: 50052
      hostPort: 50052
    # ... rest of config ...

  volumes:
  - name: usb
    hostPath:
      path: /dev/bus/usb
```

## Provider Detection Flow

The server automatically detects available analyzers on startup:

1. **Try Saleae Provider** → Connect to localhost:10430
   - ✅ If Logic 2 sidecar is running → Use Saleae provider
   - ❌ If connection fails → Skip Saleae, continue

2. **Fallback to Simulation** → Always available
   - No external dependencies
   - Full feature set with synthetic data

**Example logs:**
```
# With Logic 2 sidecar running:
Logic analyzer provider available: Saleae
Logic analyzer provider available: Simulation
Logic analyzer providers available: ['saleae', 'simulation']

# Without Logic 2 (sidecar not running):
Logic analyzer provider available: Simulation
Logic analyzer providers available: ['simulation']
```

## Performance

### Main Server (ARM64 Native)
- Zero emulation overhead
- Full native performance for:
  - Power control
  - UART handling
  - GPIO operations
  - I2C/SPI
  - Debug operations

### Logic 2 Sidecar (x86_64 + QEMU)
- ~20-30% CPU overhead from emulation
- **Still excellent for target use cases:**
  - I2C: 100-400 kHz (1000x slower than capture rate)
  - SPI: 1-10 MHz (10-100x slower)
  - UART: 9600-115200 baud (10000x slower)
- Emulation overhead is negligible compared to signal speeds

## Troubleshooting

### Saleae Not Detected

**Check if sidecar is running:**
```bash
docker ps | grep logic2
# OR
kubectl logs <pod-name> -c logic2-sidecar
```

**Check automation API:**
```bash
curl http://localhost:10430
# Should return gRPC endpoint info
```

**Check USB device:**
```bash
lsusb | grep Saleae
# Should show: Saleae, Inc. Logic8 (or Logic Pro)
```

### Sidecar Won't Start

**Common issues:**
1. USB device not passed through → Check volumes/volumeMounts
2. QEMU not available → Ensure buildx/binfmt installed
3. Port 10430 already in use → Check for other Logic 2 instances

**Verify QEMU support:**
```bash
docker run --rm --platform linux/amd64 ubuntu:22.04 uname -m
# Should output: x86_64 (even on ARM64 host)
```

## Development

### Testing Without Saleae Hardware

The simulation provider is always available:

```python
client.analyzer_capture_start(
    channels=[0, 1, 2, 3],
    sample_rate_hz=1_000_000,
    prefer_provider='simulation'  # Force simulation
)
```

### Testing With Saleae Hardware

1. Ensure sidecar is running
2. Connect Saleae device via USB
3. Server will auto-detect and prefer Saleae over simulation

```python
# Auto-selects best available provider
client.analyzer_capture_start(
    channels=[0, 1, 2, 3],
    sample_rate_hz=1_000_000,
    prefer_provider='auto'  # Default
)
```

## Build Details

**Main Server (Dockerfile):**
- Base: Ubuntu 22.04 ARM64
- Python 3.10
- J-Link tools
- nrfjprog
- Platform: linux/arm64

**Logic 2 Sidecar (Dockerfile.logic2):**
- Base: Ubuntu 22.04 x86_64
- Logic 2 AppImage extracted
- Xvfb for headless operation
- Platform: linux/amd64 (uses QEMU on ARM64)

## CI/CD Integration

```bash
# In your CI pipeline:
nx run mtib-server-v2:build-all -c production
nx run mtib-server-v2:push-all

# Deploy to Kubernetes
kubectl delete pod <mtib-pod>  # Force restart with new images
```
