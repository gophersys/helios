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

        The password is consumed during ``_initialize_client`` and then
        zeroed; it is NOT retained as an instance attribute past the
        constructor. This avoids leaking the secret via ``repr(client)``,
        ``__dict__`` introspection, debuggers, or stack-frame logging
        when an unrelated exception fires later in the client's life.
        """
        self.address = address
        self.username = username
        # NOTE: ``password`` is intentionally NOT stored on ``self``.
        # The Vault session token replaces it after authentication; if
        # auth fails, ``_initialize_client`` raises and the stack frame
        # for this constructor is the only place the password ever
        # lives.
        self.token_file_path = token_file_path
        self.vault_client = None

        # Initialize the Vault client (consumes ``password`` directly).
        self._initialize_client(password)
        # Best-effort scrub: rebind the local name so the password
        # bytes can be GC'd. Python strings are immutable so we can't
        # zero the actual bytes; this is a defense-in-depth measure
        # only — never rely on it to scrub credentials from memory.
        del password

    def _initialize_client(self, password: str = ""):
        """Initialize the Vault client with authentication.

        ``password`` is consumed locally and never stored on ``self``;
        see the constructor docstring for the rationale.
        """
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
            if self.username and password:
                self._authenticate_userpass(password)
            else:
                raise ValueError("Either token_file_path or username/password must be provided")

        except Exception as e:
            # Log only the exception type and message — never the
            # exception's repr, which can include kwargs (and thus the
            # password) for some hvac error subclasses.
            logger.error(
                "Failed to initialize Vault client: %s: %s",
                type(e).__name__, str(e),
            )
            raise

    def _read_token_from_file(self, token_file_path: str) -> str:
        """Read token from file"""
        try:
            with open(token_file_path, 'r') as f:
                token = f.read().strip()
            return token
        except Exception as e:
            raise ValueError(f"Failed to read token from file: {e}")

    def _authenticate_userpass(self, password: str):
        """Authenticate using userpass method.

        ``password`` is passed in directly rather than read from
        ``self.password`` (which doesn't exist) — keeping the secret
        confined to this stack frame.
        """
        max_retries = 3

        for attempt in range(1, max_retries + 1):
            try:
                # Authenticate using userpass
                auth_response = self.vault_client.auth.userpass.login(
                    username=self.username,
                    password=password,
                )
                
                if auth_response and 'auth' in auth_response:
                    self.vault_client.token = auth_response['auth']['client_token']
                    logger.info("Successfully authenticated with Vault")
                    return
                    
            except Exception as e:
                if attempt < max_retries:
                    logger.warning(
                        "Vault auth attempt %d/%d failed: %s: %s",
                        attempt, max_retries, type(e).__name__, str(e),
                    )
                else:
                    # Final attempt — escalate to error so the caller's
                    # log shows the auth failure as a real fault, not a
                    # transient warning.
                    logger.error(
                        "Vault auth failed after %d attempts: %s: %s",
                        max_retries, type(e).__name__, str(e),
                    )
                    raise ValueError(
                        f"Could not log in to Vault after {max_retries} attempts: "
                        f"{type(e).__name__}"
                    ) from e

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
            # Log only the exception type + message; some hvac error
            # subclasses include the request kwargs in their repr,
            # which can leak the secret payload back into the log.
            logger.error("Could not retrieve secret at %r: %s: %s",
                         path, type(e).__name__, str(e))
            raise VaultError(f"Could not retrieve secret at {path!r}") from e

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
            # See ``read_key_value`` for the rationale on log/raise format.
            logger.error("Could not create secret at %r: %s: %s",
                         path, type(e).__name__, str(e))
            raise VaultError(f"Could not create secret at {path!r}") from e

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
            logger.error("Could not delete secret at %r: %s: %s",
                         path, type(e).__name__, str(e))
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
