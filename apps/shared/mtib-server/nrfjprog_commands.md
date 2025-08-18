# nrfjprog Commands for Chip Detection

## Basic Commands

### 1. List all J-Link programmers
```bash
nrfjprog --ids
```

### 2. Get device version for a specific J-Link
```bash
nrfjprog --snr 821009540 --deviceversion # NRF52840_xxAA_REV3
nrfjprog --snr 821009544 --deviceversion # NRF9160_xxAA_REV2
```

### 3. Program modem firmware
```bash
nrfjprog \
--snr 821009544 \
--recover \
--program mfw_nrf9160_1.3.6.zip \
--verify mfw_nrf9160_1.3.6.zip \
--log \
&& \
nrfjprog \
--snr 821009544 \
--recover \
--program  Sigma5_9160_Eng_SSv0p9_343.hex \
--verify Sigma5_9160_Eng_SSv0p9_343.hex \
--log
```

### 3. Program CK app
```bash
nrfjprog \
--snr 821009540 \
--recover \
--program Sigma5_52840_Eng_343.hex \
--verify Sigma5_52840_Eng_343.hex \
--log
```

### 3. Check if device is connected (will show error if not)
```bash
nrfjprog --snr <SERIAL_NUMBER> --deviceversion
```

## Examples

### List all programmers first:
```bash
nrfjprog --ids
```
Output example:
```
123456789
987654321
```

### Check each programmer:
```bash
# Check first programmer
nrfjprog --snr 123456789 --deviceversion

# Check second programmer  
nrfjprog --snr 987654321 --deviceversion
```

## Expected Outputs

### Connected NRF9160:
```
nRF9160
```

### Connected NRF52840:
```
nRF52840_xxAA
```

### Connected NRF5340:
```
nRF5340_xxAA
```

### No device connected:
```
Error: Could not connect to device.
```

### Low voltage error:
```
Error: Low voltage detected.
```

## Quick Detection Script

```bash
#!/bin/bash
echo "Detecting connected chips..."

# Get all serial numbers
serials=$(nrfjprog --ids)

for serial in $serials; do
    echo "Checking J-Link $serial..."
    result=$(nrfjprog --snr $serial --deviceversion 2>&1)
    
    if [[ $result == *"nRF9160"* ]]; then
        echo "  ✅ NRF9160 connected"
    elif [[ $result == *"nRF52840"* ]]; then
        echo "  ✅ NRF52840 connected"
    elif [[ $result == *"nRF5340"* ]]; then
        echo "  ✅ NRF5340 connected"
    elif [[ $result == *"Low voltage"* ]]; then
        echo "  ⚠️  Low voltage detected"
    elif [[ $result == *"Error"* ]]; then
        echo "  ❌ No device connected"
    else
        echo "  ❓ Unknown device: $result"
    fi
done
``` 