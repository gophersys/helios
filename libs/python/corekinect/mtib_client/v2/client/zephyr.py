from typing import Iterator, List, Optional, Tuple

from protocols.mtib_v2.mtib_v2_pb2 import (
    TwisterRunRequest,
    ZephyrDevicetreeRequest,
    ZephyrLogStreamRequest,
    ZephyrShellRequest,
    ZephyrThreadsRequest,
)

from ._base import BaseClient
from ..types.zephyr import (
    TestResult,
    TwisterResult,
    ZephyrDevicetreeNode,
    ZephyrLogEntry,
    ZephyrShellResult,
    ZephyrThread,
)


def _convert_devicetree_node(node) -> ZephyrDevicetreeNode:
    """Convert a protobuf ZephyrDevicetreeNode to a typed dataclass recursively."""
    return ZephyrDevicetreeNode(
        path=node.path,
        compatible=node.compatible,
        label=node.label,
        status=node.status,
        properties=dict(node.properties),
        children=[_convert_devicetree_node(c) for c in node.children],
    )


class ZephyrMixin(BaseClient):
    """Zephyr RTOS integration operations."""

    def zephyr_shell(
        self, session_id: str, command: str, timeout_s: float = 10.0
    ) -> Tuple[Optional[str], Optional[ZephyrShellResult]]:
        """Execute a Zephyr shell command.

        Args:
            session_id: UART stream_id or debug session_id.
            command: Shell command string to execute.
            timeout_s: Command execution timeout in seconds.

        Returns:
            (error, ZephyrShellResult) tuple. error is None on success.
        """
        try:
            resp = self._call(
                "ZephyrShell",
                ZephyrShellRequest(
                    session_id=session_id, command=command, timeout_s=timeout_s
                ),
            )
            if not resp.success:
                return resp.message, None
            return None, ZephyrShellResult(output=resp.output, return_code=resp.return_code)
        except Exception as e:
            return f"zephyr_shell error: {e}", None

    def zephyr_log_stream(
        self,
        session_id: str,
        min_level: int = 2,
        modules: List[str] = None,
        timeout: float = None,
    ) -> Iterator[ZephyrLogEntry]:
        """Stream Zephyr log messages.

        Args:
            session_id: Active debug or UART session ID.
            min_level: Minimum log level (0=ERR, 1=WRN, 2=INF, 3=DBG).
            modules: Filter to specific modules (empty for all).
            timeout: Stream timeout in seconds.

        Yields:
            ZephyrLogEntry objects for each log message.
        """
        stream = self._server_stream(
            "ZephyrLogStream",
            ZephyrLogStreamRequest(
                session_id=session_id, min_level=min_level, modules=modules or []
            ),
            timeout=timeout,
        )
        for resp in stream:
            for entry in resp.entries:
                yield ZephyrLogEntry(
                    timestamp_s=entry.timestamp.seconds if entry.timestamp else 0,
                    timestamp_ns=entry.timestamp.nanos if entry.timestamp else 0,
                    level=entry.level,
                    module=entry.module,
                    message=entry.message,
                    file=entry.file,
                    line=entry.line,
                )

    def zephyr_devicetree(
        self, session_id: str
    ) -> Tuple[Optional[str], Optional[ZephyrDevicetreeNode]]:
        """Get the Zephyr devicetree.

        Args:
            session_id: Active debug session ID (requires ELF).

        Returns:
            (error, ZephyrDevicetreeNode) tuple. error is None on success.
            Returns the root devicetree node with children.
        """
        try:
            resp = self._call(
                "ZephyrDevicetree", ZephyrDevicetreeRequest(session_id=session_id)
            )
            if not resp.success:
                return resp.message, None
            if not resp.root:
                return None, None
            return None, _convert_devicetree_node(resp.root)
        except Exception as e:
            return f"zephyr_devicetree error: {e}", None

    def zephyr_threads(
        self, session_id: str
    ) -> Tuple[Optional[str], List[ZephyrThread]]:
        """Get Zephyr thread information.

        Args:
            session_id: Active debug session ID.

        Returns:
            (error, list[ZephyrThread]) tuple. error is None on success.
        """
        try:
            resp = self._call(
                "ZephyrThreads", ZephyrThreadsRequest(session_id=session_id)
            )
            if not resp.success:
                return resp.message, []
            threads = [
                ZephyrThread(
                    id=t.id,
                    name=t.name,
                    state=t.state,
                    priority=t.priority,
                    stack_size=t.stack_size,
                    stack_used=t.stack_used,
                    cycles=t.cycles,
                )
                for t in resp.threads
            ]
            return None, threads
        except Exception as e:
            return f"zephyr_threads error: {e}", []

    def twister_run(
        self,
        target_id: str,
        test_path: str,
        extra_args: List[str] = None,
        timeout_s: float = 300.0,
    ) -> Tuple[Optional[str], Optional[TwisterResult]]:
        """Run a Zephyr Twister test.

        Args:
            target_id: Target device ID.
            test_path: Test path (e.g. 'tests/kernel/threads/thread_apis').
            extra_args: Extra Twister command-line arguments.
            timeout_s: Test execution timeout in seconds.

        Returns:
            (error, TwisterResult) tuple. error is None on success.
        """
        try:
            resp = self._call(
                "TwisterRun",
                TwisterRunRequest(
                    target_id=target_id,
                    test_path=test_path,
                    extra_args=extra_args or [],
                    timeout_s=timeout_s,
                ),
            )
            if not resp.success:
                return resp.message, None
            results = [
                TestResult(
                    name=r.name,
                    status=r.status,
                    duration_s=r.duration_s,
                    message=r.message,
                    log=r.log,
                )
                for r in resp.results
            ]
            return None, TwisterResult(results=results, full_log=resp.full_log)
        except Exception as e:
            return f"twister_run error: {e}", None
