#!/usr/bin/env python
""" Script for exporting Doit.im data into Todoist. """

import sys
import logging
import argparse
import time
from HTMLParser import HTMLParser
import json

import todoist

def parse_json_file(filename):
    """Read in a JSON file and return native python data."""
    f = open(filename)
    raw = ''.join(f.readlines()).strip()
    f.close()
    # Some tweaks, just for the parser to accept the file
    raw = raw.replace('\r', '\\r')
    raw = raw.replace('\n', '\\n')
    # TODO: Handle the exception that the file is still in HTML and not properly
    # modified for pure JSON
    try:
        return json.loads(raw)
    except ValueError:
        # This could for instance happen if the user hasn't stripped away the
        # HTML tags from the file. Retry by trying to only fetch what's inside
        # a <body> element, if any.
        p = SimpleHTMLParser()
        p.feed(raw)
        p.close()
        return json.loads(p.get_body())

class SimpleHTMLParser(HTMLParser):

    """Simple class for just extracting the content of <body>.

    Working for the special case where the Doit data has been extracted, as
    described in README.md in the repo of this script.

    """
    def __init__(self):
        self._in_body = False
        self.bodydata = []
        HTMLParser.__init__(self)

    def handle_starttag(self, tag, attrs):
        if tag == 'body':
            self._in_body = True

    def handle_endtag(self, tag):
        if tag == 'body':
            self._in_body = False

    def handle_data(self, data):
        if self._in_body:
            self.bodydata.append(data)

    def get_body(self):
        return ''.join(self.bodydata)

def timestamp_to_date(timestamp, format='%Y-%m-%dT%H:%M'):
    """Convert a Doit timestamp into a format readable by Todoist.

    The time is normally not needed, since Todoist only cares about the dates.

    """
    return time.strftime(format, time.gmtime(timestamp/1000))

class NotFoundException(Exception):
    """If 'something' was not found."""
    pass

class CommitException(Exception):
    """If a commit to Todoist failed."""
    def __init__(self, msg, errors):
        super(CommitException, self).__init__(msg)
        # TODO: Parse and make it easier to e.g. print out the errors?
        self.errors = errors

    def __str__(self):
        print "%s (%s)" % (self.args[0], 
                           ', '.join(map(str, self.errors.itervalues())))

