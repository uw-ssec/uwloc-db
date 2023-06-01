# Underwater Localization Database

This package provides functionality to store and query WAV data recorded with [AudioMoth](https://www.openacousticdevices.info/audiomoth) devices. It reads the AudioMoth device ID from the WAV file header and uses it as part of the "row" key. 
This ensures that the waveform data is always associated with the specific device that recorded it. 
[TileDB](https://tiledb.com/) is the underlying storage mechanism. This allows for efficient access of time slices of data across multiple recording devices.


[![Template](https://img.shields.io/badge/Template-LINCC%20Frameworks%20Python%20Project%20Template-brightgreen)](https://lincc-ppt.readthedocs.io/en/latest/)

This project was automatically generated using the LINCC-Frameworks [python-project-template](https://github.com/lincc-frameworks/python-project-template).

For more information about the project template see the For more information about the project template see the [documentation](https://lincc-ppt.readthedocs.io/en/latest/).

Dummy change