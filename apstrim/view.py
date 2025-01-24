"""Plot data from the apstrim-generated files."""
__version__ = 'v4.0.3 2025-01-23'# handling case when Y is list of 1-element arrays. Handle setYRange if defined in config. 
#TODO: Cellname did not change on plot after changing it in dataset options
#TODO: data acquisition stops when section is dumped to disk. Is writing really buffered?
#TODO: interactive works only for one file
#TODO: Recall/Save viewing configuration to a file at /operations/app_store/apview/config

import sys, time, argparse, os
timer = time.perf_counter
from importlib import import_module
from functools import partial
from collections import deque
import numpy as np
from qtpy import QtWidgets as QW, QtCore, QtGui

import pyqtgraph as pg
from pyqtgraph.graphicsItems.ViewBox.ViewBoxMenu import ViewBoxMenu
from pyqtgraph.dockarea import Dock
from pyqtgraph.dockarea.DockArea import DockArea
pg.setConfigOption('background', 'w')
pg.setConfigOption('foreground', 'k')

from apstrim.scan import APScan, __version__ as scanVersion
from apstrim import helpTxtView

#``````````````````Constants
X,Y = 0,1
Nano = 1e-9
Cursors = False
legalHeaders = ['Directory', 'Abstract', 'Index']
SymbolCodes = ' ostd+x'
TxtColor = (0,128,128)# color of the plot texts
DefaultSymbolSize = 5
XRangeTooLarge = 500000# Generates warning when symbols enabled.
#``````````````````Module properties```````````````````````````````````````````
qWin = None

class C():
    curves = {}
    config = None
    dockArea = None
    dockList = []
    legends = {}

class CurveProperties():
    def __init__(self, cell:str, dock:int, enabled:bool, color:list, width:int,
                symbol:str, symbolSize):
        self.cell = cell
        self.enabled = enabled
        self.color = color
        self.width = width
        self.symbol = symbol
        self.symbolSize = symbolSize
        self.dock = dock
        self.plotDataItem = None
    def __repr__(self):
        return f'(cell:{self.cell}, dock:{self.dock}, enabled:{self.enabled}, color:{self.color}, width:{self.width}, symbol:{self.symbol}, swidth:{self.symbolSize})'

#``````````````````Helper methods
def printTime():    return time.strftime("%m%d:%H%M%S")
def printi(msg):    print((f'inf_view@{printTime()}: '+msg))
def printv(msg):
    if APScan.Verbosity >= 1:
        print(f'DBG_view1: {msg}')
def printvv(msg):
    if APScan.Verbosity >= 2:
        print(f'DBG_view2: {msg}')
def printw(msg): print((f'WAR_view@{printTime()}: '+msg))
def printe(msg): print((f'ERR_view@{printTime()}: '+msg))
def _croppedText(txt, limit=400):
    if len(txt) > limit:
        txt = txt[:limit]+'...'
    return txt
def listOfPargsItems(txt):
    items = [] if txt == 'all'\
      else [int(i) for i in txt.split(',')]
    return items

#``````````````````Below is QApplication-related code`````````````````````````
qApp = pg.mkQApp()
qApp.setStyle('Fusion')

C.dockArea = DockArea()
class MainWindow(QW.QMainWindow):
    def closeEvent(self,event):
        print('Closing all windows')
        try:    C.statisticsWindow.close()
        except: pass
        try:    C.helpWin.close()
        except: pass
        event.accept()

