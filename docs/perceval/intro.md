# Perceval

[Perceval](https://github.com/chaoss/grimoirelab-perceval) is a Python module for
retrieving data from repositories related to software development. It works with many data
sources, from git repositories and GitHub projects to mailing lists, Gerrit or
StackOverflow, In this chapter, you will learn the basics of working with Perceval,
including how to use it to retrieve information from some kinds of repositories. You’re on
your way to software development analysis!

Before starting, ensure that you have Python3 ready, and the Perceval module installed, as
detailed below:

#### Installing Perceval

In an activated virtual environment we will use pip3 to install the module from the [Pypi
archive](https://pypi.python.org/pypi).

```
(gl) $ pip3 install perceval
```

This will install Perceval and its dependencies (other Python modules that are needed by
Perceval to work). So, we’re ready to see what it can do.

Once Perceval is installed, we can check that the installation went well. For starters,
you can use the `perceval` script, which should have been installed, since it comes with
the Perceval package. It is a simple front-end to the Perceval module, which gets data
from a data source, and writes what it finds as JSON documents in stdout. To learn about
its command line arguments, just use the `--help` flag:

```
(gl) $ perceval --help
```

This should produce a banner with information about command line arguments, and a listing
of Perceval backends. If that banner doesn’t show up, it is likely that something wrong
happened during the installation.

Assuming everything was fine, next thing is getting information about an specific backend.
Let’s start with the git backend, which will be a good starter for testing:

```
(gl) $ perceval git --help
```

If this shows a banner with information about how to use the Perceval git backend, we can
assume that Perceval and all its dependencies were installed appropriately.
