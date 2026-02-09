"""Tests for file management operations."""

from corekinect.mtib_client.v2.client.files import FileInfo


class TestListFiles:
    def test_list_files_returns_entries(self, client):
        err, files = client.list_files()
        assert err is None
        assert len(files) == 1
        assert isinstance(files[0], FileInfo)
        assert files[0].name == "firmware.hex"
        assert files[0].size == 65536
        assert files[0].sha256 == "abcdef1234567890"

    def test_list_files_with_directory(self, client):
        err, files = client.list_files(directory="/firmware")
        assert err is None


class TestDeleteFile:
    def test_delete_file(self, client):
        err = client.delete_file(filename="firmware.hex")
        assert err is None


class TestUploadFile:
    def test_upload_file(self, client):
        err, sha256 = client.upload_file(filename="test.bin", data=b"\x00" * 1024)
        assert err is None
        assert sha256 == "abcdef1234567890"


class TestDownloadFile:
    def test_download_file(self, client):
        err, data = client.download_file(filename="firmware.hex")
        assert err is None
        assert data == b"file-content-here"
