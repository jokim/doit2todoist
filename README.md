Doit2Todoist
============

This is a simple script for importing projects and tasks into Todoist, from data
formatted in Doit.im's manner. Todoist have native support for importing tasks,
but only into one project at a time. This script imports all my projects from
Doit.im in one go, with their tasks per project.  Unfortunately, a small part of
manual work is needed for getting the data out of Doit.im, see further down.

The workflow of the export:

1. You must first fetch the data from Doit.im by executing some javascript code
   and save the HTML file. The file will contain most of your Doit data in JSON
   format.

2. Run the script with the file and your Todoist account's API key as arguments.
   Example:

   ```
   python doit2todoist.py doit.html 124124238922a811e13898131f
   ```

   Use the argument `--help` for guidance.

3. The script then communicates with Todoist and adds the data to the given
   account.

_Disclosure_: This script was written in short bursts at nights, with an infant
in my lap, trying to get him to sleep. _Do not expect quality software_!

Requirements
------------

For this sync to work you would need:

- A Doit.im account to fetch data from. 

- A Todoist account to import to. The script has only been tested with a paid
  account.

- A python 2.7 environment to run the script from, with the extensions:

    - todoist-python (https://developer.todoist.com/#introduction)

How to export data from Doit.im
-------------------------------

Doit.im doesn't seem to like support for exporting your data, so a workaround is
needed. This description is generic, and could be used for other imports too.

To get your data from from Doit.im, you need to:

1. Run your browser in development mode (<F12>). This is at least supported by
   Mozilla Firefox and Chrome.

2. Get a list of all the tasks you want to export. You could for instance create
   a filter to get these listed out. Only the listed tasks will be returned, so
   to get all tasks you would need to create a filter that lists all tasks.

3. Run the javascript code:

   ```javascript
   $('body').text(JSON.stringify({'tasks': TASKS, 'projects': Doit.projects,
              'contexts': Doit.contexts, 'tags': Doit.tags,
              'goals': Doit.goals, 'contacts': Doit.contacts}));
   ```

   This will change the HTML page and output your data. Don't worry, it will get
   back to original if you refresh the page, but don't do that now.

   TODO: I couldn't find out where subtasks were stored. If you do, please let
   me know. :)

4. Save the HTML document.

5. _Optional_: Open the HTML document and strip out the remaining HTML elements,
   so that only the JSON data is left. This is not needed for the script, but a
   clean JSON file would make it easier if you want use other imports. :)

You now have a file that contains all your projects, tasks, contexts, tags
etc. Some of the data is internal references for Doit. The file could now be
used for importing to other GTD applications, like Todoist.
Caveats
-------

- Some functionality requires *paid membership* in Todoist.

- Todoist is not mainly for GTD, so you might prefer a different setup. This
  script might therefore not be what you want, or you would need to tweak it
  yourself.

- Some functionality is either missing or too different for me to be able to
  implement it. For instance doesn't Todoist have end dates. Some functionality
  will therefore be missing.

How is Doit-data translated to Todoist
--------------------------------------

Some general rules for the import:

- Each GTD project becomes its own Todoist project, stuffed underneath a super
  project named "Doit.im". You would probably want to move the projects
  afterwards, e.g. to a Personal and Work project.

  Some prefer to have all the GTD projects inside one Todoist project, which
  could be implemented through Todoist native import functionality, or you could
  just modify this script. :)

- The export creates the super projects "Doit.im" and "Someday Maybe". Tasks and
  projects are added to these, in addition to "Inbox".

- All GTD _contexts_ are converted to Todoist _labels_.

- All Doit _tags_ are also converted to Todoist _labels_.

- Doit has start and end dates, Todoist only has a due date. The export will
  try:

   1. If the task has an end date, set it as the due date.

   2. If the task has a start date, set it as the due date.

   3. If the task's project has an end date, set it as the due date.

   4. If the task's project has a start date, set it as the due date.

- _Repeating tasks_ are not added correctly, and needs manual settings. An item
  is added to Todoist's Inbox to notify you about what needs to be set per
  repeating task.

- All tasks in _Waiting_ mode in Doit get a label called `@waiting` to mark
  them as this.

