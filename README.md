# Liternote

Simple literature note tool.

Written in Python using PyQt5 and sqlite3.

License: MIT. Credit: Luyao Zou (https://github.com/luyaozou)

=====================
## Release Note 1.1.0

### What's New:

* Add tagging system. User may add / remove any tags to a note entry.
Tags can be used to constraint full text search results.
* Add label for comboboxes in search dialogs.

### Bug Fixes:

* Clicking "Load" button on empty search dialog causes invalid database search.
* Genre combobox in main GUI is too narrow


=====================
## Release Note 1.0.0

First release. This light weight program offers users ability to keep notes for
the academic literatures users have read. Each note record has the following
fields:

* bibkey: the unique identifier of the literature -- this is designed so that
  the user can link the note to the bibliography entries in their favorite
  reference management programs.
* genre: the genre of the literature: theory, experiment, instrumentation, and
    reivew
* author: the authors of the paper
* thesis: the main thesis of the paper
* hypothesis: the hypothesis this paper is based on
* method: the method
* finding: the main findings of the paper
* comment: the user's comment on the paper
* images: append images / screenshots to help understand the note.
Images are automatically loaded to the panel when clipboard is refreshed.

Upon first usage, the program creates a database file "literature.db" to
keep all the notes. The images are saved in the folder 'img/' with a format
'bibkey_xxxxx.png'. Everything is saved locally.

