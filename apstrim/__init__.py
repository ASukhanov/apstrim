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
python -m apstrim.plot file.aps -iall -p

Example of Python usage for EPICS infrastructure:

>>> import apstrim
>>> from apstrim.pubEPICS import Access
>>> #Access.Dbg = True# To enable debugging in the publisher
>>> pvNames = ['testAPD:scope1:MeanValue_RBV','testAPD:scope1:Waveform_RBV']
>>> #apstrim.apstrim.Verbosity = 1# to enable debugging in apstrim
>>> aps = apstrim.apstrim(Access, pvNames)
>>> aps.start('myLogbook.aps')
... Every minute it should be printing logging progress:
... 24-10-21 10:59:44 Logged 1 sections, 2 parLists, 482.552 KBytes, 212.7 MB/s
...
>>> aps.stop()
24-10-21 11:00:15 Logged 2 sections, 4 parLists, 731.943 KBytes, 249.6 MB/s
Logging finished for 2 sections, 4 parLists, 731.943 KB.
"""

from .apstrim import apstrim

#__version__ = '2.0.5'
