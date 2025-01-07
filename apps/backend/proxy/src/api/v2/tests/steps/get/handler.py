# Standard includes
import json
import importlib.util
import os
import sys

# 3rd party includes
from flask import Blueprint, jsonify, current_app

# Corekinect includes
from corekinect.utils import Logger

# App includes
from src.server import ProxyEnvConfig

test_step_get_bp = Blueprint("test_step_get", __name__)


def import_module_from_path(module_name, file_path):
    """Dynamically import a module from the given file path."""
    try:
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        current_app.logger.debug(f"Successfully imported module '{module_name}' from '{file_path}'")
        return module
    except Exception as e:
        current_app.logger.error(f"Failed to import module '{module_name}' from '{file_path}': {str(e)}")
        raise e


@test_step_get_bp.route("/v1/tests/steps", methods=["GET"])
def test_steps_get():
    # Get global server objects
    logger: Logger = current_app.config.get("logger", None)
    env_config: ProxyEnvConfig = current_app.config.get("env_config", None)

    # Handle requests
    try:
        logger.debug("Loading test steps configuration...")

        # Define the path to the config file
        test_steps_config_file_path = env_config.TEST_STEPS_CONFIG_PATH

        # Load the JSON data from the file
        with open(test_steps_config_file_path, "r") as file:
            config_data = json.load(file)
        logger.debug(f"Configuration loaded successfully: {config_data}")

        # Initialize an empty list to collect all test steps info and default configs
        test_steps_summary = []

        # Get the list of paths from the configuration (using 'step_paths' instead of 'paths')
        paths = config_data.get("paths", {}).get("validation", [])
        logger.debug(f"Validation paths found: {paths}")

        # Loop through each path in the configuration
        for path in paths:
            logger.debug(f"Processing path: {path}")

            # Look for __init__.py in the specified path
            init_file_path = os.path.join(path, "__init__.py")

            if os.path.isfile(init_file_path):
                logger.debug(f"Found __init__.py at: {init_file_path}")

                # Extract module name from path
                module_name = os.path.basename(path).replace("/", ".")
                logger.debug(f"Attempting to import module: {module_name}")

                # Dynamically import the module
                try:
                    module = import_module_from_path(module_name, init_file_path)
                except Exception as import_error:
                    logger.error(f"Error importing module: {import_error}")
                    continue

                # Get all imported types from the module (e.g., SimpleTestStep)
                for name in dir(module):
                    obj = getattr(module, name)

                    # Check if it's a class with the expected structure
                    if isinstance(obj, type) and hasattr(obj, "info") and hasattr(obj, "Config"):
                        logger.debug(f"Found test step class: {name} in {path}")

                        # Try to access the info and default configuration
                        try:
                            # Return the actual dictionary representation instead of JSON strings
                            test_step_info = obj().info.__dict__
                            test_step_config = obj.Config().__dict__
                            logger.debug(f"Info: {test_step_info}")
                            logger.debug(f"Default config: {test_step_config}")
                        except Exception as class_error:
                            logger.error(f"Error accessing info or Config for class '{name}': {class_error}")
                            continue

                        # Append to the summary list
                        test_steps_summary.append(
                            {"class_name": name, "info": test_step_info, "config": test_step_config}
                        )
            else:
                logger.warning(f"No __init__.py found in path: {path}")

        # Return the collected test step summaries
        logger.debug(f"Returning test step summaries: {test_steps_summary}")
        return jsonify(test_steps_summary), 200

    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500
