# Copyright (c) 2021 Andrei Sukhanov. All rights reserved.
#
# Licensed under the MIT License, (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/ASukhanov/apstrim/blob/main/LICENSE
#
__version__ = '1.2.0 2021-07-19'# random-access-ready, bug __printe fixed

#TODO: consider to replace msgpack_numpy with something simple and predictable.
#The use_single_float has no efect in msgPack,
#TODO: check how ints are handled: ideally they should be dynamically
#converted to int8,int16,int32 or int64 depending of its value.

import sys, time, string, copy
import os, pathlib, datetime
import threading
import signal
#from timeit import default_timer as timer

import numpy as np
import msgpack
import msgpack_numpy
msgpack_numpy.patch()

#````````````````````````````Globals``````````````````````````````````````````
Nano = 0.000000001
#````````````````````````````Helper functions`````````````````````````````````
def _printTime(): return time.strftime("%m%d:%H%M%S")
def _printi(msg): print(f'INFO_AS@{_printTime()}: {msg}')
def _printw(msg): print(f'WARN_AS@{_printTime()}: {msg}')
def _printe(msg): print(f'ERROR_AS@{_printTime()}: {msg}')
def _printd(msg):
    if apstrim.Verbosity>0:
        print(f'DBG_AS: {msg}')

def croppedText(txt, limit=200):
    if len(txt) > limit:
        txt = txt[:limit]+'...'
    return txt

def shortkey(i:int):
    """Return string with max 2 characters, mapping i (i<1296)"""
    s = string.digits + string.ascii_lowercase
    l = len(s)
    quotient,reminder = divmod(i,l)
    return s[i] if quotient==0 else s[quotient]+s[reminder]

