"""Purpose-built test stubs for framework unit tests.

These are not mocks — they're configurable fake implementations with
event recording, following the ProgrammableFixture pattern. They let
us unit test StageAssets, FuotaOrchestrator, and BootVersionDetector
without network calls, hardware, or CoreCloud connectivity.

Usage:
    resolver = StubArtifactResolver()
    resolver.add_build("smoke_app_debug", version="0.8.3", variant="debug", track="BM")
    resolver.add_build("smoke_comms_debug", version="0.8.3", variant="debug", track="BM")

    assets = StageAssets(resolver, stage="smoke", strict=False)
    app_hex = assets.hex("app", "debug")  # resolves smoke_app_debug
"""

import os
import shutil
import struct
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from unittest.mock import MagicMock

from corekinect.test.artifact_resolver import BuildManifest, ManifestTarget


# =============================================================================
# Stub ArtifactResolver
# =============================================================================


@dataclass
class _StubBuild:
    """Internal build state for StubArtifactResolver."""

    label: str
    version: str
    variant: str
    track: str
    status: str = "SUCCESS"
    app_targets: Optional[List[Dict[str, Any]]] = None
    modem_firmware: Optional[str] = None


class StubArtifactResolver:
    """Drop-in stub for ArtifactResolver.

    Stores builds in-memory. Generates fake hex/cfw files on disk
    when get_artifact/get_artifacts is called (so file existence
    checks pass in test code).

    Args:
        product: Product name for manifests.
        board: Board name for manifests.
    """

    # Default Alpha targets if none specified
    DEFAULT_TARGETS = [
        {
            "role": "app",
            "processor": "nrf52840",
            "appId": 109,
            "hostType": "HOST_TYPE_NRF52840",
            "jlinkFamily": "NRF52",
            "plaintextHex": None,  # Filled per build
            "encryptedCfw": None,
        },
        {
            "role": "comms",
            "processor": "nrf9151",
            "appId": 108,
            "hostType": "HOST_TYPE_NRF9151",
            "jlinkFamily": "NRF91",
            "plaintextHex": None,
            "encryptedCfw": None,
        },
    ]

    def __init__(self, product: str = "alpha", board: str = "alpha_b0"):
        self._product = product
        self._board = board
        self._builds: Dict[str, _StubBuild] = {}
        self._tmp_dir = tempfile.mkdtemp(prefix="stub_resolver_")
        self._events: List[Dict[str, Any]] = []
        self._modem_trigger_path: Optional[str] = None
        self._modem_asset_set_path: Optional[str] = None

    @property
    def builds(self) -> Dict[str, Any]:
        """Expose builds dict matching ArtifactResolver.builds interface."""
        result = {}
        for label, build in self._builds.items():
            obj = MagicMock()
            obj.status = build.status
            obj.matrixLabel = label
            result[label] = obj
        return result

    def add_build(
        self,
        label: str,
        version: str = "0.8.3",
        variant: str = "debug",
        track: str = "BM",
        status: str = "SUCCESS",
        targets: Optional[List[Dict[str, Any]]] = None,
        has_cfw: bool = True,
        modem_firmware: Optional[str] = None,
    ) -> "StubArtifactResolver":
        """Add a build to the stub.

        Args:
            label: Matrix label (e.g., "smoke_app_debug").
            version: Version string (e.g., "0.8.3").
            variant: Build variant ("debug", "release", "mfg").
            track: CFW track string ("BM", "B", "P", etc.).
            status: Build status ("SUCCESS", "FAILED", "CACHED").
            targets: Custom targets list. Defaults to app+comms.
            has_cfw: Whether to generate CFW artifact paths.
            modem_firmware: Optional modem firmware path.

        Returns:
            Self for chaining.
        """
        if targets is None:
            targets = []
            for default in self.DEFAULT_TARGETS:
                t = dict(default)
                app_id = t["appId"]
                t["plaintextHex"] = f"hex/{app_id}.{version}-{track}.hex"
                if has_cfw:
                    t["encryptedCfw"] = f"cfw/{app_id}.{version}-{track}.cfw"
                targets.append(t)

        self._builds[label] = _StubBuild(
            label=label,
            version=version,
            variant=variant,
            track=track,
            status=status,
            app_targets=targets,
            modem_firmware=modem_firmware,
        )
        return self

    def get_manifest(self, label: str):
        """Return a BuildManifest-like object for the given label."""
        self._events.append({"action": "get_manifest", "label": label})
        build = self._require_build(label)

        targets = [ManifestTarget.from_dict(t) for t in build.app_targets]

        return BuildManifest(
            schema_version=1,
            product=self._product,
            board=self._board,
            version=build.version,
            variant=build.variant,
            track=build.track,
            release_track="bench",
            ncs_version="v2.9.0",
            commit_sha="abc1234",
            branch="main",
            built_at="2026-03-31T00:00:00Z",
            targets=targets,
            modem_firmware=None,
            corecloud={"deviceTypeId": 2, "deviceVariantId": 3, "apiEnv": "VAL_1_0"},
        )

    def get_version(self, label: str) -> str:
        """Return version string for the given label."""
        self._events.append({"action": "get_version", "label": label})
        return self._require_build(label).version

    def get_artifact(
        self, label: str, role: str, artifact_type: str
    ) -> Optional[str]:
        """Create a temp file and return its path (simulates download)."""
        self._events.append({
            "action": "get_artifact",
            "label": label,
            "role": role,
            "artifact_type": artifact_type,
        })
        build = self._require_build(label)

        # Find matching target
        for t in build.app_targets:
            if t["role"] == role:
                filename = t.get(
                    "plaintextHex" if artifact_type == "plaintextHex" else "encryptedCfw"
                )
                if filename:
                    path = os.path.join(self._tmp_dir, label, filename)
                    os.makedirs(os.path.dirname(path), exist_ok=True)
                    if not os.path.exists(path):
                        if artifact_type == "encryptedCfw":
                            self._write_stub_cfw(path, build, t)
                        else:
                            Path(path).write_bytes(b"\x00" * 64)
                    return path
        return None

    def get_artifacts(self, label: str, artifact_type: str) -> List[str]:
        """Return all artifacts of a type for all targets."""
        self._events.append({
            "action": "get_artifacts",
            "label": label,
            "artifact_type": artifact_type,
        })
        paths = []
        build = self._require_build(label)
        for t in build.app_targets:
            key = "plaintextHex" if artifact_type == "plaintextHex" else "encryptedCfw"
            filename = t.get(key)
            if filename:
                path = os.path.join(self._tmp_dir, label, filename)
                os.makedirs(os.path.dirname(path), exist_ok=True)
                if not os.path.exists(path):
                    if artifact_type == "encryptedCfw":
                        self._write_stub_cfw(path, build, t)
                    else:
                        Path(path).write_bytes(b"\x00" * 64)
                paths.append(path)
        return paths

    def get_targets(self, label: str) -> list:
        """Return ManifestTarget list for the given label."""
        return self.get_manifest(label).targets

    def get_modem_firmware(self, label: str) -> Optional[str]:
        """Return modem firmware path if available."""
        self._events.append({"action": "get_modem_firmware", "label": label})
        build = self._require_build(label)
        return build.modem_firmware

    def get_modem_firmware_from_trigger(self) -> Optional[str]:
        """Return modem firmware from trigger data."""
        self._events.append({"action": "get_modem_firmware_from_trigger"})
        return self._modem_trigger_path

    def get_modem_from_asset_set(self) -> Optional[str]:
        """Return modem firmware from AssetSet reference."""
        self._events.append({"action": "get_modem_from_asset_set"})
        return self._modem_asset_set_path

    def cleanup(self) -> None:
        """Remove temp files."""
        if os.path.exists(self._tmp_dir):
            shutil.rmtree(self._tmp_dir, ignore_errors=True)

    def _require_build(self, label: str) -> _StubBuild:
        """Get build or raise."""
        if label not in self._builds:
            raise KeyError(
                f"Build '{label}' not found in stub. "
                f"Available: {list(self._builds.keys())}"
            )
        return self._builds[label]

    def _write_stub_cfw(
        self, path: str, build: _StubBuild, target: Dict[str, Any]
    ) -> None:
        """Write a minimal valid CFW header for parse_cfw_header() tests."""
        parts = build.version.split(".")
        major, minor, build_num = int(parts[0]), int(parts[1]), int(parts[2])
        app_id = target["appId"]

        # Build flags byte
        track_map = {"B": 0, "E": 1, "P": 2}
        track_char = build.track[0] if build.track else "B"
        release_track = track_map.get(track_char, 0)
        is_mfg = "M" in build.track
        is_debug = "D" in build.track

        flags = (release_track << 1)
        if is_mfg:
            flags |= 0x01
        if is_debug:
            flags |= 0x08

        # Pack 23-byte CFW header
        header = struct.pack(
            ">HQHBHHHi",
            1,           # file version
            0,           # time created
            app_id,
            flags,
            major,
            minor,
            build_num,
            1024,        # image length
        )
        # Add some fake image data
        data = header + b"\xFF" * 1024

        Path(path).write_bytes(data)


