""" Module for scanning and extracting data from aplog-generated files.
"""
import sys, time, argparse, os
from timeit import default_timer as timer
#from pprint import pprint
import bisect
import numpy as np
from io import BytesIO
import msgpack
import msgpack_numpy
msgpack_numpy.patch()
__version__ = 'v2.0.0 2021-08-04'#
#TODO: the par2key is mapped to int now, therefore both par2key and key2par could be just lists, that could be faster.

#````````````````````````````Globals``````````````````````````````````````````
Nano = 0.000000001
TimeFormat_in = '%y%m%d_%H%M%S'
TimeFormat_out = '%y%m%d_%H%M%S'
MaxFileSize = 4*1024*1024*1024
#````````````````````````````Helper functions`````````````````````````````````
def _printv(msg):
    if APScan.Verbosity >= 1:
        print(f'DBG_APSV: {msg}')
def _printvv(msg):
    if APScan.Verbosity >= 2 :
        print(f'DBG_APSVV: {msg}')

def _croppedText(txt, limit=200):
    if len(txt) > limit:
        txt = txt[:limit]+'...'
    return txt

def _nanoSeconds2Datetime(ns:int):
    from datetime import datetime
    dt = datetime.fromtimestamp(ns*Nano)
    return dt.strftime('%y%m%d_%H%M%S') 

def _timeInterval(startTime, span):
    """returns sections (string) and times (float) of time interval
    boundaries"""
    ttuple = time.strptime(startTime,TimeFormat_in)
    firstDataSection = time.strftime(TimeFormat_out, ttuple)
    startTime = time.mktime(ttuple)
    endTime = startTime +span
    endTime = min(endTime, 4102462799.)# 2099-12-31
    ttuple = time.localtime(endTime)
    endSection = time.strftime(TimeFormat_out, ttuple)
    return firstDataSection, int(startTime/Nano), endSection, int(endTime/Nano)

def _unpacknp(data):
    if not isinstance(data,(tuple,list)):
        return data
    if len(data) != 2:# expect two arrays: times and values
        return data
    #print( _croppedText(f'unp: {data}'))
    unpacked = []
    for i,item in enumerate(data):
        try:
            dtype = item['dtype']
            shape = item['shape']
            buf = item['bytes']
            arr = np.frombuffer(buf, dtype=dtype).reshape(shape)
            if i == 0:
                arr = arr * Nano#
            unpacked.append(arr)
        except Exception as e:
            print(f'Exception in iter: {e}')
            if i == 0:
                print(f'ERR in unpacknp: {e}')
                return data
            else:
                print('not np-packed data')
                unpacked.append(data)
    #print( _croppedText(f'unpacked: {len(unpacked[0])} of {unpacked[0].dtype}, {len(unpacked[1])} of {unpacked[1].dtype}'))
    return unpacked
