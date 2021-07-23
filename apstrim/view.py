"""Plot data from the aplog-generated files."""
__version__ = 'v1.3.0 2021-07-22'

import sys, time, argparse, os
from timeit import default_timer as timer
from functools import partial
import numpy as np
import pyqtgraph as pg
pg.setConfigOption('background', 'w')
pg.setConfigOption('foreground', 'k')

from .scan import APScan, __version__ as scanVersion

def printv(msg):
    if APScan.Verbosity >= 1:
        print(f'DBG_view: {msg}')

parser = argparse.ArgumentParser(description=__doc__
    ,formatter_class=argparse.ArgumentDefaultsHelpFormatter
    ,epilog=f'aplog scan : {scanVersion},  view: {__version__}')
parser.add_argument('-H', '--header', help=\
'Show selected header, lecal values: Directory, Abstract, Abbreviations')
parser.add_argument('-i', '--items', help=('Items to plot. Legal values: "all" or '
'string of comma-separated keys of the parameter map e.g. "1,3,5,7,a0,az"'))
parser.add_argument('-p', '--plot', action='store_true', help=
"""Plot data using pyqtgraph""")
parser.add_argument('-s', '--startTime', help=
"""Start time, fomat: YYMMDD_HHMMSS, e.g. 210720_001725""")
parser.add_argument('-t', '--timeInterval', type=float, default=9e9, help="""
Time span in seconds.""")
parser.add_argument('-v', '--verbose', nargs='*', help=\
'Show more log messages, (-vv: show even more)')
parser.add_argument('files', nargs='*', default=['apstrim.aps'], help=\
'Input files, Unix style pathname pattern expansion allowed e.g: *.aps')
pargs = parser.parse_args()

print(f'files: {pargs.files}')

#if pargs.plot is not None:
#    pargs.plot = 'fast' if len(pargs.plot) == 0 else 'symbols'

if pargs.verbose is not None:
    APScan.Verbosity = 1 if len(pargs.verbose) == 0\
    else len(pargs.verbose[0]) + 1
print(f'Verbosity: {APScan.Verbosity}')

allExtracted = []

for fileName in pargs.files:
    apscan = APScan(fileName)
    print(f'Processing {fileName}, size: {round(apscan.logbookSize*1e-6,3)} MB')
    headers = apscan.get_headers()
    
    if pargs.header:
        print(f'Header {pargs.header}:\n {headers[pargs.header]}')

    if pargs.items is None:
        print('No items to scan')
        sys.exit()

    items = [] if pargs.items == 'all' else pargs.items.split(',')
    printv(f'scan{pargs.timeInterval, items, pargs.startTime}')
    extracted = apscan.extract_objects(pargs.timeInterval, items, pargs.startTime)
    allExtracted .append(extracted)

#````````````````````````````Plot objects`````````````````````````````````````
if pargs.plot:
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
    win.setWindowTitle(f'Graphs[{len(extracted)}] of {s}')

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
    legends = set()
    for extracted in allExtracted:
      for key,xy in list(extracted.items())[::-1]: #inverted map produces better color for first items 
        print(f"Graph[{key}]: {xy['par']}, {len(xy['time'])} points")
        idx += 1
        # sort points along X
        a = np.stack([xy['time'],xy['value']])
        a = a[:, a[0, :].argsort()]
        pen = (idx,len(extracted))
        npt = len(a[0])
        if npt < 2:
            continue
        nPoints += npt
        #print(f'npt/xSize: {npt/xSize, npt,xSize}')
        try:
            #if pargs.plot =='fast' or npt/xSize > 100:
            if npt/xSize > 500:                
                # plotting of only lines
                p = plotItem.plot(a[0], a[1], pen=pen)
            else:
                # plotting with symbols is 10 times slower
                p = plotItem.plot(a[0], a[1], pen=pen
                ,symbol='+', symbolSize=5, symbolPen=pen)
            legendText = key+' '+xy['par']
            if legendText not in legends:
                legends.add(legendText)
                legend.addItem(p, legendText)
        except Exception as e:
            print(f'WARNING: plotting is not supported for item {key}: {e}')
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