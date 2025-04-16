# Standard imports
import logging
import time
from typing import Optional, List
from dataclasses import dataclass


# Protocol imports
from protocols.mtib.mtib_pb2_grpc import MtibV1Servicer

# 3rd party imports
import grpc

# Corekinect imports
from corekinect.utils import Logger

# Protocol imports
from src.shared.types import *

# Private imports
from .config import ProviderConfig
from .helpers import grpc_method

LOG_MODULE = "dev-provider"


class DevProvider(MtibV1Servicer):
    def __init__(self, config: ProviderConfig, logger: Logger = None):
        # Setup the logger for the server
        self.logger: Logger = logger
        if self.logger is None:
            self.logger = Logger(
                Logger.Config(
                    logger_name=LOG_MODULE,
                    log_directory="logs",
                    overall_log_level=logging.DEBUG,
                    console_log_level=logging.DEBUG,
                    file_log_level=logging.DEBUG,
                    enable_log_color=True,
                )
            )
        else:
            # Create a child logger from the parent
            self.logger = logger.from_parent(LOG_MODULE)

        # Setup the config
        self.config: ProviderConfig = config

        # Create a list of the components that will be checked in the health check
        self._components: List[Component] = [
            Component(name="Gpio", ready=True, error=""),
            Component(name="Adc", ready=True, error=""),
            Component(name="DutPower", ready=False, error="DUT power is not connected"),
            Component(name="DutChargePower", ready=True, error=""),
            Component(name="Altimeter", ready=True, error=""),
            Component(name="Accel", ready=True, error=""),
        ]

        self.logger.info("Development provider initialized OK")

    @grpc_method
    def HealthCheck(self, request: Empty, context: grpc.ServicerContext) -> HealthCheckResponse:
        response = HealthCheckResponse(ready=True, components=self._components)

        # Check if the server is ready for requests
        for component in self._components:
            if not component.ready:
                self.logger.error("Component %s is not ready: %s", component.name, component.error)
                response.ready = False

        return response