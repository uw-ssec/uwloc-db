import logging
import os
from typing import Tuple

import numpy as np
import numpy.typing as npt
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

META_DEPL_DATE = "Deployment_Date"
META_RATE = "Sampling_Rate"

RATE = 192000
MAX_HOURS = 1  # 7 * 24  # ??
MAX_TIME = RATE * MAX_HOURS * 3600
EXTENT_HR = 3600 * RATE  # make tiles 1 hr wide?
EXTENT_MIN = 60 * RATE  # make tiles 1 min wide?
MAX_UNITS = 32


def init_tiledb() -> None:
    if tiledb.default_ctx() is None:
        cfg = tiledb.Ctx().config()
        cfg.update({"py.init_buffer_bytes": 1024**2 * 50})
        tiledb.default_ctx(cfg)


def create(
    dbpath: str,
    max_units: int,
    max_hrs: int,
) -> None:
    """
    Creates and initializes a new database and the given location
    """
    if not os.path.exists(dbpath):
        tiledb.group_create(dbpath)
    _create_samples_array(max_units, max_hrs, dbpath)
    _create_devices_array(dbpath)


def write_row(dbpath: str, device: str, samples: npt.NDArray[np.int16]) -> None:
    """
    Writes a row of data for the given devide ID
    """
    assert samples.ndim == 1, "Expected a 1D array"
    assert samples.dtype == np.int16, "Expected 16 bit PCM data"
    sam_path = os.path.join(dbpath, SAMPLES_ARRAY_NAME)
    dev_path = os.path.join(dbpath, DEVICES_ARRAY_NAME)

    row_id, _ = _get_row_id(dev_path, device)
    with tiledb.open(dev_path, "w") as dev_array:
        dev_array[device] = row_id
    tiledb.consolidate(dev_path)
    tiledb.vacuum(dev_path)

    with tiledb.open(sam_path, "w") as sam_array:
        sam_array[row_id, 0 : samples.size] = samples
    tiledb.consolidate(sam_path)
    tiledb.vacuum(sam_path)


def get_devices(dbpath: str) -> npt.NDArray[np.str_]:
    """
    Fetch a list of device IDs in the given database
    """
    dev_path = os.path.join(dbpath, DEVICES_ARRAY_NAME)

    with tiledb.open(dev_path, "r") as dev_array:
        # convert to str since these are natively stored as bytes
        devices: npt.NDArray[np.str_] = dev_array[:][DIM_DEVICE].astype(str)
        return devices


def read_device_slice(dbpath: str, device: str, secs_start: int, secs_end: int) -> npt.NDArray[np.int16]:
    """
    Read a slice of audio data for the given device and time range (in seconds)
    """
    sam_path = os.path.join(dbpath, SAMPLES_ARRAY_NAME)
    dev_path = os.path.join(dbpath, DEVICES_ARRAY_NAME)
    row_id, exists = _get_row_id(dev_path, device)
    if not exists:
        logger.warning(f"Device '{device}' not found")
        return np.empty(0, dtype=np.int16)

    with tiledb.open(sam_path, "r") as sam_array:
        data: npt.NDArray[np.int16] = sam_array[row_id, samples_sec(secs_start) : samples_sec(secs_end)][
            ATTRIB_SAMPLE
        ]
        return data


def read_slice(dbpath: str, secs_start: int, secs_end: int) -> npt.NDArray[np.int16]:
    """
    Read a slice (time range) of audio data across all devices
    """
    sam_path = os.path.join(dbpath, SAMPLES_ARRAY_NAME)
    dev_path = os.path.join(dbpath, DEVICES_ARRAY_NAME)

    last_row, _ = _get_row_id(dev_path, "NON_EXISTENT")
    with tiledb.open(sam_path, "r") as sam_array:
        data: npt.NDArray[np.int16] = sam_array[0:last_row, samples_sec(secs_start) : samples_sec(secs_end)][
            ATTRIB_SAMPLE
        ]
        return data


def _create_samples_array(max_units: int, max_hrs: int, dbpath: str) -> None:
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


def _create_devices_array(dbpath: str) -> None:
    arr_path = os.path.join(dbpath, DEVICES_ARRAY_NAME)
    if os.path.exists(arr_path):
        logger.warning(f"Not creating {arr_path} because it already exists")
        return

    id_dim = tiledb.Dim(name=DIM_DEVICE, dtype="ascii")
    dom = tiledb.Domain(id_dim)
    attrib_ix = tiledb.Attr(name=ATTRIB_ROW, dtype=np.int16)
    schema = tiledb.ArraySchema(domain=dom, sparse=True, attrs=[attrib_ix])
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
