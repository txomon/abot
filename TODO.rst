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


Backend plugin
--------------

Because it's now multibackend, we need to figure out a way to register the
backends and make them work separately from the bot, sending the bot events
in some way. Or at least to make the bot run them.

Need to figure out how to do the addressing to them, and need to find a way
to abstract the inner-workings of each backend to the client.

We also need to find a way to provide configuration to the backends.

Get ideas from Mopidy maybe https://www.mopidy.com/

Related to this, need to extend the base models to support most of the
features from any backend. Slack is the most challenging because you can
generate subthreads in a message, where people can interact with each other.
