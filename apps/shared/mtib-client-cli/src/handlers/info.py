from corekinect.mtib_client.v1 import MtibV1Client
import typer


def handle_info(client: MtibV1Client) -> None:
    """
    Handler for the info command

    Args:
        client: Connected MTIB client instance
    """
    info, err = client.get_server_info()
    if err:
        raise Exception(f"Failed to get server info: {err}")

    typer.echo(f"Server Name: {info.name}")
    typer.echo(f"Version: {info.version}")
    typer.echo("\nHardware Configuration:")
    typer.echo(f"  ADC Count: {info.hardware.adc_count}")
    typer.echo(f"  GPIO Count: {info.hardware.gpio_count}")
    typer.echo(f"  J-Link Count: {info.hardware.j_link_count}")
