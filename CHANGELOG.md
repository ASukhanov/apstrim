# Change Log for module apstrim
 
## [2.0.0] - 2021-08-03

### Changed 

Vertical stacking of parameters. The section is now a map of parameters.
Parameters are converted to lists of numpy arrays and stored as bytes. 
Packing bytes is 100 times faster than the packing of lists of lists.
Concatenation of parameters accross of section is done using list.extend,
this is 6 times faster than using numpy concatenation.
The iteration speed during extraction reaches 1200 MB/s (tested with 
13 GB file test_1200_MBPS.aps).

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
