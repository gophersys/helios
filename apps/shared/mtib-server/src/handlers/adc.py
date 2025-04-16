from typing import List
import grpc
from corekinect.utils import Logger
from src.shared.types import *

class AdcHandler:
    def __init__(self, logger: Logger):
        self.logger = logger

    def read(self, request: AdcReadRequest, context: grpc.ServicerContext) -> AdcReadResponse:
        """Read a single ADC channel."""
        self.logger.info(f"AdcRead request received for channel {request.channel}")
        # TODO: Implement ADC reading
        return AdcReadResponse(
            success=False,
            message="Not implemented",
            voltage_v=0.0
        )

    def read_all(self, request: Empty, context: grpc.ServicerContext) -> AdcReadAllResponse:
        """Read all ADC channels."""
        self.logger.info("AdcReadAll request received")
        # TODO: Implement reading all ADCs
        return AdcReadAllResponse(
            success=False,
            message="Not implemented",
            voltages_v=[]
        ) 