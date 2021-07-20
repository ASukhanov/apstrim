"""
View content of aplog-generated files: list sections, paragraphs and (-i) 
parameters.
Plot items using pyqtgraph.
"""
import sys, time, argparse, os
from timeit import default_timer as timer
#from pprint import pprint
from functools import partial
import bisect
import numpy as np
import msgpack
import msgpack_numpy
msgpack_numpy.patch()
__version__ = 'v06 2021-06-14'# improved plotting: cursors, legends. Qt4 compatible.

def printd(msg):
    if pargs.verbose>0 or pargs.contents:
        print(f'DBG_ALLS: {msg}')

Nano = 0.000000001
TimeFormat_in = '%y%m%d_%H%M%S'
TimeFormat_out = '%y%m%d_%H%M%S'

parser = argparse.ArgumentParser(description=__doc__
    ,formatter_class=argparse.ArgumentDefaultsHelpFormatter
    ,epilog=f'aplog.ls: {__version__}')
parser.add_argument('-c', '--contents', action='store_true', help=\
'Print only header sections: Table of contents, Abstract, Abbreviations')
parser.add_argument('-i', '--iterate', action='store_true', help=\
'Iterate through all parameters in paragraph')
parser.add_argument('-k', '--keys', help=('Items to plot. '
'String of comma-separated keys of the parameter map e.g. "1,3,5,7,a0,az"'))
parser.add_argument('-p', '--plot', default=None, help="""Plot data using 
pyqtgraph, legal values: -pf: fast (lines only), -ps: plot symbols (slow)""")
parser.add_argument('-s', '--startTime', help="""Start time, e.g. 210720_001725""")
parser.add_argument('-t', '--timeInterval', type=float, default=60, help="""
Time span in seconds""")
parser.add_argument('-v', '--verbose', action='store_true', help=\
'List a statistics of parameters.')
parser.add_argument('files', nargs='*', default=['apstrim.aps'], help=\
'Input files, Unix style pathname pattern expansion allowed e.g: pi0_2021*.aps')
pargs = parser.parse_args()
print(f'files: {pargs.files}')
try:    pargs.plot = pargs.plot[:2]
except: pass
#print(f'plot:{pargs.plot}')
try:    pargs.keys.split(',')
except: pargs.keys = []

print(f'pvor pg: {pargs.verbose>0,pargs.contents}')

if pargs.startTime:
    ttuple = time.strptime(pargs.startTime,TimeFormat_in)
    first_section = time.strftime(TimeFormat_out, ttuple)
    tu = time.mktime(ttuple)
    ttuple = time.localtime(tu + pargs.timeInterval)
    last_section = time.strftime(TimeFormat_out, ttuple)
    print(f'start,end:{first_section,last_section}')

parameterStatistics ={}
if pargs.plot:
    plotData = {}
