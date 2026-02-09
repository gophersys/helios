"""gRPC connection management for MTIB V2.

Streaming RPCs (UART, Zephyr logs) are consumed by persistent background
tasks that write into ring buffers.  MCP tools read from the buffer using
a monotonic cursor so that no data is lost between calls.
"""

from __future__ import annotations

import asyncio
import os
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

import grpc
import grpc.aio

from .proto import mtib_v2_pb2 as pb
from .proto import mtib_v2_pb2_grpc as pb_grpc

CHUNK_SIZE = 64 * 1024  # 64 KB upload chunks
DEFAULT_BUFFER_SIZE = 5_000  # max entries kept per stream


# ======================================================================
# Ring buffer with monotonic cursor
# ======================================================================


@dataclass
class _Entry:
    seq: int
    ts: float  # time.monotonic() when received
    data: dict  # payload (varies by stream type)


class StreamBuffer:
    """Thread/task-safe ring buffer with cursor-based reads.

    Every appended entry gets a monotonic sequence number.  Readers supply
    the last seq they saw and get everything after it (that hasn't been
    evicted from the ring).
    """

    def __init__(self, maxlen: int = DEFAULT_BUFFER_SIZE) -> None:
        self._buf: deque[_Entry] = deque(maxlen=maxlen)
        self._seq: int = 0
        self._lock = asyncio.Lock()

    async def append(self, data: dict) -> int:
        async with self._lock:
            self._seq += 1
            self._buf.append(_Entry(seq=self._seq, ts=time.monotonic(), data=data))
            return self._seq

    async def read_since(
        self, since_seq: int = 0, limit: int = 500
    ) -> tuple[list[dict], int]:
        """Return (entries, latest_seq) for entries with seq > since_seq."""
        async with self._lock:
            out: list[dict] = []
            latest = since_seq
            for entry in self._buf:
                if entry.seq <= since_seq:
                    continue
                out.append(entry.data)
                latest = entry.seq
                if len(out) >= limit:
                    break
            return out, latest

    @property
    def latest_seq(self) -> int:
        return self._seq

    @property
    def size(self) -> int:
        return len(self._buf)


# ======================================================================
# Background stream consumers
# ======================================================================


class _UartStreamTask:
    """Keeps a UART port open and continuously buffers output."""

    def __init__(
        self,
        stub: pb_grpc.MtibV2Stub,
        target_id: str,
        port_name: str,
        baud: int,
    ) -> None:
        self.stub = stub
        self.target_id = target_id
        self.port_name = port_name
        self.baud = baud
        self.buffer = StreamBuffer()
        self.stream_id: str | None = None
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()

    async def start(self) -> None:
        # Open the UART port on the MTIB server
        resp = await self.stub.UartOpen(
            pb.UartOpenRequest(
                target_id=self.target_id,
                port_name=self.port_name,
                config=pb.UartConfig(baud=self.baud, data_bits=8),
            )
        )
        if not resp.success:
            raise RuntimeError(f"UART open failed: {resp.message}")
        self.stream_id = resp.stream_id
        self._stop.clear()
        self._task = asyncio.create_task(self._consume())

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        if self.stream_id is not None:
            try:
                await self.stub.UartClose(
                    pb.UartCloseRequest(stream_id=self.stream_id)
                )
            except grpc.aio.AioRpcError:
                pass
            self.stream_id = None

    async def _consume(self) -> None:
        """Background: read from the bidi UART stream into the buffer."""

        async def _sender():
            # Send the initial request identifying our stream, then keep
            # the send half open for the lifetime of the connection.
            yield pb.UartStreamRequest(stream_id=self.stream_id)
            while not self._stop.is_set():
                await asyncio.sleep(1)

        try:
            call = self.stub.UartStream(_sender())
            async for resp in call:
                if self._stop.is_set():
                    break
                if resp.data:
                    text = resp.data.decode("utf-8", errors="replace")
                    for line in text.splitlines():
                        await self.buffer.append({"line": line})
        except (grpc.aio.AioRpcError, asyncio.CancelledError):
            pass


class _LogStreamTask:
    """Keeps a Zephyr log stream open and continuously buffers entries."""

    def __init__(
        self,
        stub: pb_grpc.MtibV2Stub,
        session_id: str,
        min_level: int = 0,
        modules: list[str] | None = None,
    ) -> None:
        self.stub = stub
        self.session_id = session_id
        self.min_level = min_level
        self.modules = modules or []
        self.buffer = StreamBuffer()
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()

    async def start(self) -> None:
        self._stop.clear()
        self._task = asyncio.create_task(self._consume())

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _consume(self) -> None:
        req = pb.ZephyrLogStreamRequest(
            session_id=self.session_id,
            min_level=self.min_level,
            modules=self.modules,
        )
        try:
            stream = self.stub.ZephyrLogStream(req)
            async for resp in stream:
                if self._stop.is_set():
                    break
                for entry in resp.entries:
                    await self.buffer.append(
                        {
                            "level": pb.ZephyrLogLevel.Name(entry.level),
                            "module": entry.module,
                            "message": entry.message,
                            "file": entry.file,
                            "line": entry.line,
                        }
                    )
        except (grpc.aio.AioRpcError, asyncio.CancelledError):
            pass


