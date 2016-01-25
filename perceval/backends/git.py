# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 Bitergia
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
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
#
# Authors:
#     Santiago Dueñas <sduenas@bitergia.com>
#

import json
import logging
import re

from ..errors import ParseError
from ..backend import Backend, BackendCommand, metadata


logger = logging.getLogger(__name__)


def get_update_time(item):
    """Extracts the update time from a Git item"""
    return item['CommitDate']


class Git(Backend):
    """Git backend.

    This class allows the fetch the commits from a Git log file.
    To initialize this class, the file path to the log file must be
    provided.

    :param gitlog: path to the log file
    :param cache: cache object to store raw data
    """
    version = '0.1.0'

    def __init__(self, gitlog, cache=None):
        super().__init__(gitlog, cache=cache)
        self.gitlog = gitlog

    @metadata(get_update_time)
    def fetch(self):
        """Fetch the commits from the log file.

        The method retrieves, from a Git log file, the commits listed
        on that file.

        By default, it returns the commits in reverse order or in other
        words, commits from oldest to newest. This means that the log
        needs to be parsed before returning any commit, in order to ensure
        the log history.

        :returns: a generator of commits
        """
        logger.info("Fetching commits: '%s' git log", self.gitlog)

        ncommits = 0

        commits = [commit for commit in self.parse_git_log(self.gitlog)]
        commits.reverse()

        for commit in commits:
            yield commit
            ncommits += 1

        logger.info("Fetch process completed: %s commits fetched",
                    ncommits)

    @staticmethod
    def parse_git_log(filepath):
        """Parse a Git log file.

        The method parses the Git log file and returns an iterator of
        dictionaries. Each one of this, contains a commit.

        :param filpath: path to the log file

        :returns: a generator of parsed commits

        :raises ParseError: raised when the format of the Git log file
            is invalid
        :raises IOError: raised when an error occurs reading the
            given file
        """
        with open(filepath, 'r') as f:
            parser = GitParser(f)

            for commit in parser.parse():
                yield commit


class GitCommand(BackendCommand):
    """Class to run Git backend from the command line."""

    def __init__(self, *args):
        super().__init__(*args)

        self.gitlog = self.parsed_args.gitlog
        self.outfile = self.parsed_args.outfile

        cache = None

        self.backend = Git(self.gitlog, cache=cache)

    def run(self):
        """Fetch and print the commits.

        This method runs the backend to fetch the commits from the given
        git log. Commits are converted to JSON objects and printed to the
        defined output.
        """
        commits = self.backend.fetch()

        try:
            for commit in commits:
                obj = json.dumps(commit, indent=4, sort_keys=True)
                self.outfile.write(obj)
                self.outfile.write('\n')
        except IOError as e:
            raise RuntimeError(str(e))
        except Exception as e:
            raise RuntimeError(str(e))

    @classmethod
    def create_argument_parser(cls):
        """Returns the Git argument parser."""

        parser = super().create_argument_parser()

        # Required arguments
        parser.add_argument('gitlog',
                            help="Path to the Git log file")

        return parser