#``````````````````Custom ViewBox`````````````````````````````````````````````
class CustomViewBox(pg.ViewBox):
    ''' defines actions, activated on the right mouse click in the dock
    '''
    def __init__(self, dockNum:int):
        self.dockNum = dockNum

        # call the init method of the parent class
        super(CustomViewBox, self).__init__()
        # the above is equivalent to:#pg.ViewBox.__init__(self, **kwds)
        self.setMouseMode(pg.ViewBox.RectMode)

        self.menu = None
        if Cursors:
            self.cursors = set()
        self.unzooming = False
        self.rangestack = deque([],10) #stack of 10 of view ranges

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
        printv(f'getContextMenus for dock {self.dockNum}')
        self.menu = ViewBoxMenu(self)
        self.menu.setTitle(f'{self.dockNum}: options..')

        if Cursors:
            cursorMenu = self.menu.addMenu('Add Cursor')
            for cursor in ['Vertical','Horizontal']:
                action = cursorMenu.addAction(cursor)
                action.triggered.connect(partial(self.cursorAction,cursor))
        
        # Add Curve
        #action = self.menu.addAction('Add curve')
        #action.triggered.connect(self.action_add_curve)

        # unzoom last
        unzoom = self.menu.addAction("&UnZoom")
        unzoom.triggered.connect(lambda: self.unzoom())

        # Datasets options dialog
        setDatasets = self.menu.addAction('Datasets Options')
        setDatasets.triggered.connect(change_datasetOptions)

        _statistics = self.menu.addAction('Show &Means,sigmas')
        _statistics.triggered.connect(shortcutStatistics)

        #_yProjection = self.menu.addAction('Show &YProjection')
        #_yProjection.triggered.connect(self.show_yProjection)

        # popup help
        phelp = self.menu.addAction("&help")
        phelp.triggered.connect(shortcutHelp)

        # Labels
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
        backgroundGui = QW.QCheckBox('Black background')
        backgroundGui.stateChanged.connect(
          lambda x: self.setBackgroundColor(\
          'k' if x == QtCore.Qt.Checked else 'w'))
        backgroundAction.setDefaultWidget(backgroundGui)
        self.menu.addAction(backgroundAction)

        legenAction = QW.QWidgetAction(self.menu)
        legendGui = QW.QCheckBox('Legend')
        legendGui.setChecked(True)
        legendGui.stateChanged.connect(lambda x: self.set_legend(x))
        legenAction.setDefaultWidget(legendGui)
        self.menu.addAction(legenAction)
        return self.menu

    def cursorAction(self, direction):
        angle = {'Vertical':90, 'Horizontal':0}[direction]
        plotWidget = C.dockList[cc.dock]['dock'].widgets[0]
        vid = {'Vertical':0, 'Horizontal':1}[direction]
        vr = plotWidget.getPlotItem().viewRange()
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
        plotWidget = C.dockList[cc.dock]['dock'].widgets[0]
        viewRange = plotWidget.getPlotItem().viewRange()[horizontal]
        if pos > viewRange[1]:
            pwidget.removeItem(cursor)
            self.cursors.remove(cursor)
        else:
            cursor.label.setText(str(round(pos,3)))
            
    def set_label(self,side,labelGui):
        dock,label = self.dockNum,str(labelGui.text())
        #print('Changed_label '+side+': '+str((dock,label)))
        plotWidget = C.dockList[self.dockNum]['dock'].widgets[0]
        plotWidget.setLabel(side,label, units='')
        # it might be useful to return the prompt back:
        #labelGui.setText('LabelX' if side=='bottom' else 'LabelY')

    def set_legend(self, state):
        state = (state==QtCore.Qt.Checked)
        set_legend(self.dockNum, state)

    def action_add_curve(self):
        pass

    def unzoom(self):
        try:
            if not self.unzooming:
                self.rangestack.pop()
            self.unzooming = True
            viewRange = self.rangestack.pop()
        except IndexError:
            #printw(f'nothing to unzoom')
            self.enableAutoRange()
            return
        #print(f'<rangestack {len(self.rangestack)}')
        self.setRange(xRange=viewRange[X], yRange=viewRange[Y], padding=None,
            update=True, disableAutoRange=True)

def set_legend(dockNum:int, state:bool):
    if state: # legend enabled
        #print(f'add legends to dock{dockNum}')
        plotWidget = C.dockList[dockNum]['dock'].widgets[0]
        listOfItems = plotWidget.getPlotItem().listDataItems()
        l = pg.LegendItem((100,60), offset=(70,30), verSpacing=-10,
            labelTextColor=TxtColor)  # args are (size, offset)
        l.setParentItem(plotWidget.graphicsItem())
        C.legends[dockNum] = l
        for item in listOfItems:
            iname = item.name()
            l.addItem(item, iname)
    else: # legend disabled
        #print(f'remove legend from dock{dockNum}')
        try:    
            C.legends[dockNum].scene().removeItem(C.legends[dockNum])
            del C.legends[dockNum]
        except Exception as e:
            printe(f'failed to remove legend {dockNum}: {e}')
