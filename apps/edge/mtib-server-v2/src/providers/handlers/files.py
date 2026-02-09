"""File management handler for V2 protocol."""

import hashlib
import os
from pathlib import Path
from typing import TYPE_CHECKING, Iterator

from corekinect.utils import Logger
from src.shared.types import (
    DeleteFileRequest,
    DownloadFileRequest,
    DownloadFileResponse,
    FileInfo,
    ListFilesRequest,
    ListFilesResponse,
    Response,
    Timestamp,
    UploadFileRequest,
    UploadFileResponse,
)

if TYPE_CHECKING:
    from src.hardware import HardwareContext

CHUNK_SIZE = 65536  # 64KB chunks for streaming


class FilesHandler:
    """Handles file management RPCs."""

    def __init__(self, logger: Logger, hardware: "HardwareContext", assets_dir: str):
        self.logger = logger
        self.hardware = hardware
        self.assets_dir = Path(assets_dir)
        self.assets_dir.mkdir(parents=True, exist_ok=True)

        # RAM storage for firmware files
        self.ram_storage = Path("/dev/shm/mtib_fw_files")
        self.ram_storage.mkdir(exist_ok=True)

    def _resolve_dir(self, directory: str) -> Path:
        """Resolve a directory path relative to assets dir."""
        if not directory or directory == "/":
            return self.assets_dir
        # Prevent path traversal
        resolved = (self.assets_dir / directory).resolve()
        if not str(resolved).startswith(str(self.assets_dir.resolve())):
            return self.assets_dir
        return resolved

    def _sha256(self, file_path: Path) -> str:
        """Calculate SHA256 hash of a file."""
        sha = hashlib.sha256()
        with open(file_path, "rb") as f:
            for block in iter(lambda: f.read(4096), b""):
                sha.update(block)
        return sha.hexdigest()

    def list_files(self, request: ListFilesRequest, context) -> ListFilesResponse:
        """List files in a directory."""
        try:
            target_dir = self._resolve_dir(request.directory)
            if not target_dir.exists():
                return ListFilesResponse(success=False, message=f"Directory not found: {request.directory}")

            files = []
            for entry in sorted(target_dir.iterdir()):
                if entry.is_file():
                    stat = entry.stat()
                    files.append(FileInfo(
                        name=entry.name,
                        size=stat.st_size,
                        sha256=self._sha256(entry),
                        modified=Timestamp(seconds=int(stat.st_mtime), nanos=0),
                    ))

            # Also list files from RAM storage
            if self.ram_storage.exists():
                for entry in sorted(self.ram_storage.iterdir()):
                    if entry.is_file():
                        stat = entry.stat()
                        files.append(FileInfo(
                            name=f"ram/{entry.name}",
                            size=stat.st_size,
                            sha256=self._sha256(entry),
                            modified=Timestamp(seconds=int(stat.st_mtime), nanos=0),
                        ))

            return ListFilesResponse(success=True, message="", files=files)
        except Exception as e:
            return ListFilesResponse(success=False, message=str(e))

    def upload(self, request_iterator: Iterator[UploadFileRequest], context) -> UploadFileResponse:
        """Client-streaming file upload (chunked)."""
        try:
            filename = None
            file_path = None
            sha = hashlib.sha256()

            for chunk in request_iterator:
                if filename is None:
                    filename = chunk.filename
                    # Store in RAM storage for firmware files
                    file_path = self.ram_storage / filename
                    self.logger.info(f"Uploading file: {filename}")
                    # Open file for writing (truncate if exists)
                    f = open(file_path, "wb")

                if chunk.chunk:
                    f.write(chunk.chunk)
                    sha.update(chunk.chunk)

                if chunk.final_chunk:
                    f.close()
                    digest = sha.hexdigest()
                    self.logger.info(f"Upload complete: {filename} (sha256={digest})")
                    return UploadFileResponse(success=True, message="", sha256=digest)

            # If we get here without final_chunk, close the file
            if file_path and not f.closed:
                f.close()
                digest = sha.hexdigest()
                return UploadFileResponse(success=True, message="", sha256=digest)

            return UploadFileResponse(success=False, message="Empty upload stream", sha256="")

        except Exception as e:
            self.logger.error(f"Upload error: {e}")
            return UploadFileResponse(success=False, message=str(e), sha256="")

    def download(self, request: DownloadFileRequest, context) -> Iterator[DownloadFileResponse]:
        """Server-streaming file download (chunked)."""
        try:
            # Try RAM storage first, then assets dir
            file_path = self.ram_storage / request.filename
            if not file_path.exists():
                file_path = self.assets_dir / request.filename
            if not file_path.exists():
                yield DownloadFileResponse(
                    success=False,
                    message=f"File not found: {request.filename}",
                    eof=True,
                )
                return

            file_size = file_path.stat().st_size
            offset = request.offset
            remaining = request.size if request.size > 0 else file_size - offset

            with open(file_path, "rb") as f:
                f.seek(offset)
                while remaining > 0 and context.is_active():
                    read_size = min(CHUNK_SIZE, remaining)
                    data = f.read(read_size)
                    if not data:
                        break
                    remaining -= len(data)
                    yield DownloadFileResponse(
                        success=True,
                        message="",
                        data=data,
                        eof=remaining <= 0,
                    )

        except Exception as e:
            yield DownloadFileResponse(success=False, message=str(e), eof=True)

    def delete(self, request: DeleteFileRequest, context) -> Response:
        """Delete a file."""
        try:
            # Try RAM storage first, then assets dir
            file_path = self.ram_storage / request.filename
            if not file_path.exists():
                file_path = self.assets_dir / request.filename
            if not file_path.exists():
                return Response(success=False, message=f"File not found: {request.filename}")

            file_path.unlink()
            self.logger.info(f"Deleted file: {request.filename}")
            return Response(success=True, message="File deleted")
        except Exception as e:
            return Response(success=False, message=str(e))
