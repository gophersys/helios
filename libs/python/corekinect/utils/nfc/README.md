# NFC

A simple NFC DeviceID reader to interface with the ACR1252. This is not a complete driver implementation.

If expansion is needed, see the [ACR125_API](https://www.acs.com.hk/download-manual/6402/API-ACR1252U-1.17.pdf)


Example usage:
```python
import sys
from corekinect.utils.nfc import NfcReader

try:
    with NfcReader(
        prepend_0x=False,
        console=True,
        clipboard=False,
        keyboard=False,
        file_path="sigma5_fuota_to_prod.txt",
    ) as reader:
        for device_id in reader.scan():
            pass
except KeyboardInterrupt:
    print("\nExiting NFC reader.")
    sys.exit(0)

```
