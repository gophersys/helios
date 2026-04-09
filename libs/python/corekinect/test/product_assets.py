"""Product-level asset access — explicit dot-notation for all stages.

Provides typed, discoverable access to firmware assets across validation
and manufacturing stages:

    assets = ProductAssets.from_session(session_id, api_url, api_key)

    # Validation
    assets.validation.smoke.hex("app")
    assets.validation.fuota.hex("app")
    assets.validation.fuota.cfw("app")
    assets.validation.fuota.cfw("comms")

    # Manufacturing
    assets.manufacturing.hex("app")
    assets.manufacturing.hex("comms")

Each stage accessor lazily resolves artifacts from the backend API.
The test author never deals with pipeline IDs, labels, or storage keys.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from corekinect.errors import ConfigError
from corekinect.stages import Stage, StageType
from corekinect.utils import Logger

if TYPE_CHECKING:
    from corekinect.test.stage_assets import StageAssets

log = Logger(log_name="product_assets")


class StageAccessor:
    """Access hex/cfw/modem for a single stage's assets.

    Wraps StageAssets and provides shortcut methods that resolve
    the default build label for the stage automatically.

    For stages with multiple build labels (FUOTA), use .build(label)
    to access a specific one.
    """

    def __init__(self, stage_assets: "StageAssets"):
        self._assets = stage_assets

    def hex(self, role: str) -> str:
        """Default hex for this stage. Resolves MFG_BASE or the first hex-producing label."""
        build = self._default_hex_build()
        return build.hex(role)

    def cfw(self, role: str) -> str:
        """Default CFW for this stage. Resolves the first CFW-producing label."""
        build = self._default_cfw_build()
        return build.cfw(role)

    def build(self, label: str):
        """Access a specific build by label (e.g., 'FUT_VERBOSE_A')."""
        return self._assets.by_label(label)

    @property
    def builds(self):
        """All build assets for this stage."""
        return self._assets

    def _default_hex_build(self):
        """Find the default hex-producing build."""
        # Try MFG_BASE first (most common), then first available
        try:
            return self._assets.by_label("MFG_BASE")
        except Exception:
            pass
        labels = self._assets.available_labels()
        if not labels:
            raise ConfigError("No builds available for this stage")
        return self._assets.by_label(labels[0])

    def _default_cfw_build(self):
        """Find the default CFW-producing build."""
        labels = self._assets.available_labels()
        for label in labels:
            try:
                b = self._assets.by_label(label)
                b.cfws()  # Check if it has CFWs
                return b
            except Exception:
                continue
        raise ConfigError("No CFW-producing builds for this stage")

    def __repr__(self) -> str:
        return f"StageAccessor(stage={self._assets._stage!r})"


class ValidationAssets:
    """Dot-notation access to validation stage assets.

        assets.validation.smoke.hex("app")
        assets.validation.fuota.cfw("comms")
        assets.validation.fuota.build("FUT_VERBOSE_A").hex("app")
    """

    def __init__(self, loader):
        self._loader = loader
        self._cache: dict[str, StageAccessor] = {}

    def _get(self, stage: Stage) -> StageAccessor:
        key = stage.value
        if key not in self._cache:
            self._cache[key] = StageAccessor(self._loader(stage))
        return self._cache[key]

    @property
    def smoke(self) -> StageAccessor:
        return self._get(Stage.SMOKE)

    @property
    def driver(self) -> StageAccessor:
        return self._get(Stage.DRIVER)

    @property
    def integration(self) -> StageAccessor:
        return self._get(Stage.INTEGRATION)

    @property
    def regression(self) -> StageAccessor:
        return self._get(Stage.REGRESSION)

    @property
    def fuota(self) -> StageAccessor:
        return self._get(Stage.FUOTA)


class ManufacturingAssets(StageAccessor):
    """Dot-notation access to manufacturing assets.

        assets.manufacturing.hex("app")
        assets.manufacturing.hex("comms")
    """
    pass


class ProductAssets:
    """Top-level asset accessor for a product.

        assets = ProductAssets(loader_fn)
        assets.validation.fuota.hex("app")
        assets.manufacturing.hex("app")

    The loader function takes a Stage enum and returns a StageAssets instance.
    This is typically bound to a session/pipeline context by the test runner.
    """

    def __init__(self, loader):
        self._loader = loader
        self._validation = ValidationAssets(loader)
        self._manufacturing_cache: Optional[ManufacturingAssets] = None

    @property
    def validation(self) -> ValidationAssets:
        return self._validation

    @property
    def manufacturing(self) -> ManufacturingAssets:
        if self._manufacturing_cache is None:
            self._manufacturing_cache = ManufacturingAssets(
                self._loader(Stage.MANUFACTURING)
            )
        return self._manufacturing_cache
