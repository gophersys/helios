from corekinect.test.config import ValidationTestConfig
from corekinect.utils.log import Logger


def check_required_fields(required_fields, config_name="configuration"):
    """
    Check if the required fields are present in the config.

    Parameters:
        config (object): The configuration object to validate.
        required_fields (dict): A dictionary of field names and their values to check.
        config_name (str): The name of the configuration for logging purposes (default: "configuration").

    Raises:
        ValueError: If any required fields are missing.
    """
    log = Logger.get_test_case_logger()
    log.debug(f"Checking required fields in {config_name}.")

    missing_fields = [field for field, value in required_fields.items() if value is None]

    if missing_fields:
        log.error(f"{config_name} is missing required fields: {', '.join(missing_fields)}")
        raise ValueError(f"{config_name} is missing required fields: {', '.join(missing_fields)}")
