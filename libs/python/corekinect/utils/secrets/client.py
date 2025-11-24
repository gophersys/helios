"""
Vault Secrets Client for Python

A Python client for retrieving, storing, and modifying key-value secrets and certificates
from HashiCorp Vault. This is a Python port of the Go secrets client library.
"""

import os
import json
import logging
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
import hvac
from hvac.exceptions import VaultError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
VAULT_TOKEN_FILE_PATH = "/vault/secrets/token"


@dataclass
class CertRequest:
    """Certificate request data structure"""
    common_name: str
    alt_names: str = ""
    ip_sans: str = ""
    ttl: str = "24h"
    key_type: str = "rsa"
    key_bits: int = 2048


class SecretsClient:
    """
    A secrets client used to retrieve, store, and modify key-value secrets and certificates.
    This is a Python port of the Go secrets client library.
    """

    def __init__(self, address: str, username: str = "", password: str = "", 
                 token_file_path: str = ""):
        """
        Initialize the secrets client.
        
        Args:
            address: Vault server address
            username: Username for userpass authentication (optional if using token)
            password: Password for userpass authentication (optional if using token)
            token_file_path: Path to token file for Kubernetes auth (optional)
        """
        self.address = address
        self.username = username
        self.password = password
        self.token_file_path = token_file_path
        self.vault_client = None
        
        # Initialize the Vault client
        self._initialize_client()

    def _initialize_client(self):
        """Initialize the Vault client with authentication"""
        try:
            # Create Vault client
            self.vault_client = hvac.Client(url=self.address)
            
            # If a token file path is provided, use the token from the file
            if self.token_file_path and os.path.exists(self.token_file_path):
                token = self._read_token_from_file(self.token_file_path)
                self.vault_client.token = token
                logger.info("Authenticated using token from file")
                return
            
            # Otherwise, authenticate using userpass
            if self.username and self.password:
                self._authenticate_userpass()
            else:
                raise ValueError("Either token_file_path or username/password must be provided")
                
        except Exception as e:
            logger.error(f"Failed to initialize Vault client: {e}")
            raise

    def _read_token_from_file(self, token_file_path: str) -> str:
        """Read token from file"""
        try:
            with open(token_file_path, 'r') as f:
                token = f.read().strip()
            return token
        except Exception as e:
            raise ValueError(f"Failed to read token from file: {e}")

    def _authenticate_userpass(self):
        """Authenticate using userpass method"""
        max_retries = 3
        
        for attempt in range(1, max_retries + 1):
            try:
                # Authenticate using userpass
                auth_response = self.vault_client.auth.userpass.login(
                    username=self.username,
                    password=self.password
                )
                
                if auth_response and 'auth' in auth_response:
                    self.vault_client.token = auth_response['auth']['client_token']
                    logger.info("Successfully authenticated with Vault")
                    return
                    
            except Exception as e:
                logger.warning(f"Authentication attempt {attempt} failed: {e}")
                if attempt == max_retries:
                    raise ValueError(f"Could not log in to Vault after {max_retries} attempts: {e}")

    def _refresh_token_from_file(self):
        """Refresh token from file if token file path is provided"""
        if self.token_file_path and os.path.exists(self.token_file_path):
            try:
                token = self._read_token_from_file(self.token_file_path)
                self.vault_client.token = token
            except Exception as e:
                logger.error(f"Failed to refresh token from file: {e}")
                raise

    def read_key_value(self, path: str) -> Dict[str, Any]:
        """
        Read key-value secrets from Vault.
        
        Args:
            path: Path to the secret in Vault
            
        Returns:
            Dictionary containing the secret data
            
        Raises:
            VaultError: If the secret cannot be retrieved
        """
        try:
            # Refresh token before the action
            self._refresh_token_from_file()
            
            # Retrieve the secret
            response = self.vault_client.secrets.kv.v2.read_secret_version(path=path)
            
            if not response or 'data' not in response:
                raise VaultError("Secret not found")
                
            return response['data']['data']
            
        except Exception as e:
            logger.error(f"Could not retrieve secret: {e}")
            raise VaultError(f"Could not retrieve secret: {e}")

    def write_key_value(self, path: str, data: Dict[str, Any]) -> None:
        """
        Write key-value secrets to Vault.
        
        Args:
            path: Path to store the secret in Vault
            data: Dictionary containing the secret data
            
        Raises:
            VaultError: If the secret cannot be written
        """
        try:
            # Refresh token before the action
            self._refresh_token_from_file()
            
            # Write the KV secret
            self.vault_client.secrets.kv.v2.create_or_update_secret(
                path=path,
                secret=data
            )
            
        except Exception as e:
            logger.error(f"Could not create secret: {e}")
            raise VaultError(f"Could not create secret: {e}")

    def delete_key_value(self, path: str) -> None:
        """
        Delete key-value secrets from Vault.
        
        Args:
            path: Path to the secret in Vault
            
        Raises:
            VaultError: If the secret cannot be deleted
        """
        try:
            # Refresh token before the action
            self._refresh_token_from_file()
            
            # Delete the secret
            self.vault_client.secrets.kv.v2.delete_metadata_and_all_versions(path=path)
            
        except Exception as e:
            logger.error(f"Could not delete secret: {e}")
            raise VaultError(f"Could not delete secret: {e}")

    def get_bool_from_map(self, secrets: Dict[str, Any], key: str) -> bool:
        """
        Extract a boolean value from a secrets map.
        
        Args:
            secrets: Dictionary containing secrets
            key: Key to extract the boolean value from
            
        Returns:
            Boolean value or False if not found/invalid
        """
        if key in secrets and secrets[key] is not None:
            val = secrets[key]
            
            # Handle string values
            if isinstance(val, str):
                val = val.strip('"').lower()
                if val in ["true", "1"]:
                    return True
                elif val in ["false", "0"]:
                    return False
                else:
                    logger.warning(f"Invalid boolean value for key {key}: {val}")
            else:
                logger.warning(f"Value for key {key} is not a string")
                
        return False

    def get_string_from_map(self, secrets: Dict[str, Any], key: str) -> str:
        """
        Extract a string value from a secrets map.
        
        Args:
            secrets: Dictionary containing secrets
            key: Key to extract the string value from
            
        Returns:
            String value or empty string if not found
        """
        if key in secrets and secrets[key] is not None:
            val = str(secrets[key])
            # Remove surrounding quotes if they exist
            return val.strip('"')
        return ""

    def get_int_from_map(self, secrets: Dict[str, Any], key: str) -> int:
        """
        Extract an integer value from a secrets map.
        
        Args:
            secrets: Dictionary containing secrets
            key: Key to extract the integer value from
            
        Returns:
            Integer value or 0 if not found/invalid
        """
        if key in secrets and secrets[key] is not None:
            val = secrets[key]
            
            # Handle string values
            if isinstance(val, str):
                val = val.strip('"')
                try:
                    return int(val)
                except ValueError as e:
                    logger.warning(f"Error converting {key} to integer: {e}")
            else:
                logger.warning(f"Value for key {key} is not a string")
                
        return 0


# Convenience function to create a new client
def new_client(address: str, username: str = "", password: str = "", 
               token_file_path: str = "") -> SecretsClient:
    """
    Create a new secrets client.
    
    Args:
        address: Vault server address
        username: Username for userpass authentication (optional if using token)
        password: Password for userpass authentication (optional if using token)
        token_file_path: Path to token file for Kubernetes auth (optional)
        
    Returns:
        Initialized SecretsClient instance
    """
    return SecretsClient(address, username, password, token_file_path)
