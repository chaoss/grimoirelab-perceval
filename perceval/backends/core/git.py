# -*- coding: utf-8 -*-
#
# Copyright (C) 2015-2020 Bitergia
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
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
# Authors:
#     Santiago Dueñas <sduenas@bitergia.com>
#     Valerio Cosentino <valcos@bitergia.com>
#     Israel Herraiz <israel.herraiz@bbvadata.com>
#     anveshc05 <anveshc10047@gmail.com>
#     Jesus M. Gonzalez-Barahona <jgb@gsyc.es>
#     Harshal Mittal <harshalmittal4@gmail.com>
#     Victor Morales <victor.morales@intel.com>
#     animesh <animuz111@gmail.com>
#

import collections
import io
import logging
import os
import re
import subprocess
import threading

import dulwich.client
import dulwich.repo

from grimoirelab_toolkit.datetime import datetime_to_utc, str_to_datetime

from ...backend import (Backend,
                        BackendCommand,
                        BackendCommandArgumentParser)
from ...errors import RepositoryError, ParseError
from ...utils import DEFAULT_DATETIME, DEFAULT_LAST_DATETIME

CATEGORY_COMMIT = 'commit'

logger = logging.getLogger(__name__)


class Git(Backend):
    """Git backend.

    This class allows the fetch the commits from a Git repository
    (local or remote) or from a log file. To initialize this class,
    you have to provide the URI repository and a value for `gitpath`.
    This `uri` will be set as the origin of the data.

    When `gitpath` is a directory or does not exist, it will be
    considered as the place where the repository is/will be cloned;
    when `gitpath` is a file it will be considered as a Git log file.

    :param uri: URI of the Git repository
    :param gitpath: path to the repository or to the log file
    :param tag: label used to mark the data
    :param archive: archive to store/retrieve items
    :param ssl_verify: enable/disable SSL verification

    :raises RepositoryError: raised when there was an error cloning or
        updating the repository.
    """
    version = '0.12.1'

    CATEGORIES = [CATEGORY_COMMIT]

    def __init__(self, uri, gitpath, tag=None, archive=None, ssl_verify=True):
        origin = uri

        super().__init__(origin, tag=tag, archive=archive, ssl_verify=ssl_verify)
        self.uri = uri
        self.gitpath = gitpath

    def fetch(self, category=CATEGORY_COMMIT, from_date=DEFAULT_DATETIME, to_date=DEFAULT_LAST_DATETIME,
              branches=None, latest_items=False, no_update=False):
        """Fetch commits.

        The method retrieves from a Git repository or a log file
        a list of commits. Commits are returned in the same order
        they were obtained.

        When `from_date` parameter is given it returns items committed
        since the given date.

        The list of `branches` is a list of strings, with the names of
        the branches to fetch. If the list of branches is empty, no
        commit is fetched. If the list of branches is None, all commits
        for all branches will be fetched.

        The parameter `latest_items` returns only those commits which
        are new since the last time this method was called.

        The parameter `no_update` returns all commits without performing
        an update of the repository before.

        Take into account that `from_date` and `branches` are ignored
        when the commits are fetched from a Git log file or when
        `latest_items` flag is set.

        The class raises a `RepositoryError` exception when an error
        occurs accessing the repository.

        :param category: the category of items to fetch
        :param from_date: obtain commits newer than a specific date
            (inclusive)
        :param to_date: obtain commits older than a specific date
        :param branches: names of branches to fetch from (default: None)
        :param latest_items: sync with the repository to fetch only the
            newest commits
        :param no_update: if enabled, don't update the repo with the latest changes

        :returns: a generator of commits
        """
        if not from_date:
            from_date = DEFAULT_DATETIME
        if not to_date:
            to_date = DEFAULT_LAST_DATETIME

        kwargs = {
            'from_date': from_date,
            'to_date': to_date,
            'branches': branches,
            'latest_items': latest_items,
            'no_update': no_update
        }
        items = super().fetch(category, **kwargs)

        return items

    def fetch_items(self, category, **kwargs):
        """Fetch the commits

        :param category: the category of items to fetch
        :param kwargs: backend arguments

        :returns: a generator of items
        """
        from_date = kwargs['from_date']
        to_date = kwargs['to_date']
        branches = kwargs['branches']
        latest_items = kwargs['latest_items']
        no_update = kwargs['no_update']

        ncommits = 0

        try:
            if os.path.isfile(self.gitpath):
                commits = self.__fetch_from_log()
            else:
                commits = self.__fetch_from_repo(from_date, to_date, branches,
                                                 latest_items, no_update)

            for commit in commits:
                yield commit
                ncommits += 1
        except EmptyRepositoryError:
            pass

        logger.info("Fetch process completed: %s commits fetched",
                    ncommits)

    @classmethod
    def has_archiving(cls):
        """Returns whether it supports archiving items on the fetch process.

        :returns: this backend does not support items archive
        """
        return False

    @classmethod
    def has_resuming(cls):
        """Returns whether it supports to resume the fetch process.

        :returns: this backend supports items resuming
        """
        return True

    @staticmethod
    def metadata_id(item):
        """Extracts the identifier from a Git item."""

        return item['commit']

    @staticmethod
    def metadata_updated_on(item):
        """Extracts the update time from a Git item.

        The timestamp used is extracted from 'CommitDate' field.
        This date is converted to UNIX timestamp format taking into
        account the timezone of the date.

        :param item: item generated by the backend

        :returns: a UNIX timestamp
        """
        ts = item['CommitDate']
        ts = str_to_datetime(ts)

        return ts.timestamp()

    @staticmethod
    def metadata_category(item):
        """Extracts the category from a Git item.

        This backend only generates one type of item which is
        'commit'.
        """
        return CATEGORY_COMMIT

    @staticmethod
    def parse_git_log_from_file(filepath):
        """Parse a Git log file.

        The method parses the Git log file and returns an iterator of
        dictionaries. Each one of this, contains a commit.

        :param filepath: path to the log file

        :returns: a generator of parsed commits

        :raises ParseError: raised when the format of the Git log file
            is invalid
        :raises OSError: raised when an error occurs reading the
            given file
        """
        with open(filepath, 'r', errors='surrogateescape',
                  newline=os.linesep) as f:
            parser = GitParser(f)

            for commit in parser.parse():
                yield commit

    @staticmethod
    def parse_git_log_from_iter(iterator):
        """Parse a Git log obtained from an iterator.

        The method parses the Git log fetched from an iterator, where
        each item is a line of the log. It returns and iterator of
        dictionaries. Each dictionary contains a commit.

        :param iterator: iterator of Git log lines

        :raises ParseError: raised when the format of the Git log
            is invalid
        """
        parser = GitParser(iterator)

        for commit in parser.parse():
            yield commit

    def _init_client(self, from_archive=False):
        pass

    def __fetch_from_log(self):
        logger.info("Fetching commits: '%s' git repository from log file %s",
                    self.uri, self.gitpath)
        return self.parse_git_log_from_file(self.gitpath)

    def __fetch_from_repo(self, from_date, to_date, branches, latest_items=False, no_update=False):
        # When no latest items are set or the repository has not
        # been cloned use the default mode
        default_mode = not latest_items or not os.path.exists(self.gitpath)

        repo = self.__create_git_repository()

        if default_mode:
            commits = self.__fetch_commits_from_repo(repo, from_date, to_date, branches, no_update)
        else:
            commits = self.__fetch_newest_commits_from_repo(repo)

        return commits

    def __fetch_commits_from_repo(self, repo, from_date, to_date, branches, no_update):
        if branches is None:
            branches_text = "all"
        elif len(branches) == 0:
            branches_text = "no"
        else:
            branches_text = ", ".join(branches)

        logger.info("Fetching commits: '%s' git repository from %s to %s; %s branches",
                    self.uri, str(from_date), str(to_date), branches_text)

        # Ignore default datetime to avoid problems with git
        # or convert to UTC
        if to_date == DEFAULT_LAST_DATETIME:
            to_date = None
        else:
            to_date = datetime_to_utc(to_date)

        if from_date == DEFAULT_DATETIME:
            from_date = None
        else:
            from_date = datetime_to_utc(from_date)

        if not no_update:
            repo.update()

        gitlog = repo.log(from_date, to_date, branches)
        return self.parse_git_log_from_iter(gitlog)

    def __fetch_newest_commits_from_repo(self, repo):
        logger.info("Fetching latest commits: '%s' git repository",
                    self.uri)

        hashes = repo.sync()
        if not hashes:
            return []

        gitshow = repo.show(hashes)
        return self.parse_git_log_from_iter(gitshow)

    def __create_git_repository(self):
        if not os.path.exists(self.gitpath):
            repo = GitRepository.clone(self.uri, self.gitpath, self.ssl_verify)
        elif os.path.isdir(self.gitpath):
            repo = GitRepository(self.uri, self.gitpath)
        return repo