class GitParser:
    """Git log parser.

    This class parses a plain Git log stream, converting plain commits
    into dict items.

    Not every Git log output is valid to be parsed. The Git log stream
    must have a specific structure. It must contain raw commits data and
    stats about modified files. The next excerpt shows an example of a
    valid log:

        commit aaa7a9209f096aaaadccaaa7089aaaa3f758a703
        Author:     John Smith <jsmith@example.com>
        AuthorDate: Tue Aug 14 14:30:13 2012 -0300
        Commit:     John Smith <jsmith@example.com>
        CommitDate: Tue Aug 14 14:30:13 2012 -0300

            Commit for testing

        :000000 100644 0000000... aaaaaaa... A	aaa/otherthing
        :000000 100644 0000000... aaaaaaa... A	aaa/something
        :000000 100644 0000000... aaaaaaa... A	bbb/bthing
        0	0	aaa/otherthing
        0	0	aaa/something
        0	0	bbb/bthing

    Each commit starts with the 'commit' tag that is followed by the
    SHA-1 of the commit, its parents (two or more parents in the case
    of a merge) and a list of refs, if any.

        commit 456a68ee1407a77f3e804a30dff245bb6c6b872f
               ce8e0b86a1e9877f42fe9453ede418519115f367
               51a3b654f252210572297f47597b31527c475fb8
               (HEAD -> refs/heads/master)

    The commit line is followed by one or more headers. Each header
    has a key and a value:

        Author:     John Smith <jsmith@example.com>
        AuthorDate: Tue Aug 14 14:30:13 2012 -0300
        Commit:     John Smith <jsmith@example.com>
        CommitDate: Tue Aug 14 14:30:13 2012 -0300

    Then, an empty line divides the headers from the commit message.

        First line of the commit

        Commit message splitted into one or several lines.
        Each line of the message stars with 4 spaces.

    After a new empty line, actions and stats over files can be found.
    A action line starts with one or more ':' chars and contain data
    about the old and new permissions of a file, its old and new indexes,
    the action code and the filepath to the file. In the case of a copied,
    renamed or moved file, the new filepath to that file is included.

        :100644 100644 e69de29... e69de29... R100	aaa/otherthing	aaa/otherthing.renamed

    Stats lines include the number of lines added and removed, and the
    name of the file. The new name is also included for moved or renamed
    files.

        10	0	aaa/{otherthing => otherthing.renamed}

    The commit ends with an empty line.

    This example was generated using the next command:

        git log --raw --numstat --pretty=fuller --decorate=full \
                --parents -M -C -c --remotes=origin --all

    :param stream: a file object which stores the log
    """
    COMMIT_PATTERN = r"""^commit[ \t](?P<commit>[a-f0-9]{40})
                     (?:[ \t](?P<parents>[a-f0-9][a-f0-9 \t]+))?
                     (?:[ \t]\((?P<refs>.+)\))?$
                     """

    HEADER_PATTERN = r"^(?P<header>[a-zA-z0-9]+)\:[ \t]+(?P<value>.+)$"

    MESSAGE_LINE_PATTERN = r"^[\s]{4}(?P<msg>.*)$"

    ACTION_PATTERN = r"""^(?P<sc>\:+)
                      (?P<modes>(?:\d{6}[ \t])+)
                      (?P<indexes>(?:[a-f0-9]+\.{,3}[ \t])+)
                      (?P<action>[^\t]+)\t+
                      (?P<file>[^\t]+)
                      (?:\t+(?P<newfile>.+))?$"""

    STATS_PATTERN = r"^(?P<added>\d+|-)[ \t]+(?P<removed>\d+|-)[ \t]+(?P<file>.+)$"

    EMPTY_LINE_PATTERN = r"^$"

    # Compiled patterns
    GIT_COMMIT_REGEXP = re.compile(COMMIT_PATTERN, re.VERBOSE)
    GIT_HEADER_REGEXP = re.compile(HEADER_PATTERN, re.VERBOSE)
    GIT_MESSAGE_REGEXP = re.compile(MESSAGE_LINE_PATTERN, re.VERBOSE)
    GIT_ACTION_REGEXP = re.compile(ACTION_PATTERN, re.VERBOSE)
    GIT_STATS_REGEXP = re.compile(STATS_PATTERN, re.VERBOSE)
    GIT_NEXT_STATE_REGEXP = re.compile(EMPTY_LINE_PATTERN, re.VERBOSE)

    # Git parser status
    (COMMIT,
     HEADER,
     MESSAGE,
     FILE) = range(4)

    def __init__(self, stream):
        self.stream = stream
        self.nline = 0
        self.state = self.COMMIT

        # Aux vars to store the commit that is being parsed
        self.commit = None
        self.commit_files = {}

        self.handlers = {
            self.COMMIT : self._handle_commit,
            self.HEADER : self._handle_header,
            self.MESSAGE : self._handle_message,
            self.FILE : self._handle_file
        }

    def parse(self):
        """Parse the Git log stream."""

        for line in self.stream:
            line = line.rstrip('\n')
            parsed = False
            self.nline += 1

            while not parsed:
                parsed = self.handlers[self.state](line)

                if self.state == self.COMMIT:
                    commit = self._build_commit()
                    logger.debug("Commit %s parsed", commit['commit'])
                    yield commit

        # Check the state of the last parsed commit
        if self.commit:
            if self.state in (self.COMMIT, self.HEADER):
                msg = "unexpected end of log stream"
                raise ParseError(cause=msg)

            commit = self._build_commit()
            logger.debug("Commit %s parsed", commit['commit'])
            yield commit

    def _build_commit(self):
        def remove_none_values(d):
            return {k: v for k, v in d.items() if v != None}

        commit = self.commit
        commit = remove_none_values(commit)
        commit['files'] = [remove_none_values(item) \
                           for _, item in sorted(self.commit_files.items())]

        self.commit = None
        self.commit_files = {}

        return commit

    def _handle_commit(self, line):
        m = self.GIT_COMMIT_REGEXP.match(line)
        if not m:
            msg = "commit expected on line %s" % (str(self.nline))
            raise ParseError(cause=msg)

        parents = self.__parse_data_list(m.group('parents'))
        refs = self.__parse_data_list(m.group('refs'), sep=',')

        # Initialize a new commit
        self.commit = {}
        self.commit['commit'] = m.group('commit')
        self.commit['parents'] = parents
        self.commit['refs'] = refs

        self.state = self.HEADER

        return True

    def _handle_header(self, line):
        m = self.GIT_NEXT_STATE_REGEXP.match(line)
        if m:
            self.state = self.MESSAGE
            return True

        m = self.GIT_HEADER_REGEXP.match(line)
        if not m:
            msg = "invalid header format on line %s" % (str(self.nline))
            raise ParseError(cause=msg)

        header = m.group('header')
        value = m.group('value')
        self.commit[header] = value

        return True

    def _handle_message(self, line):
        m = self.GIT_NEXT_STATE_REGEXP.match(line)
        if m:
            self.state = self.FILE
            return True

        m = self.GIT_MESSAGE_REGEXP.match(line)
        if not m:
            logger.debug("Invalid message format on line %s. Skipping.",
                         str(self.nline))
            self.state = self.FILE
            return False

        # Concatenate message lines
        if not 'message' in self.commit:
            self.commit['message'] = ''
        else:
            self.commit['message'] += '\n'
        self.commit['message'] += m.group('msg')

        return True

    def _handle_file(self, line):
        m = self.GIT_NEXT_STATE_REGEXP.match(line)
        if m:
            self.state = self.COMMIT
            return True

        m = self.GIT_ACTION_REGEXP.match(line)
        if m:
            data = m.groupdict()
            self._handle_action_data(data)
            return True

        m = self.GIT_STATS_REGEXP.match(line)
        if m:
            data = m.groupdict()
            self._handle_stats_data(data)
            return True

        # No match case
        logger.debug("Invalid action format on line %s. Skipping.",
                     str(self.nline))
        self.state = self.COMMIT
        return False

    def _handle_action_data(self, data):
        modes = self.__parse_data_list(data['modes'])
        indexes = self.__parse_data_list(data['indexes'])
        filename = data['file']

        if filename not in self.commit_files:
            self.commit_files[filename] = {}

        self.commit_files[filename]['modes'] = modes
        self.commit_files[filename]['indexes'] = indexes
        self.commit_files[filename]['action'] = data['action']
        self.commit_files[filename]['file'] = filename
        self.commit_files[filename]['newfile'] = data['newfile']

    def _handle_stats_data(self, data):
        filename = self.__get_old_filepath(data['file'])

        if filename not in self.commit_files:
            self.commit_files[filename] = {}

        self.commit_files[filename]['added'] = data['added']
        self.commit_files[filename]['removed'] = data['removed']

    def __parse_data_list(self, data, sep=' '):
        if data:
            l = data.strip().split(sep)
            return [e.strip() for e in l]
        else:
            return []

    def __get_old_filepath(self, f):
        """Get the old filepath of a moved/renamed file.

        Moved or renamed files can be found in the log with the next
        patterns: '{old_prefix => new_prefix}/name' or
        'name/{old_suffix => new_suffix}'. This method returns the
        filepath before the file was moved or renamed.
        """
        i = f.find('{')
        j = f.find('}')

        if i > -1 and j > -1:
            prefix = f[0:i]
            inner = f[i+1:f.find(' => ', i)]
            suffix = f[j+1:]
            return prefix + inner + suffix
        else:
            return f