#````````````````````````````Serializer class`````````````````````````````````
class apstrim():
    """Create the object streamer. 
    publisher:  is a class, providing a subscribe() method,
    devPar:     list of device:parameter strings,
    sectionInterval: time between writing of the logBook sections
    compression:    compression enable flag,
    quiet:      do not print section writing progress,
    use_single_float: Use single precision float type for float. (default: True)
    dirSize:    size of the table of contents, which is usd for random-access
                retrieval. If 0 then no table will be created.
        Class properties:
    eventExit:  is a threading.Event, which will be set when application
     is about to exit.
    Verbosity:  Show more log messages
    """
    eventExit = threading.Event()
    _eventStop = threading.Event()
    Verbosity = 0

    def __init__(self, publisher, devPars:list, sectionInterval=60.
    , compress=False, quiet=False, use_single_float=True, dirSize=0):
        #_printi(f'apstrim  {__version__}, sectionInterval {sectionInterval}')
        signal.signal(signal.SIGINT, _safeExit)
        signal.signal(signal.SIGTERM, _safeExit)

        self.lock = threading.Lock()
        self.publisher = publisher
        self.devPars = devPars
        self.sectionInterval = sectionInterval
        self.quiet = quiet
        self.use_single_float = use_single_float

        # table of contents - related variables
        self.dirSize = dirSize
        self.contents_downsampling_factor = 1# No downsampling 

        # create a section Abstract
        self.abstractSection = {'abstract':{'apstrim ':__version__
        , 'sectionInterval':sectionInterval}}
        abstract = self.abstractSection['abstract']

        if compress:
            import lz4framed
            self.compress = lz4framed.compress
            abstract['compression'] = 'lz4framed'
        else:
            self.compress = None
            abstract['compression'] = 'None'
        _printi(f'Abstract section: {self.abstractSection}')

        # a section has to be created before subscription
        self._create_logSection()

        # subscribe to parameters
        self.pars = {}
        #for i,pname in enumerate(self.devPars):
        i = 0
        for pname in self.devPars:
            devPar = tuple(pname.rsplit(':',1))
            try:
                self.publisher.subscribe(self._delivered, devPar)
            except:# Exception as e:
                _printe(f'Could not subscribe  for {pname}')#: {e}')
                continue
            self.pars[pname] = [shortkey(i)]
            i += 1
        if len(self.pars) == 0:
            _printe(f'Could not build the list of parameters')
            sys,exit()
        _printi(f'parameters: {self.pars}')

        self.abbreviationSection = msgpack.packb({'abbreviations':self.pars}
        , use_single_float=self.use_single_float)

    def start(self, fileName='apstrim.aps'):
        """Start streaming of the data objects to logbook file.
        If file is already exists then it will be renamed and
        a new file will be open with the provided name.
        """
        self._eventStop.clear()
        try:
            modificationTime = pathlib.Path(fileName).stat().st_mtime
            dt = datetime.datetime.fromtimestamp(modificationTime)
            suffix = dt.strftime('_%Y%m%d_%H%M') 
            try:    fname,ext = fileName.rsplit('.',1)
            except:    fname,ext = fileName,''
            otherName = fname + suffix + '.' + ext
            os.rename(fileName, otherName)
            _printw(f'Existing file {fileName} have been renamed to {otherName}')
        except Exception as e:
            pass

        self.logbook = open(fileName, 'wb')

        # write a preliminary 'Table of contents' section
        if self.dirSize:
            self.contentsSection = {'contents':{'size':self.dirSize}, 'data':{}}
            self.dataContents = self.contentsSection['data']
            self.logbook.write(msgpack.packb(self.contentsSection))
            # skip the 'Table of contents' zone of the logbook
            self.logbook.seek(self.dirSize)

        # write the sections Abstract and Abbreviations
        _printd(f'write Abstract@{self.logbook.tell()}')
        self.logbook.write(msgpack.packb(self.abstractSection
        , use_single_float=self.use_single_float))
        _printd(f'write Abbreviations@{self.logbook.tell()}')
        self.logbook.write(self.abbreviationSection)

        self._create_logSection()

        #_printi('starting serialization  thread')
        myThread = threading.Thread(target=self._serialize_sections)
        myThread.start()

        _printi(f'Logbook file: {fileName} created')

    def stop(self):
        """Stop the streaming."""
        self._eventStop.set()
        #self.logbook.close()

    def _delivered(self, *args):
        """Callback, specified in the subscribe() request. 
        Called when the requested data have been changed.
        args is a map of delivered objects."""
        #print(f'delivered: {args}')
        #self.timestampedMap = {}
        for devPar,props in args[0].items():
            #print(f'devPar: {devPar,props}, {type(devPar)}')
            try:
              if isinstance(devPar, tuple):
                # EPICS and ADO packing
                dev,par = devPar
                value = props['value']
                timestamp = props.get('timestamp')# valid in EPICS and LITE
                if timestamp == None:# decode ADO timestamp 
                    timestamp = int(props['timestampSeconds']/Nano
                    + props['timestampNanoSeconds'])
                else:
                    timestamp = int(timestamp/Nano)
                skey = self.pars[dev+':'+par][0]
              elif devPar == 'ppmuser':# ADO has extra item, skip it.
                continue
              else:
                #LITE packing:
                pars = props
                for par in pars:
                    try:
                        value = pars[par]['v']
                        timestamp = int(pars[par]['t'])
                    except: # try old LITE packing
                        value = pars[par]['value']                     
                        timestamp = int(pars[par]['timestamp']/Nano)
                    skey = self.pars[devPar+':'+par][0]
            except Exception as e:
                _printw(f'exception in unpacking: {e}')
                continue

            if self.use_single_float:
                # Changing numpy float64 to float32 halves the data volume
                #ts = timer()
                try:    
                    if value.dtype=='float64':
                        value = value.astype('float32')
                    #print(f'Numpy f64->f32 downsampling time: {round(timer()-ts,6)}')
                except:    pass
            #print(f'ts:{timestamp}, keys:{self.timestampedMap.keys()}')
            #print(f'ts:{timestamp}, tsMap:{self.timestampedMap}')
            if timestamp in self.timestampedMap:
                #print(f'add to self.timestampedMap: {timestamp,skey}')
                self.timestampedMap[timestamp][skey] = value
            else:
                #print(f'    create entry in self.timestampedMap: {timestamp,skey}')
                self.timestampedMap[timestamp] = {skey:value}
            #print(f'devPar {devPar}@{timestamp}, tsMap: {self.timestampedMap[timestamp].keys()}')
        #TODO: self.timestampedMap may need sorting
        #print(f'self.timestampedMap: {self.timestampedMap}')
        
    def _create_logSection(self):
      with self.lock:
        #print('create empty list of paragraphs')
        self.sectionKey = time.strftime("%y%m%d_%H%M%S")
        self.timestampedMap = {}

    def _serialize_sections(self):
        #_printi('serialize_sections started')
        periodic_update = time.time()
        statistics = [0, 0, 0, 0]#
        NSections, NParagraphs, BytesRaw, BytesFinal = 0,1,2,3
        try:
          while not self._eventStop.is_set():
            self._eventStop.wait(self.sectionInterval)
            if len(self.timestampedMap) == 0:
                continue

            # register the section in the table of contents, this should be skipped
            # for some entries when the contents downsampling is active.
            if self.dirSize:
                #offset = statistics[BytesRaw] + self.dirSize
                #self.dataContents[self.sectionKey] = offset
                rf = self.contents_downsampling_factor
                if rf <=1 or (statistics[NSections]%rf) == 0:
                    self.dataContents[self.sectionKey] = self.logbook.tell()
                    packed = msgpack.packb(self.contentsSection)
                    if len(packed) < self.dirSize:
                        self.packedContents = packed
                    else:
                        _printw((f'The contents size is too small for'
                        f' {len(packed)} bytes. Half of the entries will be'
                        ' removed to allow for more entries.}'))
                        self.contents_downsampling_factor *= 2
                        downsampled_contents = dict(list(self.dataContents.items())\
                          [::self.contents_downsampling_factor])
                        self.contentsSection['data'] = downsampled_contents
                        _printd(f'downsampled contentsSection:{self.contentsSection}')
                        self.packedContents = msgpack.packb(self.contentsSection)

            #print(f'section is ready, write it to logbook {self.logSection}')
            _printd(f'writing section {statistics[NSections]} @ {self.logbook.tell()}')
            statistics[NSections] += 1
            with self.lock:
                paragraphs = list(self.timestampedMap.items())
                self.logSection = (self.sectionKey, paragraphs)
                #print(f'section:{self.logSection}')
            packed = msgpack.packb(self.logSection
            , use_single_float=self.use_single_float)
            statistics[NParagraphs] += len(paragraphs)
            statistics[BytesRaw] += len(packed)
            if self.compress is not None:
                compressed = self.compress(packed)
                packed = msgpack.packb(compressed
                , use_single_float=self.use_single_float)
            statistics[BytesFinal] += len(packed)
            self.logbook.write(packed)
            self.logbook.flush()

            self._create_logSection()
            timestamp = time.time()
            dt = timestamp - periodic_update
            if dt > 10.:
                periodic_update = timestamp
                if not self.quiet:
                    print(f'{time.strftime("%y-%m-%d %H:%M:%S")} Logged'
                    f' {statistics[NSections]} sections,'
                    f' {statistics[NParagraphs]} paragraphs,'
                    f' {statistics[BytesFinal]/1000.} KBytes')
        except Exception as e:
            print(f'ERROR: Exception in serialize_sections: {e}')

        # logging finished
        # rewrite the contentsSection
        if self.dirSize:
            self.logbook.seek(0)
            self.logbook.write(self.packedContents)

        # print status
        msg = (f'Logging finished for {statistics[NSections]} sections,'
        f' {statistics[NParagraphs]} paragraphs,'
        f' {statistics[BytesFinal]/1000.} KB.')
        if self.compress is not None:
            msg += f' Compression ratio:{round(statistics[BytesRaw]/statistics[BytesFinal],2)}'
        print(msg)
        self.logbook.close()
                
def _safeExit(_signo, _stack_frame):
    print('safeExit')
    apstrim._eventStop.set()
    apstrim.eventExit.set()
    
                
