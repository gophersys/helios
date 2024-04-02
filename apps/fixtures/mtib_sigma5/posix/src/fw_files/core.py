import os
import hashlib
import logging
from typing import List, Tuple, Optional

class FileInfo:
    """Represents information about a file.

    Attributes:
        name (str): The name of the file.
        size_kb (int): The size of the file in kilobytes.
        sha256_digest (str): The SHA-256 digest of the file's contents.
    """

    def __init__(self, name: str, size_kb: int, sha256_digest: str):
        self.name = name
        self.size_kb = size_kb
        self.sha256_digest = sha256_digest

class FwFileManager:
    """Manages firmware files within a specified storage path.

    Attributes:
        storage_path (str): The path to the directory where files are stored.
    """

    def __init__(self, storage_path: str):
        self.storage_path = storage_path
        logging.info(f"Creating directory {self.storage_path}")
        os.makedirs(self.storage_path, exist_ok=True)

    def list_files(self) -> List[FileInfo]:
        """Lists all files in the storage directory.

        Returns:
            List[FileInfo]: A list of FileInfo objects for each file.
        """
        files_info = []
        for filename in os.listdir(self.storage_path):
            path = os.path.join(self.storage_path, filename)
            if os.path.isfile(path):
                size_kb = int(os.path.getsize(path) / 1024)
                sha256_digest = self._calculate_sha256(path)
                files_info.append(FileInfo(filename, size_kb, sha256_digest))
            else:
                logging.info(f"Skipping directory: {path}")
        return files_info

    def save_file(self, filename: str, content: bytes) -> Tuple[bool, Optional[str], Optional[str]]:
        """Saves content to a file within the storage path.

        Args:
            filename (str): The name of the file to save.
            content (bytes): The content to save to the file.

        Returns:
            Tuple[bool, Optional[str], Optional[str]]: Success status, error message (if any), and SHA-256 digest.
        """
        try:
            file_path = os.path.join(self.storage_path, filename)
            if not os.path.normpath(file_path).startswith(os.path.abspath(self.storage_path)):
                return False, "Invalid filename", None
            if os.path.exists(file_path):
                return False, "File already exists", None
            with open(file_path, 'wb') as f:
                f.write(content)
            sha256_digest = hashlib.sha256(content).hexdigest()
            return True, None, sha256_digest
        except Exception as e:
            return False, str(e), None

    def delete_file(self, filename: str) -> Tuple[bool, Optional[str]]:
        """Deletes a file from the storage path.

        Args:
            filename (str): The name of the file to delete.

        Returns:
            Tuple[bool, Optional[str]]: Success status and an error message (if any).
        """
        file_path = os.path.join(self.storage_path, filename)
        if not os.path.exists(file_path):
            return False, "File does not exist"
        try:
            os.remove(file_path)
            return True, None
        except Exception as e:
            return False, str(e)

    def _calculate_sha256(self, filepath: str) -> str:
        """Calculates the SHA-256 digest of a file's contents.

        Args:
            filepath (str): The path to the file.

        Returns:
            str: The SHA-256 digest as a hexadecimal string.
        """
        hash_sha256 = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
