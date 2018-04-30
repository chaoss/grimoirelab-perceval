# -*- coding: utf-8 -*-
#
# Copyright (C) 2015-2018 Bitergia
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, 51 Franklin Street, Fifth Floor, Boston, MA 02110-1335, USA.
#
# Authors:
#     Valerio Cosentino <valcos@bitergia.com>
#

import logging
import os

from perceval.backends.core.graal import (Graal,
                                          GraalRepository,
                                          GraalCommand,
                                          DEFAULT_WORKTREE_PATH)
from perceval.backends.analyzers.cloc import Cloc
from perceval.backends.analyzers.lizard import Lizard
from ...backend import BackendCommandArgumentParser
from ...utils import DEFAULT_DATETIME, DEFAULT_LAST_DATETIME

CATEGORY_CODE_ANALYSIS = 'code_complexity'

logger = logging.getLogger(__name__)


class CodeComplexity(Graal):
    """CodeComplexity backend.

    This class extends the Graal backend. It gathers
    insights about code complexity, such as cyclomatic complexity,
    number of functions and lines of code of a several programming
    languages.

    :param uri: URI of the Git repository
    :param gitpath: path to the repository or to the log file
    :param worktreepath: the directory where to store the working tree
    :param tag: label used to mark the data
    :param archive: archive to store/retrieve items

    :raises RepositoryError: raised when there was an error cloning or
        updating the repository.
    """
    version = '0.1.0'

    CATEGORIES = [CATEGORY_CODE_ANALYSIS]

    def __init__(self, uri, git_path, worktreepath=DEFAULT_WORKTREE_PATH, functions=False,
                 tag=None, archive=None):
        super().__init__(uri, git_path, worktreepath, tag=tag, archive=archive)
        self.file_analyser = FileAnalyser(functions)

    def fetch(self, category=CATEGORY_CODE_ANALYSIS, paths=None,
              from_date=DEFAULT_DATETIME, to_date=DEFAULT_LAST_DATETIME,
              branches=None, latest_items=False):
        """Fetch commits and add code complexity information."""

        items = super().fetch(category, paths=paths,
                              from_date=from_date, to_date=to_date,
                              branches=branches, latest_items=latest_items)

        return items

    @staticmethod
    def metadata_category(item):
        """Extracts the category from a Code item.

        This backend only generates one type of item which is
        'commit'.
        """
        return CATEGORY_CODE_ANALYSIS

    def _filter_commit(self, commit, paths=None):
        """Filter the commits that do not contain the paths

        :param commit: a Perceval commit item
        :param paths: a list of paths to drive the filtering

        :returns: a boolean value
        """
        for f in commit['files']:
            for p in paths:
                if f['file'].endswith(p):
                    return False

        return True

    def _analyse(self, commit, paths=None):
        """Analyse a commit and the corresponding
        checkout version of the repository

        :param commit: a Perceval commit item
        :param paths: a list of paths to narrow the analysis
        """
        files = GraalRepository.files(self.worktreepath)
        analysis = []

        for f in files:

            found = [p for p in paths if f.endswith(p)]
            if not found:
                continue

            file_path = os.path.join(self.worktreepath, f)
            file_info = self.file_analyser.analyse(file_path)
            file_info.update({'file_path': f})
            analysis.append(file_info)

        return analysis

    def _post(self, commit):
        """Remove attributes of the Graal item obtained

        :param commit: a Graal commit item
        """
        commit.pop('Author', None)
        commit.pop('Commit', None)
        commit.pop('files', None)
        commit.pop('parents', None)
        commit.pop('refs', None)
        return commit


class FileAnalyser:
    """Class to analyse the content of files"""

    ALLOWED_EXTENSIONS = ['java', 'py', 'php', 'scala', 'js', 'rb', 'cs', 'cpp', 'c']
    FORBIDDEN_EXTENSIONS = ['tar', 'bz2', "gz", "lz", "apk", "tbz2",
                            "lzma", "tlz", "war", "xar", "zip", "zipx"]

    def __init__(self, functions):
        self.functions = functions
        self.cloc = Cloc()
        self.lizard = Lizard()

    def analyse(self, file_path):
        """Analyse the content of a file using CLOC and Lizard

        :param file_path: file path
        """
        result = {'blanks': None,
                  'comments': None,
                  'loc': None,
                  'ccn': None,
                  'avg_ccn': None,
                  'avg_loc': None,
                  'avg_tokens': None,
                  'funs': None,
                  'tokens': None,
                  'funs_data': []}

        kwargs = {'file_path': file_path}
        cloc_analysis = self.cloc.analyze(**kwargs)

        if GraalRepository.extension(file_path) not in self.ALLOWED_EXTENSIONS:
            return cloc_analysis

        kwargs['functions'] = self.functions
        lizard_analysis = self.lizard.analyze(**kwargs)
        # the LOC returned by CLOC is replaced by the one obtained with Lizard
        # for consistency purposes

        lizard_analysis['blanks'] = cloc_analysis['blanks']
        lizard_analysis['comments'] = cloc_analysis['comments']

        return lizard_analysis


class CodeComplexityCommand(GraalCommand):
    """Class to run CodeComplexity backend from the command line."""

    BACKEND = CodeComplexity

    @staticmethod
    def setup_cmd_parser():
        """Returns the Graal argument parser."""

        parser = BackendCommandArgumentParser(from_date=True, to_date=True)

        # Optional arguments
        group = parser.parser.add_argument_group('Git arguments')
        group.add_argument('--branches', dest='branches',
                           nargs='+', type=str, default=None,
                           help="Fetch commits only from these branches")
        group.add_argument('--latest-items', dest='latest_items',
                           action='store_true',
                           help="Fetch latest commits added to the repository")
        group.add_argument('--worktree-path', dest='worktreepath',
                           default=DEFAULT_WORKTREE_PATH,
                           help="Path where to save the working tree")
        group.add_argument('--paths', dest='paths',
                           nargs='+', type=str, default=None,
                           help="Paths to narrow the analysis")
        group.add_argument('--functions', dest='functions',
                           action='store_true', default=False,
                           help="get function details")

        # Required arguments
        parser.parser.add_argument('uri',
                                   help="URI of the Git log repository")
        parser.parser.add_argument('--git-path', dest='git_path',
                                   help="Path where the Git repository will be cloned")

        return parser
