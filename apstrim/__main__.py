Description = '''Serializer of Process Variables (from EPICS infrastructure)
or Data Objects from other infrastructures, e.g. ADO or LITE).'''
__version__ = '3.1.0 2024-10-21'# conform to pubEPICS 3.1.0, wait for eventStop() after starting.

import sys, argparse
from .apstrim  import apstrim, __version__

def main():
    # parse common arguments
    parser = argparse.ArgumentParser(description=Description
    ,formatter_class=argparse.ArgumentDefaultsHelpFormatter
    ,epilog=f'apstrim: {__version__}')
    parser.add_argument('-c', '--compress', action='store_true', help=\
    'Enable online compression')
    #parser.add_argument('-D', '--dirSize', type=int, default=10240, help=\
    #'Size of a directory section, set it to 0 to disable random access retrieval')
    #parser.add_argument('-d', '--doublePrecision', action='store_true', help=\
    #'Disable conversion of float64 to float32')
    #parser.add_argument('-f', '--file', default=None, help=\
    #'Configuration file')
    parser.add_argument('-o', '--outfile', default='apstrim.aps', help=\
    'Logbook file for storing PVs and data objects')
    parser.add_argument('-n', '--namespace', default='EPICS', help=\
    'Infrastructure namespace, e.g.: EPICS, ADO or LITE')
    parser.add_argument('-t', '--sectionTime', type=float, default=60., help=\
    'Time interval of writing of sections to logbook')
    parser.add_argument('-T', '--acqTime', type=float, default=99e6, help=\
    'How long (seconds) to take data.')
    parser.add_argument('-q', '--quiet', action='store_true', help=\
    'Quiet: dont print section progress')
    parser.add_argument('-v', '--verbose', action='count', default=0, help=\
    'Show more log messages (-vv: show even more).')
    parser.add_argument('pvNames', nargs='*', help=\
    'Data Object names, one item per device, parameters are comma-separated: dev1:par1,par2 dev2:par1,par2') 
    pargs = parser.parse_args()
    #print(f'pargs:{pargs}')

    s = pargs.namespace.upper()
    if s == 'LITE':
        from liteaccess import Access as publisher
    elif s == 'EPICS':
        from .pubEPICS import Access as publisher
    else:
        print(f'ERROR: Unsupported namespace {s}')
        sys.exit(1)

    pvNames = []
    for pvn in pargs.pvNames:
        tokens = pvn.split(',')
        first = tokens[0]
        pvNames.append(first)
        if len(tokens) > 1:
            dev = first.rsplit(':',1)[0]
            for par in tokens[1:]:
                pvNames.append(dev+':'+par)
    #print(f'pvNames: {pvNames}')

    apstrim.Verbosity = pargs.verbose
    aps = apstrim(publisher, pvNames, pargs.sectionTime, compress=pargs.compress
    #, quiet=pargs.quiet, use_single_float=not pargs.doublePrecision)
    , quiet=pargs.quiet)
    aps.start(pargs.outfile, howLong=pargs.acqTime)

    txt = f'for {round(pargs.acqTime/60., 2)} m' if pargs.acqTime<99e6 else 'endlessly'
    print(f'Streaming started {txt}, press Ctrl/C to stop.')
    apstrim._eventStop.wait()

if __name__ == '__main__':
    main()
