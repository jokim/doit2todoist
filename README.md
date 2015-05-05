Doit2Todoist
============

This is a short script for importing projects and tasks into Todoist, from data
formatted in Doit.im's manner. Todoist supports importing tasks, but only into
one project at a time. This script imports all my projects from Doit.im in one
go, with their tasks per project.

The script works like:

1. You fetch the data from Doit.im by executing some javascript code and saves
   the HTML file.

2. Start the script with the file as input.

3. The script will communicate with Todoist and add the data to the given
   account.

Caveats
-------

Some functionality requires *paid membership* in Todoist.

NOTE: Todoist is not mainly for GTD, so your setup might vary from this. This
script might therefore not be what you want. Some general rules for the import:

- Each GTD project becomes its own Todoist project. Some prefers to have all the
  GTD projects inside one Todoist project, which could be implemented through
  Todoist own import functionality.

- All GTD contexts becomes their own Todoist label.

- All Doit tags becomes their own Todoist label.

Requirements
------------

You would need:

- A Doit.im account to fetch data from

- A Todoist account to import to

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

    $('body').text(JSON.stringify({'tasks': TASKS, 'projects': Doit.projects,
                'contexts': Doit.contexts, 'tags': Doit.tags, 'goals':
                Doit.goals, 'contacts': Doit.contacts}));

   This will change the HTML page and output your data. Don't worry, it will get
   back to original if you refresh the page, but don't do that now.

4. Save the HTML document.

5. Open the HTML document and strip out the remaining HTML elements, so that
   only the JSON data is left.

You now have a valid JSON file, with all your projects, tasks, contexts, tags
etc. Some of the data is internal references for Doit. The file could now be
used for importing to other GTD applications, like Todoist.
