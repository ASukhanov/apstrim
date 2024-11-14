"""Plot data from the aplog-generated files."""
__version__ = 'v3.2.0 2024-11-14'# Cleanup, removed non-functional Dataset and MapOfDatasets
#TODO: data acquisition stops when section is dumped to disk. Is writing really buffered?

import sys, time, argparse, os
from timeit import default_timer as timer
from functools import partial
import numpy as np
from qtpy import QtWidgets as QW, QtCore#, QtGui
import pyqtgraph as pg
from pyqtgraph.graphicsItems.ViewBox.ViewBoxMenu import ViewBoxMenu
pg.setConfigOption('background', 'w')
pg.setConfigOption('foreground', 'k')

from apstrim.scan import APScan, __version__ as scanVersion

Nano = 1e-9
Cursors = False
def printv(msg):
    if APScan.Verbosity >= 1:
        print(f'DBG_view1: {msg}')
def printvv(msg):
    if APScan.Verbosity >= 2 :
        print(f'DBG_view2: {msg}')
def _croppedText(txt, limit=400):
    if len(txt) > limit:
        txt = txt[:limit]+'...'
    return txt

parser = argparse.ArgumentParser(description=__doc__
    ,formatter_class=argparse.ArgumentDefaultsHelpFormatter
    ,epilog=f'aplog scan : {scanVersion},  view: {__version__}')
choices = ['Directory', 'Abstract', 'Index', 'None']
parser.add_argument('-H', '--header', default='None', choices=choices, help=\
'Show all headers (-H) or selected header')
parser.add_argument('-i', '--items', help=('Items to plot. Legal values: "all" or '
'string of comma-separated keys of the parameter map e.g. "0,1,3,5,7,..."'))
parser.add_argument('-p', '--plot', action='store_true', help=
"""Plot data using pyqtgraph""")
parser.add_argument('-s', '--startTime', help=
"""Start time, fomat: YYMMDD_HHMMSS, e.g. 210720_001725""")
parser.add_argument('-t', '--timeInterval', type=float, default=9e9, help="""
Time span in seconds.""")
parser.add_argument('-v', '--verbose', action='count', default=0, help=\
  'Show more log messages (-vv: show even more).')
parser.add_argument('files', nargs='*', default=['apstrim.aps'], help=\
'Input files, Unix style pathname pattern expansion allowed e.g: *.aps')
pargs = parser.parse_args()
#print(f'files: {pargs.files}')

#if pargs.plot is not None:
#    pargs.plot = 'fast' if len(pargs.plot) == 0 else 'symbols'
APScan.Verbosity = pargs.verbose
#print(f'Verbosity: {APScan.Verbosity}')

#``````````````arrange keyboard interrupt to kill the program from terminal.
import signal
signal.signal(signal.SIGINT, signal.SIG_DFL)

allExtracted = []

for fileName in pargs.files:
    apscan = APScan(fileName)
    print(f'Processing {fileName}, size: {round(apscan.logbookSize*1e-6,3)} MB')
    headers = apscan.get_headers()
    
    if pargs.header != '':
        if pargs.header is None: pargs.header = 'All'
        pargs.header = pargs.header.capitalize()
        if pargs.header == 'All':
            pargs.header = legalHeaders.split(', ')
        else:
            pargs.header = [pargs.header]
        for header in pargs.header:
            if header == 'None':
                continue
            d = headers[header]
            s = f'Header {header}:{{\n'
            if header == 'Index':
                d = {i:v for i,v in enumerate(d)}
            elif header == 'Directory':                
                def seconds2Datetime(ns:int):
                    from datetime import datetime
                    dt = datetime.fromtimestamp(ns)
                    return dt.strftime('%y%m%d_%H%M%S') 
                d = {seconds2Datetime(ns):v for ns,v in d.items()}
            s += f'{d}'[1:].replace(', ',',\t')
            print(s)

    if pargs.items is None:
        print('No items to scan')
        sys.exit()

    items = [] if pargs.items == 'all'\
      else [int(i) for i in pargs.items.split(',')]
    printv(f'scan{pargs.timeInterval, items, pargs.startTime}')

    # extract the items
    ts = timer()
    extracted = apscan.extract_objects(pargs.timeInterval, items
    , pargs.startTime)
    print(f'Total (reading + extraction) time: {round(timer()-ts,3)}')
    allExtracted.append(extracted)
    #print(_croppedText(f'allEextracted: {allExtracted}'))

