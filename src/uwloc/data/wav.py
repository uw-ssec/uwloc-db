import logging
from datetime import datetime, timedelta
from typing import Tuple

import numpy as np
import numpy.typing as npt
import pytz
import scipy.io.wavfile as wf
import wavinfo
from dateutil import parser

logger = logging.getLogger(__name__)


def parse_date(dstr: str) -> datetime:
    # Positive due to unix artifact
    # See https://pubs.opengroup.org/onlinepubs/7908799/xsh/tzset.html
    # See https://stackoverflow.com/questions/11984618/why-does-python-return-a-negative-timezone-value
    dt = parser.parse(dstr, fuzzy=True)
    if dt.tzinfo is None:
        raise ValueError(f"'{dstr}' is missing time zone info")
    offset = dt.tzinfo.utcoffset(dt) or timedelta(0)
    date = (dt + offset).replace(tzinfo=pytz.utc)
    return date


def read_wav(file: str) -> Tuple[str, datetime, int, npt.NDArray[np.int16]]:
    """
    Read data and metadata for a .wav file

    Returns:
    Tuple of (device Id, recording timestamp, sample rate, data)
    """
    device_id, date = read_wav_metadata(file)
    if len(device_id) == 0:
        return ("", datetime.min, 0, np.empty(0, dtype=np.int16))

    # Read data:
    rate, data = wf.read(file)
    return (device_id, date, rate, data)


def read_wav_metadata(file: str) -> Tuple[str, datetime]:
    AUDIOMOTH = "AudioMoth"

    # Read metadata:
    info = wavinfo.WavInfoReader(file)
    if not hasattr(info.info, "artist"):
        logger.warning(f"'{file}' is missing the Device ID in the artist metadata")
        return ("", datetime.min)

    # Artist field looks like this:
    # 'AudioMoth 24F3190361DA539A'
    device_id = info.info.artist.replace(AUDIOMOTH, "").strip()
    cmt = info.info.comment
    # Comment looks like this:
    # 'Recorded at 15:09:20 25/04/2023 (UTC) by AudioMoth 24F3190361DA539A ...'
    str_date = cmt[len("Recorded at ") : cmt.index(f"by {AUDIOMOTH}") - 1]
    date = parse_date(str_date)
    return (device_id, date)
