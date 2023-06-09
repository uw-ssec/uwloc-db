import logging
import os
from datetime import datetime
from typing import Any, Tuple

import numpy as np
import numpy.typing as npt
import pandas as pd
import tiledb

logger = logging.getLogger(__name__)


# constants
SAMPLES_ARRAY_NAME = "samples"
DEVICES_ARRAY_NAME = "devices"
DIM_DEVICE = "device"
DIM_UNIT = "unit"
DIM_TIME = "time"
ATTRIB_SAMPLE = "sample"
ATTRIB_ROW = "row"
ATTRIB_TS = "timestamp"

META_RATE = "Sampling_Rate"
META_START_DATE = "Start_Date"

RATE = 192000
MAX_HOURS = 7  # 7 * 24  # ??
MAX_TIME = RATE * MAX_HOURS * 3600
EXTENT_HR = 3600 * RATE  # make tiles 1 hr wide?
EXTENT_MIN = 60 * RATE  # make tiles 1 min wide?
EXTENT_10S = 10 * RATE  # make tiles 1 min wide?
MAX_UNITS = 32


def init_tiledb() -> None:
    if tiledb.default_ctx() is None:
        cfg = tiledb.Ctx().config()
        cfg.update({"py.init_buffer_bytes": 1024**2 * 50})
        tiledb.default_ctx(cfg)


def create(
    dbpath: str,
    start_date: datetime,
    max_units: int,
    max_hrs: int,
) -> None:
    """
    Creates and initializes a new database and the given location
    """
    if not os.path.exists(dbpath):
        tiledb.group_create(dbpath)
    _create_samples_array(start_date, max_units, max_hrs, dbpath)
    _create_devices_array(dbpath)


def write_row(dbpath: str, device: str, timestamp: datetime, samples: npt.NDArray[np.int16]) -> None:
    """
    Writes a row of data for the given device ID
    """
    assert samples.ndim == 1, "Expected a 1D array"
    assert samples.dtype == np.int16, "Expected 16 bit PCM data"
    sam_path, dev_path = _get_array_paths(dbpath)

    # TODO: The timestamp should refer to the first recording for the device
    # we need to enforce this and append/shift data accordingly
    row_id, _ = _get_row_id(dev_path, device)
    with tiledb.open(dev_path, "w") as dev_array:
        dev_array[device] = {ATTRIB_ROW: row_id, ATTRIB_TS: timestamp}

    start_date = read_start_date(dbpath)
    if timestamp < start_date:
        raise ValueError(f"The timestamp {timestamp} is before the start date of the db ({start_date})")

    index = int((timestamp - start_date).total_seconds() * RATE)
    schema = tiledb.ArraySchema.load(sam_path)
    capacity = schema.domain.dim(DIM_TIME).size
    if index + samples.size > capacity:
        raise ValueError(
            f"The start timestamp ({timestamp}) and length ({samples.size}) "
            f"exceeds the DB capacity: {capacity}"
        )
    with tiledb.open(sam_path, "w") as sam_array:
        sam_array[row_id, index : index + samples.size] = samples


def tidy(dbpath: str) -> None:
    sam_path, dev_path = _get_array_paths(dbpath)
    tiledb.consolidate(sam_path)
    tiledb.consolidate(dev_path)
    tiledb.vacuum(dev_path)
    tiledb.vacuum(sam_path)


def get_devices(dbpath: str) -> npt.NDArray[np.str_]:
    """
    Fetch a list of device IDs in the given database
    """
    _, dev_path = _get_array_paths(dbpath)

    with tiledb.open(dev_path, "r") as dev_array:
        # convert to str since these are natively stored as bytes
        devices: npt.NDArray[np.str_] = dev_array[:][DIM_DEVICE].astype(str)
        return devices


def read_start_date(dbpath: str) -> datetime:
    """
    Read a slice of audio data for the given device and time range (in seconds)
    """
    sam_path, _ = _get_array_paths(dbpath)

    with tiledb.open(sam_path, "r") as sam_array:
        return _get_start_date(sam_array)


def _get_start_date(sam_array: Any) -> datetime:
    str_date = sam_array.meta[META_START_DATE]
    return datetime.fromisoformat(str_date)


def read_device_slice(dbpath: str, device: str, secs_start: int, secs_end: int) -> npt.NDArray[np.int16]:
    """
    Read a slice of audio data for the given device and time range (in seconds)
    """
    sam_path, dev_path = _get_array_paths(dbpath)
    row_id, exists = _get_row_id(dev_path, device)
    if not exists:
        logger.warning(f"Device '{device}' not found")
        return np.empty(0, dtype=np.int16)

    with tiledb.open(sam_path, "r") as sam_array:
        # tiledb.stats_enable()
        data: npt.NDArray[np.int16] = sam_array[row_id, samples_sec(secs_start) : samples_sec(secs_end)][
            ATTRIB_SAMPLE
        ]
        # tiledb.stats_dump()
        # tiledb.stats_disable()
        return data