if not pargs.plot:
    exit()
#````````````````````````````Plot objects`````````````````````````````````````
pg.setConfigOption('background', 'w')
pg.setConfigOption('foreground', 'k')

class CustomViewBox(pg.ViewBox):
    ''' defines actions, activated on the right mouse click in the dock
    '''
    def __init__(self, **kwds):
        #self.dockName = kwds['name'] # cannot use name
        self.dockName = 'apView'
        #del kwds['name'] # the name in ViewBox.init fails in demo
        print('CustomViewBox: '+str(self.dockName)+', '+str(kwds))

        # call the init method of the parent class
        super(CustomViewBox, self).__init__()
        # the above is equivalent to:#pg.ViewBox.__init__(self, **kwds)

        # IMPORTANT: menu creation is deferred because it is expensive 
        # and often the user will never see the menu anyway.
        self.menu = None
        if Cursors:
            self.cursors = set()
           
    #v32#def mouseClickEvent(self, ev) removed, due to blank exports

    def raiseContextMenu(self, ev):
        # Let the scene add on to the end of our context menu
        menuIn = self.getContextMenus()        
        menu = self.scene().addParentContextMenus(self, menuIn, ev)
        menu.popup(ev.screenPos().toPoint())
        return True

    def getContextMenus(self, event=None):
        ''' This method will be called when this item's children want to raise
        a context menu that includes their parents' menus.
        '''
        if self.menu:
            printv('menu exist')
            return self.menu
        printv('getContextMenus for '+str(self.dockName))
        self.menu = ViewBoxMenu(self)
        self.menu.setTitle(str(self.dockName)+ " options..")

        if Cursors:
            cursorMenu = self.menu.addMenu('Add Cursor')
            for cursor in ['Vertical','Horizontal']:
                action = cursorMenu.addAction(cursor)
                action.triggered.connect(partial(self.cursorAction,cursor))
        
        labelX = QW.QWidgetAction(self.menu)
        self.labelXGui = QW.QLineEdit('LabelX')
        self.labelXGui.returnPressed.connect(
            lambda: self.set_label('bottom',self.labelXGui))
        labelX.setDefaultWidget(self.labelXGui)
        self.menu.addAction(labelX)
        labelY = QW.QWidgetAction(self.menu)
        self.labelYGui = QW.QLineEdit('LabelY')
        self.labelYGui.returnPressed.connect(
            lambda: self.set_label('left',self.labelYGui))
        labelY.setDefaultWidget(self.labelYGui)
        self.menu.addAction(labelY)
                   
        backgroundAction = QW.QWidgetAction(self.menu)
        backgroundGui = QW.QCheckBox('&Black background')
        backgroundGui.stateChanged.connect(
          lambda x: self.setBackgroundColor(\
          'k' if x == QtCore.Qt.Checked else 'w'))
        backgroundAction.setDefaultWidget(backgroundGui)
        self.menu.addAction(backgroundAction)

        legenAction = QW.QWidgetAction(self.menu)
        legendGui = QW.QCheckBox('&Legend')
        legendGui.setChecked(True)
        legendGui.stateChanged.connect(lambda x: self.set_legend(x))
        legenAction.setDefaultWidget(legendGui)
        self.menu.addAction(legenAction)
        return self.menu

    def cursorAction(self, direction):
        angle = {'Vertical':90, 'Horizontal':0}[direction]
        #pwidget = gMapOfPlotWidgets[self.dockName]
        pwidget = plotItem
        vid = {'Vertical':0, 'Horizontal':1}[direction]
        vr = pwidget.getPlotItem().viewRange()
        #print(f'vid: {vid,vr[vid]}')
        pos = (vr[vid][1] + vr[vid][0])/2.
        pen = pg.mkPen(color='b', width=1, style=QtCore.Qt.DotLine)
        cursor = pg.InfiniteLine(pos=pos, pen=pen, movable=True, angle=angle
        , label=str(round(pos,3)))
        cursor.sigPositionChangeFinished.connect(\
        (partial(self.cursorPositionChanged,cursor)))
        self.cursors.add(cursor)
        pwidget.addItem(cursor)

    def cursorPositionChanged(self, cursor):
        pos = cursor.value()
        horizontal = cursor.angle == 0.
        #pwidget = gMapOfPlotWidgets[self.dockName]
        #viewRange = pwidget.getPlotItem().viewRange()[horizontal]
        viewRange = plotItem().viewRange()[horizontal]
        if pos > viewRange[1]:
            pwidget.removeItem(cursor)
            self.cursors.remove(cursor)
        else:
            cursor.label.setText(str(round(pos,3)))
            
    def set_label(self,side,labelGui):
        dock,label = self.dockName,str(labelGui.text())
        printv('changed_label '+side+': '+str((dock,label)))
        #gMapOfPlotWidgets[dock].setLabel(side,label, units='')
        plotItem.setLabel(side,label, units='')
        # it might be useful to return the prompt back:
        #labelGui.setText('LabelX' if side=='bottom' else 'LabelY')

    def set_legend(self, state):
        state = (state==QtCore.Qt.Checked)
        print(f'set_legend {state}')
        set_legend(self.dockName, state)

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

