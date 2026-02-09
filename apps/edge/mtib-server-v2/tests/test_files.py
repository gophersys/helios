"""Tests for FilesHandler."""

import os
import tempfile

import pytest

from src.providers.handlers.files import FilesHandler
from src.shared.types import (
    DeleteFileRequest,
    DownloadFileRequest,
    ListFilesRequest,
    UploadFileRequest,
)


@pytest.fixture
def files_handler(logger, hardware, assets_dir):
    """Create a FilesHandler with a temp directory."""
    handler = FilesHandler(logger, hardware, assets_dir)
    # Override RAM storage to use a temp dir too
    handler.ram_storage = handler.assets_dir / "ram"
    handler.ram_storage.mkdir(exist_ok=True)
    return handler


class TestListFiles:
    def test_list_empty_dir(self, files_handler, context):
        response = files_handler.list_files(ListFilesRequest(directory=""), context)
        assert response.success is True
        # May have the "ram" subdirectory but no files in root
        file_names = [f.name for f in response.files]
        assert isinstance(file_names, list)

    def test_list_with_files(self, files_handler, context):
        # Create a test file in the assets directory
        test_file = files_handler.assets_dir / "test.bin"
        test_file.write_bytes(b"hello world")

        response = files_handler.list_files(ListFilesRequest(directory=""), context)
        assert response.success is True
        file_names = [f.name for f in response.files]
        assert "test.bin" in file_names

    def test_file_has_sha256(self, files_handler, context):
        test_file = files_handler.assets_dir / "test.bin"
        test_file.write_bytes(b"hello world")

        response = files_handler.list_files(ListFilesRequest(directory=""), context)
        test_info = [f for f in response.files if f.name == "test.bin"][0]
        assert len(test_info.sha256) == 64  # SHA256 hex digest length


class TestUploadFile:
    def test_upload_single_chunk(self, files_handler, context):
        chunks = [
            UploadFileRequest(filename="upload.bin", chunk=b"test data", final_chunk=True),
        ]
        response = files_handler.upload(iter(chunks), context)
        assert response.success is True
        assert len(response.sha256) == 64

    def test_upload_multi_chunk(self, files_handler, context):
        chunks = [
            UploadFileRequest(filename="multi.bin", chunk=b"part1"),
            UploadFileRequest(filename="multi.bin", chunk=b"part2"),
            UploadFileRequest(filename="multi.bin", chunk=b"part3", final_chunk=True),
        ]
        response = files_handler.upload(iter(chunks), context)
        assert response.success is True

        # Verify the file exists and has correct content
        file_path = files_handler.ram_storage / "multi.bin"
        assert file_path.exists()
        assert file_path.read_bytes() == b"part1part2part3"

    def test_upload_empty_stream(self, files_handler, context):
        response = files_handler.upload(iter([]), context)
        assert response.success is False


class TestDownloadFile:
    def test_download_existing_file(self, files_handler, context):
        # Create a file to download
        test_file = files_handler.ram_storage / "download.bin"
        test_content = b"test download content"
        test_file.write_bytes(test_content)

        chunks = list(files_handler.download(
            DownloadFileRequest(filename="download.bin", offset=0, size=0),
            context,
        ))
        assert len(chunks) > 0
        assert chunks[0].success is True
        received = b"".join(c.data for c in chunks)
        assert received == test_content

    def test_download_nonexistent_file(self, files_handler, context):
        chunks = list(files_handler.download(
            DownloadFileRequest(filename="nonexistent.bin"),
            context,
        ))
        assert len(chunks) > 0
        assert chunks[0].success is False

    def test_download_with_offset(self, files_handler, context):
        test_file = files_handler.ram_storage / "offset.bin"
        test_file.write_bytes(b"0123456789")

        chunks = list(files_handler.download(
            DownloadFileRequest(filename="offset.bin", offset=5, size=5),
            context,
        ))
        received = b"".join(c.data for c in chunks if c.success)
        assert received == b"56789"


class TestDeleteFile:
    def test_delete_existing_file(self, files_handler, context):
        test_file = files_handler.ram_storage / "delete_me.bin"
        test_file.write_bytes(b"delete me")

        response = files_handler.delete(DeleteFileRequest(filename="delete_me.bin"), context)
        assert response.success is True
        assert not test_file.exists()

    def test_delete_nonexistent_file(self, files_handler, context):
        response = files_handler.delete(DeleteFileRequest(filename="nonexistent.bin"), context)
        assert response.success is False


class TestPathTraversal:
    """Security tests for path traversal prevention."""

    def test_upload_sanitizes_traversal_filename(self, files_handler, context):
        """Upload should strip path traversal to just the basename."""
        chunks = [
            UploadFileRequest(filename="../../../etc/passwd", chunk=b"safe data", final_chunk=True),
        ]
        response = files_handler.upload(iter(chunks), context)
        assert response.success is True
        # Should be stored as just "passwd" (basename), not traversing to /etc/
        assert (files_handler.ram_storage / "passwd").exists()
        assert not os.path.exists("/etc/passwd_mtib_test")

    def test_upload_rejects_dotfile(self, files_handler, context):
        """Upload should reject hidden (dot) files."""
        chunks = [
            UploadFileRequest(filename=".bashrc", chunk=b"malicious", final_chunk=True),
        ]
        response = files_handler.upload(iter(chunks), context)
        assert response.success is False

    def test_upload_rejects_empty_filename(self, files_handler, context):
        """Upload should reject empty filenames."""
        chunks = [
            UploadFileRequest(filename="", chunk=b"data", final_chunk=True),
        ]
        response = files_handler.upload(iter(chunks), context)
        assert response.success is False

    def test_download_sanitizes_traversal_filename(self, files_handler, context):
        """Download should strip path traversal to just the basename."""
        # Create a file with the sanitized name
        (files_handler.ram_storage / "shadow").write_bytes(b"test data")
        chunks = list(files_handler.download(
            DownloadFileRequest(filename="../../../etc/shadow"),
            context,
        ))
        assert len(chunks) > 0
        # Should find the file as "shadow" (basename) in ram_storage
        assert chunks[0].success is True

    def test_download_traversal_no_file_found(self, files_handler, context):
        """Download with traversal should not escape to filesystem."""
        chunks = list(files_handler.download(
            DownloadFileRequest(filename="../../../etc/nonexistent_test"),
            context,
        ))
        assert len(chunks) > 0
        assert chunks[0].success is False

    def test_delete_sanitizes_traversal_filename(self, files_handler, context):
        """Delete should strip path traversal to just the basename."""
        # Since "important_file" doesn't exist, this should return "File not found"
        response = files_handler.delete(
            DeleteFileRequest(filename="../../important_file"),
            context,
        )
        assert response.success is False
        assert "File not found" in response.message

    def test_upload_strips_directory_components(self, files_handler, context):
        """Upload with subdirectory in filename should only use the basename."""
        chunks = [
            UploadFileRequest(filename="subdir/firmware.hex", chunk=b"data", final_chunk=True),
        ]
        response = files_handler.upload(iter(chunks), context)
        assert response.success is True
        # Should be stored as just "firmware.hex", not "subdir/firmware.hex"
        assert (files_handler.ram_storage / "firmware.hex").exists()
