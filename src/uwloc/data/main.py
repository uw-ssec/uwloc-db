import os
from datetime import datetime
from typing import Tuple

import numpy as np

# import scipy.io.wavfile as wf
import tiledb
import typer
import wavinfo

# constants
ATTRIB_SAMPLE = "sample"
META_DEPL_DATE = "Deployment_Date"
META_RATE = "Sampling_Rate"
AUDIOMOTH = "AudioMoth"

# Define the array size for one deployment. These are a best guess at this point
# but can be made to match the actual data size once we have it.
RATE = 192000
MAX_DAYS = 7  # ??
MAX_TIME = RATE * MAX_DAYS * 24 * 3600
EXTENT_HR = 3600 * RATE  # make tiles 1 hr wide?
MAX_UNITS = 32
DATE_FORMAT = "%H:%M:%S %d/%m/%Y (%Z)"

main = typer.Typer()


def init_tiledb() -> None:
    if tiledb.default_ctx() is None:
        cfg = tiledb.Ctx().config()
        cfg.update({"py.init_buffer_bytes": 1024**2 * 50})
        tiledb.default_ctx(cfg)


def samples_hr(hrs: int) -> int:
    return hrs * 3600 * RATE


def fail(msg: str) -> None:
    typer.echo(msg)
    raise typer.Exit(code=1)


@main.command()
def read_wav_meta(file: str) -> Tuple[str, datetime]:
    typer.echo(f"Reading {file}")
    info = wavinfo.WavInfoReader(file)
    device_id = info.info.artist.replace(AUDIOMOTH, "").strip()
    cmt = info.info.comment
    # Comment looks like this:
    # Recorded at 15:09:20 25/04/2023 (UTC) by AudioMoth 24F3190361DA539A ...
    str_date = cmt[len("Recorded at ") : cmt.index(f"by {AUDIOMOTH}") - 1]
    date = datetime.strptime(str_date, DATE_FORMAT)
    typer.echo(f"Device ID: '{device_id}', Date: {date}")
    return (device_id, date)


@main.command()
def initdb(dbpath: str) -> None:
    typer.echo(f"Initializing TileDB in {dbpath}")
    if not os.path.exists(dbpath):
        os.makedirs(dbpath, exist_ok=True)
        # Create the two dimensions: unit -> rows, time -> columns
        unit_dim = tiledb.Dim(name="unit", domain=(0, MAX_UNITS), tile=1, dtype=np.int64)
        time_dim = tiledb.Dim(name="time", domain=(0, MAX_TIME), tile=EXTENT_HR, dtype=np.int64)
        # Create a domain using the two dimensions
        dom1 = tiledb.Domain(unit_dim, time_dim)
        attrib_sample = tiledb.Attr(name=ATTRIB_SAMPLE, dtype=np.int16)
        schema = tiledb.ArraySchema(domain=dom1, sparse=False, attrs=[attrib_sample])
        tiledb.Array.create(dbpath, schema)


@main.command(name="import")
def _import(wavs_dir: str, dbpath: str) -> None:
    typer.echo(f"Uploading WAV files from {wavs_dir} {dbpath}")
    if not os.path.isdir(dbpath):
        fail(f"TileDB '{dbpath}' not found. Run initdb command first.")

    MIN_5 = RATE * 60 * 5
    data = np.zeros((1, MIN_5))
    with tiledb.open(dbpath, "w") as A:
        # Data
        A[0, 0 : data.size] = data
        # Metadata
        A.meta[META_DEPL_DATE] = str(datetime.now())
        A.meta[META_RATE] = RATE


if __name__ == "__main__":
    main()