viewBox = CustomViewBox()
viewBox.setMouseMode(pg.ViewBox.RectMode)
plotItem = win.addPlot(viewBox=viewBox,#title="apstrim plotItem",
    axisItems={'bottom':DateAxis(orientation='bottom')})
plotItem.setDownsampling(auto=True)#, mode='subsample')
legend = pg.LegendItem((80,60), offset=(70,20))
legend.setParentItem(plotItem)

idx = 0
ts = timer()
nPoints = 0
#viewRect = plotItem.viewRect()
#xSize = int(viewRect.right() - viewRect.left())
legends = set()
curves = {}
for extracted in allExtracted:
  for key,ptv in list(extracted.items())[::-1]: #inverted map produces better color for first items
    idx += 1
    pen = (idx,len(extracted))
    par = ptv['par']
    timestamps = ptv['times']
    #No gain:timestamps = np.array(timestamps)
    #print(_croppedText(f'times: {timestamps}'))
    nTStamps = len(timestamps)
    y = ptv['values']

    # check if y is array of numbers
    if APScan.Verbosity >= 2:   printvv(f'y: {y}')
    if not np.issubdtype(y[0].dtype, np.number):
        msg = f'PV[{key}] is not array of numbers dtype:{y[0].dtype}'
        print(f'WARNING: {msg}')
        #raise ValueError(msg)
        y = [float(i) for i in y]

    #y = np.array(y)
    #No gain:print(_croppedText(f'values: {y}'))

    # expand X, take care if Y is list of lists
    x = []
    spread = 0
    for i,tstamp in enumerate(timestamps):
        try: ly = len(y[i])
        except: ly = 1
        try:	spread = (timestamps[i+1] - tstamp)/2
        except: pass
        x.append(np.linspace(tstamp, tstamp+spread, ly))
    x = np.array(x).flatten()
    y = np.array(y).flatten()
    nn = len(x)
    print(f"Graph[{key}]: {par}, {nTStamps} tstamps, {nn} points")
    
    if nTStamps < 2:
        continue
    nPoints += nn
    #print(f'nn/xSize: {nn/xSize, nn,xSize}')
    try:
        #if pargs.plot =='fast' or nTStamps/xSize > 100:
        if nn > 500: #/xSize > 500:                
            # plotting of only lines
            p = plotItem.plot(x, y, pen=pen)
        else:
            # plotting with symbols is 10 times slower
            p = plotItem.plot(x, y, pen=pen
            ,symbol='+', symbolSize=5, symbolPen=pen)
        curves[par] = p
        legendText = str(key)+' '+par
        if legendText not in legends:
            legends.add(legendText)
            legend.addItem(p, legendText)
    except Exception as e:
        print(f'WARNING: plotting is not supported for item {key}: {e}')
print(f'Plotting time of {nPoints} points: {round(timer()-ts,3)} s')

if Cursors:
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
