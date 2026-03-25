import logging
import os
from typing import Any, Optional, Type

from dotenv import load_dotenv

from .log import setup_logging


class Config:
    """
    A singleton class for application configuration.
    """

    _instance = None

    LOG_LEVEL: int
    LOG_PATH: str
    OPERATOR_URL: str
    PROXY_SERVER_URL: str
    ELECTRICAL_TEST_PORT: int
    ELECTRICAL_TEST_UUID: str
    FW_FLASH_TEST_PORT: int
    FW_FLASH_TEST_UUID: str
    POST_TEST_PORT: int
    POST_TEST_UUID: str

    def __new__(cls: Type["Config"]) -> "Config":
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self) -> None:
        env_file_path = os.getenv("ENV_FILE_PATH")
        env_file_name = os.getenv("ENV_FILE_NAME")

        loaded = False
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
            loaded = load_dotenv()

            default_env_file = ".env"
            if os.path.exists(default_env_file) and os.path.isfile(default_env_file):
                print(f"Contents of {default_env_file}:", flush=True)
                with open(default_env_file, "r") as file:
                    print(file.read(), flush=True)
                loaded = True

        if not loaded:
            print("No .env file found. Falling back to OS environment variables.", flush=True)

        # Load environment variables
        self.LOG_LEVEL = self._get_env_var("LOG_LEVEL", int)
        self.LOG_PATH = self._get_env_var("LOG_PATH", str)
        self.OPERATOR_URL = self._get_env_var("OPERATOR_URL", str)
        self.PROXY_SERVER_URL = self._get_env_var("PROXY_SERVER_URL", str)
        self.ELECTRICAL_TEST_PORT = self._get_env_var("ELECTRICAL_TEST_PORT", int)
        self.ELECTRICAL_TEST_UUID = self._get_env_var("ELECTRICAL_TEST_UUID", str)
        self.FW_FLASH_TEST_PORT = self._get_env_var("FW_FLASH_TEST_PORT", int)
        self.FW_FLASH_TEST_UUID = self._get_env_var("FW_FLASH_TEST_UUID", str)
        self.POST_TEST_PORT = self._get_env_var("POST_TEST_PORT", int)
        self.POST_TEST_UUID = self._get_env_var("POST_TEST_UUID", str)

    def _get_env_var(self, var_name: str, expected_type: type, default: Optional[Any] = None) -> Any:
        value_str = os.getenv(var_name, default)
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

    def __str__(self) -> str:
        attributes = []
        for attr_name in dir(self):
            if not attr_name.startswith("_") and not callable(getattr(self, attr_name)):
                value = getattr(self, attr_name)
                attributes.append(f"{attr_name}: {value}")
        return "\n".join(attributes)


# Load env vars at startup
conf = Config()

# Setup global logging as early as possible
setup_logging(conf)