#,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,
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

#``````````Shorthcut handlers
def shortcutHelp():
    #print(f'>shortcutHelp: {helpTxtView.txt}')
    C.helpWin = PopupHelp()
    C.helpWin.label.setText(helpTxtView.txt)
    C.helpWin.show()

    for pvName,cc in C.curves.items():
        data = cc.plotDataItem.getData()

def shortcutStatistics():
    sl = get_statistics()
    try:    statWindow = C.statisticsWindow
    except:
        header = ['Parameter','XMin','XMax','Mean','StDev','Peak2Peak']
        C.statisticsWindow = TableWindow(sl, header)
        statWindow = C.statisticsWindow
    statWindow.model.refresh_data(sl)
    statWindow.show()

def shortcutUnzoom():
    for dockNum in range(len(C.dockList)):
        #vb = PVPlot.mapOfPlotWidgets[dockNum].getPlotItem().getViewBox()
        vb = C.dockList[cc.dock]['dock'].widgets[0].getViewBox()
        vb.unzoom()
        
def xRange(plotDataItem):
    # return left and right indexes of visual range of X array of plotDataItem
    vr = plotDataItem.getViewBox().viewRange()
    x,y = plotDataItem.getData()
    ileft = np.argmax(x>vr[X][0])
    iright = np.argmax(x>vr[X][1])
    if iright == 0: iright = len(x)-1
    return ileft,iright

def get_statistics():
    statList = []
    for pvName,cc in C.curves.items():
        if not cc.enabled:
            continue
        plotDataItem = cc.plotDataItem
        ileft,iright = xRange(plotDataItem)
        x,y = plotDataItem.getData()
        y = np.array(y[ileft:iright])
        numbers = ileft, iright, y.mean(), y.std(), (y.max() - y.min())
        ntxt = [f'{i:.6g}' for i in numbers]
        statList.append([pvName, *ntxt])
    return statList

class PopupHelp(QW.QWidget): 
    """ This "window" is a QWidget. If it has no parent, it
    will appear as a free-floating window as we want.
    Note: The created window will not be closed on app exit.
    To make it happen, the MainWindow should call close this widget in its closeEvent() 
    """
    def __init__(self):
        super().__init__()
        qr = qWin.geometry()
        self.setGeometry(QtCore.QRect(qr.x(), qr.y(), 0, 0))
        self.setWindowTitle('PVPlot short help')
        layout = QW.QVBoxLayout()
        self.label = QW.QLabel()
        self.label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        layout.addWidget(self.label)
        self.setLayout(layout)

class TableModel(QtCore.QAbstractTableModel):
    def __init__(self, data, headers):
        super(TableModel, self).__init__()
        self._data = data
        self.headers = headers

    def headerData(self, section: int, orientation: QtCore.Qt.Orientation, role=QtCore.Qt.DisplayRole):
        if role == QtCore.Qt.DisplayRole and orientation == QtCore.Qt.Horizontal:
            try:    r = self.headers[section]
            except: r = f's{section+1}'
            return r

    def data(self, index, role):
        if role == QtCore.Qt.DisplayRole:
            # See below for the nested-list data structure.
            # .row() indexes into the outer list,
            # .column() indexes into the sub-list
            return self._data[index.row()][index.column()]

    def rowCount(self, parent=QtCore.QModelIndex()):
        # The length of the outer list.
        return len(self._data)

    def columnCount(self, parent=QtCore.QModelIndex()):
        # The following takes the first sub-list, and returns
        # the length (only works if all rows are an equal length)
        return len(self._data[0])

    def refresh_data(self, data):
        self._data = data
        #print(f'>refresh_data: {self._data}')
        topLeft = self.createIndex(0, 0)
        bottomRight = self.createIndex(self.rowCount(), self.columnCount())
        self.dataChanged.emit(topLeft, bottomRight)