# ======================================================================
# Main client
# ======================================================================


class MtibClient:
    """Manages a single async gRPC channel to the MTIB server."""

    def __init__(self) -> None:
        self._channel: grpc.aio.Channel | None = None
        self._stub: pb_grpc.MtibV2Stub | None = None
        # Persistent stream state, keyed by a user-chosen name
        self._uart_streams: dict[str, _UartStreamTask] = {}
        self._log_streams: dict[str, _LogStreamTask] = {}

    async def connect(self) -> None:
        if self._channel is not None:
            return
        target = _target()
        self._channel = grpc.aio.insecure_channel(target)
        self._stub = pb_grpc.MtibV2Stub(self._channel)

    async def close(self) -> None:
        # Tear down all background streams
        for task in list(self._uart_streams.values()):
            await task.stop()
        self._uart_streams.clear()
        for task in list(self._log_streams.values()):
            await task.stop()
        self._log_streams.clear()
        if self._channel is not None:
            await self._channel.close()
            self._channel = None
            self._stub = None

    @property
    def stub(self) -> pb_grpc.MtibV2Stub:
        if self._stub is None:
            raise RuntimeError("Not connected — call connect() first")
        return self._stub

    # ------------------------------------------------------------------
    # File upload helper (client-streaming RPC)
    # ------------------------------------------------------------------
    async def upload_file(self, local_path: str) -> str:
        """Upload a local file to the MTIB server. Returns sha256 on success."""
        path = Path(local_path)
        if not path.is_file():
            raise FileNotFoundError(f"Firmware file not found: {local_path}")

        filename = path.name
        data = path.read_bytes()

        async def _chunks():
            offset = 0
            while offset < len(data):
                chunk = data[offset : offset + CHUNK_SIZE]
                offset += len(chunk)
                yield pb.UploadFileRequest(
                    filename=filename,
                    chunk=chunk,
                    final_chunk=(offset >= len(data)),
                )

        resp = await self.stub.UploadFile(_chunks())
        if not resp.success:
            raise RuntimeError(f"Upload failed: {resp.message}")
        return resp.sha256

    # ------------------------------------------------------------------
    # UART stream management
    # ------------------------------------------------------------------
    async def uart_open(
        self,
        target_id: str,
        port_name: str = "uart0",
        baud: int = 115200,
    ) -> str:
        """Open a UART port and start background buffering.

        Returns a key to identify this stream in subsequent calls.
        """
        key = f"{target_id}:{port_name}"
        if key in self._uart_streams:
            return key  # already open
        task = _UartStreamTask(self.stub, target_id, port_name, baud)
        await task.start()
        self._uart_streams[key] = task
        return key

    async def uart_read(
        self, key: str, since_seq: int = 0, limit: int = 200
    ) -> tuple[list[dict], int]:
        """Read buffered UART lines since the given cursor."""
        task = self._uart_streams.get(key)
        if task is None:
            raise RuntimeError(f"No open UART stream '{key}' — call uart_open first")
        return await task.buffer.read_since(since_seq, limit)

    async def uart_close(self, key: str) -> None:
        task = self._uart_streams.pop(key, None)
        if task is not None:
            await task.stop()

    def uart_keys(self) -> list[str]:
        return list(self._uart_streams.keys())

    # ------------------------------------------------------------------
    # Zephyr log stream management
    # ------------------------------------------------------------------
    async def logs_open(
        self,
        session_id: str,
        min_level: int = 0,
        modules: list[str] | None = None,
    ) -> str:
        """Open a Zephyr log stream and start background buffering."""
        key = f"logs:{session_id}"
        if key in self._log_streams:
            return key
        task = _LogStreamTask(self.stub, session_id, min_level, modules)
        await task.start()
        self._log_streams[key] = task
        return key

    async def logs_read(
        self, key: str, since_seq: int = 0, limit: int = 200
    ) -> tuple[list[dict], int]:
        """Read buffered log entries since the given cursor."""
        task = self._log_streams.get(key)
        if task is None:
            raise RuntimeError(f"No open log stream '{key}' — call logs_open first")
        return await task.buffer.read_since(since_seq, limit)

    async def logs_close(self, key: str) -> None:
        task = self._log_streams.pop(key, None)
        if task is not None:
            await task.stop()


def _target() -> str:
    host = os.environ.get("MTIB_HOST", "localhost")
    port = os.environ.get("MTIB_PORT", "50054")
    return f"{host}:{port}"
