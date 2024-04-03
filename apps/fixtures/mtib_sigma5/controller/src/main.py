# Standard includes
from concurrent import futures
from typing import Tuple, Optional
import grpc
import logging
import threading
import time
import requests

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
#                                                                                        Keep Alive
# -----------------------------------------------------------------------------------------------*/
def keep_alive():
    proxy_url = "http://localhost:6969/v1/cluster/register"  
    cluster_data = {
        "cluster_id": "your_cluster_id",
        "cluster_info": {
            # Fill in the cluster information required by your proxy server
        }
    }

    while True:
        try:
            response = requests.post(proxy_url, json=cluster_data)
            if response.status_code == 200:
                pass
            else:
                logging.error(f"Failed to register cluster. Status code: {response.status_code}")
        except Exception as e:
            logging.error(f"Error during cluster registration: {str(e)}")

        time.sleep(1)  # Wait for 1 second before the next registration attempt

# -------------------------------------------------------------------------------------------------
#                                                                                              Main
# -----------------------------------------------------------------------------------------------*/
if __name__ == '__main__':
    print(conf)

    # Setup gRPC server
    success, server = setup_grpc_server()
    if not success:
        raise ValueError("Error setting up GRPC server")
    
    # Create a new thread to start for the keep alive in the server
    keep_alive_thread = threading.Thread(target=keep_alive, daemon=True)
    keep_alive_thread.start()

    # Await for kill signal
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        print("\n")
        logging.warning("Kill signal detected, stopping server...")
        server.stop(0)
        # daemon.stop()
        logging.info("Server stopped.")
    
    
