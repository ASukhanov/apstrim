# Change Log for module apstrim

## [2.0.5] - 2021-08-25

### Fixed

Consistency check for MessagePack version.

apstrim.py: False exit if span < section interval

scan.py
Short files showed no data.

## [2.0.2] - 2021-08-09

### Changed

apstrim. Directory section is updated each time when new section is created.
This allows for simultaneous reading and writing access to lobooks.

scan.extract_objects():
Added bufSize argument. Corrected the handling of startTime and span arguments
Calculation of the extraction speed is corrected. The extraction speed reaches
950 MB/s.

setup.py:
Dependency of msgpack_numpy have been removed.

## [2.0.0] - 2021-08-03

### Changed 

Major upgrade. The extraction performance drastically improved (~100 times). 
Vertical stacking of parameters. The sections are now maps of parameters.
Parameters are converted to lists of numpy arrays, stored as bytes. 
The packing of bytes is 100 times faster than the packing of lists of lists.
Concatenation of parameters accross of sections is done using list.extend(),
this is 6 times faster than using numpy concatenation.
The iteration speed during extraction reaches 1000 MB/s (tested with 
1.3 GB file test_1200_MBPS.aps).

## [1.4.0] - 2021-07-26

### Changed 
Par2key maps to integer instead of string. Msgpack allows it.
Section 'abbreviation' renamed by 'index'.

## [1.3.1] - 2021-07-26
Docstrings have been updated.

### Added

API reference in **html**.

## [1.3.0] - 2021-07-22

### Added

The apstrim.plot.py have been replaced by two files: apstrim.scan.py and 
apstrim.view.py. 

## [1.2.0] - 2021-07-20

### Added
-verbose

### Fixed
Handling of DirSize=0.
Handling of wrong device name.

## [1.1.3] - 2021-07-20
 
### Added

Table of contents to provide for random-access retrieval.
Downsampling of the table of contents in case of too many sections.
Section count, Verbosity, 
 


logParagraphs removed, the timestampedMap is converted to list when 
section is ready.
Sections renamed: -> contents, parameters -> Abbreviations

### Fixed

Joining of paragraphs.
File positioning prior to construction of the Unpacker.

## [1.1.1] - 2021-06-23
  
Compression ratio printed at the end
  
## [1.1.0] - 2021-06-23

### Fixed
fixed bug when subscriptions was multiplied every start().

## [1.0.11] - 2021-06-22

intercept exception in _delivered()

## [1.0.10] - 2021-06-22

separate events for exit and stop

## [1.0.9] - 2021-06-21

new keyword: self.use_single_float

## [1.0.7] - 2021-06-20

Docstrings updated

## [1.0.6] - 2021-06-19

Filename moved from instantiation to new method: start(), timestamp is int(nanoseconds)

## [1.0.5] - 2021-06-14

Handling of different returned maps

## [1.0.4] - 2021-06-11

If file exists then rename the existing file, flush the file after each section.

## [1.0.3] - 2021-06-01

EPICS and LITE support is OK, Compression supported