class UnhandledRepeaterError(Exception):
    """For when the repeat mode hasn't been translated."""
    pass

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
        logger.debug("Status from Doit: %d projects, %d tasks, %d tags, "
                     "%d contexts", len(self.projects), len(self.tasks),
                     len(self.tags), len(self.contexts))
        for k in ('tasks', 'projects', 'tags', 'contexts'):
            print "%7d %s" % (len(getattr(self, k)), k)

    def get_project_name(self, uuid):
        """Return the name of a project.

        @param basestr uuid: The project id.

        """
        return self.projects[uuid]['name']

    def get_project(self, uuid):
        """Return the project's details."""
        return self.projects[uuid]

    def get_project_by_name(self, name):
        """Find a project by its name/title."""
        if not hasattr(self, '_project_names'):
            self._project_names = dict((p['name'], p) for p in
                                       self.projects.itervalues())
        return self._project_names[name]

    def list_context_names(self):
        """Return a list of all the contexts, by its names."""
        return dict((c['name'], c) for c in self.contexts.itervalues())

    def get_context_name(self, ctx_id):
        """Get the name of a given context."""
        return self.contexts[ctx_id]['name']

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

        The list is sorted by position, but with the active projects first.

        Elements in a Doit project, with my understanding of it:

        - uuid (str): The unique id of the project
        - name (str): The name of the project
        - status (str): If the project is 'active' or 'inactive'. Inactive does
          here mean that the project has a start date in the future.
        - deleted: If the project is deleted
        - archived: If the project is archived
        - trashed: If the project is trashed
        - completed: If the project has been completed
        - pos (int): Relative position of the project in the project list
        - active_notice (bool): TODO 
        - usn (int): Don't know
        - medias (list): Reference to media that has been added to the project,
          e.g. links to Evernote notes.
        - local_attachments (list): TODO: Maybe file uploads?
        - group_by (str): E.g. 'box'. Don't know.
        - from_task (str): Reference to the uuid of a task - maybe this is for
          when a task got converted into a project? TODO

        Timestamps:
        - created: When the project was created
        - updated: When the project was last edited
        - start_at: The start date for the project
        - end_at: The end date for the project

        """
        active = []
        inactive = []
        for k, pr in self.projects.iteritems():
            if (pr['deleted'] or pr['completed'] or pr['archived'] or
                    pr['trashed']):
                continue
            if pr['status'] == 'active':
                active.append(pr)
            else:
                inactive.append(pr)
        logger.debug("From Doit, listing %d active and %d inactive projects",
                     len(active), len(inactive))
        return self.sort_by_pos(active) + self.sort_by_pos(inactive)

    def list_active_tasks(self):
        """Get all active tasks from Doit data.

        Tasks have many elements. This is my attempt to explain what I think are
        *probable* usage of them:

        - id (str): Some id
        - uuid (str): Another id. Note that two tasks from the same repetition
          gets the same `uuid`, but a different `id`.
        - project (str): The id of its project. Go to self.projects[id] to get
          the details.
        - title (str): Title
        - notes (str): More details
        - tags (list): A list with the name of the tags. Example: ['work',
          'gtd', 'proj_Alpha']
        - context (str): The id to the task's context
        - attribute (str): Where the task is put. Example on status: 'waiting',
          'inbox', 'plan', 'noplan' and 'next'. Tasks marked as "Someday/Maybe"
          are tagged with 'noplan', it seems.
        - estimated_time: How long it's estimated to take, or 0 if not set
        - spent_time: How long it's estimated to take, or 0 if not set
        - pos (int): Relative position of task in lists
        - $$hashKey (str): Three digits, added by Angular (javascript) at
          conversion.
        - completed: When task was completed? Mine are all set to 0
        - archived: When task was archived? Mine are all set to 0
        - deleted: When task is supposed to be deleted? Mine are all set to 0.
        - trashed: If task is deleted? All mine are set to 0
        - sent_at: When tasks was sent to someone, when cooperating through
          Doit? Mine are all set to 0. It's at least not for marking tasks
          incoming by e-mail, since I've used that.
        - usn (int): Don't know
        - all_day (bool): If the task is for all day long, or for a specific
          time of the day. Used in combination with `start_at`.
        - repeater (dict): Repeating tasks has it repeating frequency config set
          here. 

          Examples:

            {'ends_on': 0, 'mode': 'daily', 'daily': {'cycle': 3}}

            {'ends_on': 0, 'mode': 'weekly', 
             'weekly': {'days': [0], 'cycle': 2}}

            {'ends_on': 0, 'mode': 'weekly',
             'weekly': {'days': [1, 2, 3, 4], 'cycle': 1}}

            {'monthly': {'week': {'day_of_week': 0, 'week_of_month': 1},
                         'cycle': 1}, 
             'ends_on': 0, 'mode': 'monthly'}

            {'yearly': {'cycle': 1, 'day_of_month': 21, 'month': 11},
             'ends_on': 0, 'mode': 'yearly'}

        - repeat_no (str): Looks like the date for when it should be repeated?
        - source (str): From where the task is retrieved from. Example: 'email'.
          This doesn't seem to always be correct, as I've seen tasks sent
          through mail without this tag.
        - google_event_id (str): An id to a google event. Probably to match the
          event in Google Calendar.
        - now (bool): If the task should be done here and now.
        - reminders (list): A list of reminders, or an empty list. Example on
          format:

            [{"view":"relative","uuid":"506fb474-015b-4570-b09a-717cd2687fd3",
             "time":1417388500000,"mode":"popup"},
             {"view":"relative","mode":"popup","time":1430380750000}]

        - priority (int): A priority set in the range 0-3, where 0 is the
          lowest.
        - medias (list): If some media has been attached to the task, for
          instance Evernote notes. Example on the format:

            [{'url': 'https://www.evernote.com/shard/s465/sh/8d311aab...',
              'type': 'evernote', 'uuid': '8c308aab-a401...',
              'title': 'Title of note from Evernote'}]

        - hidden: If the task should be hidden? Mine are all set to 0
        - local_attachments (list): Don't know
        - type (str): All tasks set to "task", at least for me

        Timestamps, in seconds since Epoch:
        - start_at: When task is set to be started on, or 0 for no start date
        - end_at: When the is supposed to end, i.e. the deadline, or 0 for no
          end date
        - updated: When task was last edited 
        - created: When the task was created

        """
        ret = []
        for k, t in self.tasks.iteritems():
            if t['trashed'] or t['deleted']:
                continue
            if t['completed'] or t['archived']:
                continue
            ret.append(t)
        logger.debug("From Doit, listing %d active tasks", len(ret))
        return self.sort_by_pos(ret)

    @staticmethod
    def sort_by_pos(elements):
        """Sort a list of elements by position.

        The elements could be tasks or projects, or other element types that has
        the attribute "pos".

        """
        return sorted(elements, key=lambda e: e['pos'])

class TodoistHelperAPI(todoist.TodoistAPI):
    """Subclassing TodoistAPI for easier code."""

    def get_label_id_by_name(self, name):
        """Get the id of a label by searching by its name"""
        r = self.labels.all(lambda x: x['name'] == name)
        if len(r) == 1:
            return r[0]['id']
        raise NotFoundException('Not found label named: %s' % name)

    def get_project_by_name(self, name):
        """Find the project by the name of the project."""
        r = self.projects.all(lambda x: x['name'] == name)
        if len(r) == 1:
            return r[0]
        raise NotFoundException('Not found project named: %s' % name)

    def get_project_id_by_name(self, name):
        """Find the project id by the name of the project."""
        return self.get_project_by_name(name)['id']

    def get_projectname(self, project_id):
        """Return the project's name."""
        return self.projects.get_by_id(project_id)['name']

    def assert_and_get_project(self, prname):
        """Shortcut for getting a project, and creating it if doesn't exist."""
        try:
            return self.get_project_by_name(prname)
        except NotFoundException:
            logger.info('Creating (empty) project: %s', prname)
            print("Creating project: %s" % prname)
            r = self.projects.add(prname)
            self.commit()
        return self.get_project_by_name(prname)

    _max_len_request_uri = 4000

    def add_note(self, note, item_id=None, project_id=None):
        """Add a note to Todoist, if it's not already there.

        If a note with the same content exists for the same item or project, it
        will not be created once more.

        Takes care of long notes by splitting them up.

        """
        assert item_id or project_id, "Missing item or project id"
        note = note.strip()

        if item_id:
            logger.info("Add note for item_id=%s: '%s...' (%d chars)", item_id,
                        note[:200].replace('\n', ''), len(note))
        else:
            logger.info("Add project note for project_id=%s: '%s...' "
                        "(%d chars)", project_id, note[:200].replace('\n', ''),
                        len(note))
        def match(n):
            if item_id and n['item_id'] != item_id:
                return False
            if project_id and n['project_id'] != project_id:
                return False
            return n['content'] == note

        existing = self.notes.all(filt=match)
        if existing:
            logger.debug("Note already created, skipping")
            return existing[0]

        if len(note) > self._max_len_request_uri:
            logger.debug("Note too long (%d chars), splitting", len(note))
            logger.debug("...for now, only cutting out the first part")
            # TODO: Split!
            # For now, I'm only cutting out the first part...
            return self.notes.add(item_id=item_id, project_id=project_id,
                                  content=note[:self._max_len_request_uri])
        else:
            return self.notes.add(item_id=item_id, content=note,
                                  project_id=project_id)

    def assert_project(self, name, **kwargs):
        """Assert that a given project exists and is updated.

        Makes sure that the given details are correct. Uses the *name* of the
        project as identificator in Todoist.

        :rtype: bool
        :return: True if the project was created, otherwise False.

        """
        created = False
        try:
            project = self.get_project_by_name(name)
        except NotFoundException:
            project = self.add_project(name, **kwargs)
            created = True
        else:
            needs_update = False
            print kwargs
            for key, val in kwargs.iteritems():
                if key == 'notes':
                    # notes are special
                    continue
                if project.data.get(key) != val:
                    needs_update = True
            if needs_update:
                logger.info('Updating project "%s" with: %s', name, kwargs)
                project.update(**kwargs)
            else:
                logger.debug("No need to update project: %s", name)
        if kwargs.get('notes'):
            # TODO: Check if note is already added to the project
            self.add_note(kwargs['notes'], project_id=project['id'])
            try:
                self.commit()
            except CommitException, e:
                logger.warn("Failed adding project note to %s: %s", name, e)
                print "Failed adding project note to %s" % name
        self.commit()
        return created

    def add_project(self, name, **kwargs):
        """Add a project to Todoist and commit.

        :rtype: todoist.models.Project
        :return: The created project
        
        """
        logger.info("Creating project: '%s', with args: %s", name, kwargs)
        p = self.projects.add(name, **kwargs)
        self.commit()
        return p

    def add_item(self, content, project_id, **kwargs):
        """Add an item to Todoist and commit.

        The note is added as well.

        :param list labels:
            The list of labels to add to the item. Note that these should be the
            name of the label and not its ID, as this is translated.

        :rtype: todoist.models.Item
        :return: The created item
       
        """
        logger.info("Creating item: '%s', for project %s (%s), with args: %s",
                content, project_id, self.get_projectname(project_id), kwargs)
        if kwargs.get('labels'):
            kwargs['labels'] = [self.get_label_id_by_name(l) for l in
                                kwargs['labels']]
        else:
            kwargs['labels'] = ()
        notes = kwargs.get('notes')
        # Add notes separately, after the item has been created
        if 'notes' in kwargs:
            del kwargs['notes']
        it = self.items.add(content=content, project_id=project_id, **kwargs)
        self.commit()
        if notes:
            self.add_note(notes, item_id=it['id'])
        self.commit()
        return it

    def add_inbox_item(self, content):
        """Add an item to Todoist's Inbox.
        
        This is a shortcut for a simple task, just adding something to the
        Inbox. If you want so set some params, please see `add_item`.
        
        """
        if not hasattr(self, '_inbox_id'):
            self._inbox_id = self.get_project_id_by_name('Inbox')
        return self.add_item(content=content, project_id = self._inbox_id)

    def commit(self):
        """Commit and check feedback and raise Exception.

        This is for easier code, rasising errors if something is wrong. It also
        have simple handling of request limits.

        """
        errors = {}
        logger.debug("Sending commit message to Todoist")
        logger.debug("Commit queue: %s", self.queue)
        ret = super(TodoistHelperAPI, self).commit()
        logger.debug("Commit response: %s", ret)
        # Handle limit block exceptions specially, by rerunning it after a few
        # seconds:
        if isinstance(ret, dict) and ret.get('error_tag') == 'LIMITS_REACHED':
            logger.debug("Todoist's request limit reached, pause and rerun")
            time.sleep(10)
            return self.commit()

        if isinstance(ret, dict):
            if 'error' in ret:
                logger.error("Error from Todoist: %s", ret)
                raise CommitException('Commit to Todoist failed', ret)
            for key, row in ret.iteritems():
                if isinstance(row, dict) and 'error' in row:
                    logger.error("Errors from Todoist: %s: %s", key, row)
                    errors[key] = row
        if errors:
            raise CommitException('Commit to Todoist failed, %d errors' %
                                  len(errors), errors)
        return ret

    def get_max_project_position(self):
        """Get the max `item_order` set in Todoist for projects."""
        return max(p['item_order'] for p in self.projects.all())