class GitCommand(BackendCommand):
    """Class to run Git backend from the command line."""

    BACKEND = Git

    def _pre_init(self):
        """Initialize repositories directory path"""

        if self.parsed_args.git_log:
            git_path = self.parsed_args.git_log
        elif self.parsed_args.git_path:
            git_path = self.parsed_args.git_path
        else:
            if self.parsed_args.base_path:
                base_path = self.parsed_args.base_path
            else:
                base_path = os.path.expanduser('~/.perceval/repositories/')

            processed_uri = self.parsed_args.uri.lstrip('/')
            git_path = os.path.join(base_path, processed_uri) + '-git'

        setattr(self.parsed_args, 'gitpath', git_path)

    @classmethod
    def setup_cmd_parser(cls):
        """Returns the Git argument parser."""

        parser = BackendCommandArgumentParser(cls.BACKEND,
                                              from_date=True,
                                              to_date=True,
                                              ssl_verify=True)

        # Optional arguments
        group = parser.parser.add_argument_group('Git arguments')
        group.add_argument('--branches', dest='branches',
                           nargs='+', type=str, default=None,
                           help="Fetch commits only from these branches")

        # Mutual exclusive parameters
        exgroup = group.add_mutually_exclusive_group()
        exgroup.add_argument('--base-path', dest='base_path',
                             help="Base path where the Git repositories will be cloned")
        exgroup.add_argument('--git-path', dest='git_path',
                             help="Path where the Git repository will be cloned")
        exgroup.add_argument('--git-log', dest='git_log',
                             help="Path to the Git log file")

        exgroup_fetch = group.add_mutually_exclusive_group()
        exgroup_fetch.add_argument('--latest-items', dest='latest_items',
                                   action='store_true',
                                   help="Fetch latest commits added to the repository")
        exgroup_fetch.add_argument('--no-update', dest='no_update',
                                   action='store_true',
                                   help="Fetch all commits without updating the repository")

        # Required arguments
        parser.parser.add_argument('uri',
                                   help="URI of the Git log repository")

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

    Commit messages can contain a list of 'trailers'. These trailers
    have the same format of headers but their meaning is project
    dependent. This is an example of a commit message with trailers:

        Commit message with trailers

        This is the body of the message where trailers are included.
        Trailers are part of the body so each line of the message
        stars with 4 spaces.

        Signed-off-by: John Doe <jdoe@example.com>
        Signed-off-by: Jane Rae <jrae@example.com>

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

    Take into account that one empty line is valid at the beginning
    of the log. This allows to parse empty logs without raising
    exceptions.

    This example was generated using the next command:

        git log --raw --numstat --pretty=fuller --decorate=full \
                --parents -M -C -c --remotes=origin --all

    :param stream: a file object which stores the log
    """
    COMMIT_PATTERN = r"""^commit[ \t](?P<commit>[a-f0-9]{40})
                     (?:[ \t](?P<parents>[a-f0-9][a-f0-9 \t]+))?
                     (?:[ \t]\((?P<refs>.+)\))?$
                     """

    HEADER_TRAILER_PATTERN = r"^(?P<name>[a-zA-z0-9\-]+)\:[ \t]+(?P<value>.+)$"

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
    GIT_HEADER_TRAILER_REGEXP = re.compile(HEADER_TRAILER_PATTERN, re.VERBOSE)
    GIT_MESSAGE_REGEXP = re.compile(MESSAGE_LINE_PATTERN, re.VERBOSE)
    GIT_ACTION_REGEXP = re.compile(ACTION_PATTERN, re.VERBOSE)
    GIT_STATS_REGEXP = re.compile(STATS_PATTERN, re.VERBOSE)
    GIT_NEXT_STATE_REGEXP = re.compile(EMPTY_LINE_PATTERN, re.VERBOSE)

    # Git parser status
    (INIT,
     COMMIT,
     HEADER,
     MESSAGE,
     FILE) = range(5)

    # Git trailers
    TRAILERS = ['Signed-off-by']

    def __init__(self, stream):
        self.stream = stream
        self.nline = 0
        self.state = self.INIT

        # Aux vars to store the commit that is being parsed
        self.commit = None
        self.commit_files = {}

        self.handlers = {
            self.INIT: self._handle_init,
            self.COMMIT: self._handle_commit,
            self.HEADER: self._handle_header,
            self.MESSAGE: self._handle_message,
            self.FILE: self._handle_file
        }

    def parse(self):
        """Parse the Git log stream."""

        for line in self.stream:
            line = line.rstrip('\n')
            parsed = False
            self.nline += 1

            while not parsed:
                parsed = self.handlers[self.state](line)

                if self.state == self.COMMIT and self.commit:
                    commit = self._build_commit()
                    logger.debug("Commit %s parsed", commit['commit'])
                    yield commit

        # Return the last commit, if any
        if self.commit:
            commit = self._build_commit()
            logger.debug("Commit %s parsed", commit['commit'])
            yield commit

    def _build_commit(self):
        def remove_none_values(d):
            return {k: v for k, v in d.items() if v is not None}

        commit = self.commit
        commit = remove_none_values(commit)
        commit['files'] = [remove_none_values(item)
                           for _, item in sorted(self.commit_files.items())]

        self.commit = None
        self.commit_files = {}

        return commit

    def _handle_init(self, line):
        m = self.GIT_NEXT_STATE_REGEXP.match(line)

        # In both cases, the parser advances to the next state.
        # It only has to check whether the line has to be parsed
        # again or not
        self.state = self.COMMIT
        parsed = m is not None

        return parsed

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

        m = self.GIT_HEADER_TRAILER_REGEXP.match(line)
        if not m:
            msg = "invalid header format on line %s" % (str(self.nline))
            raise ParseError(cause=msg)

        header = m.group('name')
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

        msg_line = m.group('msg')

        # Concatenate message lines
        if 'message' not in self.commit:
            self.commit['message'] = ''
        else:
            self.commit['message'] += '\n'
        self.commit['message'] += msg_line

        # Check trailers
        self._handle_trailer(msg_line)

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

    def _handle_trailer(self, line):
        m = self.GIT_HEADER_TRAILER_REGEXP.match(line)
        if not m:
            return

        trailer = m.group('name')
        value = m.group('value')

        if trailer not in self.TRAILERS:
            logger.debug("Trailer %s found on line %s but is not a core trailer. Skipping.",
                         trailer, str(self.nline))
            return

        self.commit.setdefault(trailer, []).append(value)

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
            self.commit_files[filename] = {'file': filename}

        self.commit_files[filename]['added'] = data['added']
        self.commit_files[filename]['removed'] = data['removed']

    def __parse_data_list(self, data, sep=' '):
        if data:
            lst = data.strip().split(sep)
            return [e.strip() for e in lst]
        else:
            return []

    def __get_old_filepath(self, f):
        """Get the old filepath of a moved/renamed file.

        Moved or renamed files can be found in the log with any of the
        next patterns:
          'old_name => new_name'
          '{old_prefix => new_prefix}/name'
          'name/{old_suffix => new_suffix}'

        This method returns the filepath before the file was moved or
        renamed.
        """
        i = f.find('{')
        j = f.find('}')

        if i > -1 and j > -1:
            prefix = f[0:i]
            inner = f[i + 1:f.find(' => ', i)]
            suffix = f[j + 1:]
            return prefix + inner + suffix
        elif ' => ' in f:
            return f.split(' => ')[0]
        else:
            return f


class EmptyRepositoryError(RepositoryError):
    """Exception raised when a repository is empty"""

    message = "%(repository)s is empty"


GitRef = collections.namedtuple('GitRef', ['hash', 'refname'])


class _GraphWalker:
    """Commit walker needed by fetch_pack"""

    def __init__(self, local_refs):
        self.heads = [
            ref.hash.encode('utf-8') for ref in local_refs
            if ref.refname.startswith('refs/heads/')
        ]

    def ack(self, sha):
        pass

    def next(self):
        if self.heads:
            ret = self.heads.pop()
            return ret
        return None

    __next__ = next


class GitRepository:
    """Manage a Git repository.

    This class provides access to a Git repository running some
    common commands such as `clone`, `pull` or `log`.
    To create an instance from a remote repository, use `clone()`
    class method.

    :param uri: URI of the repository
    :param dirpath: local directory where the repository is stored
    """
    GIT_PRETTY_OUTPUT_OPTS = [
        '--raw',  # show data in raw format
        '--numstat',  # show added/deleted lines per file
        '--pretty=fuller',  # pretty output
        '--decorate=full',  # show full refs
        '--parents',  # show parents information
        '-M',  # detect and report renames
        '-C',  # detect and report copies
        '-c',  # show merge info
    ]

    def __init__(self, uri, dirpath):
        gitdir = os.path.join(dirpath, 'HEAD')

        if not os.path.exists(dirpath):
            cause = "directory '%s' for Git repository '%s' does not exist" % (dirpath, uri)
            raise RepositoryError(cause=cause)
        elif not os.path.exists(gitdir):
            warning = "Working directories for Git repositories no longer supported." \
                "Please remove it or clone it using --mirror option."
            logger.warning(warning)
            cause = "directory '%s' is not a Git mirror of repository '%s'" % (dirpath, uri)
            raise RepositoryError(cause=cause)

        self.uri = uri
        self.dirpath = dirpath
        self.gitenv = {
            'LANG': 'C',
            'PAGER': '',
            'HTTP_PROXY': os.getenv('HTTP_PROXY', ''),
            'HTTPS_PROXY': os.getenv('HTTPS_PROXY', ''),
            'NO_PROXY': os.getenv('NO_PROXY', ''),
            'HOME': os.getenv('HOME', '')
        }

    @classmethod
    def clone(cls, uri, dirpath, ssl_verify=True):
        """Clone a Git repository.

        Make a bare copy of the repository stored in `uri` into `dirpath`.
        The repository would be either local or remote.

        :param uri: URI of the repository
        :param dirpath: directory where the repository will be cloned
        :param ssl_verify: enable/disable SSL verification

        :returns: a `GitRepository` class having cloned the repository

        :raises RepositoryError: when an error occurs cloning the given
            repository
        """
        cmd = ['git', 'clone', '--bare', uri, dirpath]
        if not ssl_verify:
            cmd += ['-c', 'http.sslVerify=false']
        env = {
            'LANG': 'C',
            'HOME': os.getenv('HOME', '')
        }

        cls._exec(cmd, env=env)

        logger.debug("Git %s repository cloned into %s",
                     uri, dirpath)

        return cls(uri, dirpath)

    def count_objects(self):
        """Count the objects of a repository.

        The method returns the total number of objects (packed and unpacked)
        available on the repository.

        :raises RepositoryError: when an error occurs counting the objects
            of a repository
        """
        cmd_count = ['git', 'count-objects', '-v']

        outs = self._exec(cmd_count, cwd=self.dirpath, env=self.gitenv)
        outs = outs.decode('utf-8', errors='surrogateescape').rstrip()

        try:
            cobjs = {k: v for k, v in (x.split(': ') for x in outs.split('\n'))}
            nobjs = int(cobjs['count']) + int(cobjs['in-pack'])
        except KeyError as e:
            error = "unable to parse 'count-objects' output; reason: '%s' entry not found" \
                % e.args[0]
            raise RepositoryError(cause=error)
        except ValueError as e:
            error = "unable to parse 'count-objects' output; reason: %s" % str(e)
            raise RepositoryError(cause=error)

        logger.debug("Git %s repository has %s objects",
                     self.uri, str(nobjs))

        return nobjs

    def is_detached(self):
        """Check if the repo is in a detached state.

        The repository is in a detached state when HEAD is not a symbolic
        reference.

        :returns: whether the repository is detached or not

        :raises RepositoryError: when an error occurs checking the state
            of the repository
        """
        cmd_sym = ['git', 'symbolic-ref', 'HEAD']

        try:
            self._exec(cmd_sym, cwd=self.dirpath, env=self.gitenv)
        except RepositoryError as e:
            if e.msg.find("ref HEAD is not a symbolic ref") == -1:
                raise e
            return True
        else:
            return False

    def is_empty(self):
        """Determines whether the repository is empty or not.

        Returns `True` when the repository is empty. Under the hood,
        it checks the number of objects on the repository. When
        this number is 0, the repositoy is empty.

        :raises RepositoryError: when an error occurs accessing the
            repository
        """
        return self.count_objects() == 0

    def update(self):
        """Update repository from its remote.

        Calling this method, the repository will be synchronized with
        the remote repository using 'fetch' command for 'heads' refs.
        Any commit stored in the local copy will be removed; refs
        will be overwritten.

        :raises RepositoryError: when an error occurs updating the
            repository
        """
        cmd_update = ['git', 'fetch', 'origin', '+refs/heads/*:refs/heads/*', '--prune']
        self._exec(cmd_update, cwd=self.dirpath, env=self.gitenv)

        logger.debug("Git %s repository updated into %s",
                     self.uri, self.dirpath)

    def sync(self):
        """Keep the repository in sync.

        This method will synchronize the repository with its 'origin',
        fetching newest objects and updating references. It uses low
        level commands which allow to keep track of which things
        have changed in the repository.

        The method also returns a list of hashes related to the new
        commits fetched during the process.

        :returns: list of new commits

        :raises RepositoryError: when an error occurs synchronizing
            the repository
        """
        pack_name, refs = self._fetch_pack()

        if pack_name:
            commits = self._read_commits_from_pack(pack_name)
        else:
            commits = []
            logger.debug("Git repository %s (%s) does not have any new object",
                         self.uri, self.dirpath)

        self._update_references(refs)

        logger.debug("Git repository %s (%s) is synced",
                     self.uri, self.dirpath)

        return commits

    def rev_list(self, branches=None):
        """Read the list commits from the repository

        The list of branches is a list of strings, with the names of the
        branches to fetch. If the list of branches is empty, no commit
        is fetched. If the list of branches is None, all commits
        for all branches will be fetched.

        The method returns the Git rev-list of the repository using the
        following options:

            git rev-list --topo-order

        :param branches: names of branches to fetch from (default: None)

        :raises EmptyRepositoryError: when the repository is empty and
            the action cannot be performed
        :raises RepositoryError: when an error occurs executing the command
        """
        if self.is_empty():
            logger.warning("Git %s repository is empty; unable to get the rev-list",
                           self.uri)
            raise EmptyRepositoryError(repository=self.uri)

        cmd_rev_list = ['git', 'rev-list', '--topo-order']

        if branches is None:
            cmd_rev_list.extend(['--branches', '--tags', '--remotes=origin'])
        elif len(branches) == 0:
            cmd_rev_list.extend(['--branches', '--tags', '--max-count=0'])
        else:
            branches = ['refs/heads/' + branch for branch in branches]
            cmd_rev_list.extend(branches)

        for line in self._exec_nb(cmd_rev_list, cwd=self.dirpath, env=self.gitenv):
            yield line.rstrip('\n')

        logger.debug("Git rev-list fetched from %s repository (%s)",
                     self.uri, self.dirpath)

    def log(self, from_date=None, to_date=None, branches=None, encoding='utf-8'):
        """Read the commit log from the repository.

        The method returns the Git log of the repository using the
        following options:

            git log --raw --numstat --pretty=fuller --decorate=full
                --all --reverse --topo-order --parents -M -C -c
                --remotes=origin

        When `from_date` is given, it gets the commits equal or older
        than that date. This date is given in a datetime object.

        The list of branches is a list of strings, with the names of the
        branches to fetch. If the list of branches is empty, no commit
        is fetched. If the list of branches is None, all commits
        for all branches will be fetched.

        :param from_date: fetch commits newer than a specific
            date (inclusive)
        :param branches: names of branches to fetch from (default: None)
        :param encoding: encode the log using this format

        :returns: a generator where each item is a line from the log

        :raises EmptyRepositoryError: when the repository is empty and
            the action cannot be performed
        :raises RepositoryError: when an error occurs fetching the log
        """
        if self.is_empty():
            logger.warning("Git %s repository is empty; unable to get the log",
                           self.uri)
            raise EmptyRepositoryError(repository=self.uri)

        cmd_log = ['git', 'log', '--reverse', '--topo-order']
        cmd_log.extend(self.GIT_PRETTY_OUTPUT_OPTS)

        if from_date:
            dt = from_date.strftime("%Y-%m-%d %H:%M:%S %z")
            cmd_log.append('--since=' + dt)

        if to_date:
            dt = to_date.strftime("%Y-%m-%d %H:%M:%S %z")
            cmd_log.append('--until=' + dt)

        if branches is None:
            cmd_log.extend(['--branches', '--tags', '--remotes=origin'])
        elif len(branches) == 0:
            cmd_log.append('--max-count=0')
        else:
            branches = ['refs/heads/' + branch for branch in branches]
            cmd_log.extend(branches)

        for line in self._exec_nb(cmd_log, cwd=self.dirpath, env=self.gitenv):
            yield line

        logger.debug("Git log fetched from %s repository (%s)",
                     self.uri, self.dirpath)

    def show(self, commits=None, encoding='utf-8'):
        """Show the data of a set of commits.

        The method returns the output of Git show command for a
        set of commits using the following options:

            git show --raw --numstat --pretty=fuller --decorate=full
                --parents -M -C -c [<commit>...<commit>]

        When the list of commits is empty, the command will return
        data about the last commit, like the default behaviour of
        `git show`.

        :param commits: list of commits to show data
        :param encoding: encode the output using this format

        :returns: a generator where each item is a line from the show output

        :raises EmptyRepositoryError: when the repository is empty and
            the action cannot be performed
        :raises RepositoryError: when an error occurs fetching the show output
        """
        if self.is_empty():
            logger.warning("Git %s repository is empty; unable to run show",
                           self.uri)
            raise EmptyRepositoryError(repository=self.uri)

        if commits is None:
            commits = []

        cmd_show = ['git', 'show']
        cmd_show.extend(self.GIT_PRETTY_OUTPUT_OPTS)
        cmd_show.extend(commits)

        for line in self._exec_nb(cmd_show, cwd=self.dirpath, env=self.gitenv):
            yield line

        logger.debug("Git show fetched from %s repository (%s)",
                     self.uri, self.dirpath)

    def _fetch_pack(self):
        """Fetch changes and store them in a pack."""

        def prepare_refs(refs):
            return [ref.hash.encode('utf-8') for ref in refs
                    if not ref.refname.endswith('^{}')]

        def determine_wants(refs):
            remote_refs = prepare_refs(self._discover_refs(remote=True))
            local_refs = prepare_refs(self._discover_refs())
            wants = [ref for ref in remote_refs if ref not in local_refs]
            return wants

        client, repo_path = dulwich.client.get_transport_and_path(self.uri)
        repo = dulwich.repo.Repo(self.dirpath)
        fd = io.BytesIO()

        local_refs = self._discover_refs()
        graph_walker = _GraphWalker(local_refs)

        result = client.fetch_pack(repo_path,
                                   determine_wants,
                                   graph_walker,
                                   fd.write)
        refs = [GitRef(ref_hash.decode('utf-8'), ref_name.decode('utf-8'))
                for ref_name, ref_hash in result.refs.items()]

        if len(fd.getvalue()) > 0:
            fd.seek(0)
            pack = repo.object_store.add_thin_pack(fd.read, None)
            pack_name = pack.name().decode('utf-8')
        else:
            pack_name = None

        return (pack_name, refs)

    def _read_commits_from_pack(self, packet_name):
        """Read the commits of a pack."""

        filepath = 'objects/pack/pack-' + packet_name

        cmd_verify_pack = ['git', 'verify-pack', '-v', filepath]

        outs = self._exec(cmd_verify_pack, cwd=self.dirpath, env=self.gitenv)
        outs = outs.decode('utf-8', errors='surrogateescape').rstrip()

        lines = [line.split(' ') for line in outs.split('\n')]

        # Commits usually come in the pack ordered from newest to oldest
        commits = [parts[0] for parts in lines if parts[1] == 'commit']
        commits.reverse()

        return commits

    def _update_references(self, refs):
        """Update references removing old ones."""

        new_refs = [ref.refname for ref in refs]

        # Delete old references
        for old_ref in self._discover_refs():
            if not old_ref.refname.startswith('refs/heads/'):
                continue
            if old_ref.refname in new_refs:
                continue
            self._update_ref(old_ref, delete=True)

        # Update new references
        for new_ref in refs:
            refname = new_ref.refname

            if refname.endswith('^{}'):
                logger.debug("Annotated tag %s ignored for updating in sync process",
                             refname)
                continue
            elif not refname.startswith('refs/heads/') and not refname.startswith('refs/tags/'):
                logger.debug("Reference %s not needed; ignored for updating in sync process",
                             refname)
                continue
            else:
                self._update_ref(new_ref)

        # Prune repository to remove old branches
        cmd = ['git', 'remote', 'prune', 'origin']
        self._exec(cmd, cwd=self.dirpath, env=self.gitenv)

    def _discover_refs(self, remote=False):
        """Get the current list of local or remote refs."""

        if remote:
            cmd_refs = ['git', 'ls-remote', '-h', '-t', '--exit-code', 'origin']
            sep = '\t'
            ignored_error_codes = [2]
        else:
            # Check first whether the local repo is empty;
            # Running 'show-ref' in empty repos gives an error
            if self.is_empty():
                raise EmptyRepositoryError(repository=self.uri)

            cmd_refs = ['git', 'show-ref', '--heads', '--tags']
            sep = ' '
            ignored_error_codes = [1]

        # Error codes returned when no matching refs (i.e, no heads
        # or tags) are found in a repository will be ignored. Otherwise,
        # the full process would fail for those situations.
        outs = self._exec(cmd_refs, cwd=self.dirpath,
                          env=self.gitenv,
                          ignored_error_codes=ignored_error_codes)
        outs = outs.decode('utf-8', errors='surrogateescape').rstrip()
        outs = outs.split('\n') if outs else []

        refs = []

        for line in outs:
            data = line.split(sep)
            ref = GitRef(data[0], data[1])
            refs.append(ref)

        return refs

    def _update_ref(self, ref, delete=False):
        """Update a reference."""

        cmd = ['git', 'update-ref']

        if delete:
            cmd.extend(['-d', ref.refname])
            action = 'deleted'
        else:
            cmd.extend([ref.refname, ref.hash])
            action = 'updated to %s' % ref.hash

        try:
            self._exec(cmd, cwd=self.dirpath, env=self.gitenv)
        except RepositoryError as e:
            logger.warning("Git %s ref could not be %s during sync process in %s (%s); skipped",
                           ref.refname, action, self.uri, self.dirpath)
        else:
            logger.debug("Git %s ref %s in %s (%s)",
                         ref.refname, action, self.uri, self.dirpath)

    def _exec_nb(self, cmd, cwd=None, env=None, encoding='utf-8'):
        """Run a command with a non blocking call.

        Execute `cmd` command with a non blocking call. The command will
        be run in the directory set by `cwd`. Enviroment variables can be
        set using the `env` dictionary. The output data is returned
        as encoded bytes in an iterator. Each item will be a line of the
        output.

        :returns: an iterator with the output of the command as encoded bytes

        :raises RepositoryError: when an error occurs running the command
        """
        self.failed_message = None

        logger.debug("Running command %s (cwd: %s, env: %s)",
                     ' '.join(cmd), cwd, str(env))

        try:
            self.proc = subprocess.Popen(cmd,
                                         stdout=subprocess.PIPE,
                                         stderr=subprocess.PIPE,
                                         cwd=cwd,
                                         env=env)
            err_thread = threading.Thread(target=self._read_stderr,
                                          kwargs={'encoding': encoding},
                                          daemon=True)
            err_thread.start()
            for line in self.proc.stdout:
                yield line.decode(encoding, errors='surrogateescape')
            err_thread.join()

            self.proc.communicate()
            self.proc.stdout.close()
            self.proc.stderr.close()
        except OSError as e:
            err_thread.join()
            raise RepositoryError(cause=str(e))

        if self.proc.returncode != 0:
            cause = "git command - %s (return code: %d)" % \
                (self.failed_message, self.proc.returncode)
            raise RepositoryError(cause=cause)

    def _read_stderr(self, encoding='utf-8'):
        """Reads self.proc.stderr.

        Usually, this should be read in a thread, to prevent blocking
        the read from stdout of the stderr buffer is filled, and this
        function is not called becuase the program is busy in the
        stderr reading loop.

        Reads self.proc.stderr (self.proc is the subprocess running
        the git command), and reads / writes self.failed_message
        (the message sent to stderr when git fails, usually one line).
        """
        for line in self.proc.stderr:
            err_line = line.decode(encoding, errors='surrogateescape')

            if self.proc.returncode != 0:
                # If the subprocess didn't finish successfully, we expect
                # the last line in stderr to provide the cause
                if self.failed_message is not None:
                    # We had a message, there is a newer line, print it
                    logger.debug("Git log stderr: " + self.failed_message)
                self.failed_message = err_line
            else:
                # The subprocess is successfully up to now, print the line
                logger.debug("Git log stderr: " + err_line)

    @staticmethod
    def _exec(cmd, cwd=None, env=None, ignored_error_codes=None,
              encoding='utf-8'):
        """Run a command.

        Execute `cmd` command in the directory set by `cwd`. Environment
        variables can be set using the `env` dictionary. The output
        data is returned as encoded bytes.

        Commands which their returning status codes are non-zero will
        be treated as failed. Error codes considered as valid can be
        ignored giving them in the `ignored_error_codes` list.

        :returns: the output of the command as encoded bytes

        :raises RepositoryError: when an error occurs running the command
        """
        if ignored_error_codes is None:
            ignored_error_codes = []

        logger.debug("Running command %s (cwd: %s, env: %s)",
                     ' '.join(cmd), cwd, str(env))

        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE,
                                    cwd=cwd, env=env)
            (outs, errs) = proc.communicate()
        except OSError as e:
            raise RepositoryError(cause=str(e))

        if proc.returncode != 0 and proc.returncode not in ignored_error_codes:
            err = errs.decode(encoding, errors='surrogateescape')
            cause = "git command - %s" % err
            raise RepositoryError(cause=cause)
        else:
            logger.debug(errs.decode(encoding, errors='surrogateescape'))

        return outs
