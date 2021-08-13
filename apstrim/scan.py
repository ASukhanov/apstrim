""" Module for scanning and extracting data from aplog-generated files.
"""
import sys, time, argparse, os
from timeit import default_timer as timer
#from pprint import pprint
import bisect
import numpy as np
from io import BytesIO
import msgpack
__version__ = 'v2.0.4 2021-08-12'#

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

def _croppedText(txt, limit=200):
    if len(txt) > limit:
        txt = txt[:limit]+'...'
    return txt

def _seconds2Datetime(seconds:int):
    from datetime import datetime
    dt = datetime.fromtimestamp(seconds)
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
    return firstDataSection, int(startTime), endSection, int(endTime)

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
                # timestamps converted from int(nanoseconds) to floats (with loss of precision) 
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
            _printvv(_croppedText(f'Table of contents: {contents}'))
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
                par2key = section['index']
                #self.key2par = {value:key for key,value in self.par2key.items()}
                self.key2par = par2key
                _printvv(f'Index@{self.logbook.tell()}: {self.key2par}')                
                break

    def get_headers(self):
        """Returns dict of header sections: Directory, Abstract, Index"""
        return {'Directory':self.directory, 'Abstract':self.abstract
        , 'Index':self.key2par}

    def extract_objects(self, span=0., items=[], startTime=None
        , bufSize=128*1024*1024):
        """
        Returns correlated dict of times and values of the logged items during
        the selected time interval.
        
        **span**:   Time interval for data extraction in seconds. If 0, then
                the data will be extracted starting from the startTime and
                ending at the end of the logbook.
        
        **items**:  List of items to extract
        
        **startTime**: String for selecting start of the extraction interval. 
                Format: YYMMDD_HHMMSS. Set it to None for the logbook
                beginning. 

        **bufSize**:  Size of the bytesIO buffer. If file size is smaller than
                the bufSize, then the whole file will be read into the buffer.
                Otherwise each section will be read from the file sequentially.
                Note, the Python3 read() for binary files is using very
                effective buffering scheme, therefore using very large bufSize
                have almost no effect on performance."""
        extracted = {}
        parameterStatistics = {}
        endPosition = self.logbookSize
        readerBufferSize = bufSize

        # create empty map for return
        if len(items) == 0: # enable handling of all items 
            #items = self.key2par.keys()
            items = [i for i in range(len(self.key2par))]
        #for key,par in self.key2par.items():
        for key,par in enumerate(self.key2par):
            if key not in parameterStatistics:
                #print(f'add to stat[{len(parameterStatistics)+1}]: {key}') 
                parameterStatistics[key] = 0
            if par not in extracted and key in items:
                _printvv(f'add extracted[{len(extracted)+1}]: {par}') 
                extracted[key] = {'par':par, 'times':[], 'values':[]}
    
        if len(self.directory) == 0:
               print('ERROR. Directory is missing')
               sys.exit()

        # determine a part of the logbook for extraction
        keys = list(self.directory.keys())
        if startTime is  None:
            firstTStamp = keys[0]
            startTime = _seconds2Datetime(firstTStamp)
        #print(f's,s:{startTime, span}')
        firstDataSection, startTStampS, endSection, endTStampS\
        = _timeInterval(startTime, span)
        _printv(f'start,end:{firstDataSection, startTStampS, endSection, endTStampS}')

        # position logbook to first data section
        lk = len(keys)
        bt = timer()
        # find nearest_key ising bisect, that is fast, ~10us
        startSection_idx = bisect.bisect_left(keys, startTStampS)
        #print(f'bisect:{startTStampS,startSection_idx,keys}')
        startSectionTStamp = keys[startSection_idx]
        if startSectionTStamp > startTStampS:
            startSection_idx -= 1
            startSectionTStamp = keys[max(startSection_idx,0)]
        endTStampS = startTStampS + span
        nearest_idx = min(bisect.bisect_left(keys, endTStampS),lk-1)
        lastSectionTStamp = keys[nearest_idx]
        if lastSectionTStamp < endTStampS:
            lastSectionTStamp = keys[min(nearest_idx+1,lk-1)]
        self.position = self.directory[startSectionTStamp]
        endPosition = self.directory[lastSectionTStamp]
        _printvv(f'first dsection {self.position}')
        _printvv(f'last dsection {endPosition}')
        self.logbook.seek(self.position)
        _printvv(f'logbook@{self.logbook.tell()}, offset={self.dirSize}')

        # Try to read required sections into a buffer. If successful, then
        # the streamReader for unpacker will be this buffer, otherwise
        # it will be the logbook file.
        toRead =  endPosition - self.logbook.tell()
        if toRead <= 0:
            print('No data to read')
            sys.exit()
        if toRead < readerBufferSize:
            ts = timer()
            rbuf = self.logbook.read(toRead)
            ts1 = timer()
            dt1 = round(ts1 - ts,6)
            streamReader = BytesIO(rbuf)
            dt2 = round(timer() - ts1,6)
            print(f'Read {round(toRead/1e6,3)}MB in {dt1}s, adopted in {dt2}s')
            _printv(f'Read {round(toRead/1e6,3)}MB in {dt1}s, adopted in {dt2}s')
        else:
            print((f'Read size {round(toRead/1e6,1)}MB >'
            f' {round(readerBufferSize/1e6,1)}MB'
            ', processing it sequentially'))
            streamReader = self.logbook

        # re-create the Unpacker to re-position it in the logbook
        self.unpacker = msgpack.Unpacker(streamReader, use_list=False
        ,strict_map_key=False) #use_list=False speeds up 20%

        # loop over sections in the logbook
        nSections = 0
        if APScan.Verbosity >= 1:
            sectionTime = [0.]*3
        startTStampNS = startTStampS/Nano
        endTStampNS = endTStampS/Nano
        #print(f'sts,ets:{int(startTStampNS),int(endTStampNS)}')
        extractionTime = 0.
        perfMonTime = 0.
        timerTotal = timer()
        for section in self.unpacker:
            extractionTStart = timer()
            nSections += 1
            # data sections
            _printv(f'Data Section: {nSections+startSection_idx}')
            if nSections%60 == 0:
                dt = time.time() - extractionTime
                _printv((f'Data sections: {nSections}'
                f', elapsed time: {round(dt,4)}'))#, paragraphs/s: {nParagraphs//dt}'))
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
            _printv(f"Data section {nSections}: {section['tstart']}")

            # iterate over parameters
            ts = timer()
            try:
                # the following loop takes 90% time
                for parIndex, tsValsNP in section['pars'].items():
                    if not parIndex in items:
                        continue
                    tstamps, values = _unpacknp(tsValsNP)

                    # trim array {} if needed
                    #print(f'sts {tstamps[0],startTStampS}')
                    if tstamps[0] < startTStampS:
                        first = bisect.bisect_left(tstamps, startTStampS)
                        tstamps = tstamps[first:]
                        values = values[first:]
                    try:
                        if tstamps[-1] > endTStampS:
                            last = bisect.bisect_left(tstamps, endTStampS)
                            tstamps = tstamps[:last]
                            values = values[:last]
                    except: pass
                    if APScan.Verbosity >= 2:
                        print( _croppedText(f'times{parIndex}[{len(tstamps)}]: {tstamps}'))
                        try:    vshape = f'of numpy arrays {values.dtype,values.shape}'
                        except: vshape = ''
                        print(f'vals{parIndex}[{len(values)}] {vshape}:')
                        print( _croppedText(f'{values}'))

                    #`````````Concatenation of parameter lists.``````````````
                    # Using numpy.concatenate turned to be very slow.
                    # The best performance is using list.extend() 
                    extracted[parIndex]['times'].extend(list(tstamps))
                    ts2 = timer()
                    extracted[parIndex]['values'].extend(list(values))
                    perfMonTime += timer() - ts2
                    #,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,

                    n = len(extracted[parIndex]['times'])
                    _printvv(f"par{parIndex}[{n}]")
                    parameterStatistics[parIndex] = n

            except Exception as e:
                print(f'WARNING: in concatenation: {e}')

            dts = timer() - ts
            if APScan.Verbosity >= 1:
                sectionTime[2] += dts
            extractionTime += timer() - extractionTStart

        if APScan.Verbosity >= 1:
            print(f'SectionTime: {[round(i/nSections,6) for i in sectionTime]}')
        print(f'Deserialized from {self.logbookName}: {nSections} sections')
        print(f'Sets/Parameter: {parameterStatistics}')
        ttime = timer()-timerTotal
        mbps = (f' {round(toRead/1e6/extractionTime,1)} MB/s'
        f', including disk: {round(ttime,3)} s, {round(toRead/1e6/ttime,1)} MB/s')
        print(f'Processing time: {round(extractionTime,3)} s, {mbps}')
        print(f'Spent {round(perfMonTime/extractionTime*100,1)}% in the monitored code.')
        return extracted
