from dataclasses import dataclass

# -------------------------------------------------
#                                            Config
# -------------------------------------------------
@dataclass
class ProviderConfig:
    # Where the server will look for assets for all of its components
    # that need configurations or firmware files (e.g. FluidNC)
    ASSETS_DIR: str
