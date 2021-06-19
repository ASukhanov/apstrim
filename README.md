# apstrim
Logger of Control System parameters and data objects. Analog of SDDS writer.

- Supported infrastructures: ADO, EPICS, LITE.
- Efficient binary serialization format.
- Like JSON. But it's faster and smaller.
- Numpy arrays supported.
- Optional online compression.
- Basic plotting of logged data.

## Installation
Dependencies: **msgpack, msgpack-numpy, caproto**. 
These packages will be installed using pip:

    pip3 install apstrim

The example program for deserialization and plotting **apstrim.plot**
requires additional package: **pyqtgraph**.

## Examples

Serialization


	:python -m apstrim -nEPICS testAPD:scope1:MeanValue_RBV
	pars: {'testAPD:scope1:MeanValue_RBV': ['0']}
	21-06-19 11:06:57 Logged 61 paragraphs, 1.36 KBytes
	...

	:python -m apstrim -nEPICS --compress testAPD:scope1:MeanValue_RBV
	pars: {'testAPD:scope1:MeanValue_RBV': ['0']}
	21-06-19 11:10:35 Logged 61 paragraphs, 1.06 KBytes
	...
	# Compression ratio = 1.28

    :python -m apstrim -nEPICS testAPD:scope1:MeanValue_RBV,Waveform_RBV
    21-06-18 22:51:15 Logged 122 paragraphs, 492.837 KBytes
    ...

    :python -m apstrim -nEPICS --compress testAPD:scope1:MeanValue_RBV,WaveForm_RBV
    21-06-19 11:04:58 Logged 122 paragraphs, 492.682 KBytes
	...
	# Note, Compression is very poor for vector parameters

	python -m apstrim -nLITE acnlin23:dev1:cycle
	pars: {'acnlin23:dev1:cycle': ['0']}
	21-06-19 11:16:42 Logged 5729 paragraphs, 103.14 KBytes
	...

	:python -m apstrim -nLITE --compress acnlin23:dev1:cycle
	21-06-19 11:18:02 Logged 5733 paragraphs, 53.75 KBytes
	...
	# Compression ratio = 1.9

    :python -m apstrim -nLITE liteHost:dev1:cycle,y
    pars: {'acnlin23:dev1:cycle': ['0'], 'acnlin23:dev1:y': ['1']}
	21-06-19 10:57:30 Logged 5743 paragraphs, 46247.198 KBytes
    ...


Example of deserialization and plotting of the logged data files.

    python -m apstrim.plot *.aps