def read_slice(dbpath: str, secs_start: int, secs_end: int) -> npt.NDArray[np.int16]:
    """
    Read a slice (time range) of audio data across all devices
    """
    sam_path, dev_path = _get_array_paths(dbpath)

    last_row, _ = _get_row_id(dev_path, "NON_EXISTENT")
    with tiledb.open(sam_path, "r") as sam_array:
        data: npt.NDArray[np.int16] = sam_array[0:last_row, samples_sec(secs_start) : samples_sec(secs_end)][
            ATTRIB_SAMPLE
        ]
        return data


def to_pandas(dbpath: str) -> pd.DataFrame:
    """
    Read the database into a pandas dataframe
    """
    sam_path, dev_path = _get_array_paths(dbpath)

    # get device id, row id and timestamp from the sparce devices array
    with tiledb.open(dev_path, "r") as dev_array:
        d = dev_array[:]

    # read the dense samples data
    with tiledb.open(sam_path, "r") as sam_array:
        samples = sam_array[0 : len(d[DIM_DEVICE])][ATTRIB_SAMPLE]

    columns = [DIM_DEVICE, ATTRIB_TS]
    data = {c: d[c] for c in columns}
    # TODO: This could be large but the access patterns and uses cases are not
    # known yet to make this more optimized.
    data[ATTRIB_SAMPLE] = list(samples)
    return pd.DataFrame(data, index=d[ATTRIB_ROW])


def _get_array_paths(dbpath: str) -> Tuple[str, str]:
    sam_path = os.path.join(dbpath, SAMPLES_ARRAY_NAME)
    dev_path = os.path.join(dbpath, DEVICES_ARRAY_NAME)
    return (sam_path, dev_path)


def _create_samples_array(start_date: datetime, max_units: int, max_hrs: int, dbpath: str) -> None:
    arr_path = os.path.join(dbpath, SAMPLES_ARRAY_NAME)
    if os.path.exists(arr_path):
        logger.warning(f"Not creating {arr_path} because it already exists")
        return

    # Create the two dimensions: unit -> rows, time -> columns
    unit_dim = tiledb.Dim(name=DIM_UNIT, domain=(0, max_units - 1), tile=1, dtype=np.int64)
    time_dim = tiledb.Dim(name=DIM_TIME, domain=(0, samples_hr(max_hrs) - 1), tile=EXTENT_MIN, dtype=np.int64)
    # Create a domain using the two dimensions
    dom1 = tiledb.Domain(unit_dim, time_dim)
    attrib_sample = tiledb.Attr(name=ATTRIB_SAMPLE, dtype=np.int16)
    schema = tiledb.ArraySchema(domain=dom1, sparse=False, attrs=[attrib_sample])
    tiledb.Array.create(arr_path, schema)
    with tiledb.open(arr_path, "w") as sam_array:
        sam_array.meta[META_START_DATE] = start_date.isoformat()


def _create_devices_array(dbpath: str) -> None:
    arr_path = os.path.join(dbpath, DEVICES_ARRAY_NAME)
    if os.path.exists(arr_path):
        logger.warning(f"Not creating {arr_path} because it already exists")
        return

    id_dim = tiledb.Dim(name=DIM_DEVICE, dtype="ascii")
    dom = tiledb.Domain(id_dim)
    attrib_ix = tiledb.Attr(name=ATTRIB_ROW, dtype=np.int16)
    # timestamp at millisecond resolution
    attrib_ts = tiledb.Attr(name=ATTRIB_TS, dtype=np.datetime64("", "ms").dtype)
    schema = tiledb.ArraySchema(domain=dom, sparse=True, attrs=[attrib_ix, attrib_ts])
    tiledb.Array.create(arr_path, schema)


def _get_row_id(dev_path: str, device: str) -> Tuple[int, bool]:
    with tiledb.open(dev_path, "r") as dev_array:
        # Does the device already have a row id?
        row_id = dev_array[device][ATTRIB_ROW]
        if len(row_id) > 0:
            return row_id[0], True

        # Assign the next row id
        row_ids = dev_array[:][ATTRIB_ROW]
        if len(row_ids) == 0:
            # emtpy array, first row is 0
            return 0, False
        else:
            return np.max(row_ids) + 1, False


def samples_hr(hrs: int) -> int:
    return samples_sec(3600 * hrs)


def samples_sec(sec: int) -> int:
    return sec * RATE
