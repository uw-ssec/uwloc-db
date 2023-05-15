import glob
import os

import typer
from typing_extensions import Annotated

from .tile import MAX_HOURS, MAX_UNITS, create, init_tiledb, write_row
from .wav import read_wav

main = typer.Typer()


def fail(msg: str) -> None:
    typer.echo(msg)
    raise typer.Exit(code=1)


@main.command()
def initdb(
    dbpath: str,
    max_units: Annotated[
        int, typer.Argument(help="Maximum number of units (rows) to store in the array")
    ] = MAX_UNITS,
    max_hrs: Annotated[int, typer.Argument(help="Maximum amount of hours to store in the array")] = MAX_HOURS,
) -> None:
    typer.echo(f"Initializing TileDB in {dbpath}")
    create(dbpath, max_units, max_hrs)


@main.command(name="import")
def _import(wavs_dir: str, dbpath: str) -> None:
    typer.echo(f"Uploading WAV files from {wavs_dir} {dbpath}")
    if not os.path.isdir(dbpath):
        fail(f"TileDB '{dbpath}' not found. Run initdb command first.")

    files = glob.iglob(os.path.join(wavs_dir, "**/*.[wW][aA][vV]"), recursive=True)
    # TODO: Handle multiple recording files from the same device. These need to be sorted
    # and laid out correctly in the array
    for f in files:
        (device, timestamp, rate, data) = read_wav(f)
        if len(device) == 0:
            typer.echo(f"{f} is missing the Device ID, skipping")
            continue
        secs = data.size // rate
        typer.echo(
            f"Importing  {f}. Timestamp: {timestamp} Device: {device}, rate: {rate}, dtype: {data.dtype}, secs: {secs}"
        )
        write_row(dbpath, device, timestamp, data)


if __name__ == "__main__":
    init_tiledb()
    main()
