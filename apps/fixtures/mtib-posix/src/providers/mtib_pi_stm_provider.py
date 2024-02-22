# Standard includes
from typing import Tuple, Optional

# App includes
from config import conf

# Corekinect includes
from cipher import Cipher, CipherRpcErr

# Protocol includes
from .types import *
from protos.mtib_pi_stm.mtib_pi_stm_pb2_cipher import MtibPiStm

class MtibPiStmProvider(MtibPiStm):
    def __init__(self,daemon:Cipher):
        self.daemon = daemon
    
    def SigmaToPiMessageHandler(self, request) -> Tuple[UartMessageResponse, Optional[CipherRpcErr]]:
        print("Actual SigmaToPiMessageHandler handler called")
        response = UartMessageResponse()
        # Assuming no error occurs, return None as the error.
        return response, None

