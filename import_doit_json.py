#!/usr/bin/env python

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
    return j(raw)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('projects', help='The projects file, in JSON format')
    parser.add_argument('tasks', help='The tasks file, in JSON format')
    args = parser.parse_args()

    projects = parse_json_file(args.projects)
    print "%d projects found" % len(projects)
    print projects[0]
    tasks = parse_json_file(args.tasks)
    print "%d tasks found" % len(tasks)
    print tasks[0]

if __name__ == '__main__':
    main()
