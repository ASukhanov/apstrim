"""Plot data from the aplog-generated files."""
__version__ = 'v3.0.0 2023-09-24'#
#TODO: data acquisition stops when section is dumped to disk. Is writing really buffered?
#TODO: Dataset option does not work

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
def printv(msg):
    if APScan.Verbosity >= 1:
        print(f'DBG_view: {msg}')
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
parser.add_argument('-v', '--verbose', nargs='*', help=\
'Show more log messages, (-vv: show even more)')
parser.add_argument('files', nargs='*', default=['apstrim.aps'], help=\
'Input files, Unix style pathname pattern expansion allowed e.g: *.aps')
pargs = parser.parse_args()
#print(f'files: {pargs.files}')

#if pargs.plot is not None:
#    pargs.plot = 'fast' if len(pargs.plot) == 0 else 'symbols'

if pargs.verbose is not None:
    APScan.Verbosity = 1 if len(pargs.verbose) == 0\
    else len(pargs.verbose[0]) + 1
#print(f'Verbosity: {APScan.Verbosity}')

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

class Dataset():
    ''' dataset storage, keeps everything what is necessary to plot the curve.
    '''
    def __init__(self,name,paramAndCount):
        self.name = name
        self.adoPars = paramAndCount # list of max 2 of (adoPar,count)
        self.plotItem = None # plotting object PlotCurveItem
        self.pen = None # current pen
        self.width = 1 # pen width
        self.timestamp = 0 # latest timestamp
        self.timestampReported = 0 # time of the last title update
        self.plotWidget = None
        
        # plotting options, described in 
        # http://www.pyqtgraph.org/documentation/graphicsItems/plotdataitem.html#pyqtgraph.PlotDataItem
        self.connect = None
        self.shadowPen = None
        self.fillLevel = None
        self.fillBrush = None
        self.stepMode = None
        self.symbol = None
        self.symbolPen = None
        self.symbolBrush = None
        self.symbolSize = None
        self.pxMode = None

        # ``````````````````` Add plotItem ``````````````````````````````````````
        dock = name.split('.')[0]
        printv('plotItem for: '+str([s for s in self.adoPars])+', name:'+str(dock))
        ScrolLength = 10
        self.data = [np.empty(ScrolLength),np.empty(ScrolLength)]# [X,U] data storage
        self.dataPtr = 0
        count = self.adoPars[0][1] #
        print(f'adoPars,count: {self.adoPars,count}')

        # create plotItem with proper pen
        lineNumber = 0
        try: lineNumber = int(name.split('.')[1])
        except: pass
        isCorrelationPlot = len(self.adoPars) == 2
        self.pen = pg.mkPen(lineNumber)                
        if self.adoPars[0][0] == '':
            printv('no dataset - no plotItem')
        else:
            self.plotItem = pg.PlotDataItem(name=name, pen=self.pen)
            #self.plotItem = pg.PlotCurveItem(name=name, pen=self.pen)
        
        # assign the plotwidget if it exist, if not, create new dock and widget
        if dock in gMapOfPlotWidgets:
            self.plotWidget = gMapOfPlotWidgets[dock]
        else:
            viewBox = CustomViewBox(name=dock)             
            viewBox.setMouseMode(viewBox.RectMode)
            printv('adding plotwidget:'+str(dock))
            #title = self.adoPars[0][0]
            title = None
            if count == 1 and not isCorrelationPlot:
                self.plotWidget = pg.PlotWidget(title=title, viewBox=viewBox,
                  axisItems={'bottom':DateAxis(orientation='bottom')})
            else: 
                self.plotWidget = pg.PlotWidget(title=title, viewBox=viewBox)
            #self.plotWidget.showGrid(True,True)
            gMapOfPlotWidgets[dock] = self.plotWidget
            gMapOfDocks[dock].addWidget(self.plotWidget)
            if isCorrelationPlot:                        
                self.plotWidget.setLabel('bottom',self.pvNames[1][0])
            elif count == 1:
                self.plotWidget.setLabel('bottom','time', units='date', unitPrefix='')
            else:
                self.plotWidget.setLabel('bottom',gScaleUnits[X][Units])

        rangeMap = {X: (pargs.xrange, self.plotWidget.setXRange),
                    Y: (pargs.yrange, self.plotWidget.setYRange)}
        for axis,v in rangeMap.items():
            r,func = v
            if r is None:
                continue
            r = [float(i) for i in v[0].split(':')]
            func(*r)

        if self.plotItem: 
            self.plotWidget.addItem(self.plotItem)
        self.timestamp = 0.
    
    def remove(name):
        printv('MapOfDatasets.remove '+name)
        dataset = MapOfDatasets.dtsDict[name]
        dataset.plotWidget.removeItem(dataset.plotItem)
        del MapOfDatasets.dtsDict[dataset.name]

