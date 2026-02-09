from dataclasses import dataclass
from typing import List, Optional, Tuple

from protocols.mtib_v2.mtib_v2_pb2 import (
    DeleteFileRequest,
    DownloadFileRequest,
    ListFilesRequest,
    UploadFileRequest,
)

from ._base import BaseClient


@dataclass
class FileInfo:
    """Information about a file on the MTIB server.

    Args:
        name: File name.
        size: File size in bytes.
        sha256: SHA-256 hash of file contents.
        modified_s: Last modified timestamp seconds.
        modified_ns: Last modified timestamp nanoseconds.
    """

    name: str
    size: int
    sha256: str = ""
    modified_s: int = 0
    modified_ns: int = 0


class FilesMixin(BaseClient):
    """File management operations."""

    def list_files(self, directory: str = "") -> Tuple[Optional[str], List[FileInfo]]:
        """List files on the MTIB server.

        Args:
            directory: Directory path to list (empty for root).

        Returns:
            (error, list[FileInfo]) tuple. error is None on success.
        """
        try:
            resp = self._call("ListFiles", ListFilesRequest(directory=directory))
            if not resp.success:
                return resp.message, []
            files = [
                FileInfo(
                    name=f.name,
                    size=f.size,
                    sha256=f.sha256,
                    modified_s=f.modified.seconds if f.modified else 0,
                    modified_ns=f.modified.nanos if f.modified else 0,
                )
                for f in resp.files
            ]
            return None, files
        except Exception as e:
            return f"list_files error: {e}", []

    def upload_file(
        self, filename: str, data: bytes, chunk_size: int = 65536
    ) -> Tuple[Optional[str], Optional[str]]:
        """Upload a file to the MTIB server.

        Args:
            filename: Destination filename.
            data: File contents.
            chunk_size: Size of each upload chunk in bytes.

        Returns:
            (error, sha256) tuple. error is None on success.
        """
        try:
            def chunk_generator():
                offset = 0
                while offset < len(data):
                    chunk = data[offset : offset + chunk_size]
                    offset += chunk_size
                    is_final = offset >= len(data)
                    yield UploadFileRequest(
                        filename=filename, chunk=chunk, final_chunk=is_final
                    )

            resp = self._client_stream("UploadFile", chunk_generator())
            if not resp.success:
                return resp.message, None
            return None, resp.sha256
        except Exception as e:
            return f"upload_file error: {e}", None

    def download_file(
        self, filename: str, offset: int = 0, size: int = 0
    ) -> Tuple[Optional[str], bytes]:
        """Download a file from the MTIB server.

        Args:
            filename: File to download.
            offset: Byte offset to start from.
            size: Number of bytes to download (0 for entire file).

        Returns:
            (error, data) tuple. error is None on success.
        """
        try:
            stream = self._server_stream(
                "DownloadFile",
                DownloadFileRequest(filename=filename, offset=offset, size=size),
            )
            chunks = []
            for resp in stream:
                if not resp.success:
                    return resp.message, b""
                chunks.append(resp.data)
                if resp.eof:
                    break
            return None, b"".join(chunks)
        except Exception as e:
            return f"download_file error: {e}", b""

    def delete_file(self, filename: str) -> Optional[str]:
        """Delete a file from the MTIB server.

        Args:
            filename: File to delete.

        Returns:
            Error message string, or None on success.
        """
        try:
            resp = self._call("DeleteFile", DeleteFileRequest(filename=filename))
            if not resp.success:
                return resp.message
            return None
        except Exception as e:
            return f"delete_file error: {e}"