class TableWindow(QW.QWidget):
    """
    This "window" is a QWidget. If it has no parent, it
    will appear as a free-floating window.
    """
    def __init__(self, data, headers=[]):
        super().__init__()
        self.setWindowTitle('Statistics')
        layout = QW.QVBoxLayout()
        self.table = QW.QTableView()
        self.model = TableModel(data, headers)
        self.table.setModel(self.model)
        vh = self.table.verticalHeader()
        vh.setDefaultSectionSize(20)
        #vh.sectionResizeMode(QW.QHeaderView.Fixed)
        hh = self.table.horizontalHeader()       
        #DNW#hh.setSectionResizeMode(QW.QHeaderView.ResizeToContents)
        for column in range(len(headers)):
            hh.setSectionResizeMode(column, QW.QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.table)
        self.setLayout(layout)

        qr = qWin.geometry()
        self.move(qr.x(), qr.y())
        self.table.setShowGrid(False)
        self.table.setSizeAdjustPolicy(
            QW.QAbstractScrollArea.AdjustToContents)

#``````````````````Parse Arguments````````````````````````````````````````````
parser = argparse.ArgumentParser(description=__doc__
    ,formatter_class=argparse.ArgumentDefaultsHelpFormatter
    ,epilog=f'aplog scan : {scanVersion},  view: {__version__}')
parser.add_argument('-a','--apstrim', default='/operations/app_store/apstrim',
  help='Directory of logbook files')
parser.add_argument('-c','--configDir',default='/operations/app_store/apview',
  help='Configuration directory')
parser.add_argument('-f', '--file', help=
  'Configuration file')
parser.add_argument('-H', '--header', nargs='?', default='', choices=legalHeaders,help=
'Show all headers (-H) or selected header, plotting disabled')
parser.add_argument('-i', '--items', help=
('Items to plot. Legal values: "all" or '
'string of comma-separated keys of the parameter map e.g. "0,1,3,5,7,..."'))
parser.add_argument('-I', '--interactive', action='store_true', help=
'Interactive selection of items for plotting')
parser.add_argument('-p', '--plot', action='store_true', help=
'Plot data using pyqtgraph')
parser.add_argument('-s', '--startTime', help=
'Start time, fomat: YYMMDD_HHMMSS, e.g. 210720_001725')
parser.add_argument('-t', '--timeInterval', type=float, default=9e9, help=
'Time span in seconds')
parser.add_argument('-v', '--verbose', action='count', default=0, help=
'Show more log messages (-vv: show even more).')
parser.add_argument('files', nargs='*', help=
'Input files, Unix style pathname pattern expansion allowed e.g: *.aps')
pargs = parser.parse_args()
#print(f'pargs: {pargs}')

APScan.Verbosity = pargs.verbose

#``````````````arrange keyboard interrupt to kill the program from terminal.
import signal
signal.signal(signal.SIGINT, signal.SIG_DFL)

allExtracted = []

#``````````process configuration file
if pargs.file is not None:
    # parse_input_parameters
    sys.path.append(pargs.configDir)
    fn = pargs.file
    print(f'Config file: {pargs.configDir}/{fn}.py')
    try:
        ConfigModule = import_module(fn)
        configFormat = ConfigModule.configFormat
    except ModuleNotFoundError as e:
        printe(f'Trying to import {pargs.configDir}/{fn}: {e}')
        sys.exit(0)
    C.config = ConfigModule