class MapOfDatasets():
    '''Global dictionary of Datasets, provides safe methods to add and remove 
    the datasets '''
    dtsDict = {}
    
    def add(name:str, pvNames:str):
        '''add new datasets, the pvNames is the space delimited string of items.
        An item is name of the PV or comma-separated string of sevral PVs
        (for correlation plots)'''
        if name in MapOfDatasets.dtsDict:
            printv('Need to remove '+name)
            MapOfDatasets.remove(name)
        printv('MapOfDatasets.add '+str((name, pvNames)))
        for i, token in enumerate(pvNames.split()):
            dname = f'{name}.{i}'
            pnameAndCount = [];
            alist = token.split(',')
            alist = alist[:2] # we cannot handle more than 2 curves in correlation plot
            if len(alist) == 0:
                MapOfDatasets.dtsDict[dname] = Dataset(dname,[('',0)])
            else:
                alist.reverse()
                for pvName in alist:
                    newName = pvName
                    try:    count = len(val)
                    except: count = 1
                    pnameAndCount.append((newName,count))
                #printv('adding '+str(pnameAndCount)+' to datasets['+dname+']')
                MapOfDatasets.dtsDict[dname] = Dataset(dname,pnameAndCount)
        printv(f'MapOfDatasets: {MapOfDatasets}')
        return 0
    
    def remove(name):
        printv('MapOfDatasets.remove '+name)
        dataset = MapOfDatasets.dtsDict[name]
        dataset.plotWidget.removeItem(dataset.plotItem)
        del MapOfDatasets.dtsDict[dataset.name]

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

        # reset zoom
        #resetzoom = self.menu.addAction("&Reset Zoom")
        #resetzoom.triggered.connect(lambda: self.autoRange())

        # Datasets options dialog
        setDatasets = self.menu.addAction('Datasets &Options')
        setDatasets.triggered.connect(self.changed_datasetOptions)

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

    def changed_datasetOptions(self):
        '''Dialog Plotting Options'''
        dlg = QW.QDialog()
        dlg.setWindowTitle("Dataset plotting config")
        dlg.setWindowModality(QtCore.Qt.ApplicationModal)
        dlgSize = 500,200
        dlg.setMinimumSize(*dlgSize)
        rowCount,columnCount = 0,6
        tbl = QW.QTableWidget(rowCount, columnCount, dlg)
        tbl.setHorizontalHeaderLabels(['Dataset','Color','Width','Symbol','Size','Color'])
        for column,width in ((1,30),(3,50),(5,30)): # change column widths
            tbl.setColumnWidth(column, width)
        tbl.setShowGrid(False)
        tbl.setSizeAdjustPolicy(
            QW.QAbstractScrollArea.AdjustToContents)
        tbl.resize(*dlgSize)

        #listOfItems = gMapOfPlotWidgets[self.dockName].getPlotItem().listDataItems()
        for row,curveName in enumerate(curves):
            printv(f'row: {row}')
            tbl.insertRow(row)
            #curveName = dataitem.name()
            printv(f'curveName: {curveName}')
            #dataset = MapOfDatasets.dtsDict[curveName]
            #adoparName = dataset.adoPars[0][0]
            #printv(f'dataset:{adoparName}')
            #item = QW.QTableWidgetItem(adoparName.rsplit(':',1)[1])
            item = QW.QTableWidgetItem(curveName)
            #DNW#item.setTextAlignment(QtCore.Qt.AlignRight)
            tbl.setItem(row, 0, item)

            # color button for line
            colorButton = pg.ColorButton(color=MapOfDatasets.dtsDict[curveName].pen.color())
            colorButton.setObjectName(curveName)
            colorButton.sigColorChanging.connect(lambda x:
              change_plotOption(str(self.sender().objectName()),color=x.color()))
            tbl.setCellWidget(row, 1, colorButton)

            # slider for changing the line width
            widthSlider = QW.QSlider()
            widthSlider.setObjectName(curveName)
            widthSlider.setOrientation(QtCore.Qt.Horizontal)
            widthSlider.setMaximum(10)
            widthSlider.setValue(1)
            widthSlider.valueChanged.connect(lambda x:
              change_plotOption(str(self.sender().objectName()),width=x))
            tbl.setCellWidget(row, 2, widthSlider)
            
            # symbol, selected from a comboBox
            self.symbol = QW.QComboBox() # TODO: why self?
            for symbol in ' ostd+x': self.symbol.addItem(symbol)
            self.symbol.setObjectName(curveName)
            self.symbol.currentIndexChanged.connect(self.set_symbol)
            tbl.setCellWidget(row, 3, self.symbol)

            # slider for changing the line width
            symbolSizeSlider = QW.QSlider()
            symbolSizeSlider.setObjectName(curveName)
            symbolSizeSlider.setOrientation(QtCore.Qt.Horizontal)
            symbolSizeSlider.setMaximum(10)
            symbolSizeSlider.setValue(1)
            symbolSizeSlider.valueChanged.connect(lambda x:
              change_plotOption(str(self.sender().objectName()),symbolSize=x))
            tbl.setCellWidget(row, 4, symbolSizeSlider)

            # color button for symbol
            symbolColorButton = pg.ColorButton(color=MapOfDatasets.dtsDict[curveName].pen.color())
            symbolColorButton.setObjectName(curveName)
            symbolColorButton.sigColorChanging.connect(lambda x:
              change_plotOption(str(self.sender().objectName()),scolor=x.color()))
            tbl.setCellWidget(row, 5,symbolColorButton)
        dlg.exec_()

    def set_symbol(self, x):
        ''' Change symbol of the scatter plot. The size and color are taken
        from the curve setting'''
        dtsetName = str(self.sender().objectName())
        symbol = str(self.sender().itemText(x))
        printv('set_symbol for '+dtsetName+' to '+symbol)
        dataset = MapOfDatasets.dtsDict[dtsetName]
        if symbol != ' ':
            dataset.symbol = symbol
            if not dataset.symbolSize:
                dataset.symbolSize = 4 # default size
            if not dataset.symbolBrush:
                dataset.symbolBrush = dataset.pen.color() # symbol color = line color
        else:
            # no symbols - remove the scatter plot
            dataset.symbol = None
            pass
            
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