for fileName in pargs.files:
    print(f'Processing {fileName}')
    fileSize = os.path.getsize(fileName)
    logbook = open(fileName,'rb')
 
    # unpack logbook contents and position file pointer after it
    book = msgpack.Unpacker(logbook, use_list=False) #use_list speeds up 20%, # does not help:, read_size=100*1024*1024)
    contentsSize = 0
    for contents in book:
        printd(f'Table of contents: {contents}')
        try:
            contentsSize = contents['contents']['size']
        except:
            print('Warning: Table of contents is missing or wrong')
            break
        dataContents = contents['data']
        break

    # unpack two sections after the contents: Abstract and Abbreviations
    logbook.seek(contentsSize)
    book = msgpack.Unpacker(logbook, use_list=False) #use_list speeds up 20%, # does not help:, read_size=100*1024*1024)
    nSections = 0
    for section in book:
        nSections += 1
        if nSections == 1:# section: Abstract
            printd(f'Abstract@{logbook.tell()}: {section}')
            abstract = section['abstract']
            compression = abstract.get('compression')
            if compression is None:
                continue
            if compression != 'None':
                module = __import__(compression)
                decompress = module.decompress
            continue
        if nSections == 2:# section: Abbreviations
            par2key = section['abbreviations']
            key2par = {value[0]:key for key,value in par2key.items()}
            printd(f'Abbreviations@{logbook.tell()}: {key2par}')
            if len(pargs.keys) == 0: # enable handling of all parameters 
                pargs.keys = key2par.keys()
            for key,par in key2par.items():
                if par not in parameterStatistics:
                    #print(f'add to stat[{len(parameterStatistics)+1}]: {par}') 
                    parameterStatistics[key] = 0
                if pargs.plot and par not in plotData and key in pargs.keys:
                        printd(f'add to graph[{len(plotData)+1}]: {par}') 
                        plotData[par] = {'x':[], 'y':[]}
            break
    if pargs.contents:
        break
    # re-create the unpacker for reading logbook starting from required section
    if contentsSize != 0 and pargs.startTime:
        print(f'fs:{first_section} = {dataContents[first_section]}')
        keys = list(dataContents.keys())
        nearest_idx = bisect.bisect_left(keys, first_section)
        nearest_section = keys[nearest_idx]
        printd(f'first_section {first_section}, nearest: {nearest_section}')
        section_pos = dataContents[nearest_section]
        logbook.seek(section_pos)
        printd(f'logbook positioned to section {nearest_section}, offset={contentsSize}')
        book = msgpack.Unpacker(logbook, use_list=False) #use_list speeds up 20%, # does not help:, read_size=100*1024*1024)

    # loop over sections in the logbook
    tstart = time.time()
    nSections = 0
    nParagraphs = 0
    for section in book:
        nSections += 1
        # data sections
        #print(f'Data Section: {section}')
        dt = time.time() - tstart
        if nSections%60 == 0:
            print((f'Data sections: {nSections}, paragraphs: {nParagraphs}'
            f', elapsed time: {round(dt,1)}, paragraphs/s: {nParagraphs//dt}'))
        try:
            if compression != 'None':
                decompressed = decompress(section)
                section = msgpack.unpackb(decompressed)
            sectionDatetime, paragraphs = section
        except Exception as e:
            print(f'WARNING: wrong section {nSections}: {str(section)[:75]}...')
            break
        if pargs.startTime and sectionDatetime > last_section:
            print(f'reached last section {sectionDatetime}')
            break
        nParagraphs += len(paragraphs)
        if pargs.iterate or pargs.plot:
            try:
              for timestamp,parkeys in paragraphs:
                timestamp *= Nano
                #print(f'paragraph: {timestamp, parkeys}')
                for key in parkeys:
                    if key not in pargs.keys:
                        continue
                    parameterStatistics[key] += 1
                    if pargs.plot:
                        values = parkeys[key]
                        try:    nVals = len(values)
                        except: values = [values] # make it subscriptable
                        par = key2par[key]
                        # if values is a vector then append all its points spaced by 1 us
                        for i,v in enumerate(values):
                            plotData[par]['x'].append(timestamp + i*1.e-6)
                            plotData[par]['y'].append(v)
                            #print(f'key {key}, ts: {timestamp}')                    
            except Exception as e:
                print(f'WARNING: wrong paragraph {nParagraphs}: {e}')
    print(f'Deserialized from {fileName}: {nSections} sections, {nParagraphs} paragraphs')
    if pargs.iterate:
        print(f'Parameters {parameterStatistics}')
    dt = time.time() - tstart
    print((f'Elapsed time: {round(dt,1)}, {int(nParagraphs/dt)} paragraphs/s:'
    f' , {round(fileSize/1e6/dt,1)} MB/s'))
