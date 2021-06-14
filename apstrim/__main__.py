Description = '''Serializer of Process Variables (from EPICS infrastructure)
or Data Objects (from other infrastructures, e.g. EPICS, ADO or LITE).'''

import sys, argparse
from .apstrim  import apstrim 

def main():
    
    # parse common arguments
    parser = argparse.ArgumentParser(description=Description)
    parser.add_argument('-c', '--compress', action='store_true', help=\
    'Enable online compression')
    #parser.add_argument('-d', '--dbg', action='store_true', help=\
    #'turn on debugging')
    #parser.add_argument('-f', '--file', default=None, help=\
    #'Configuration file')
    parser.add_argument('-o', '--outfile', default='apstrim.aps', help=\
    'File for storing PVs and data objects')
    parser.add_argument('-n', '--namespace', default='EPICS', help=\
    'Infrastructure namespace, e.g.: EPICS, ADO or LITE')
    parser.add_argument('pvNames', nargs='*', help=\
    'Data Object names, one item per device parameters are comma-separated: dev1:par1,par2 dev2:par1,par2') 
    pargs = parser.parse_args()
    #print(f'pargs:{pargs}')

    s = pargs.namespace.upper()
    if s == 'LITE':
        from .pubLITE import Access as publisher
    elif s == 'EPICS':
        from .pubEPICS import Access
        publisher = Access()
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

    ups = apstrim(pargs.outfile, publisher, pvNames, pargs.compress) 

if __name__ == '__main__':
    main()
