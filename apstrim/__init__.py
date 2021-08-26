# Copyright (c) 2021 Andrei Sukhanov. All rights reserved.
#
# Licensed under the MIT License, (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/ASukhanov/upstrim/blob/main/LICENSE
#

"""Logger of Control System parameters and data objects.
Features:
- Supported Control Systems infrastructures: ADO, EPICS, LITE.
- Very fast random access retrieval of objects for selected time interval.
- Nonhomogeneous and homogeneous data are processed equally fast.
- Self-describing data format, no schema required.
- Efficient binary serialization format.
- Like JSON. But it's faster and smaller.
- Numpy arrays supported.
- Optional online compression.
- Basic plotting of logged data.
- Data extraction from a file is allowed when the file is being written.

Example of command line usage:

# Serialization of EPICS PVs MeanValue_RBV and Waveform_RBV from simscope IOC
python -m apstrim -nEPICS --compress testAPD:scope1:MeanValue_RBV,Waveform_RBV

# Serialization of 'cycle' and 'y'-array from a liteServer, running at liteHost
python -m apstrim -nLITE --compress liteHost:dev1:cycle,y

# De-serialization and plotting of the logged data files
python -m apstrim.plot *.aps

Example of Python usage for EPICS infrastructure:

import apstrim
from apstrim.pubEPICS import Access as publisher
pvNames = ['testAPD:scope1:MeanValue_RBV','testAPD:scope1:Waveform_RBV']
aps = apstrim.apstrim(publisher, pvNames)
aps.start('myLogbook.aps')
...
aps.stop()
"""

from .apstrim import apstrim

__version__ = '2.0.5'
