import glob
import logging
import os
from datetime import datetime, timezone

import typer
from typing_extensions import Annotated

from .tile import MAX_HOURS, MAX_UNITS, create, init_tiledb, tidy, write_row
from .wav import read_wav, read_wav_metadata

WAV_PATTERN = "**/*.[wW][aA][vV]"
app = typer.Typer()
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(module)s %(funcName)s %(message)s"
)


def fail(msg: str) -> None:
    typer.echo(msg)
    raise typer.Exit(code=1)


@app.command()
def initdb(
    dbpath: str,
    wavs_dir: str,
    max_units: Annotated[
        int, typer.Argument(help="Maximum number of units (rows) to store in the array")
    ] = MAX_UNITS,
    max_hrs: Annotated[int, typer.Argument(help="Maximum amount of hours to store in the array")] = MAX_HOURS,
) -> None:
    start_date: datetime = _find_start_date(wavs_dir)
    typer.echo(f"Initializing TileDB in {dbpath} with start date: {start_date}")
    create(dbpath, start_date, max_units, max_hrs)
    import_wavs(dbpath, wavs_dir)


@app.command(name="import")
def import_wavs(
    dbpath: str,
    wavs_dir: str,
) -> None:
    typer.echo(f"Uploading WAV files from {wavs_dir} {dbpath}")
    if not os.path.isdir(dbpath):
        fail(f"TileDB '{dbpath}' not found. Run initdb command first.")

    files = sorted(glob.iglob(os.path.join(wavs_dir, WAV_PATTERN), recursive=True))
    for f in files:
        try:
            device, timestamp, rate, data = read_wav(f)
            if len(device) == 0:
                logger.warning(f"{f} is missing the Device ID, skipping")
                continue
            secs = data.size // rate
            typer.echo(f"Importing  {f}. Timestamp: {timestamp} Device: {device}, secs: {secs}")
            write_row(dbpath, device, timestamp, data)
        except Exception as e:
            logger.warning(f"Warning: Failed to import {f}. {e}")
    tidy(dbpath)


def _find_start_date(wavs_dir: str) -> datetime:
    start_date = datetime.max.replace(tzinfo=timezone.utc)
    files = sorted(glob.iglob(os.path.join(wavs_dir, WAV_PATTERN), recursive=True))
    for f in files:
        try:
            _, timestamp = read_wav_metadata(f)
            start_date = min(timestamp, start_date)
        except Exception as e:
            logger.warning(f"Warning: Failed to read {f}. {e}")
    return start_date


init_tiledb()