#`````````````````````````````````````````````````````````````````````````````
def change_datasetOptions():
    """Dialog Plotting Options"""
    dlg = QW.QDialog()
    dlg.setWindowTitle(f"PVs in {pargs.files[0]}")
    dlg.setWindowModality(QtCore.Qt.ApplicationModal)
    rowCount,columnCount = 0,8
    tbl = QW.QTableWidget(rowCount, columnCount, dlg)
    tbl.setHorizontalHeaderLabels(
             ['','Cell','Dock','PV','Color','Width','Symbol','Size',''])
    widths = (10, 50,    10,    100, 25,     80,     35,      80,   80)
    for column,width in enumerate(widths):
        tbl.setColumnWidth(column, width)
    tbl.setShowGrid(False)
    tbl.setSizeAdjustPolicy(
        QW.QAbstractScrollArea.AdjustToContents)

    for row,items, in enumerate(C.curves.items()):
        pvName,curveProp = items
        curveName = curveProp.cell
        tbl.insertRow(row)
        printv(f'curveName:{curveName}')

        # Checkbox
        col = 0
        cbox = QW.QCheckBox()
        cbox.setToolTip('Enable/Disable plotting of this curve')
        cbox.setChecked(curveProp.enabled)
        cbox.stateChanged.connect(partial(change_enable, pvName))
        #cbox.setObjectName(curveName)
        tbl.setCellWidget(row, col, cbox)

        # Cell
        col+=1
        item = QW.QLineEdit(curveName)
        item.setToolTip('Curve name, you can change it')
        item.textEdited.connect(partial(change_cell, pvName))
        tbl.setCellWidget(row, col, item)

        # Dock
        col+=1
        item = QW.QTableWidgetItem(str(curveProp.dock))
        item.setToolTip('Dock number')
        #DNW#item.setTextAlignment(QtCore.Qt.AlignLeft)
        tbl.setItem(row, col, QW.QTableWidgetItem(item))

        # PV name
        col+=1
        printv(f'pv:{pvName}')
        txt = pvName[-24:]
        txt = txt[:12]+'\n'+txt[12:]
        #txt = pvName
        item = QW.QTableWidgetItem(txt)
        #item.setTextAlignment(QtCore.Qt.AlignCenter)
        #DNW#item.setWordWrap(True)
        item.setToolTip('Name of the logged parameter')
        tbl.setItem(row, col, QW.QTableWidgetItem(item))

        # Color button for line
        col+=1
        colorButton = pg.ColorButton(color=curveProp.color)
        #colorButton.setObjectName(curveName)
        colorButton.sigColorChanging.connect(partial(change_color, pvName))
        tbl.setCellWidget(row, col, colorButton)

        # Slider for changing the line width
        col+=1
        widthSlider = QW.QSlider()
        #widthSlider.setObjectName(curveName)
        widthSlider.setOrientation(QtCore.Qt.Horizontal)
        widthSlider.setMaximum(10)
        widthSlider.setValue(curveProp.width)
        widthSlider.valueChanged.connect(partial(change_width, pvName))
        tbl.setCellWidget(row, col, widthSlider)

        # Symbol, selected from a comboBox
        col+=1
        combo = QW.QComboBox()
        for symbol in SymbolCodes:
            combo.addItem(symbol)
        try:    index = SymbolCodes.index(curveProp.symbol)
        except: index = 0
        combo.setCurrentIndex(index)
        #combo.setObjectName(curveName)
        combo.currentIndexChanged.connect(partial(change_symbol, pvName))
        tbl.setCellWidget(row, col, combo)

        # Slider for changing symbol size
        col+=1
        symbolSizeSlider = QW.QSlider()
        #symbolSizeSlider.setObjectName(curveName)
        symbolSizeSlider.setOrientation(QtCore.Qt.Horizontal)
        symbolSizeSlider.setMaximum(10)
        symbolSizeSlider.setValue(curveProp.symbolSize)
        symbolSizeSlider.valueChanged.connect(partial(change_symbolSize, pvName))
        tbl.setCellWidget(row, col, symbolSizeSlider)

    #dlg.add(pb)
    #dlg.resize(tbl.width(),tbl.height())
    dy = 24
    dialogWidth = tbl.horizontalHeader().length() + dy
    dialogHeight = tbl.verticalHeader().length()   + dy

    bb = QW.QDialogButtonBox(QW.QDialogButtonBox.Ok, parent=dlg)# | QW.QDialogButtonBox.Save, parent=dlg)
    bb.accepted.connect(dlg.accept)
    bb.move(150, dialogHeight)
    dialogHeight += 32
    dlg.setMinimumSize(dialogWidth, dialogHeight)
    dlg.exec_()

#def clicked_Save():
#    print('Save clicked')

