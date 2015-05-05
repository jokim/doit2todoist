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

class Doit:

    """ A representation of the data from Doit.im. """

    def __init__(self, doit_data):
        self._doit_data = doit_data

        cl = self._cleanup
        self.tasks = dict((t['id'], cl(t)) for t in doit_data['tasks'])
        self.tags = dict((t['uuid'], cl(t)) for t in doit_data['tags'])
        self.contexts = dict((t['uuid'], cl(t)) for t in doit_data['contexts'])
        self.projects = dict((t['uuid'], cl(t)) for t in doit_data['projects'])
        # self.contacts not tested yet

    def _cleanup(self, item):
        """Do clean up on a given item and return it prettified.

        Some elements in the various items are a bit messy. For instance could
        names and titles have newlines in them, probably due to the conversion
        through JSON.

        """
        ret = item.copy()
        # Remove newlines
        for k in ('name', 'title'):
            if k in ret:
                ret[k] = ret[k].replace('\n', '')
        return ret

    def print_status(self):
        """Print status on the Doit content."""
        for k in ('tasks', 'projects', 'tags', 'contexts'):
            print "%7d %s" % (len(getattr(self, k)), k)

    def get_project_name(self, uuid):
        """Return the name of a project.

        @param basestr uuid: The project id.

        """
        return self.projects[uuid]['name']

def main():
    parser = argparse.ArgumentParser(description="Import Doit.im data and "
                                                 "export it to Todoist")
    parser.add_argument('doit_file',
                        help='The file with data from Doit.im, in JSON format')
    args = parser.parse_args()

    doit_data = parse_json_file(args.doit_file)
    doit = Doit(doit_data)

    print "Doit.im data read:"
    doit.print_status()

if __name__ == '__main__':
    main()
