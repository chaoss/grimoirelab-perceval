How to produce documentation for this software using Sphinx
===========================================================

If there is no change in the list of modules:

* Fix sys.path.insert in docs/conf.py, by adding the paths that must be included in PYHTONPATH to import all modules needed by those to be documented.
* Run:

::

   cd docs
   make html

This will try to build all HTML content in html directory under BUILDDIR, as defined in docs/Makefile (which should exist). Therefore, change that variable to your taste.

If there are changes in the list of modules:

::

   cd docs
   sphinx-apidoc --force -d 4 -o . ../percevalsphinx-apidoc --force -d 4 -o . ../perceval
   make html

More information about documenting with Sphinx

* `reStructuredText Primer <http://sphinx-doc.org/rest.html>`_
* `Publishing sphinx-generated docs on github <http://daler.github.io/sphinxdoc-test/includeme.html>`_