def change_cell(pvName, txt):
    C.curves[pvName].cell = txt

def change_enable(pvName, state):
    C.curves[pvName].enabled = state
    if len(C.dockList) == 0:# This is interactive case
        return
    cc = C.curves[pvName]
    plotWidget = C.dockList[cc.dock]['dock'].widgets[0]
    plotDataItem = C.curves[pvName].plotDataItem
    if plotDataItem is None:
        return
    if state == False:
        plotWidget.removeItem(plotDataItem)
    else:
        plotWidget.addItem(plotDataItem)

def change_color(pvName, color):
    clist = list(color.color().getRgb())
    cc = C.curves[pvName]
    cc.color = clist
    if cc.plotDataItem is not None:
        cc.plotDataItem.setPen(pg.mkPen(cc.color, width=cc.width))
        cc.plotDataItem.setSymbolBrush(cc.color)
        cc.plotDataItem.setSymbolPen(cc.color)

def change_width(pvName, v):
    cc = C.curves[pvName]
    cc.width = v
    if cc.plotDataItem is not None:
        if v == 0:
            cc.plotDataItem.setPen(pg.mkPen(None))
        else:
            cc.plotDataItem.setPen(pg.mkPen(cc.color, width=cc.width))

def change_symbol(pvName, v):
    cc = C.curves[pvName]
    if cc.plotDataItem is not None:
        x,y = cc.plotDataItem.getData()
        if len(x) > XRangeTooLarge:
            mb = QW.QMessageBox()
            mb.setIcon(QW.QMessageBox.Warning)
            mb.setText(f'Using Symbols in large plot\n will slow down the plotting')
            mb.setWindowTitle("Symbols in large array")
            mb.setStandardButtons(QW.QMessageBox.Ok | QW.QMessageBox.Cancel)
            returnValue = mb.exec()
            if not returnValue == QW.QMessageBox.Ok:
                cc.symbol = ' '
                cc.plotDataItem.setSymbol(None)
                return
        cc.symbol = SymbolCodes[v]
        symbol = None if cc.symbol == ' ' else cc.symbol
        #if not isXRangeTooLarge(cc.plotDataItem):
        cc.plotDataItem.setSymbol(symbol)

def change_symbolSize(pvName, v):
    cc = C.curves[pvName]
    cc.symbolSize = v
    if cc.plotDataItem is not None:
        #if not isXRangeTooLarge(cc.plotDataItem):
        cc.plotDataItem.setSymbolSize(cc.symbolSize)

def pathName(fileName):
    r = fileName
    if not '/' in r:
        r = f'{pargs.apstrim}/{fileName}'
    return(r)
#,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,
# Select logbooks
if len(pargs.files) == 0:
    def select_file_interactively(title='Select an *.aps file'):
        directory = pargs.apstrim
        #print(f'select_file_interactively:{directory}')
        dialog = QW.QFileDialog()
        ffilter = 'apstrim (*.aps)'
        r = dialog.getOpenFileName( None, title, directory, ffilter)
        fname = r[0]
        return fname
    fname = select_file_interactively()
    if fname == '':
        print('No logbook selected')
        sys.exit()
    print(f'Logbook selected: {fname}')
    pargs.files = [fname]

# Fill C.curves with all items
printv(f'Scanning first file in sequence: {pathName(pargs.files[0])}')
header0 = APScan(pathName(pargs.files[0])).get_headers()
items = header0['Index']
printv(f'Items in first logobook: {items}')

def hsvToRgb(idx, maxColors, offset=2/3):
    # stepping throgh hsv color space, starting from offset (2/3 is blue).
    return list(pg.hsvColor((offset+idx/maxColors)%1.).getRgb())
for i,item in enumerate(items):
    cell = item.rsplit(':',1)[1]
    lcolor = hsvToRgb(i, len(items))
    C.curves[item] = CurveProperties(cell, 0, False, lcolor, 1, None,
         DefaultSymbolSize)
#printv(f'curves: {C.curves.keys()}')

