#!/usr/bin/env python
""" Script for exporting Doit.im data into Todoist. """

import argparse
try:
    import simplejson
    SIMPLEJSON = True
except ImportError:
    import json
    SIMPLEJSON = False


def parse_json_file(filename):
    """Read in a JSON file and return native python data."""
    f = open(filename)
    raw = ''.join(f.readlines()).strip()
    f.close()
    # Some tweaks, just for the parser to accept the file
    raw = raw.replace('\r', '\\r')
    raw = raw.replace('\n', '\\n')
    if SIMPLEJSON:
        j = simplejson.loads
    else:
        j = json.loads
    # TODO: Handle the exception that the file is still in HTML and not properly
    # modified for pure JSON
    return j(raw)

def main():
    parser = argparse.ArgumentParser(description="Import Doit.im data and "
                                                 "export it to Todoist")
    parser.add_argument('doit_file',
                        help='The file with data from Doit.im, in JSON format')
    args = parser.parse_args()

    doit_data = parse_json_file(args.doit_file)
    print "Doit.im data read. Status:"
    for k in doit_data:
        print "%15s: %5d elements" % (k, len(doit_data[k]))

    for p in doit_data['tags']:
        print p['name']

if __name__ == '__main__':
    main()
