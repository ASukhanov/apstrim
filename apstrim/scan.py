""" Module for scanning and extracting data from aplog-generated files.
"""
import sys, time, argparse, os
from timeit import default_timer as timer
#from pprint import pprint
import bisect
import numpy as np
import msgpack
import msgpack_numpy
msgpack_numpy.patch()
__version__ = 'v1.3.0 2021-07-22'

#````````````````````````````Globals``````````````````````````````````````````
Nano = 0.000000001
TimeFormat_in = '%y%m%d_%H%M%S'
TimeFormat_out = '%y%m%d_%H%M%S'
#````````````````````````````Helper functions`````````````````````````````````
def _printv(msg):
    if APScan.Verbosity >= 1:
        print(f'DBG_APSV: {msg}')
def _printvv(msg):
    if APScan.Verbosity >= 2 :
        print(f'DBG_APSVV: {msg}')

def _timeInterval(startTime, span):
    """returns sections (string) and times (float) of time interval
    boundaries"""
    ttuple = time.strptime(startTime,TimeFormat_in)
    startSection = time.strftime(TimeFormat_out, ttuple)
    startTime = time.mktime(ttuple)
    endTime = startTime +span
    endTime = min(endTime, 4102462799.)# 2099-12-31
    ttuple = time.localtime(endTime)
    endSection = time.strftime(TimeFormat_out, ttuple)
    _printv(f'start,end:{startSection, endSection}')
    return startSection, startTime, endSection, endTime
