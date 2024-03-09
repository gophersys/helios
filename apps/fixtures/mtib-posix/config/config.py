import os, builtins
import logging
from dotenv import load_dotenv
from typing import Optional, Any, Type

class Config:
    """
    A singleton class for application configuration.

    Attributes:
        DEBUG_ENABLED (int): Debug level for the logging library (4:DBG), (3:INF), (2:WRN), (1:ERR)
        MTIB_SERIAL_PORT (str): File descriptor for serial port connection with MTIB board.
        GRPC_SERVER_PORT (int): Port number for the GRPC server.
        FW_FILE_STORAGE_DIR (str): Host directory used to save/delete firmware files.
        MCU_9160_USB_BUS (str): USB bus were the JLink connected to the nrf9160 is connected
        MCU_52840_USB_BUS (str): USB bus were the JLink connected to the nrf52840 is connected
    """

    _instance = None

    DEBUG_LEVEL: int
    MTIB_SERIAL_PORT: str
    MTIB_SERIAL_BAUD: int
    GRPC_SERVER_PORT: int
    FW_FILE_STORAGE_DIR: str
    MCU_9160_USB_BUS: str
    MCU_52840_USB_BUS: str
    SERVER_RESET_ENABLED: bool
    SERVER_RESET_GPIO: int

    def __new__(cls: Type['Config']) -> 'Config':
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
        env_file_path = os.getenv('ENV_FILE_PATH')
        env_file_name = os.getenv('ENV_FILE_NAME')

        if env_file_path and env_file_name:
            loaded = load_dotenv(os.path.join(env_file_path, env_file_name))
        else:
            loaded = load_dotenv()  # This will load from '.env' file if present

        if not loaded:
            raise EnvironmentError("No configuration file found.")

        # Load 
        self.DEBUG_LEVEL = self._get_env_var('DEBUG_LEVEL', int)
        self.MTIB_SERIAL_PORT = self._get_env_var('MTIB_SERIAL_PORT', str)
        self.MTIB_SERIAL_BAUD = self._get_env_var('MTIB_SERIAL_BAUD', int)
        self.GRPC_SERVER_PORT = self._get_env_var('GRPC_SERVER_PORT', int)
        self.FW_FILE_STORAGE_DIR = self._get_env_var('FW_FILE_STORAGE_DIR', str)
        self.MCU_9160_USB_BUS = self._get_env_var('MCU_9160_USB_BUS', str)
        self.MCU_52840_USB_BUS = self._get_env_var('MCU_52840_USB_BUS', str)
        self.SERVER_RESET_ENABLED = self._get_env_var('SERVER_RESET_ENABLED', bool)
        self.SERVER_RESET_GPIO = self._get_env_var('SERVER_RESET_GPIO', int)

    def _get_env_var(self,
                     var_name: str,
                     expected_type: type,
                     default: Optional[Any] = None) -> type:
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
            raise TypeError(f"Environment variable '{var_name}' should be of type '{expected_type.__name__}', but got value '{value_str}' of type '{received_type}'.")

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

# Set the global debug level for the application
if conf.DEBUG_LEVEL == 4:
    logging.basicConfig(level=logging.DEBUG)
elif conf.DEBUG_LEVEL == 3:
    logging.basicConfig(level=logging.INFO)
elif conf.DEBUG_LEVEL == 2:
    logging.basicConfig(level=logging.WARN)
elif conf.DEBUG_LEVEL == 1:
    logging.basicConfig(level=logging.ERROR)
else:
    raise ValueError(f"Invalid debug level {conf.DEBUG_LEVEL}. Valid values 0-4")
