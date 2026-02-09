from typing import List, Optional, Tuple

from protocols.mtib_v2.mtib_v2_pb2 import Empty

from ._base import BaseClient
from ..types.target import DebugProbe, TargetDevice


class TargetMixin(BaseClient):
    """Target and debug probe discovery operations."""

    def list_targets(self) -> Tuple[Optional[str], List[TargetDevice]]:
        """List all available target devices.

        Returns:
            (error, list[TargetDevice]) tuple. error is None on success.
        """
        try:
            resp = self._call("ListTargets", Empty())
            if not resp.success:
                return resp.message, []
            targets = [
                TargetDevice(
                    id=t.id,
                    name=t.name,
                    arch=t.arch,
                    chip=t.chip,
                    board=t.board,
                    has_debug=t.has_debug,
                    has_uart=t.has_uart,
                    has_rtt=t.has_rtt,
                    has_swo=t.has_swo,
                    flash_size_kb=t.flash_size_kb,
                    ram_size_kb=t.ram_size_kb,
                )
                for t in resp.targets
            ]
            return None, targets
        except Exception as e:
            return f"list_targets error: {e}", []

    def list_probes(self) -> Tuple[Optional[str], List[DebugProbe]]:
        """List all available debug probes.

        Returns:
            (error, list[DebugProbe]) tuple. error is None on success.
        """
        try:
            resp = self._call("ListProbes", Empty())
            if not resp.success:
                return resp.message, []
            probes = [
                DebugProbe(
                    id=p.id,
                    type=p.type,
                    serial=p.serial,
                    firmware_version=p.firmware_version,
                    supported_targets=list(p.supported_targets),
                )
                for p in resp.probes
            ]
            return None, probes
        except Exception as e:
            return f"list_probes error: {e}", []