#,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,
#````````````````````````````class APView`````````````````````````````````````
class APScan():
    Verbosity = 0
    """Show dedugging messages."""

    def __init__(self, fileName):
        """Open logbook fileName, unpack headers, position file to data sections."""
        self.logbookName = fileName
        try:
            self.logbookSize = os.path.getsize(fileName)
        except Exception as e:
            print(f'ERROR opening file {fileName}: {e}')
            sys.exit()
        self.logbook = open(fileName,'rb')

        # unpack logbook contents and set file position after it
        self.unpacker = msgpack.Unpacker(self.logbook, use_list=False
        ,strict_map_key=False) #use_list speeds up 20%, # does not help:, read_size=100*1024*1024)
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

        # unpack two sections after the contents: Abstract and Index
        self.position = self.dirSize
        self.logbook.seek(self.position)
        self.unpacker = msgpack.Unpacker(self.logbook, use_list=False
        ,strict_map_key=False) #use_lis=False speeds up 20%
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
            if nSections == 2:# section: Index
                #_printvv(f'Index@{self.logbook.tell()}: {section}')
                self.par2key = section['index']
                self.key2par = {value:key for key,value in self.par2key.items()}
                _printvv(f'Index@{self.logbook.tell()}: {self.key2par}')                
                break

    def get_headers(self):
        """Returns dict of header sections: Directory, Abstract, Index"""
        return {'Directory':self.directory, 'Abstract':self.abstract
        , 'Index':self.key2par}

    def extract_objects(self, span=0., items=[], startTime=None):
        """
        Returns correlated dict of times and values of the logged items during
        the selected time interval.
        
        **span**:   Time interval for data extraction in seconds. If 0, then the
                data will be extracted starting from the startTime and ending 
                at the end of the logbook.
        
        **items**:  List of items to extract. Item are coded with keys. 
                The mapping of the Process Variables (PV) could be found in
                the self.par2key map. The reversed mapping is in the 
                self.key2par map.
        
        **startTime**: String for selecting start of the extraction interval. 
                Format: YYMMDD_HHMMSS. Set it to None for the logbook beginning. 
                """
        extracted = {}
        parameterStatistics = {}
        endPosition = self.logbookSize

        if len(items) == 0: # enable handling of all items 
            items = self.key2par.keys()
        for key,par in self.key2par.items():
            if key not in parameterStatistics:
                #print(f'add to stat[{len(parameterStatistics)+1}]: {key}') 
                parameterStatistics[key] = 0
            if par not in extracted and key in items:
                _printvv(f'add extracted[{len(extracted)+1}]: {par}') 
                extracted[key] = {'par':par, 'times':[], 'values':[]}
    
        if len(self.directory) == 0:
               _printe('Directory is missing')
               sys.exit()

        keys = list(self.directory.keys())
        if startTime is  None:
            firstTStamp = keys[0]
            startTime = _nanoSeconds2Datetime(firstTStamp)
        firstDataSection, startTStamp, endSection, endTStamp\
        = _timeInterval(startTime, span)
        _printv(f'start,end:{firstDataSection, startTStamp, endSection, endTStamp}')

        # position logbook to first data section
        #if len(self.directory) != 0 and startTime:
        lk = len(keys)
        nearest_idx = bisect.bisect_left(keys, startTStamp)
        if keys[nearest_idx] != startTStamp:
            startTStamp = keys[max(nearest_idx-1,0)]
        nearest_idx = min(bisect.bisect_left(keys, endTStamp),lk-1)
        lastDataSection = endTStamp if keys[nearest_idx] == endTStamp\
            else keys[min(nearest_idx+1,lk-1)]
        self.position = self.directory[startTStamp]
        endPosition = self.directory[lastDataSection]
        _printvv(f'first dsection {firstDataSection, self.position}')
        _printvv(f'last dsection {lastDataSection, endPosition}')
        self.logbook.seek(self.position)

        _printvv(f'logbook@{self.logbook.tell()}, offset={self.dirSize}')

        # read required sections into a buffer
        toRead =  endPosition - self.logbook.tell()
        if toRead < MaxFileSize:
            ts = timer()
            rbuf = self.logbook.read(toRead)
            ts1 = timer()
            dt1 = round(ts1 - ts,6)
            bytesIO = BytesIO(rbuf)
            dt2 = round(timer() - ts1,6)
            _printv(f'Read {round(toRead/1e6,3)}MB in {dt1}s, adopted in {dt2}s')
        else:
            print(f'File size > {self.logbookSize}, processing it sequentially')

        # re-create the Unpacker
        self.unpacker = msgpack.Unpacker(bytesIO, use_list=False
        ,strict_map_key=False) #use_list=False speeds up 20%

        # loop over sections in the logbook
        nSections = 0
        if APScan.Verbosity >= 1:
            sectionTime = [0.]*3
        endTStampNS = endTStamp*Nano
        tstart = time.time()
        perfMonTime = 0.
        for section in self.unpacker:
            nSections += 1
            # data sections
            _printv(f'Data Section: {nSections}')
            extractionTime = time.time() - tstart
            if nSections%60 == 0:
                _printv((f'Data sections: {nSections}'
                f', elapsed time: {round(extractionTime,4)}'))
            try:# handle compressed data
                if self.compression != 'None':
                    ts = timer()
                    decompressed = self.decompress(section)
                    if APScan.Verbosity >= 1:
                        sectionTime[0] += timer() - ts
                    ts = timer()
                    section = msgpack.unpackb(decompressed
                    ,strict_map_key=False)#ISSUE: strict_map_key does not work here
                    if APScan.Verbosity >= 1:
                        sectionTime[1] += timer() - ts
            except Exception as e:
                print(f'WARNING: wrong section {nSections}: {str(section)[:75]}...', {e})
                break

            #sectionStartTStamp = section['t']
            #startTStamp = sectionStartTStamp
            #sectionEndTStamp = startTStamp + span/Nano

            # iterate over parameters
            ts = timer()
            perfMonTimeSum = 0.
            if True:#try:
                # the following loop takes 90% time
                for parIndex, tsValsNP in section['pars'].items():
                    if not parIndex in items:
                        continue
                    tstamps, values = _unpacknp(tsValsNP)
                    if tstamps[-1] > endTStampNS:
                        last = bisect.bisect_left(tstamps, endTStampNS)
                        tstamps = tstamps[:last]
                        values = values[:last]
                    if APScan.Verbosity >= 2:
                        print( _croppedText(f'times{parIndex}[{len(tstamps)}]: {tstamps}'))
                        try:    vshape = f'of numpy arrays {values.shape}'
                        except: vshape = ''
                        print(f'vals{parIndex}[{len(values)}] {vshape}:')
                        print( _croppedText(f'{values}'))

					#`````````Concatenation of parameter lists.``````````````
                    # Using numpy.concatenate turned to be very slow.
                    # The best performance is using list.extend() 

                    extracted[parIndex]['times'].extend(list(tstamps))

                    ts2 = timer()
                    # Slowest code: 90% of time spent here
                    '''
                    if extracted[parIndex]['values'] is None:
                        extracted[parIndex]['values'] = values
                    else:
                        extracted[parIndex]['values'] =\
                        np.concatenate((extracted[parIndex]['values']
                        ,values), axis=0)'''

                    # that piece is 6 times faster:
                    extracted[parIndex]['values'].extend(list(values))
                    perfMonTimeSum += timer() - ts2
                    #,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,

                    n = len(extracted[parIndex]['times'])
                    _printvv(f"par{parIndex}[{n}]")
                    parameterStatistics[parIndex] = n

            else:#except Exception as e:
                print(f'WARNING: in concatenation: {e}')

            dts = timer() - ts
            if APScan.Verbosity >= 1:
                sectionTime[2] += dts
            perfMonTime += perfMonTimeSum

        extractionTime = time.time() - tstart
        if APScan.Verbosity >= 1:
            print(f'SectionTime: {[round(i/nSections,6) for i in sectionTime]}')
        print(f'Deserialized from {self.logbookName}: {nSections} sections')
        print(f'Sets/Parameter: {parameterStatistics}')
        mbps = f', {round(toRead/1e6/extractionTime,1)} MB/s'
        print((f'Elapsed time: {round(extractionTime,4)}, {mbps}'))
        print(f'Spent {round(perfMonTime/extractionTime*100,1)}% in the monitored code.')
        return extracted
