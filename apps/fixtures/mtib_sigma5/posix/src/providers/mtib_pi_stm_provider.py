# Standard includes
import os
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
    
    def SigmaToPiMessageHandler(self, request) -> Tuple['UartMessageResponse', Optional['CipherRpcErr']]:
        log_file_path = "/workspaces/concord/apps/fixtures/mtib_posix/logs/log.txt"

        # Ensure the directory exists before attempting to open the file
        os.makedirs(os.path.dirname(log_file_path), exist_ok=True)

        # Open the log file in append mode, or create it if it doesn't exist.
        try:
            with open(log_file_path, "ab") as log_file:  # Use "ab" for appending in binary mode
                log_file.write(request.data)
        except Exception as e:
            response = UartMessageResponse(success=False, error=str(e))
            return response, None
        
        response = UartMessageResponse(success=True, error="") 
        return response, None

