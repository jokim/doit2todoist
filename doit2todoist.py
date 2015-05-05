#!/usr/bin/env python
""" Script for exporting Doit.im data into Todoist. """

import sys
import argparse
import todoist
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

    def list_context_names(self):
        """Return a list of all the contexts, by its names."""
        return dict((c['name'], c) for c in self.contexts.itervalues())

    def list_tag_names(self):
        """Return a list of all the tags, by its names."""
        return dict((t['name'], t) for t in self.tags.itervalues())

    def list_project_names(self):
        """Return a list of all the projects, by its names."""
        return dict((t['name'], t) for t in self.projects.itervalues())

    def list_active_projects(self):
        """Get all active projects.

        The list is filtering for deleted and archived projects, so only active
        or upcoming projects are returned.

        The list is sorted by position.

        """
        ret = []
        for k, pr in self.projects.iteritems():
            if pr['status'] not in ('active', 'inactive'):
                print "Ignore not active project: %s" % pr
                continue
            if (pr['deleted'] or pr['completed'] or pr['archived'] or
                    pr['trashed']):
                continue
            ret.append(pr)
        return self.sort_project_list(ret)

    @staticmethod
    def sort_project_list(projects):
        """Sort a list of projects by position."""
        return sorted(projects, key=lambda pr: pr['pos'])

class Todoist_exporter:

    """ Class that handles the export to Todoist. """

    def __init__(self, doit, tdst):
        self.doit = doit
        self.tdst = tdst

    def export(self):
        """Do the full export to Todoist"""

        self.export_labels()
        self.export_projects()
        # TODO: inbox is special
        # self.export_tasks()
        # TODO: Ask for confirmation before commiting
        self.tdst.commit()
        #self.tdst.sync()

    def export_labels(self):
        """Export all labels to Todoist.

        It fetches Contexts and Tags from the Doit data and creates them in
        Todoist as Labels.

        """
        names = self.doit.list_context_names().keys()
        names += self.doit.list_tag_names().keys()
        self.tdst.labels.sync()
        existing = [l['name'] for l in self.tdst.labels.all()]

        for name in names:
            if name in existing:
                continue
            print "Creating label: %s" % name
            self.tdst.labels.add(name)

    def export_projects(self):
        """Export all projects to Todoist.

        All projects from Doit are created in Todoist as regular projects. This
        might not be what you want.
        
        All the projects are stored under a super project called "Doit". The
        super project gets created if it doesn't exist.

        TODO: Might want to have the Goals as their super projects?

        """
        projects = self.doit.list_active_projects()
        self.tdst.projects.sync()
        # Find the super project to position the projects underneath
        superpr = self.tdst.projects.all(lambda p: p['name'] == 'Doit.im')
        if superpr:
            position = superpr[0]['item_order']
        else:
            print "Creating super project: Doit.im"
            ret = self.tdst.projects.add('Doit.im', indent=1)
            position = ret['indent']

        existing = [l['name'] for l in self.tdst.projects.all()]

        # The returned list is sorted
        for pr in projects:
            name = pr['name']
            if name in existing:
                continue
            print "Creating project: %s" % name
            position += 1
            ret = self.tdst.projects.add(name, indent=2, item_order=position)
            # TODO: Remove debug info
            print ret

    def export_tasks(self):
        """Export all tasks to Todoist.

        Some special handling is needed, as Doit and Todoist works differently. 

        TODO.

        """
        pass

def main():
    parser = argparse.ArgumentParser(description="Import Doit.im data and "
                                                 "export it to Todoist")
    parser.add_argument('doit_file',
                        help='The file with data from Doit.im, in JSON format')
    parser.add_argument('apikey',
                        help='Your API key for your account in Todoist')
    args = parser.parse_args()

    doit_data = parse_json_file(args.doit_file)
    doit = Doit(doit_data)

    print "Doit.im data read:"
    doit.print_status()

    tdst = todoist.TodoistAPI(args.apikey)
    status = tdst.sync()
    if 'error' in status:
        print "Error from Todoist: %s" % status['error']
        return 1
    exp = Todoist_exporter(doit, tdst)
    print "Exporting to Todoist..."
    exp.export()
    print "export done!"

    return 0

if __name__ == '__main__':
    sys.exit(main())
