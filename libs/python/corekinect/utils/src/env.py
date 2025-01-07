import os
from dotenv import load_dotenv
from typing import Any, Optional, List, Type


class EnvConfig:
    """
    A base configuration class that dynamically loads environment variables
    based on the fields defined in subclasses.
    """

    def __init__(self) -> None:
        """
        Initialize the configuration by dynamically loading environment variables.
        Subclasses should define fields with the expected types, and the values
        will be loaded and converted automatically.
        """
        self._load_env_file()  # Load .env file before initializing
        self._initialize()

    def _load_env_file(self) -> None:
        """
        Loads environment variables from a specific .env file or a default .env file.
        If no file is found, it falls back to system environment variables.
        """
        env_file_path = os.getenv("ENV_FILE_PATH")
        env_file_name = os.getenv("ENV_FILE_NAME")

        loaded = False
        if env_file_path and env_file_name:
            env_file = os.path.join(env_file_path, env_file_name)

            if os.path.exists(env_file):
                if os.path.isfile(env_file):
                    loaded = load_dotenv(env_file)  # Loads variables from the .env file
                else:
                    raise EnvironmentError(f"{env_file} is not a file.")
            else:
                raise EnvironmentError(f"{env_file} does not exist.")
        else:
            print("No specific env file path and name provided, trying to load default .env", flush=True)
            loaded = load_dotenv(".env")  # This will load from '.env' file if present

            default_env_file = ".env"
            if os.path.exists(default_env_file) and os.path.isfile(default_env_file):
                loaded = True

        if not loaded:
            print("No .env file found. Falling back to OS environment variables.", flush=True)

    def _initialize(self) -> None:
        """
        Dynamically initialize the configuration by loading values from environment variables.
        The subclass defines the configuration fields, and their types are inferred.
        """
        for attr_name, expected_type in self.__annotations__.items():
            # Make sure environment variables are checked after loading the .env file
            env_var_value = os.getenv(attr_name.upper())
            if env_var_value is None:
                raise EnvironmentError(f"Environment variable '{attr_name.upper()}' not found.")
            else:
                setattr(self, attr_name, self._convert_value(env_var_value, expected_type))

    def _convert_value(self, value: str, expected_type: Type[Any]) -> Any:
        """
        Convert the value from the environment variable to the expected type.

        Args:
            value (str): The value from the environment variable.
            expected_type (Type[Any]): The expected type to convert the value to.

        Returns:
            Any: The converted value.
        """
        try:
            if expected_type == bool:
                return value.lower() in ["true", "1", "yes"]
            elif expected_type == List[str]:
                return value.split(",")  # Assuming comma-delimited strings for lists
            else:
                return expected_type(value)
        except ValueError:
            raise TypeError(f"Could not convert '{value}' to {expected_type.__name__}.")

    def __str__(self) -> str:
        """
        Provide a string representation of all the configuration attributes.
        """
        attributes = []
        for attr_name in dir(self):
            if not attr_name.startswith("_") and not callable(getattr(self, attr_name)):
                value = getattr(self, attr_name)
                attributes.append(f"{attr_name}: {value}")
        return "\n".join(attributes)