def register_dock(dockNum:int):
    dockName = str(dockNum)
    dock = Dock(dockName, size=(500,200), hideTitle=True)
    vb = CustomViewBox(dockNum)
    try:    vb.setYRange(C.config.YMINIMUM, C.config.YMAXIMUM)
    except: pass
    #Exception as e:
    #    printw(f'in setYRange: {e}')        
    ax = {'bottom':DateAxis(orientation='bottom')}
    plotWidget = pg.PlotWidget(title=None, name=dockName, viewBox=vb, axisItems=ax)#, plotItem=plotItem)
    dock.addWidget(plotWidget)
    C.dockList.append({'dock':dock, 'curves':[]})
    plotWidget = dock.widgets[0]
    if dockNum == 0:
        C.dockArea.addDock(dock, 'right', closable=True)
    else:
        C.dockArea.addDock(dock, 'top', C.dockList[-2]['dock'],
                        closable=True) #TODO:closable does not work
        plotWidget.setXLink('0')
    curveCount = 0
    return dock

# Configuration from command line
if pargs.items is not None:
    if pargs.plot:
        register_dock(0)
        items = listOfPargsItems(pargs.items)
        i = -1
        for pvName,cc in C.curves.items():
            i += 1
            if i in items or len(items) == 0:
                cc.enabled = True
                C.dockList[0]['curves'].append(pvName)
else:
    # Configuration from file
    if C.config is not None:
        for dockNum,curveMap in enumerate(C.config.DOCKS):
            #print(f'add_curves to dock{dockNum}, {curveMap}')
            #print(f'dw: {dock.widgets}')
            register_dock(dockNum)
            maxColors = len(curveMap)
            i = 0
            for cell,pvName in curveMap.items():
                #print(f'color {i} of {pvName}') 
                lcolor = hsvToRgb(i, maxColors)
                printv(f'adding curve {pvName}{lcolor} as {cell} to dock {dockNum}')
                C.curves[pvName].dock = dockNum
                C.curves[pvName].enabled = True
                C.curves[pvName].color = lcolor
                C.dockList[dockNum]['curves'].append(pvName)
                i += 1
    # Interactive configuration
    elif pargs.interactive:
        change_datasetOptions()
        #print(f'C.curves: {C.curves.keys()}')
        register_dock(0)
        for pvName in C.curves:
            C.dockList[0]['curves'].append(pvName)

    # Update list of required items for scan in pargs.items
    s = ''
    for i,pvName in enumerate(C.curves):
        if C.curves[pvName].enabled:
            printv(f'Enabled: {C.curves[pvName].cell}')
            s += str(i)+','
    pargs.items = s[:-1]
    print(f'Index list of requested items from the apstrim: {pargs.items}')

printv(f'dockList: {C.dockList}')

# Process files headers
for fileName in pargs.files:
    apscan = APScan(pathName(fileName))
    print(f'Processing {fileName}, size: {round(apscan.logbookSize*1e-6,3)} MB')
    headers = apscan.get_headers()
    
    if pargs.header != '':
        if pargs.header is None: pargs.header = 'All'
        #pargs.header = pargs.header.capitalize()
        if pargs.header == 'All':
            pargs.header = legalHeaders
        else:
            pargs.header = [pargs.header]
        for header in pargs.header:
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

    if pargs.items == '':
        print('No items to scan')
        sys.exit()

    items = listOfPargsItems(pargs.items)
    print(f'Extracting items{items}, for {pargs.timeInterval} seconds, starting at {pargs.startTime}')

    # extract the items
    ts = timer()
    extracted = apscan.extract_objects(pargs.timeInterval, items
    , pargs.startTime)
    print(f'Total (reading + extraction) time: {round(timer()-ts,3)}')
    allExtracted.append(extracted)
    if APScan.Verbosity >= 2:
        printvv(_croppedText(f'allEextracted: {allExtracted}'))

if pargs.header != '':
    exit()
     
#````````````````````````````Plot objects`````````````````````````````````````
pg.setConfigOption('background', 'w')
pg.setConfigOption('foreground', 'k')

