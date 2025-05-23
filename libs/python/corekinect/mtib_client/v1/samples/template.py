# Standard includes
# Add your imports here

# Corekinect includes
from corekinect.utils import Logger

# Private includes
from corekinect.mtib_client.v1 import MtibV1Client
from corekinect.mtib_client.v1.samples.helper import run_sample


def template_sample(client: MtibV1Client, logger: Logger) -> None:
    """
    Template for creating new samples.
    Replace this docstring with a description of what your sample does.
    """
    # Your sample code goes here
    logger.info("Running template sample")
    
    # Example of how to access the client
    ready, errors = client.health_check()
    logger.info(f"Server health: ready={ready}, errors={errors}")
    
    # Add your functionality here


if __name__ == "__main__":
    run_sample(template_sample, "template_sample") 