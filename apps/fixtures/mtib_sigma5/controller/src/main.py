# Standard includes
from concurrent import futures
from typing import Tuple, Optional
import grpc
import logging

# App includes
from config import conf
from src.providers.mtib_controller_provider import MtibControllerServicerProvider

# Protocol includes
from protos.mtib_controller.mtib_controller_pb2 import *
from protos.mtib_controller.mtib_controller_pb2_grpc import add_MtibControllerServicer_to_server

# -------------------------------------------------------------------------------------------------
#                                                                                             Setup
# -----------------------------------------------------------------------------------------------*/
def setup_grpc_server() -> Tuple[bool, Optional[grpc.Server]]:
    # Create gRPC server
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    
    # Register the MTIB service
    provider = MtibControllerServicerProvider()
    add_MtibControllerServicer_to_server(provider, server)
        
    # Serve
    server.add_insecure_port(f'[::]:{conf.GRPC_SERVER_PORT}') 
    server.start()
    
    logging.info(f"Server started, listening on port {conf.GRPC_SERVER_PORT}.") 

    return True, server

# -------------------------------------------------------------------------------------------------
#                                                                                              Main
# -----------------------------------------------------------------------------------------------*/
if __name__ == '__main__':
    print(conf)

    # Setup gRPC server
    success, server = setup_grpc_server()
    if not success:
        raise ValueError("Error setting up GRPC server")
    
    # Await for kill signal
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        print("\n")
        logging.warning("Kill signal detected, stopping server...")
        server.stop(0)
        # daemon.stop()
        logging.info("Server stopped.")
    
    
