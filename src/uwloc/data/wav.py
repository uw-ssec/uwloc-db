import logging
from datetime import datetime
from typing import Tuple

import numpy as np
import numpy.typing as npt
import scipy.io.wavfile as wf
import wavinfo

logger = logging.getLogger(__name__)


def read_wav(file: str) -> Tuple[str, datetime, int, npt.NDArray[np.int16]]:
    """
    Read data and metadata for a .wav file

    Returns:
    Tuple of (device Id, recording timestamp, sample rate, data)
    """
    AUDIOMOTH = "AudioMoth"
    DATE_FORMAT = "%H:%M:%S %d/%m/%Y (%Z)"

    # Read metadata:
    info = wavinfo.WavInfoReader(file)
    if not hasattr(info.info, "artist"):
        logger.warning(f"'{file}' is missing the Device ID in the artist metadata")
        return ("", datetime.min, 0, np.empty(0, dtype=np.int16))

    # Artist field looks like this:
    # 'AudioMoth 24F3190361DA539A'
    device_id = info.info.artist.replace(AUDIOMOTH, "").strip()
    cmt = info.info.comment
    # Comment looks like this:
    # 'Recorded at 15:09:20 25/04/2023 (UTC) by AudioMoth 24F3190361DA539A ...'
    str_date = cmt[len("Recorded at ") : cmt.index(f"by {AUDIOMOTH}") - 1]
    date = datetime.strptime(str_date, DATE_FORMAT)

    # Read data:
    rate, data = wf.read(file)
    return (device_id, date, rate, data)
