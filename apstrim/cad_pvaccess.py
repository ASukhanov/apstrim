"""Basic EPICS PVAccess API using p4p python wrapper.
The API is similar to cad_io.
The devPar argument is tuple (deviceName,parameterName).

For example: pvaccess.get(('simScope1','NoiseAmplitude')) returns:
{('simScope1', 'NoiseAmplitude'): {'value': 3.0, 'timestampSeconds': 1735615833, 'timestampNanoSeconds': 822335958}}

To set NoiseAmplitude to 1.:
pvaccess.set(('simScope1','NoiseAmplitude',1.))
"""
__version__ = 'v0.1.2 2025-01-05'# _pvname()

import time
#from time import perf_counter as timer
from functools import partial
from p4p.client.thread import Context
from p4p.nt.enum import ntenum

_dbg = False
_Ctx = Context()# provides only PV values
_CtxRaw = Context(unwrap=False)# provides PV properties
_PVInfo = {}# cache of PVs
_Subscriptions = []# list of EPICS PV subscriptions

def _printd(msg):
    if _dbg:
        print(f'CPAccess:{msg}')
def printTime(): return time.strftime("%m%d:%H%M%S")
def printi(msg): print(f'inf_PVA@{printTime()}: {msg}')
def printw(msg): print(f'WAR_PVA@{printTime()}: {msg}')
def printe(msg): print(f'ERR_PVA@{printTime()}: {msg}')
def init():
    return

def _pvname(devPar:tuple):
    return ':'.join(devPar)

def info(devPar:tuple):
    """Abridged PV info"""
    pvName = _pvname(devPar)
    v = _CtxRaw.get(pvName)
    #print(f'v of {pvName}: {v.todict()}')
    r = {devPar:{'value':v.value,
        'timestampSeconds': v.timeStamp.secondsPastEpoch,
        'timestampNanoSeconds': v.timeStamp.nanoseconds
        }}

    # With p4p it is impossible to detect if parameter is writable
    r[devPar]['features'] = 'RWE'

    try:    r[devPar]['desc'] = v.display.description
    except: pass
    try:  r[devPar]['units'] = v.display.units
    except: pass
    try:
        if not (v.display.limitLow == v.display.limitHigh == 0.0):
            r[devPar]['opLow'] = v.display.limitLow
            r[devPar]['opHigh'] = v.display.limitHigh
    except: pass
    try:  r[devPar]['units'] = v.display.units
    except: pass
    try:
        r[devPar]['legalValues'] = v.value['choices']
        r[devPar]['value'] = v.value['choices'][v.value['index']]
    except: pass
    _PVInfo[devPar] = r
    #print(f'info of {pvName}: {r}')
    return r

#``````````````````PVCache methods````````````````````````````````````````````
def _cachedInfo(devPar:tuple):
    pvinfo = _PVInfo.get(devPar)
    if pvinfo is None:
        pvinfo = info(devPar)[devPar]
        print(f'register pvinfo {devPar}: {pvinfo}')
        _PVInfo[devPar] = pvinfo
    return pvinfo

def get(devPar:tuple, *args, **kwargs):
    """Returns devPar-keyed map of PV properties: {'value','timestamp'...}"""
    pvName = _pvname(devPar)
    v = _CtxRaw.get(pvName)
    #print(f'got {pvName}: {v.todict()}')
    try:    value = v.value['choices'][v.value['index']]
    except: value = v.value
    try:    #to interpret it as NTENum
        idx = value.index
        value = value.choices[idx]
    except: pass
    rDict = {devPar:{'value':value,
        'timestampSeconds': v.timeStamp.secondsPastEpoch,
        'timestampNanoSeconds': v.timeStamp.nanoseconds
        }}
    return rDict

def set(devParValue:tuple):
    """Sets the PV value. The devParValue is (deviceName, ParameterName, value)
    """
    dev, par, value = devParValue
    info = _cachedInfo((dev,par))
    #print(f'>set({dev,par,type(value),value, info})')
    try:
        if value < info['opLow']:
            printw(f'Value {value} is lower than opLow of {dev,par}')
            return False
    except: pass
    try:
        if value > info['opHigh']:
            printw(f'Value {value} is higher than opHigh of {dev,par}')
            return False
    except: pass
    try:
        if value not in info['legalValues']:
            printw(f'Value {value} is not in legalValues of {dev,par}')
            return False
        value = info['legalValues'][value]
    except: pass
    pvName = _pvname((dev,par))
    try:
        _Ctx.put(pvName, value)
    except Exception as e:
        printw(f'Set {dev, par, value}: {e}')
        return False 
    return True
    
def _callback(callback, devPar, value):
    vr = value.raw
    #print(f'>_callback: {devPar}, {vr}')#{pvData})')
    if isinstance(value, ntenum):
        d = vr.value.todict()
        v = d['choices'][d['index']]
    else:
        v = vr.value
    r = {devPar:{'value':v,
        'timestampSeconds':vr.timeStamp.secondsPastEpoch,
        'timestampNanoSeconds':vr.timeStamp.nanoseconds,
        }}
    #print(f'cb {devPar,r}')
    callback(r)

def subscribe(callback:callable, devPar:tuple):
    """Subscribe callback method to changes of PVs, defined by devPar"""
    pvName = _pvname(devPar)
    subscription = _Ctx.monitor(pvName, partial(_callback, callback, devPar))
    _Subscriptions.append((subscription,callback))

def unsubscribe():
    """Unsubscribe all subscriptions"""
    global _Subscriptions
    for subs,cb in _Subscriptions:
        #print(f'>pvaccess close subs: {subs}')
        subs.close()
    _Subscriptions = []
    
