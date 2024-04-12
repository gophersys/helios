# Standard includes
from concurrent import futures
from typing import Tuple, Optional
import grpc
import logging
import wiringpi

# Corekinect includes
from cipher import *
from iface import *

# App includes
from config import conf
from providers.cluster_runner_provider import *
from src.providers.mtib_zephyr_provider import *

# Protocol includes
from protos.cluster_runner.cluster_runner_pb2 import *
from protos.cluster_runner.cluster_runner_pb2_grpc import add_ClusterRunnerServicer_to_server
from protos.mtib_zephyr.mtib_zephyr_pb2_cipher import *

# -------------------------------------------------------------------------------------------------
#                                                                       Cipher STM32 Server Helpers
# -----------------------------------------------------------------------------------------------*/
def reset_server():
    # Initialize wiringPi and set the mode to OUTPUT
    wiringpi.wiringPiSetup()
    wiringpi.pinMode(conf.SERVER_RESET_GPIO, wiringpi.GPIO.OUTPUT)
    
    # Drive the pin low
    wiringpi.digitalWrite(conf.SERVER_RESET_GPIO, wiringpi.GPIO.LOW)

    time.sleep(1)

    # Drive the pin high
    wiringpi.digitalWrite(conf.SERVER_RESET_GPIO, wiringpi.GPIO.HIGH)

    # Give it some time to start
    time.sleep(2)

    logging.info("Zephyr server has been reset")

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
    daemon.register_service(service=mtibzephyr_service_info, local=True)       

    # Register service provider
    mtib_service_provider = MtibZephyrProvider(daemon)
    daemon.register_service_provider(mtib_service_provider, mtibzephyr_service_info)
    
    logging.info(f"Cipher started") 
    
    return True, daemon

def setup_grpc_server(daemon:Cipher) -> Tuple[bool, Optional[grpc.Server]]:
    # Create gRPC server
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    
    # Register the MTIB service
    provider = ClusterRunnerServicerProvider()
    add_ClusterRunnerServicer_to_server(provider, server)

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
    logging.debug(f"App configuration: \n{conf}")
    
    # Reset the server
    if conf.SERVER_RESET_ENABLED is True:
        reset_server()

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
    
    
