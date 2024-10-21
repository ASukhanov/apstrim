# Copyright (c) 2021 Andrei Sukhanov. All rights reserved.
#
# Licensed under the MIT License, (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/ASukhanov/apstrim/blob/main/LICENSE
#

"""Basic EPICS access API using caproto: a pure-Python Channel Access protocol library
"""
__version__ = 'v3.1.0 2023-10-21'# Access() is static class 
print(f'pubEPICS: {__file__}, {__version__}')

#from timeit import default_timer as timer

from caproto.threading.client import Context
Ctx = Context()

PVC_PV, PVC_CB, PVC_Props = 0, 1, 2
dbg = True
CA_data_type_STRING = 14

def printd(msg):
    if Access.Dbg:
        print(f'CPAccess:{msg}')
    
class Access():
    Dbg = False
    __version__ = __version__
    _Subscriptions = []
    _PVCache = {}

    def _get_pv(pvName):
        r = Access._PVCache.get(pvName)
        if r is not None:
            pv,*_ = r
        else:
            #print( f'register pv {pvName}')
            pv,*_ = Ctx.get_pvs(pvName, timeout=2)
            #print(f'>pvCache: {pv}')
            Access._PVCache[pvName] = [pv, None, None]
            Access._fill_PVCacheProps(pvName)
        return pv
    
    def _fill_PVCacheProps(pvName):
        pv = Access._PVCache[pvName][PVC_PV]
        if pv is None:
            return None
        pvData = pv.read(data_type='time')
        #printd(f'pvData:{pvData}')
        val = pvData.data
        #printd(f'val:{val}')
        if len(val) == 1:
            try:
                # treat it as numpy
                val = pvData.data[0].item()
            except:
                # data is not numpy
                val = pvData.data[0]
        
        # get properties
        #ISSUE: the caproto reports timestamp as float, the precision for float64 
        #presentation is ~300ns
        featureBit2Letter = {1:'R', 2:'WE'}
        featureCode = pv.access_rights
        features = ''
        for bit, letter in featureBit2Letter.items():
            if bit & featureCode:
                features += letter
        pvControl = pv.read(data_type='control')
        #printd(f'pvcontrol {pvName}: {pvControl}')
        datatype = pvControl.data_type
        #printd(f'data_type:{datatype}')
        if datatype == CA_data_type_STRING:# convert text bytearray to str
            val = val.decode()
        props = {'value':val}
        props['timestamp'] = pvData.metadata.timestamp
        props['count'] = len(pvData.data)
        props['features'] = features
        try:    
            props['units'] = pvControl.metadata.units.decode()
            if props['units'] == '':   props['units'] = None
        except: pass
    
        try:    props['engLow'] = pvControl.metadata.lower_ctrl_limit
        except: pass
    
        try:    
            props['engHigh'] = pvControl.metadata.upper_ctrl_limit
            if props['engHigh'] == 0.0 and props['engHigh'] == 0.0:
                props['engHigh'], props['engLow'] = None, None
        except: pass
    
        try:
            props['alarm'] = pvControl.metadata.severity 
            #printd(f'status {pvControl.metadata.severity}')
            if props['alarm'] == 17:# UDF
                props['alarm'] = None
        except: pass
    
        try:    # legalValues
            enum_strings = pvControl.metadata.enum_strings
            props['legalValues'] = [i.decode() for i in enum_strings]
            props['value'] = props['legalValues'][val]
        except:
            #props['legalValues'] = None
            if 'legalValues' in props:
                del props['legalValues']
        #printd(f'_props {props}')
        Access._PVCache[pvName][PVC_Props] = props
    
    def _unpack_ReadNotifyResponse(pvName, pvData):
        #printd('>uRNR')
        val = pvData.data
        if len(val) == 1:
            try:    #it as numpy
                val = pvData.data[0].item()
            except: # it is not numpy
                val = pvData.data[0]
        #printd(f'pvData:{pvData}')
        #printd(f'val:{val}, {pvData.data_type}')
        if pvData.data_type == CA_data_type_STRING:
            val = val.decode()
        rDict = {'pvname':pvName, 'value':val}
        
        rDict['timestamp'] = pvData.metadata.timestamp
        ##printd(f'uRNR1:{rDict}')
    
        legalValues = Access._PVCache[pvName][PVC_Props].get('legalValues')
        #printd(f'uRNR2:{legalValues}')
        if legalValues is not None:
            #rDict['value'] = legalValues[int(val)]
            val = legalValues[int(val)]
        #printd('uRNR3')
        alarm = pvData.metadata.severity
        rDict['alarm'] = alarm
        #printd(f'pvName:{pvName}')
        key = tuple(pvName.rsplit(':',1))
        #printd(f'key:{key}')
        rDict = {key: {'value':val\
        , 'timestamp':pvData.metadata.timestamp, 'alarm': alarm}}
        #printd(f'<uRNR:{rDict}')
        return rDict
    
    def info(devParName):
        """Abridged PV info"""
        pvName = ':'.join(devParName)
        pv = Access._get_pv(pvName)
        return {pvName:Access._PVCache[pvName][PVC_Props]}


    def get(devParName, **kwargs):
        pvName = ':'.join(devParName)
        pv = Access._get_pv(pvName)
        pvData = pv.read(data_type='time')
        rDict = Access._unpack_ReadNotifyResponse(pvName, pvData)
        return rDict

    def set(devParValue):
        dev, par, value = devParValue
        #print(f'epicsAccess.set({dev,par,value})')
        pvName = ':'.join((dev,par))
        pv = Access._get_pv(pvName)
        try: # if PV has legalValues then the value should be index of legalValues
            value = Access._PVCache[pvName][PVC_Props]['legalValues'].index(value)
            #lv = Access._PVCache[pvName][PVC_Props]['legalValues']
            #print(f'lv:{lv}')
        except Exception as e:
            #print(f'in epicsAccess.set. Value not in legalValues: {e}')
            pass
        pv.write(value)
        return 1

    def _callback(subscription, pvData):
        printd(f'>epicsAccess._callback: {pvData})')
        #tMark = [timer(), 0., 0.]
        pvName = subscription.pv.name
        rDict = Access._unpack_ReadNotifyResponse(pvName, pvData)
        #tMark[1] = timer()
        #printd(f'rDict for {pvName}:{rDict}')
        #printd(f'Access._PVCache:{Access._PVCache}')
        cache = Access._PVCache.get(pvName)
        #printd(f'cache[{len(cache)}]:{cache}')
        cb = cache[PVC_CB]
        #printd(f'cb:{str(cb)}')
        if cb:
            #print(f'epicsAccess call {cb}({rDict})')
            cb(rDict)
        #tMark[2] = timer() - tMark[1]
        #tMark[1] -= tMark[0]
        ##printd(f'caproto cb times {tMark}')# 20-30 uS
        printd('<callback')
        
    def subscribe(callback, devParName):
        printd('>subscribe')
        pvName = ':'.join(devParName)
        if not isinstance(pvName, str):
            msg = f'ERROR: Second argument of subscribe() should be a string, not {type(pvName)}'
            raise SystemError(msg)
        pv = Access._get_pv(pvName)
        subscription = pv.subscribe(data_type='time')
        Access._PVCache[pvName][PVC_CB] = callback
        #printd('>add_callback')
        subscription.add_callback(Access._callback)
        Access._Subscriptions.append(subscription)
    
    def unsubscribe(self):
        for subscription in Access._Subscriptions:
            #print(f'>epicsAccess clear subs: {subscription}')
            Access._Subscriptions.clear()
        Access._Subscriptions = []
    