#,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,
#````````````````````````````class APView`````````````````````````````````````
class APScan():
    Verbosity = 0# Verbosity level

    def __init__(self, fileName):
        """Open logbook fileName, unpack headers, position file to data sections."""

        try:
            self.logbookSize = os.path.getsize(fileName)
        except Exception as e:
            print(f'ERROR opening file {fileName}: {e}')
            sys.exit()
        self.logbook = open(fileName,'rb')

        # unpack logbook contents and set file position after it
        self.unpacker = msgpack.Unpacker(self.logbook, use_list=False) #use_list speeds up 20%, # does not help:, read_size=100*1024*1024)
        self.dirSize = 0
        self.directory = []
        for contents in self.unpacker:
            #printvv(f'Table of contents: {contents}')
            try:
                self.dirSize = contents['contents']['size']
            except:
                print('Warning: Table of contents is missing or wrong')
                break
            self.directory = contents['data']
            break

        # unpack two sections after the contents: Abstract and Abbreviations
        self.position = self.dirSize
        self.logbook.seek(self.position)
        self.unpacker = msgpack.Unpacker(self.logbook, use_list=False) #use_list speeds up 20%, # does not help:, read_size=100*1024*1024)
        nSections = 0
        for section in self.unpacker:
            #print(f'section:{nSections}')
            nSections += 1
            if nSections == 1:# section: Abstract
                _printvv(f'Abstract@{self.logbook.tell()}: {section}')
                self.abstract = section['abstract']
                self.compression = self.abstract.get('compression')
                if self.compression is None:
                    continue
                if self.compression != 'None':
                    module = __import__(self.compression)
                    self.decompress = module.decompress
                continue
            if nSections == 2:# section: Abbreviations
                self.par2key = section['abbreviations']
                self.key2par = {value[0]:key for key,value in self.par2key.items()}
                _printvv(f'Abbreviations@{self.logbook.tell()}: {self.key2par}')                
                break

    def get_headers(self):
        """Returns dict of header sections: Directory, Abstract, Abbreviations"""
        return {'Directory':self.directory, 'Abstract':self.abstract
        , 'Abbreviations':self.key2par}

    def extract_objects(self, span=0., items=[], startTime=None):
        """Returns correlated dict of times and values of logged items during
        selected time interval.
        span:   Duration of time interval in seconds, set it 0 for whole logbook.
        items:  List of items to extract. Item are coded with keys. 
                The mapping of Process Variables (PV) is in self.par2key map.
                The reversed mapping is in self.key2par map.
        startTime: String for selecting start of the time interval. 
                Format: YYMMDD_HHMMSS. Set it to None for the logbook beginning. 
                """
        extracted = {}
        parameterStatistics = {}

        if len(items) == 0: # enable handling of all items 
            items = self.key2par.keys()
        for key,par in self.key2par.items():
            if par not in parameterStatistics:
                #print(f'add to stat[{len(parameterStatistics)+1}]: {par}') 
                parameterStatistics[key] = 0
            if par not in extracted and key in items:
                    _printvv(f'add to graph[{len(extracted)+1}]: {par}') 
                    extracted[key] = {'par':par, 'time':[], 'value':[]}
        
        if startTime is not None:
            startSection, startTStamp, endSection, endTime\
            = _timeInterval(startTime, span)

        # re-create the unpacker for reading logbook starting from required section
        if len(self.directory) != 0 and startTime:
            keys = list(self.directory.keys())
            nearest_idx = bisect.bisect_left(keys, startSection)
            if keys[nearest_idx] != startSection:
                startSection = keys[nearest_idx-1]
            _printvv(f'start section {startSection, startTStamp, endTime}')
            self.position = self.directory[startSection]
            self.logbook.seek(self.position)
            _printvv(f'logbook positioned to section {startSection}, offset={self.dirSize}')
            self.unpacker = msgpack.Unpacker(self.logbook, use_list=False) #use_list speeds up 20%, # does not help:, read_size=100*1024*1024)

        # loop over sections in the logbook
        tstart = time.time()
        nSections = 0
        nParagraphs = 0
        reached_endTime = False
        for section in self.unpacker:
            if reached_endTime:
                break
            nSections += 1
            # data sections
            #print(f'Data Section: {nSections}')
            dt = time.time() - tstart
            if nSections%60 == 0:
                _printv((f'Data sections: {nSections}, paragraphs: {nParagraphs}'
                f', elapsed time: {round(dt,1)}, paragraphs/s: {nParagraphs//dt}'))
            try:
                if self.compression != 'None':
                    decompressed = self.decompress(section)
                    section = msgpack.unpackb(decompressed)
                sectionDatetime, paragraphs = section
            except Exception as e:
                print(f'WARNING: wrong section {nSections}: {str(section)[:75]}...', {e})
                break
            if startTime is None:
                startSection, startTStamp, endSection, endTime\
                = _timeInterval(sectionDatetime, span)
                startTime = startTStamp
                
            if sectionDatetime > endSection:
                _printvv(f'reached last section {sectionDatetime}')
            nParagraphs += len(paragraphs)

            # iterate paragraphs 
            try:
                for timestamp,parkeys in paragraphs:
                    timestamp *= Nano
                    #print(f'paragraph: {timestamp}')#, parkeys}')
                    if timestamp < startTStamp:
                        continue
                    if timestamp > endTime:
                        _printvv(f'reached endTime {endTime}')
                        reached_endTime =True
                        break
                    for key in parkeys:
                        if key not in items:
                            continue
                        parameterStatistics[key] += 1
                        values = parkeys[key]
                        try:    nVals = len(values)
                        except: values = [values] # make it subscriptable
                        par = self.key2par[key]
                        # if values is a vector then append all its points spaced by 1 us
                        for i,v in enumerate(values):
                            extracted[key]['time'].append(timestamp + i*1.e-6)
                            extracted[key]['value'].append(v)
                            #print(f'key {key}, ts: {timestamp}')
            except Exception as e:
                print(f'WARNING: wrong paragraph {nParagraphs}: {e}')

        print(f'Deserialized from {self.logbook.name}: {nSections} sections, {nParagraphs} paragraphs')
        print(f'Point/Parameter: {parameterStatistics}')
        dt = time.time() - tstart
        mbps = f', {round((self.logbook.tell() - self.position)/1e6/dt,1)} MB/s'
        print((f'Elapsed time: {round(dt,1)} s, {int(nParagraphs/dt)}'
        f' paragraphs/s')+mbps)
        return extracted
