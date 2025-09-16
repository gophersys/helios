# Standard includes
import asyncio
import logging
import sys
import urllib3

# Suppress HTTP requests warnings when (verify=False)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# App includes
from config import conf
from tests.electrical.test import electrical_test
from tests.fw_flash.test import fw_flash_test
from tests.post.test import post_test

# from tests.post.test import post_test


async def wait_for_termination(servers):
    try:
        await asyncio.gather(*(server.wait_for_termination() for server in servers))
    except KeyboardInterrupt:
        for server in servers:
            server.teardown()
        sys.exit(1)


if __name__ == "__main__":
    logging.debug(f"Test app environment configuration: \n{conf}")

    # Electrical test
    if error := electrical_test.setup(conf.ELECTRICAL_TEST_UUID, conf.ELECTRICAL_TEST_PORT, conf.OPERATOR_URL):
        logging.error(f"Could not setup electrical test: {error}")
        sys.exit(1)

    # Firmware flashing test
    if error := fw_flash_test.setup(conf.FW_FLASH_TEST_UUID, conf.FW_FLASH_TEST_PORT, conf.OPERATOR_URL):
        logging.error(f"Could not setup firmware flash test: {error}")
        sys.exit(1)

    # POST Test
    if error := post_test.setup(conf.POST_TEST_UUID, conf.POST_TEST_PORT, conf.OPERATOR_URL):
        logging.error(f"Could not setup POST test: {error}")
        sys.exit(1)

    # Await program termination
    servers = [electrical_test.server, fw_flash_test.server, post_test.server]
    asyncio.run(wait_for_termination(servers))
