import builtins
import logging
import os
from typing import Any, List, Optional, Type

from dotenv import load_dotenv

from .log import setup_logging


class Config:
    """
    A singleton class for application configuration.

    Attributes:
    """

    _instance = None

    LOG_LEVEL: int
    LOG_PATH: str
    CLUSTER_UUID: str
    PROXY_SERVER_URL: str
    GRPC_SERVER_PORT: int
    LOCAL_REGISTRY_PORT: int
    KUBECONFIG_PATH: str
    NODES_HOSTNAMES: List[str]
    NODES_MGMT_ENABLED: bool
    GRPC_SERVER_HOST: str

    def __new__(cls: Type["Config"]) -> "Config":
        """
        Ensures only one instance of the Config class is created.

        Args:
            cls (Type[Config]): The class of which an instance is required.

        Returns:
            Config: The singleton instance of the Config class.
        """
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self) -> None:
        """
        Initializes the configuration by loading values from environment variables.

        Raises:
            EnvironmentError: If no configuration file or environment variables are found.
        """
        env_file_path = os.getenv("ENV_FILE_PATH")
        env_file_name = os.getenv("ENV_FILE_NAME")

        if env_file_path and env_file_name:
            env_file = os.path.join(env_file_path, env_file_name)
            print(f"Full env file path: {env_file}", flush=True)

            if os.path.exists(env_file):
                if os.path.isfile(env_file):
                    print(f"Contents of {env_file}:", flush=True)
                    with open(env_file, "r") as file:
                        print(file.read(), flush=True)

                    loaded = load_dotenv(env_file)
                else:
                    print(f"Error: {env_file} is not a file.", flush=True)
                    raise EnvironmentError(f"{env_file} is not a file.")
            else:
                print(f"Error: {env_file} does not exist.", flush=True)
                raise EnvironmentError(f"{env_file} does not exist.")
        else:
            print("No specific env file path and name provided, trying to load default .env", flush=True)
            loaded = load_dotenv()  # This will load from '.env' file if present

            default_env_file = ".env"
            if os.path.exists(default_env_file) and os.path.isfile(default_env_file):
                print(f"Contents of {default_env_file}:", flush=True)
                with open(default_env_file, "r") as file:
                    print(file.read(), flush=True)

        if not loaded:
            print("No .env file found. Falling back to OS environment variables.", flush=True)

        # Load
        self.LOG_LEVEL = self._get_env_var("LOG_LEVEL", int)
        self.LOG_PATH = self._get_env_var("LOG_PATH", str)
        self.CLUSTER_UUID = self._get_env_var("CLUSTER_UUID", str)
        self.PROXY_SERVER_URL = self._get_env_var("PROXY_SERVER_URL", str)
        self.GRPC_SERVER_PORT = self._get_env_var("GRPC_SERVER_PORT", int)
        self.LOCAL_REGISTRY_PORT = self._get_env_var("LOCAL_REGISTRY_PORT", int)
        self.KUBECONFIG_PATH = self._get_env_var("KUBECONFIG_PATH", str)
        self.NODES_HOSTNAMES = self._get_env_var_list("NODES_HOSTNAMES", str, delimiter=",")
        self.NODES_MGMT_ENABLED = self._get_env_var("NODES_MGMT_ENABLED", bool)
        self.GRPC_SERVER_HOST = self._get_env_var("GRPC_SERVER_HOST", str)

    def _get_env_var(self, var_name: str, expected_type: type, default: Optional[Any] = None) -> type:
        """
        Retrieves an environment variable and converts it to the expected type.

        Args:
            var_name (str): The name of the environment variable.
            expected_type (Type[T]): The type to which the variable value is expected to be converted.
            default (Optional[Any], optional): The default value to use if the environment variable is not found. Defaults to None.

        Returns:
            T: The value of the environment variable, converted to the expected type.

        Raises:
            EnvironmentError: If the environment variable is not found and no default is provided.
            TypeError: If the value of the environment variable cannot be converted to the expected type.
        """
        value_str = os.getenv(var_name)
        if value_str is None:
            raise EnvironmentError(f"Environment variable '{var_name}' not found.")

        try:
            if expected_type == bool:
                lower_value = value_str.lower()
                if lower_value in ["true", "1", "yes"]:
                    return True
                elif lower_value in ["false", "0", "no"]:
                    return False
                else:
                    raise ValueError("Invalid boolean value.")
            return expected_type(value_str)
        except ValueError:
            received_type = type(value_str).__name__
            raise TypeError(
                f"Environment variable '{var_name}' should be of type '{expected_type.__name__}', but got value '{value_str}' of type '{received_type}'."
            )

    def _get_env_var_list(
        self, var_name: str, expected_type: type, delimiter: str = ",", default: Optional[List[Any]] = None
    ) -> List:
        """
        Retrieves an environment variable intended to be a list and converts it to the expected type.

        Args:
            var_name (str): The name of the environment variable.
            expected_type (Type[T]): The type to which each list item is expected to be converted.
            delimiter (str): The delimiter used to split the environment variable string into a list.
            default (Optional[List[Any]], optional): The default value to use if the environment variable is not found.

        Returns:
            List[T]: The list of values, each converted to the expected type.

        Raises:
            EnvironmentError: If the environment variable is not found and no default is provided.
            ValueError, TypeError: If conversion to the expected type fails.
        """
        value_str = os.getenv(var_name)
        if value_str is None:
            if default is not None:
                return default
            else:
                raise EnvironmentError(f"Environment variable '{var_name}' not found.")

        items = value_str.split(delimiter)
        try:
            return [expected_type(item.strip()) for item in items]
        except ValueError:
            raise ValueError(f"Conversion error for one or more items in '{var_name}'.")

    def __str__(self) -> str:
        """
        Provides a string representation of all the configuration attributes.

        Returns:
            str: A string representation of the configuration attributes.
        """
        attributes = []
        for attr_name in dir(self):
            if not attr_name.startswith("_") and not callable(getattr(self, attr_name)):
                value = getattr(self, attr_name)
                attributes.append(f"{attr_name}: {value}")
        return "\n".join(attributes)


# Load env vars at startup
conf = Config()

# Setup global logging
setup_logging(conf)
