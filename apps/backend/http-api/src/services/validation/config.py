# Standard includes
import os
from dataclasses import dataclass
from typing import Dict, List, Optional

import yaml
from config.env import env_config
from corekinect.utils import Logger
from src.services.log.logger import get_logger

# -------------------------------------------------
#                                             Types
# -------------------------------------------------


@dataclass
class TestJobConfig:
    """Configuration for a single validation test job"""

    name: str
    test_type: str
    test_enable: Dict[str, bool]  # {"electrical": true, "app_post": false, etc.}
    required_features: Dict[str, str]  # {"joulescope": "true", etc.}
    description: Optional[str] = None


@dataclass
class ProductTestConfig:
    """Product validation test configuration loaded from YAML"""

    product: str
    jobs: List[TestJobConfig]

    @classmethod
    def from_yaml(cls, product: str, yaml_path: str) -> "ProductTestConfig":
        """Load product test configuration from YAML file"""
        logger: Logger = get_logger()

        if not os.path.exists(yaml_path):
            raise FileNotFoundError(f"Product test config not found: {yaml_path}")

        with open(yaml_path, "r") as f:
            config_data = yaml.safe_load(f)

        if not config_data:
            raise ValueError(f"Empty or invalid YAML file: {yaml_path}")

        if config_data.get("product") != product:
            logger.warning(f"Product mismatch in YAML: expected {product}, got {config_data.get('product')}")

        jobs = []
        for job_data in config_data.get("jobs", []):
            job = TestJobConfig(
                name=job_data["name"],
                test_type=job_data["test_type"],
                test_enable=job_data.get("test_enable", {}),
                required_features=job_data.get("required_features", {}),
                description=job_data.get("description"),
            )
            jobs.append(job)

        logger.info(f"Loaded {len(jobs)} test jobs for product {product} from {yaml_path}")

        return cls(product=product, jobs=jobs)


# -------------------------------------------------
#                                           Helpers
# -------------------------------------------------


def get_product_test_config(product: str) -> ProductTestConfig:
    """
    Get product test configuration from YAML file.

    Args:
        product: Product name (e.g., "sigma5")

    Returns:
        ProductTestConfig with all job definitions

    Raises:
        FileNotFoundError: If product config file doesn't exist
    """
    logger: Logger = get_logger()

    # Construct path to product config file
    products_dir = os.path.join(env_config.ASSETS_FOLDER, "products")
    yaml_path = os.path.join(products_dir, f"{product}.yaml")

    logger.debug(f"Loading product test config from: {yaml_path}")

    return ProductTestConfig.from_yaml(product, yaml_path)


def list_available_products() -> List[str]:
    """
    List all available product configurations.

    Returns:
        List of product names that have configuration files
    """
    products_dir = os.path.join(env_config.ASSETS_FOLDER, "products")

    if not os.path.exists(products_dir):
        return []

    products = []
    for filename in os.listdir(products_dir):
        if filename.endswith(".yaml") or filename.endswith(".yml"):
            product_name = os.path.splitext(filename)[0]
            products.append(product_name)

    return products
