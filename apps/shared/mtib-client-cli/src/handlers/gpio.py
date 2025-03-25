from typing import Optional
import typer
from corekinect.mtib_client.v1 import MtibV1Client, GpioDirection, GpioResistorConfig


def handle_gpio_config(client: MtibV1Client, gpio: int, direction: str, resistor: str) -> None:
    """Handler for GPIO configuration"""
    try:
        gpio_direction = GpioDirection[direction.upper()]
        gpio_resistor = GpioResistorConfig[resistor.upper()]
    except KeyError:
        raise Exception(f"Invalid direction or resistor configuration")

    err = client.gpio_config(gpio, gpio_direction, gpio_resistor)
    if err:
        raise Exception(f"Failed to configure GPIO: {err}")

    typer.echo(f"Successfully configured GPIO {gpio}")


def handle_gpio_write(client: MtibV1Client, gpio: int, state: bool) -> None:
    """Handler for GPIO write"""
    err = client.gpio_write(gpio, state)
    if err:
        raise Exception(f"Failed to write GPIO: {err}")

    typer.echo(f"Successfully set GPIO {gpio} to {'HIGH' if state else 'LOW'}")


def handle_gpio_read(client: MtibV1Client, gpio: int) -> None:
    """Handler for GPIO read"""
    state, err = client.gpio_read(gpio)
    if err:
        raise Exception(f"Failed to read GPIO: {err}")

    typer.echo(f"GPIO {gpio} state: {'HIGH' if state else 'LOW'}")
