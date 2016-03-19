Contributing
============

We welcome your contributions, as long as they are under the same license that covers the rest of Perceval.

Quick start for contributing
----------------------------

These are the basic steps to set up a developing and testing environment to contribute with code, using GitHub facilities. You can read more details about how to contribute to a project in GitHub in `How to GitHub: Fork, Branch, Track, Squash and Pull Request <https://gun.io/blog/how-to-github-fork-branch-and-pull-request/>`_

1. Fork the Perceval repository in GitHub. You can use the GitHub web interface for this. The result will be a new repository with the rest of your repositories, which is a fork (copy) of Perceval.

2. Clone the forked git repository, and create in a local branch for your contribution. In this repository, set up a remote for the upstream (Perceval original) git repository (below, this will be upstream). If in doubt of its convenience or how to better implement it, open a GitHub issue, and comment there.

3. Once your contribution is ready, rebase your local branch with upstream/master, so that it merges clean with that branch, and push your local branch to a remote branch in your GitHub repository. Except that the contribution really needs it, use a single commit, and comment in detail in the corresponfing commit message what it is intended to do. If it fixes some bug, refence it (with the text "Fixes #23", for example, for issue number 23).

4. In the GitHub interface, produce a pull request from your branch (you will see an option to do that if you visit the webpage for your own repository in GitHub). Be sure of including a reasonble comment with the pull request.

5. Visit frequently the pull request in GitHub, to attend to comments and requests by Perceval developers (or watch it via email). Please keep in mind tha the pull request will be merged into the codebase only if those comments and requests are addressed.

Contributing code
-----------------

Please, follow this advise before proposing a pull request with your contribution:

* Perceval is intended to be written for Python3. It should work with Python 3.4 or newer.

* Be sure that all tests (in directory tests) are passed without errors.

* Whenever convenient, write tests for your contribution, and add it in that directory. Have in mind that usually, adding tests is convenient, and will likely be required by reviewers of your pull request before considering it for a merge.

* Follow the guidelines in `PEP-8 (Style Guide for Python Code) <https://www.python.org/dev/peps/pep-0008/>`_ as much as possible.

Contributing documentation
--------------------------

For documentation, we use reStructuredText, both in comments in the code, and in the manual.

A good reference to reStructuredText can be found in the `reStructuredText Markup Specification <http://docutils.sourceforge.net/docs/ref/rst/restructuredtext.html>`_

You can learn how to produce documentation from the reStructuredText content in :ref:`howto_doc`.
