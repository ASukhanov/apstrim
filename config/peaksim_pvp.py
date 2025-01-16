""" Configuration of apview for peaksim.aps
"""
configFormat='pvplot'

TITLE="PeakSimulator"
XLABEL = "Time (us)"
YLABEL = "V"
POINTS = 1000# data arrays will be rolled over after accumulating this number of points

dev='acnlin23;9710:dev1:'

DOCKS = [
  {
    'YMax':f'{dev}yMax',# without device()
    'YMin':f'{dev}yMin',#device({dev}yMin)
    #'YvsX':f'{dev}y',#f'de{dev}y)'),
    #'Rps':f'{dev}rps',
    #'Y[10]':f'device({dev}y[500])',
  },
  {
    'YvsX':f'{dev}y',#f'de{dev}y)'),
    'Rps':f'{dev}rps',
    #'YMin':f'{dev}yMin',#device({dev}yMin)
  }
]