#,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,    
if pargs.plot:
    #```````````````````````````` Plot objects````````````````````````````````
    import pyqtgraph as pg
    pg.setConfigOption('background', 'w')
    pg.setConfigOption('foreground', 'k')

    class DateAxis(pg.AxisItem):
        """Time scale for plotItem"""
        def tickStrings(self, values, scale, spacing):
            strns = []
            if len(values) == 0: 
                return ''
            rng = max(values)-min(values)
            #if rng < 120:
            #    return pg.AxisItem.tickStrings(self, values, scale, spacing)
            if rng < 3600*24:
                string = '%d %H:%M:%S'
            elif rng >= 3600*24 and rng < 3600*24*30:
                string = '%d'
            elif rng >= 3600*24*30 and rng < 3600*24*30*24:
                string = '%b'
            elif rng >=3600*24*30*24:
                string = '%Y'
            for x in values:
                try:
                    strns.append(time.strftime(string, time.localtime(x)))
                except ValueError:  ## Windows can't handle dates before 1970
                    strns.append('')
            return strns

    #QT5#win = pg.GraphicsLayoutWidget(show=True)
    qApp = pg.mkQApp()
    win = pg.GraphicsLayoutWidget()
    win.show()

    win.resize(800,600)
    s = pargs.files[0] if len(pargs.files)==1 else pargs.files[0]+'...'
    win.setWindowTitle(f'Graphs[{len(plotData)}] of {s}')

    plotItem = win.addPlot(#title="apstrim plotItem",
        axisItems={'bottom':DateAxis(orientation='bottom')})
    plotItem.setDownsampling(auto=True)#, mode='subsample')
    legend = pg.LegendItem((80,60), offset=(70,20))
    legend.setParentItem(plotItem)
    viewBox = plotItem.getViewBox()
    viewBox.setMouseMode(pg.ViewBox.RectMode)

    idx = 0
    ts = timer()
    nPoints = 0
    viewRect = plotItem.viewRect()
    xSize = int(viewRect.right() - viewRect.left())
    for par,xy in list(plotData.items())[::-1]: #inverted map produces better color for first items 
        print(f'Graph[{idx}]: {par}')
        idx += 1
        # sort points along X
        a = np.stack([xy['x'],xy['y']])
        a = a[:, a[0, :].argsort()]
        pen = (idx,len(plotData))
        npt = len(a[0])
        nPoints += npt
        try:
            if pargs.plot[0] =='f' or npt/xSize > 100:
                # plotting of only lines
                p = plotItem.plot(a[0], a[1], pen=pen)
            else:
                # plotting with symbols is 10 times slower
                p = plotItem.plot(a[0], a[1], pen=pen
                ,symbol='+', symbolSize=2, symbolPen=pen)
            legend.addItem(p, par)
        except Exception as e:
            print(f'WARNING: plotting is not supported for item {par}: {e}')
    print(f'plotting time of {nPoints} points: {round(timer()-ts,3)} s')

    cursors = set()
    def add_cursor(direction):
        global cursor
        angle = {'Vertical':90, 'Horizontal':0}[direction]
        vid = {'Vertical':0, 'Horizontal':1}[direction]
        viewRange = plotItem.viewRange()
        pos = (viewRange[vid][1] + viewRange[vid][0])/2.
        pen = pg.mkPen(color='y', width=1, style=pg.QtCore.Qt.DotLine)
        cursor = pg.InfiniteLine(pos=pos, pen=pen, movable=True, angle=angle
        , label=str(round(pos,3)))
        cursor.sigPositionChangeFinished.connect(\
        (partial(cursorPositionChanged,cursor)))
        cursors.add(cursor)
        plotItem.addItem(cursor)
        cursorPositionChanged(cursor)

    def cursorPositionChanged(cursor):
        pos = cursor.value()
        horizontal = cursor.angle == 0.
        viewRange = plotItem.viewRange()[horizontal]
        if pos > viewRange[1]:
            plotItem.removeItem(cursor)
            cursors.remove(cursor)
        else:
            if horizontal:
                text = str(round(pos,3))
            else:
                text = time.strftime('%H:%M:%S', time.localtime(pos))
            cursor.label.setText(text)

    add_cursor('Vertical')
    add_cursor('Horizontal')

    qApp.exec_()
