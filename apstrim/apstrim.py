# Copyright (c) 2021 Andrei Sukhanov. All rights reserved.
#
# Licensed under the MIT License, (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/ASukhanov/apstrim/blob/main/LICENSE
#
#__version__ = '1.0.3 2021-06-01'# EPICS and LITE support is OK, Compression supported
#__version__ = '1.0.4a 2021-06-11'# flush the file after each section
#__version__ = '1.0.4 2021-06-11'# if file exist then rename the existing file
#__version__ = '1.0.5 2021-06-14'# handling of different returned maps
#__version__ = '1.0.6 2021-06-19'# filename moved from instantiation to new method: start(), timestamp is int(nanoseconds)
#__version__ = '1.0.7 2021-06-20'# Docstrings updated
#__version__ = '1.0.9 2021-06-21'# new keyword: self.use_single_float
__version__ = '1.0.10 2021-06-21'# separate events for exit and stop

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
SecDateTime, SecParagraph = 0,1
Nano = 1000000000
#````````````````````````````Helper functions`````````````````````````````````
def _printTime(): return time.strftime("%m%d:%H%M%S")
def _printi(msg): print(f'INFO_AS@{_printTime()}: {msg}')
def _printw(msg): print(f'WARN_AS@{_printTime()}: {msg}')
def _printe(msg): print(f'ERROR_AS@{_printTime()}: {msg}')

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
    publisher:      is a class, providing a subscribe() method,
    devPar:         list of device:parameter strings,
    sectionInterval: time between writing of the logBook sections
    compression:    compression enable flag,
    quiet:          do not print section writing progress,
    use_single_float: Use single precision float type for float. (default: False)
    eventExit:      is a threading.Event, which will be set when application
     is about to exit.
    """
    eventExit = threading.Event()
    _eventStop = threading.Event()

    def __init__(self, publisher, devPars:list, sectionInterval=60.
    , compress=False, quiet=False, use_single_float=True):
        #_printi(f'apstrim  {__version__}, sectionInterval {sectionInterval}')
        self.publisher = publisher
        self.devPars = devPars
        self.sectionInterval = sectionInterval
        self.quiet = quiet
        self.use_single_float = use_single_float
        signal.signal(signal.SIGINT, _safeExit)
        signal.signal(signal.SIGTERM, _safeExit)
        self.headerSection = {'apstrim ':__version__
        , 'sectionInterval':sectionInterval}
        if compress:
            import lz4framed
            self.compress = lz4framed.compress
            self.headerSection['compression'] = 'lz4framed'
        else:
            self.compress = None
            self.headerSection['compression'] = 'None'
        _printi(f'Header section: {self.headerSection}')
        self.lock = threading.Lock()

    def start(self, fileName='apstrim.aps'):
        """Start streaming of the data objects to logbook file.
        If file is already exist then it will be renamed and
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
        self.logbook.write(msgpack.packb(self.headerSection
        , use_single_float=self.use_single_float))

        self._create_logSection()

        #_printi('starting periodic thread')
        myThread = threading.Thread(target=self._serialize_section)
        myThread.start()

        self.pars = {}
        for i,pname in enumerate(self.devPars):
            devPar = tuple(pname.rsplit(':',1))
            if True:#try:
                self.publisher.subscribe(self._delivered, devPar)
            else:#except Exception as e:
                __printe(f'Subscription failed for {pname}: {e}')
                continue
            self.pars[pname] = [shortkey(i)]
        _printi(f'parameters: {self.pars}')
        buf = msgpack.packb({'parameters':self.pars}
        , use_single_float=self.use_single_float)
        self.logbook.write(buf)
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
        timestampedMap = {}
        for devPar,props in args[0].items():
            #print(f'devPar: {devPar,props}, {type(devPar)}')
            try:
              if isinstance(devPar, tuple):
                # EPICS and ADO packing
                dev,par = devPar
                value = props['value']
                timestamp = props.get('timestamp')# valid in EPICS and LITE
                if timestamp == None:# decode ADO timestamp 
                    timestamp = int(props['timestampSeconds']*Nano
                    + props['timestampNanoSeconds'])
                else:
                    timestamp = int(timestamp*Nano)
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
                        timestamp = int(pars[par]['timestamp']*Nano)
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
                    #print(f'Numpy f64->f32 reduction time: {round(timer()-ts,6)}')
                except:    pass

            if timestamp in timestampedMap:
                timestampedMap[timestamp][skey] = value
            else:
                timestampedMap[timestamp] = {skey:value}
        #TODO: timestampedMap may need sorting
        #print(f'timestampedMap: {timestampedMap}')
        with self.lock:
            self.logParagraph.append(list(timestampedMap.items())[0])
        
    def _create_logSection(self):
      with self.lock:
        self.logParagraph = []
        key = time.strftime("%y%m%d:%H%M%S")
        self.logSection = (key, self.logParagraph)

    def _serialize_section(self):
        #_printi('serialize_section started')
        periodic_update = time.time()
        stat = [0, 0]
        try:
          while not self._eventStop.is_set():
            self._eventStop.wait(self.sectionInterval)
            if len(self.logSection[SecParagraph]) == 0:
                continue

            #print(f'write section {self.logSection}')
            packed = msgpack.packb(self.logSection
            , use_single_float=self.use_single_float)
            if self.compress is not None:
                compressed = self.compress(packed)
                packed = msgpack.packb(compressed
                , use_single_float=self.use_single_float)
            self.logbook.write(packed)
            self.logbook.flush()

            stat[0] += len(self.logSection[SecParagraph])
            stat[1] += len(packed)
            self._create_logSection()
            timestamp = time.time()
            dt = timestamp - periodic_update
            if dt > 10.:
                periodic_update = timestamp
                if not self.quiet:
                    print(f'{time.strftime("%y-%m-%d %H:%M:%S")} Logged {stat[0]} paragraphs, {stat[1]/1000.} KBytes')
        except Exception as e:
            print(f'ERROR: Exception in serialize_section: {e}')
        print(f'Logging finished after {stat[0]} paragraphs')
        self.logbook.close()
                
def _safeExit(_signo, _stack_frame):#, self=None):
    print('safeExit')
    apstrim._eventStop.set()
    apstrim.eventExit.set()
    
                
