List of things ToDo
===================

So, now that there are bindings to another backend apart from slack. There are
a few things to be done.

Pattern matching
----------------

Commands, being a subset of all the things that can come to the bot, have
really special treatment. They need to be matched and checked for correctness
before passing them to the handlers.

After having solutions using shlex, regexp, etc. Taking click
(http://click.pocoo.org/6/) to do that heavy work for us seems quite appealing.

Commands have a singularity that makes them different from the rest, and is
that they always start with a reference to the bot. Making them similar to
command-line calls.

Part of this work is not only to glue the doings of click to the library, but
also to provide a way to match the initial name.


Dubtrack datamodel corrections
------------------------------

Right now there are some simplifications that have been done in the data model
and there is a need to value how important they are.

 1. Dubtrack backend only works on one channel at once. Therefore multiple
 dubtrack backends need to be specified if it's desired to have more than one
 room

 2. Using 1., it has been assumed that the user-queue is the user, therefore
 all the stats of the queue (dubs, playedtimes) are assumed to be from the
 user, Need to value if it's worth the refactoring

 3. The code is extremely unclean and overlapped on the binding part, it
 needs restructuring and documentation of the process that is to be followed,
 it also lacks many functions to make actions.

