import eventlet
from flask import Flask
from flask_socketio import SocketIO
import asyncio
from prisma import Prisma
from typing import List

# Corekinect libraries
from corekinect.utils import Logger, EnvConfig

eventlet.monkey_patch(socket=True, select=False, time=False, os=False, thread=False)


class ProxyEnvConfig(EnvConfig):
    DELETE_ALL_KEY: str
    LOG_LEVEL: int
    LOG_PATH: str
    SERVER_PORT: int
    DB_STORAGE_PATH: str
    DB_STORAGE_LIMIT_GB: int
    SUPPORTED_REGISTRIES: List[str]
    AUTH_ENABLED: bool
    AUTH_SERVER_URL: str
    AUTH_SERVER_API_KEY: str
    AUTH_SERVER_CREDENTIALS_USER: str
    AUTH_SERVER_CREDENTIALS_PASS: str
    MANU_SERVER_URL: str
    TEST_STEPS_CONFIG_PATH: str


class Proxy:
    class Config:
        def __init__(
            self,
            debug: bool = False,
            addr: str = "0.0.0.0",
            logger: Logger = None,
            env: ProxyEnvConfig = None,
        ):
            self.debug = debug
            self.addr = addr
            self.logger = logger
            self.env = env

    def __init__(
        self,
        config: Config,
    ):
        """Initialize the main components of the proxy server using provided config."""
        self.config: Proxy.Config = config

        # Flask application
        self.app = Flask(__name__)

        # Store the logger in the app config so it can be accessed globally
        self.logger: Logger = self.config.logger
        self.app.config["logger"] = self.logger

        # Store the environment config in the app so it can be accessed globally
        self.env_config: ProxyEnvConfig = self.config.env
        self.app.config["env_config"] = self.env_config

        # Prisma database client (initialize with the specified database URL from config)
        self.postgres_db = Prisma(auto_register=True)
        self.app.config["postgres_db"] = self.postgres_db

        # SocketIO server wrapped around the Flask app for real-time communication
        self.socketio_server = SocketIO(self.app, debug=True, cors_allowed_origins="*", async_mode="eventlet")

    def init_db(self):
        """Initialize the Prisma database client and create a sample record."""
        try:
            self.postgres_db.connect()
            self.logger.debug("Postgres database connected")
        except Exception as e:
            self.logger.error(f"Error connecting to postgres database: {e}")
            self.deinit()

    def deinit(self):
        """Clean up resources when the server stops or is killed."""
        self.logger.debug("Cleaning up resources...")

        # Disconnect the Prisma database client
        if self.postgres_db.is_connected():
            self.postgres_db.disconnect()
            self.logger.debug("Postgres database disconnected.")

    def listen(self):
        """Run the server and initialize all services."""
        try:
            # Initialize any server's global objects
            self.init_db()

            self.logger.info("All server services initialized. Starting the server...")

            # Start the SocketIO server
            self.socketio_server.run(
                app=self.app,
                host=self.config.addr,
                port=self.config.env.SERVER_PORT,
                debug=self.config.debug,
            )

        except Exception as e:
            self.logger.error(f"Error starting the server: {e}")

        finally:
            # Ensure clean-up when the server stops or encounters an error
            self.deinit()


# Global server object
proxy_server: Proxy = None