# =============================================================================
# Stub FuotaClient
# =============================================================================


class StubFuotaClient:
    """Drop-in stub for FuotaClient.

    Records all API calls and returns configurable responses.
    No network access.

    Usage:
        client = StubFuotaClient()
        client.set_plan_id(42)

        orchestrator = FuotaOrchestrator(client)
        plan_id = orchestrator.create_and_assign_plan(...)
        assert plan_id == 42
        assert client.events[-1]["action"] == "assign_device"
    """

    def __init__(self):
        self.events: List[Dict[str, Any]] = []
        self._plan_id: int = 1
        self._progress_responses: List[Dict[str, Any]] = []
        self._progress_index: int = 0
        self._registered_devices: Set[str] = set()
        self._assigned_devices: Dict[str, int] = {}  # device_id -> plan_id
        self._device_status: Dict[str, Dict[str, Any]] = {}

    def set_plan_id(self, plan_id: int) -> "StubFuotaClient":
        """Set the plan ID returned by create_plan()."""
        self._plan_id = plan_id
        return self

    def set_progress_sequence(
        self, responses: List[Dict[str, Any]]
    ) -> "StubFuotaClient":
        """Set the sequence of progress responses returned by polling."""
        self._progress_responses = responses
        self._progress_index = 0
        return self

    def ensure_device_registered(
        self, device_id: str, device_type_id: int, device_variant_id: int
    ) -> None:
        """Record registration."""
        self.events.append({
            "action": "ensure_device_registered",
            "device_id": device_id,
            "device_type_id": device_type_id,
            "device_variant_id": device_variant_id,
        })
        self._registered_devices.add(device_id)

    def upload_cfw(self, cfw_path: str) -> None:
        """Record upload."""
        self.events.append({"action": "upload_cfw", "path": cfw_path})

    def create_plan(
        self,
        stages: List[Dict[str, Any]],
        description: str,
        device_type_id: int,
        device_variant_id: int,
    ) -> int:
        """Record plan creation, return configured plan_id."""
        self.events.append({
            "action": "create_plan",
            "stages": stages,
            "description": description,
            "device_type_id": device_type_id,
            "device_variant_id": device_variant_id,
        })
        return self._plan_id

    def assign_device(
        self,
        plan_id: int,
        device_ids: List[str],
        max_stage: int,
        enable: bool,
        device_type_id: int,
        device_variant_id: int,
    ) -> None:
        """Record assignment."""
        self.events.append({
            "action": "assign_device",
            "plan_id": plan_id,
            "device_ids": device_ids,
            "max_stage": max_stage,
            "enable": enable,
        })
        for did in device_ids:
            self._assigned_devices[did] = plan_id

    def disable_device(self, device_id: str, plan_id: int) -> None:
        """Record disable."""
        self.events.append({
            "action": "disable_device",
            "device_id": device_id,
            "plan_id": plan_id,
        })
        self._assigned_devices.pop(device_id, None)

    def _singleton_request(self, method: str, path: str, **kwargs) -> MagicMock:
        """Return a mock response for singleton API calls."""
        self.events.append({
            "action": "_singleton_request",
            "method": method,
            "path": path,
            "kwargs": kwargs,
        })
        resp = MagicMock()

        # Handle progress polling
        if "firmwareupdates/progress" in path:
            if self._progress_index < len(self._progress_responses):
                data = self._progress_responses[self._progress_index]
                self._progress_index += 1
                resp.status_code = 200
                resp.json.return_value = data
            else:
                resp.status_code = 404
                resp.json.return_value = {}
            return resp

        # Handle plan verification
        if "firmwareupdates/plans" in path and method == "GET":
            resp.status_code = 200
            # Return whatever stages were last created
            last_plan = next(
                (e for e in reversed(self.events) if e["action"] == "create_plan"),
                None,
            )
            if last_plan:
                resp.json.return_value = {"stages": last_plan["stages"]}
            else:
                resp.json.return_value = {"stages": []}
            return resp

        # Handle device settings query
        if "firmwareupdates/settings/devices" in path:
            resp.status_code = 200
            devices_found = []
            for did, pid in self._assigned_devices.items():
                devices_found.append({
                    "deviceId": did,
                    "planId": pid,
                    "enableFuota": True,
                })
            resp.json.return_value = {"devicesFound": devices_found}
            return resp

        resp.status_code = 200
        resp.json.return_value = {}
        return resp

    def _api_request(self, method: str, path: str, **kwargs) -> MagicMock:
        """Return a mock response for REST API calls."""
        self.events.append({
            "action": "_api_request",
            "method": method,
            "path": path,
            "kwargs": kwargs,
        })
        resp = MagicMock()

        # Handle device status
        if "/System/Devices/Status" in path:
            resp.status_code = 200
            device_ids = kwargs.get("json", {}).get("deviceIds", [])
            devices = []
            for did in device_ids:
                status = self._device_status.get(did, {})
                devices.append({
                    "positionInfo": {"recordId": status.get("recordId", 0)},
                })
            resp.json.return_value = {"devices": devices}
            return resp

        resp.status_code = 200
        resp.json.return_value = {}
        return resp

    def set_device_record_id(self, device_id: str, record_id: int) -> None:
        """Set the recordId returned for a device status query."""
        self._device_status[device_id] = {"recordId": record_id}
