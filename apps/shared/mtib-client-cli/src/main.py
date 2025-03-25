# Standard includes
import os
import sys
import typer
from typing import Optional

# Corekinect includes
from corekinect.utils import EnvConfig, Logger

# Local includes
from src.handlers import (
    handle_info,
    handle_gpio_config,
    handle_gpio_write,
    handle_gpio_read,
    handle_motion_status,
    run_with_client,
)

# Create the Typer app
app = typer.Typer(
    name="mtib-cli",
    help="CLI tool for interacting with MTIB server",
    add_completion=False,
)


# Environment variables for the Mtib client
class MtibCliEnvConfig(EnvConfig):
    LOG_LEVEL: int
    LOG_PATH: str
    SERVER_HOST: str
    SERVER_PORT: int


# Global config and logger - declare without type annotations
config = None
logger = None


def init_app():
    """Initialize the application configuration and logging"""
    global config, logger

    try:
        # Load configuration
        config = MtibCliEnvConfig()

        # Setup logging
        log_config = Logger.Config(
            logger_name="mtib-cli",
            log_directory=config.LOG_PATH,
            overall_log_level=config.LOG_LEVEL,
            console_log_level=config.LOG_LEVEL,
            file_log_level=config.LOG_LEVEL,
            enable_log_color=True,
        )
        logger = Logger(log_config)

    except Exception as e:
        print(f"Failed to initialize application: {e}", file=sys.stderr)
        sys.exit(1)


# Example command group
@app.command()
def info():
    """Get server information"""
    run_with_client(handle_info, config, logger)


@app.command()
def dummy():
    """Dummy command"""
    print("Dummy command")


# GPIO command group
@app.command(name="gpio-config")
def gpio_config(
    gpio: int = typer.Argument(..., help="GPIO pin number"),
    direction: str = typer.Argument(..., help="Direction (INPUT/OUTPUT)"),
    resistor: str = typer.Argument(..., help="Resistor config (NONE/PULL_UP/PULL_DOWN)"),
):
    """Configure a GPIO pin"""
    run_with_client(handle_gpio_config, config, logger, gpio, direction, resistor)


@app.command(name="gpio-write")
def gpio_write(
    gpio: int = typer.Argument(..., help="GPIO pin number"),
    state: bool = typer.Argument(..., help="Pin state (True/False)"),
):
    """Set GPIO output state"""
    run_with_client(handle_gpio_write, config, logger, gpio, state)


@app.command(name="gpio-read")
def gpio_read(gpio: int = typer.Argument(..., help="GPIO pin number")):
    """Read GPIO input state"""
    run_with_client(handle_gpio_read, config, logger, gpio)


@app.command(name="motion-status")
def motion_status():
    """Get motion status"""
    run_with_client(handle_motion_status, config, logger)


# Add more command groups here...

if __name__ == "__main__":
    init_app()
    app()
