# Change Log
All notable changes to this project will be documented in this file.
 
The format is based on [Keep a Changelog](http://keepachangelog.com/)
and this project adheres to [Semantic Versioning](http://semver.org/).
 
## [1.1.2] - 2021-07-20
 
### Added

Table of contents to provide for random-access retrieval.
Downsampling of the table of contents in case of too many sections.
Section count, Verbosity, 
 
### Changed 

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
