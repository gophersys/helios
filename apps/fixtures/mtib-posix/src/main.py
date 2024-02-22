# Standard includes
from concurrent import futures
from typing import Tuple, Optional
import grpc
import logging

# Corekinect includes
from cipher import *
from iface import *

# App includes
from config import conf
from src.providers.mtib_cs_pi_provider import *
from src.providers.mtib_pi_stm_provider import *

# Protocol includes
from protos.mtib_cs_pi.mtib_cs_pi_pb2_cipher import *
from protos.mtib_cs_pi.mtib_cs_pi_pb2_grpc import add_MtibCsPiServicer_to_server
from protos.mtib_pi_stm.mtib_pi_stm_pb2_cipher import *

# -------------------------------------------------------------------------------------------------
#                                                                                             Setup
# -----------------------------------------------------------------------------------------------*/
def setup_cipher_daemon() -> Tuple[bool, Optional[Cipher]]:
    # Daemon configuration
    uart_iface =  Iface(
        type=IfaceType.UART,
        link=IfaceLinkType.CLIENT,
        uart_port=conf.MTIB_SERIAL_PORT,
        baudrate=conf.MTIB_SERIAL_BAUD
    )
    client_config = CipherConfig(server_ifaces=[], client_ifaces=[uart_iface])

    # Instantiate & start the daemon
    daemon = Cipher()
    if not daemon.init(client_config):
        logging.error("Could not initialize cipher application daemon")
        return False, None
    
    logging.info("Daemon initialized OK")
    
    # Register services
    daemon.register_service(service=mtibpistm_service_info, local=True)       

    # Register service provider
    mtib_service_provider = MtibPiStmProvider(daemon)
    daemon.register_service_provider(mtib_service_provider, mtibpistm_service_info)
    
    logging.info(f"Cipher started") 
    
    return True, daemon

def setup_grpc_server(daemon:Cipher) -> Tuple[bool, Optional[grpc.Server]]:
    # Create gRPC server
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    
    # Register the MTIB service
    provider = MtibCsPiServicerProvider()
    add_MtibCsPiServicer_to_server(provider, server)

    # Pass the cipher daemon to the service provider
    provider.SetInternalDaemon(daemon)
        
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
    # Setup Cipher Daemon
    success, daemon = setup_cipher_daemon()
    if not success:
        raise ValueError("Error setting up communication with MTIB")
    
    # Setup gRPC server
    success, server = setup_grpc_server(daemon)
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
    
    
