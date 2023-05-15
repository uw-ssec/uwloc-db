import logging
import os
from pathlib import Path

import numpy as np

from uwloc.data.tile import (
    ATTRIB_SAMPLE,
    ATTRIB_TS,
    DEVICES_ARRAY_NAME,
    DIM_DEVICE,
    RATE,
    _get_row_id,
    create,
    get_devices,
    read_device_slice,
    to_pandas,
    write_row,
)
from uwloc.data.wav import read_wav

logger = logging.getLogger(__name__)
# device id in the metadata of data/test.wav
TEST_DEVICE_ID = "24F3190361DA539A"


def test_import(tmp_path: Path) -> None:
    dbpath = tmp_path.joinpath("db")
    dev_array = str(dbpath.joinpath(DEVICES_ARRAY_NAME))
    testwav = os.path.join(os.path.dirname(__file__), "../../../data/test.wav")

    # read wav data
    id, timestamp, rate, data = read_wav(testwav)
    assert id == TEST_DEVICE_ID
    assert rate == RATE
    assert data.size > 200000
    logger.info(f"Data size: {data.size}")

    # create new DB
    create(str(dbpath), 1, 1)
    # empty DB case, first row is 0
    assert _get_row_id(dev_array, "NEWID") == (0, False)

    # write data
    write_row(dbpath, id, timestamp, data)
    # the imported data should get the first row id
    assert _get_row_id(dev_array, TEST_DEVICE_ID) == (0, True)
    # now the new ID will be 1
    assert _get_row_id(dev_array, "NEWID") == (1, False)

    # read data
    assert get_devices(str(dbpath)) == [TEST_DEVICE_ID]
    data = read_device_slice(str(dbpath), TEST_DEVICE_ID, 2, 3)
    assert data.shape[0] == RATE  # 1 sec
    assert np.sum(data) != 0
    empty_data = read_device_slice(str(dbpath), "non existent", 2, 3)
    assert empty_data.shape[0] == 0  # emtpy

    df = to_pandas(str(dbpath))
    assert len(df) == 1
    assert len(df.columns) == 3
    for c in [DIM_DEVICE, ATTRIB_TS, ATTRIB_SAMPLE]:
        assert c in df.columns
