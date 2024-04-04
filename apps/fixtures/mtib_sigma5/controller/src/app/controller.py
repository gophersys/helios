import logging
import grpc
import uuid
import time
import threading

class ControllerServer:
    _instance = None
    error:str = ""

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(ControllerServer, cls).__new__(cls, *args, **kwargs)
        return cls._instance
    
    def set_internal_error(self, error:str):
        self.error = error