class Todoist_exporter:

    """ Class that handles the export to Todoist. """

    # Name of the super project that all the projects should be put underneath
    # in Todoist:
    superproject_name = 'Doit.im'

    somedayproject_name = 'Someday Maybe'

    inboxproject_name = 'Inbox'

    def __init__(self, doit, tdst):
        self.doit = doit
        self.tdst = tdst

    def export(self):
        """Do the full export to Todoist"""
        logger.debug("Start export from Doit to Todoist")
        self.tdst.sync()
        self.tdst.items.sync()
        self.tdst.projects.sync()
        self.tdst.labels.sync()
        self.tdst.notes.sync()
        logger.debug("Status in Todoist: %d projects, %d items, %d labels, "
                     "%d notes", len(self.tdst.projects.all()),
                     len(self.tdst.items.all()), len(self.tdst.labels.all()),
                     len(self.tdst.notes.all()))
        self.export_labels()
        self.export_projects()
        self.export_tasks()
        # Not really needed, but just to be sure
        self.tdst.commit()
        logger.debug("Export from Doit to Todoist done")

    def export_labels(self):
        """Export all labels to Todoist.

        It fetches Contexts and Tags from the Doit data and creates them in
        Todoist as Labels. Some labels are used in the sync and are therefore
        always created, like the special label "waiting".

        """
        names = set(self.doit.list_context_names().keys())
        names.update(self.doit.list_tag_names().keys())
        names.add('waiting')
        existing = [l['name'] for l in self.tdst.labels.all()]
        for name in names:
            logger.debug("Prosessing Doit context or tag: %s", name)
            if name in existing:
                continue
            print "Creating label: %s" % name
            logger.debug("Creating new label in Todoist: %s", name)
            self.tdst.labels.add(name)
            self.tdst.commit()

    def export_projects(self):
        """Export all projects to Todoist.

        All projects from Doit are created in Todoist as regular projects. This
        might not be what you want.
        
        All the projects are stored under a super project called "Doit". The
        super project gets created if it doesn't exist.

        TODO: Might want to have the Goals as their super projects?

        - If the project has status "inactive", it gets moved into a project
          "Someday Maybe".

        """
        projects = self.doit.list_active_projects()
        
        # Create the meta projects:
        somedaypr = self.tdst.assert_and_get_project(self.somedayproject_name)
        superpr = self.tdst.assert_and_get_project(self.superproject_name)
        # The projects must be positioned underneath the super project:
        if 'item_order' in superpr.data:
            super_pos = superpr['item_order']
            logger.debug("Setting project's item_order: %s", super_pos)
        else:
            super_pos = self.tdst.get_max_project_position() + 1
            logger.debug("Setting project's item_order to max: %s", super_pos)

        super_indent = superpr.data.get('indent', 1)

        # The returned list is sorted
        for pr in projects:
            logger.debug("Processing Doit project: %s", pr)
            name = pr['name']
            created = self.tdst.assert_project(pr['name'],
                                               indent=super_indent + 1,
                                               item_order=super_pos,
                                               notes=pr.get('notes'))
            if created:
                print "Created project: %s" % pr['name']
                super_pos += 1

    def export_tasks(self):
        """Export all Doit tasks as Items in Todoist.

        Some special handling is needed, as Doit and Todoist works a bit
        differently. A description of its behaviour:

        - Tasks without a project are put directly into the Doit super project
          in Todoist.

        - Dates, see `self.calculate_due_date` for how it's set.

        - Tasks set to Waiting are instead given the @waiting label, and are
          kept into its correct project.

        - The task's description is added as a Note.

        """
        tasks = self.doit.list_active_tasks()
        existing = [l['content'] for l in self.tdst.items.all()]

        # Positions are relative to the projects
        positions = {}

        # TODO: Find project from Doit and match in Todoist

        # The returned list is sorted
        for task in tasks:
            logger.debug("Processing Doit task: %s", task)
            name = task['title']
            if name in existing:
                # TODO: Handle updating existing tasks!
                continue
            print "Creating task: %s" % name

            doit_project = None
            if 'project' in task:
                doit_project = self.doit.get_project(task['project'])

            # Special treatment for tasks in the inbox and someday categories
            if task['attribute'] == 'inbox':
                prname = self.inboxproject_name
            elif task['attribute'] == 'noplan':
                prname = self.somedayproject_name
            elif 'project' in task:
                prname = self.doit.get_project_name(task['project'])
            else:
                prname = self.superproject_name

            try:
                prid = self.tdst.get_project_id_by_name(prname)
            except KeyError:
                print("Couldn't add task '%s' due to missing project '%s'"
                      % (name, prname))
                continue
            positions.setdefault(prid, 0)
            positions[prid] += 1

            labels = set()
            if 'tags' in task:
                labels.update(task['tags'])
            if 'context' in task:
                labels.add(self.doit.get_context_name(task['context']))
            # Add if the task is in Waiting mode, then the @waiting context is
            # added:
            if task['attribute'] == 'waiting':
                labels.add('waiting')

            # TODO: Check if recurring dates
            date_str = ''
            due_str = ''
            repeater_unhandled = False
            if 'repeater' in task:
                try:
                    date_str = self.generate_repeating_string(task['repeater'])
                except UnhandledRepeaterError:
                    # TODO: Add to inbox
                    repeater_unhandled = True
            if not date_str or 'repeater' not in task:
                due_str = self.calculate_due_date(task, doit_project)
                if due_str and not date_str:
                    # Need to set date_string to something for Todoist to
                    # recognise the due_date_utc to work, don't know why
                    date_str = 'someday'
            ret = self.tdst.add_item(content=name, project_id=prid, indent=1,
                                     item_order=positions[prid],
                                     priority=task['priority'] + 1,
                                     date_string=date_str, due_date_utc=due_str,
                                     labels=labels, notes=task.get('notes'))
            if repeater_unhandled:
                self.tdst.add_inbox_item("New item missing repeat date: "
                            "https://todoist.com/showTask?id=%s - please "
                            "fix: %s" % (ret['id'], task['repeater']))

    def calculate_due_date(self, task, project):
        """Figure out what due date to set in Todoist for a task.

        The problem is that Todoist only has one date, the "due date", while
        Doit has both a start and end date, in addition to the projects' own
        start and end dates. It seems that Todoist recognizes the "due date" as
        an *end date*, at least if you look at the Todoist Karma.
        
        The algorithm is then:

        - If a Doit task has an end date, use that. TODO: Lower the position if
          the task has a start date into the future?

        - If a Doit task only has a start date, set that. This will be
          incorrect, and might be messy for how you use your GTD system, but at
          least we have a date.

        - If a Doit task doesn't have dates set, I use the projects dates
          instead, if set. The end date have priority.

        - No due date is set if no dates were found.

        """
        if task['end_at']:
            return timestamp_to_date(task['end_at'])
        if task['start_at']:
            return timestamp_to_date(task['start_at'])
        if project:
            if project['end_at']:
                return timestamp_to_date(project['end_at'])
            if project['start_at']:
                return timestamp_to_date(project['start_at'])
        return None

    def generate_repeating_string(self, rep):
        """Translate a Doit repeater into Todoist's human readable format.

        Note that I take the liberty to use the form *after* instead of *every*
        in the tasks. The difference is that the next task will occur the given
        period after *completion* and not stuck in the schedule. You might need
        to clean things up afterwards in the tasks.

        The Doit format is just reverse engineered, so the translation is not
        complete.

        Explanations for Todoist could be located at
        https://todoist.com/Help/DatesTimes.

        """
        if not rep:
            return ""

        # Mapping of cycles
        cycles = ('', '', '2nd', '3rd', '4th', '5th', '6th', '7th', '8th',
                  '9th', '10th', '11th', '12th', '13th', '14th', '15th', '16th',
                  '17th', '18th', '19th', '20th', '21st', '22nd', '23rd',
                  '24th', '25th', '26th', '27th', '28th', '29th', '30th')

        config = rep[rep['mode']]
        days = ''

        if rep['mode'] == 'daily':
            days = 'day'
        elif rep['mode'] == 'weekly':
            print("Task is set to repeat, but that is not added to Todoist. "
                  "Manual intervention is needed.")
            # TODO: Translation not fixed
            raise UnhandledRepeaterError("Unhandled weekly repetition")
        elif rep['mode'] == 'monthly':
            print("Task is set to repeat, but that is not added to Todoist. "
                  "Manual intervention is needed.")
            # TODO: Translation not fixed
            raise UnhandledRepeaterError("Unhandled monthly repetition")
        elif rep['mode'] == 'yearly':
            print("Task is set to repeat, but that is not added to Todoist. "
                  "Manual intervention is needed.")
            # TODO: Translation not fixed
            raise UnhandledRepeaterError("Unhandled yearly repetition")
        else:
            logger.warn('Unhandled repeater mode: %s', rep['mode'])
            print "Unhandled repeat mode for task, needs manual intervention"
            # TODO: Translation not fixed
            raise UnhandledRepeaterError("Unhandled repetition")
        return 'every %s %s' % (cycles[config['cycle']], days)


