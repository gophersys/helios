from dataclasses import dataclass
from typing import List, Optional, Dict

from corekinect.test.config import TestConfig


@dataclass
class CompatibleValidationTestConfig(TestConfig):
    def __init__(
        self,
        platforms: List[str],
        hw_versions: List[str],
        fw_versions: List[str],
        hosts: List[str],
        socket_server_versions: List[str],
        socket_server_messages: List[str],
    ):
        self.platform: str = platforms
        self.hw_version: str = hw_versions
        self.fw_version: str = fw_versions
        self.hosts: List[str] = hosts
        self.socket_server_version: str = socket_server_versions
        self.socket_server_messages: List[str] = socket_server_messages


@dataclass
class ValidationTestConfig(TestConfig):
    def __init__(
        self,
        platform: str,
        hw_version: str,
        fw_version: str,
        hosts: List[str],
        socket_server_version: str,
        socket_server_messages: List[str],
    ):
        self.platform: str = platform
        self.hw_version: str = hw_version
        self.fw_version: str = fw_version
        self.hosts: List[str] = hosts
        self.socket_server_version: str = socket_server_version
        self.socket_server_messages: List[str] = socket_server_messages
