# apstrim
Logger and extractor of Control System parameters (a.k.a EPICS PVs).

- Supported Control Infrastructures: EPICS, ADO, LITE.
- Typical speed of compressed serialization to a logbook file is 70 MB/s.
- Fast random-access retrieval of objects for selected time interval.
- De-serialization speed is up to 1200 MB/s when the logbook is chached in memory.
- Simultaneous serialization and de-serialization from the same logbook file.
- Fast online compression.
- Inhomogeneous and homogeneous data objects.
- Data with different updating frequency could be mixed in the data set.
- Self-describing data format no schema required.
- Efficient binary serialization format of data objects (msgpack).
- Numpy arrays are supported.
- Basic plotting of the logged data.
- Data extraction from a logbook is allowed when the logbook is being written.

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

## Serialization

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

### De-serialization
Example of deserialization and plotting of all parameters from several logbooks.

    python -m apstrim.view -i all -v -p *.aps

Python code snippet to extract items 1,2 and 3 from a logbook
for 20 seconds interval starting on 2021-08-12 at 23:31:31.

```python
from apstrim.scan import APScan
apscan = APScan('aLogbook.aps')
headers = apscan.get_headers()
print(f'{headers["Index"]}')
extracted = apscan.extract_objects(span=20, items=[1,2,3], startTime='210812_233131')
print(f'{extracted[3]}')# print the extracted data for item[3]
# returned:
{'par': 'liteBridge.peakSimulator:rps',           # object (PV) name of the item[3]
'times': [1628825500.8938403, 1628825510.898658], # list of the item[3] timestamps
'values': [95.675125, 95.55396]}                  # list of the item[3] values
```

