.. _howto_pkg:

How to produce Pypi packages
============================

These are instructions for producing packages of this module for Pypi.
The first step is to produce pip packages. Then, they may be uploaded to Pypi.

How to produce packages for pip
-------------------------------

For producing packages suitable for installation with pip, just follow these
instructions:

* Install the wheel Python module, if you want to create a wheel for a package.
This is recommended, but not needed if you only intend to create a source code
package.

::

  pip install wheel

* If you don't have it installed, install support for pandoc, both at the
operating system level (the Pandoc package) and at the python level
(the pypandoc Python module). This is really not required, but is needed
to convert the README.md file to reStructuredText, which is the format that
Pypi seems to like. The apt-get command below works in Debian, Ubuntu, and
other Debian derivatives, substitute by the installation command for your
operating system.

::

  sudo apt-get install pandoc
  pip install pypandoc

* In the root directory for this source code (the root of the cloned git
repository, for example) create the packages. First command below is for
creating a source code package, second is for creating a wheel for your
environment.

::

  python3 setup.py bdist_wheel
  python3 setup.py sdist

That's it. Your packages (source code and wheel) are now in the dist directory.

How to upload packages to Pypi
------------------------------

* First, upload pacakges to the test Pypi repository, to check that everything
is in working condition:

::

  python setup.py register -r pypitest
  python setup.py sdist upload -r pypitest
  python setup.py bdist_wheel upload -r pypitest

Now, you can check that the package is working by installing it in a clean
virtual environment. For example, using pyvenv:

::

  pyvenv test-perceval
  source test-perceval/bin/activate
  pip install -i https://testpypi.python.org/pypi perceval

Warning: since the test Pypi repository includes only some packages, it is
very likely that some dependencies have to be installed from the live Pypi
repository.

More details about the test Pypi repository in the `Python wiki
<https://wiki.python.org/moin/TestPyPI>`_.

* Then, upload to the live Pypi repository, and you're done (there is
no need to register in this case):

::

  python setup.py sdist upload -r pypi
  python setup.py bdist_wheel upload -r pypi

The complete instructions can be found at `How to submit a package to PyPI
<http://peterdowns.com/posts/first-time-with-pypi.html>`_.
