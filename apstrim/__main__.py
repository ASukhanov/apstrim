# Copyright (c) 2021 Andrei Sukhanov. All rights reserved.
#
# Licensed under the MIT License, (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/ASukhanov/apstrim /blob/main/LICENSE
#

Description = '''Serializer of Process Variables (from EPICS infrastructure)
or Data Objects (from other infrastructures, e.g. LITE or ADO).'''

import sys, argparse
from .apstrim  import apstrim 

def main():
	
    # parse common arguments
    parser = argparse.ArgumentParser(description=Description)
    parser.add_argument('-c', '--compression', action='store_true', help=\
    'Compression')
    #parser.add_argument('-d', '--dbg', action='store_true', help=\
    #'turn on debugging')
    parser.add_argument('-f', '--file', default='apstrim .ups', help=\
    'Configuration file')
    parser.add_argument('-o', '--outfile', default='apstrim .ups', help=\
    'File for storing PVs and data objects')
    parser.add_argument('-n', '--namespace', default='LITE', help=\
    'Infrastructure namespace, e.g.: LITE or EPICS')
    parser.add_argument('pvNames', nargs='*') 
    pargs = parser.parse_args()
    print(f'pargs:{pargs}')

    s = pargs.namespace.upper()
    if s == 'LITE':
        from .pubLITE import Access as publisher
    elif s == 'EPICS':
        from .pubEPICS import Access
        publisher = Access()
    else:
        print(f'ERROR: Unsupported namespace {s}')
        sys.exit(1)

    ups = apstrim (pargs.outfile, publisher, pargs.pvNames, pargs.compression) 

if __name__ == '__main__':
    main()