#,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,
#``````````````````Graphics Layout````````````````````````````````````````````
if len(C.dockList) > 0:
    #qWin = pg.GraphicsLayoutWidget()
    qWin = MainWindow()
    qWin.setCentralWidget(C.dockArea)
    qWin.resize(800,600)
    qWin.show()

    # Shortcuts
    shortcut = QW.QShortcut(QtGui.QKeySequence("Ctrl+H"), qWin)
    shortcut.activated.connect(shortcutHelp)
    shortcut = QW.QShortcut(QtGui.QKeySequence("Ctrl+M"), qWin)
    shortcut.activated.connect(shortcutStatistics)
    shortcut = QW.QShortcut(QtGui.QKeySequence("Ctrl+U"), qWin)
    shortcut.activated.connect(shortcutUnzoom)
    try:    winTitle = C.config.TITLE
    except:
        winTitle =\
            pargs.files[0] if len(pargs.files)==1 else pargs.files[0]+'...'
    qWin.setWindowTitle(f'Graphs[{len(extracted)}] of {winTitle}')

idx = 0
ts = timer()
nPoints = 0
#printi('Plotting')
for extracted in allExtracted:
    for key,ptv in extracted.items():
        lts = [timer()]
        par = ptv['par']
        pen = pg.mkPen(color=C.curves[par].color, width=C.curves[par].width)#, style=QtCore.Qt.DotLine)
        idx += 1
        timestamps = ptv['times']
        nTStamps = len(timestamps)
        y = ptv['values']
        if len(y) == 0:
            continue
        # check if y is array of numbers
        if APScan.Verbosity >= 2:   printvv(f'y: {y}')
        if not np.issubdtype(y[0].dtype, np.number):
            msg = f'PV[{key}] is not array of numbers dtype:{y[0].dtype}'
            print(f'WARNING: {msg}')
            #raise ValueError(msg)
            y = np.array([float(i) for i in y])
        x = []
        spread = 0
        try:
            ly = len(y[0])
        except: ly = 1
        if ly == 1:
            # y is 1D list
            x = np.array(timestamps)
            if isinstance(y[0],np.ndarray):
                y = np.array(y).flatten()
        else:
            # y is list of ndarrays. Expand X.
            for i,tstamp in enumerate(timestamps):
                ly = len(y[i])
                try:    spread = (timestamps[i+1] - tstamp)/2
                except: pass
                x.append(np.linspace(tstamp, tstamp+spread, ly))
            x = np.array(x).flatten()
            y = np.array(y).flatten()
        lts.append(timer())
        nn = len(x)
        if len(C.dockList) == 0:
            continue
        lts.append(timer())
        print(f"Graph[{key}]: {par}, {nTStamps} tstamps, {nn} points, dt={[round(i,3) for i in (lts[1]-lts[0], lts[2]-lts[1])]}")
        
        if nTStamps < 2:
            continue
        nPoints += nn
        cc = C.curves[par]
        plotWidget = C.dockList[cc.dock]['dock'].widgets[0]
        #print(f'pw {cc.cell}: {plotWidget}')
        symPen,symBrush = pen.color(), pen.color()
        sym = None if nn > XRangeTooLarge else cc.symbol
        #print(f'x,y of {par}: {len(x),type(x[0]),len(y),type(y[0])}')
        try:
            plotDataItem = pg.PlotDataItem(x, y, name=cc.cell,
                downsample=1, autoDownsample=False, downsampleMethod='peak',#3.6s plotting time, this is default
                #downsample=1, autoDownsample=True, downsampleMethod='peak',#6.0s plotting
                skipFiniteCheck=True,# no improvements
                pen=pen,symbol=sym, symbolPen=symPen, symbolBrush=symBrush)
            plotWidget.addItem(plotDataItem)
            cc.plotDataItem = plotDataItem
        except Exception as e:
            print(f'WARNING: plotting is not supported for item {key}: {e}')

    for dockNum in range(len(C.dockList)):
        set_legend(dockNum, True)
operation = 'Plotting' if len(C.dockList) > 0 else 'Scanning'
print(f'{operation} time of {nPoints} points: {round(timer()-ts,3)} s')

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

if len(C.dockList) > 0:
    qApp.exec_()
