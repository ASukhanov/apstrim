# apstrim
Logger and extractor of Control System parameters (a.c.a EPICS PVs).

- Supported infrastructures: ADO, EPICS, LITE.
- Very fast random access retrieval of objects for selected time interval. Retrieval performance of 300 million of floats per second has been demonstrated.
- Nonhomogeneous and homogeneous data are processed equally fast.
- Scalar and vector data could be mixed.
- Data with different updating frequency can be mixed.
- Self-describing data format, no schema required.
- Efficient binary serialization format.
- Like JSON. But it's faster and smaller. 
- Numpy arrays supported.
- Fast online compression.
- Basic plotting of the logged data.
- Data extraction from a file is allowed when the file is being written.

## Installation
Dependencies: **msgpack, caproto, lz4framed**. 
These packages will be installed using pip:

    pip3 install apstrim

The example program for deserialization and plotting **apstrim.view**,
requires additional package: **pyqtgraph**.

## API refrerence

[apstrim](https://htmlpreview.github.io/?https://github.com/ASukhanov/apstrim/blob/main/docs/apstrim.html)

[scan](https://htmlpreview.github.io/?https://github.com/ASukhanov/apstrim/blob/main/docs/scan.html)

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

    :python -m apstrim -nEPICS --compress testAPD:scope1:MeanValue_RBV,Waveform_RBV
    21-06-19 11:04:58 Logged 122 paragraphs, 492.682 KBytes
	...
	# Note, Compression is poor for floating point arrays with high entropy.

	python -m apstrim -nLITE liteHost:dev1:cycle
	pars: {'acnlin23:dev1:cycle': ['0']}
	21-06-19 11:16:42 Logged 5729 paragraphs, 103.14 KBytes
	...

	:python -m apstrim -nLITE --compress liteHost:dev1:cycle
	21-06-19 11:18:02 Logged 5733 paragraphs, 53.75 KBytes
	...
	# Compression ratio = 1.9

Example of deserialization and plotting of all parameters from several logbooks.

    python -m apstrim.view -i all -v -p *.aps