def setup_logger(debug=False):
    """Setup the script's logger."""
    global logger
    logger = logging.getLogger('doit2todoist')
    ch = logging.FileHandler('doit2todoist.log')
    logger.setLevel(logging.DEBUG)
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    if debug:
        ch2 = logging.StreamHandler()
        ch2.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s: %(message)s')
        ch2.setFormatter(formatter)
        logger.addHandler(ch2)
    return logger

def main():
    parser = argparse.ArgumentParser(description="Import Doit.im data and "
                                                 "export it to Todoist")
    parser.add_argument('doit_file',
                        help='The file with data from Doit.im, in JSON format')
    parser.add_argument('apikey',
                        help='Your API key for your account in Todoist')
    parser.add_argument('-d', '--debug', action='store_true',
                        help='Print debug information, for developers')
    args = parser.parse_args()

    setup_logger(args.debug)

    doit_data = parse_json_file(args.doit_file)
    doit = Doit(doit_data)

    print("Doit.im data read:")
    doit.print_status()

    tdst = TodoistHelperAPI(args.apikey)
    status = tdst.sync()
    if 'error' in status:
        logger.error('Failed sync with Todoist: %s', status)
        print("Error from Todoist: %s - %s" % (status['error_code'],
                status['error']))
        return 1
    exp = Todoist_exporter(doit, tdst)
    print "Start syncing with Todoist..."
    exp.export()
    print "Sync done!"
    return 0

if __name__ == '__main__':
    sys.exit(main())
