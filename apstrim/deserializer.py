"""Test of an upstrim-generated file: deserialze and plot all its items"""
import sys, argparse
import numpy as np
import msgpack
import msgpack_numpy
msgpack_numpy.patch()

SecDateTime, SecParagraph = 0,1

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('file', nargs='?', default='upstrim.ups', help=\
'Input file, e.g: upstrim.ups')
pargs = parser.parse_args()

f = open(pargs.file,'rb')
book = msgpack.Unpacker(f)

def decompress(arg):
	return

nsec = 0
for section in book:
	#print(f'nsec: {nsec}')
	#if nsec > 100:  break
	nsec += 1
	if nsec == 1:# skip info section 
		print(f'file info: {section}')
		compression = section['compression']
		if compression != 'None':
			module = __import__(compression)
			decompress = module.decompress
		continue
	if nsec == 2:# section: parameters
		par2key = section['parameters']
		key2par = {value[0]:key for key,value in par2key.items()}
		print(f'parameter map: {key2par}')
		ykeys = list(key2par.keys())
		nkeys = len(ykeys)
		x,y = [],[]
		for i in range(nkeys):
			x.append([])
			y.append([])
		continue

	# data sections
	#print(f'dsec: {section}')
	try:
		if compression != 'None':
			decompressed = decompress(section)
			section = msgpack.unpackb(decompressed)
		sectionDatetime, paragraph = section
	except Exception as e:
		print(f'WARNING: wrong section {nsec}: {str(section)[:75]}...')
		continue
	for timestamp,parkeys in paragraph:
		for i,ykey in enumerate(ykeys):
			if ykey in parkeys:
				#print(f'ik: {i,ykey}, {parkeys}')
				x[i].append(timestamp)
				try:	
					v = parkeys[ykey][0]
				except:
					v = parkeys[ykey]
				y[i].append(v)
#print(f'xy: {list(zip(x[0],y[0]))}')

import pyqtgraph as pg
#from pyqtgraph.Qt import QtGui, QtCore
#app = pg.mkQApp('upstrim')
for i in range(len(ykeys)):
	try:
		pg.plot(x[i],y[i])#, pen=None, symbol='o')
	except Exception as e:
		print(f'WARNING: plotting is not supported for item {i}: {e}')
pg.mkQApp().exec_()
