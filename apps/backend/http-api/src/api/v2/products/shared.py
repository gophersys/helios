from src.services.storage.client import presigned_get_url

ALLOWED_FIRMWARE_EXTENSIONS = {"zip", "hex", "ckbin", "bin"}

MIME_TYPES = {
    "zip": "application/zip",
    "hex": "application/octet-stream",
    "ckbin": "application/octet-stream",
    "bin": "application/octet-stream",
}

# ── Supported Chipsets Configuration ─────────────────────
# Maps chipset (board family) to its available target MCUs.
# Update this when new chipsets or SoCs are introduced.
SUPPORTED_CHIPSETS = {
    "Sigma5 Cx": {
        "targetMcus": ["nRF9160", "nRF52840"],
    },
    "Alpha Ax": {
        "targetMcus": ["nRF9160", "nRF52840"],
    },
    "Alpha Bx": {
        "targetMcus": ["nRF9151", "nRF52840"],
    },
    "Theta Cx": {
        "targetMcus": ["nRF9151", "nRF52840"],
    },
}

SUPPORTED_SOCS = sorted(set(
    mcu
    for config in SUPPORTED_CHIPSETS.values()
    for mcu in config["targetMcus"]
))


def presigned_url(key: str | None, download_filename: str | None = None) -> str | None:
    return presigned_get_url(key, download_filename=download_filename)
