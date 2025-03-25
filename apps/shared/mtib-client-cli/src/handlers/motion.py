from corekinect.mtib_client.v1 import MtibV1Client
import typer


def handle_motion_status(client: MtibV1Client) -> None:
    status, err = client.get_motion_status()
    if err:
        raise Exception(f"Failed to get motion status: {err}")

    typer.echo(f"Motion status: {status}")
