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

from glob import glob
import io
import logging
import os
import shutil
import tarfile

from grimoirelab.toolkit.datetime import str_to_datetime

from perceval.backends.core.git import (Git,
                                        GitRepository,
                                        GitCommand)
from ...backend import BackendCommandArgumentParser
from ...errors import RepositoryError
from ...utils import DEFAULT_DATETIME, DEFAULT_LAST_DATETIME

CATEGORY_GRAAL = 'graal'
DEFAULT_WORKTREE_PATH = '/tmp/worktrees/'

logger = logging.getLogger(__name__)


class Graal(Git):
    """Generic Repository AnALyzer backend.

    This class inherits from Git backend, thus it fetches the commits
    from a local Git repository and enables to add the result of
    the analysis within the `analysis` attribute of the Perceval
    item returned. To initialize this class, you have to provide
    the local path of a Git repository (URI), a value for
    `git_path`, where the repository will be mirrored, and the path where
    a working tree will be created. The working tree is added to the
    mirror and removed after the analysis is over.

    For each target commit (by default all of them), a checkout version
    of the repository is created at `worktreepath` to ease the analysis.
    Note that you can customize the filter to select commits, by
    redefining the method `_filter_commit(self, commit, files)`.
    Furthermore, you can plug your analysis by redefining the
    method `_analyse(self, commit)` as well as tweak
    the item generated by redefining the method `_post(commit)`.

    :param uri: URI of the Git repository
    :param git_path: path to where is/to clone the repository
    :param worktreepath: the directory where to store the working tree
    :param tag: label used to mark the data
    :param archive: archive to store/retrieve items

    :raises RepositoryError: raised when there was an error cloning or
        updating the repository.
    """
    version = '0.1.0'

    CATEGORIES = [CATEGORY_GRAAL]

    def __init__(self, uri, git_path, worktreepath=DEFAULT_WORKTREE_PATH, tag=None, archive=None):
        super().__init__(uri, git_path, tag=tag, archive=archive)
        self.uri = uri
        self.gitpath = git_path
        self.worktreepath = os.path.join(worktreepath, os.path.split(self.gitpath)[1])

        if not os.path.exists(worktreepath):
            os.mkdir(worktreepath)

        self.graalRepo = None

    def fetch(self, category=CATEGORY_GRAAL, paths=None,
              from_date=DEFAULT_DATETIME, to_date=DEFAULT_LAST_DATETIME,
              branches=None, latest_items=False):
        """Fetch commits and supports the inclusion of code
        analysis information.

        The method retrieves from a Git repository a list of
        commits. Commits are returned in the same order they were
        obtained.

        The list of `paths` is a list of strings with the names of
        paths within the repository used to narrow the analysis.

        When `from_date` parameter is given it returns items commited
        since the given date.

        The list of `branches` is a list of strings, with the names of
        the branches to fetch. If the list of branches is empty, no
        commit is fetched. If the list of branches is None, all commits
        for all branches will be fetched.

        The parameter `latest_items` returns only those commits which
        are new since the last time this method was called.

        Take into account that `from_date` and `branches` are ignored
        when the commits are fetched from a Git log file or when
        `latest_items` flag is set.

        The class raises a `RepositoryError` exception when an error
        occurs accessing the repository.

        :param category: the category of items to fetch
        :param paths: the file paths to narrow the analysis
        :param from_date: obtain commits newer than a specific date
            (inclusive)
        :param to_date: obtain commits older than a specific date
        :param branches: names of branches to fetch from (default: None)
        :param latest_items: sync with the repository to fetch only the
            newest commits

        :returns: a generator of commits
        """
        if not from_date:
            from_date = DEFAULT_DATETIME
        if not to_date:
            to_date = DEFAULT_LAST_DATETIME

        kwargs = {
            'paths': paths,
            'from_date': from_date,
            'to_date': to_date,
            'branches': branches,
            'latest_items': latest_items
        }
        items = super(Git, self).fetch(category, **kwargs)

        return items

    def fetch_items(self, category, **kwargs):
        """Fetch the commits and adds analysis information

        :param category: the category of items to fetch
        :param kwargs: backend arguments

        :returns: a generator of items
        """
        ncommits = 0
        paths = kwargs['paths']

        self.graalRepo = self.__create_graal_repository()

        commits = super().fetch_items(category, **kwargs)
        for commit in commits:
            try:
                if self._filter_commit(commit, paths):
                    continue

                self.graalRepo.checkout(commit['commit'])
                commit['analysis'] = self._analyse(commit, paths)

                commit = self._post(commit)
                yield commit
                ncommits += 1
            except Exception as e:
                logger.error("Analysis failed at %s" % commit['commit'])
                raise e

        self.graalRepo.prune()

        logger.info("Fetch process completed: %s commits inspected",
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
        """Extracts the identifier from a Graal item."""

        return item['commit']

    @staticmethod
    def metadata_updated_on(item):
        """Extracts the update time from a Graal item.

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
        """Extracts the category from a Graal item.

        This backend only generates one type of item which is
        'commit'.
        """
        return CATEGORY_GRAAL

    def _filter_commit(self, commit, paths=None):
        """Filter a commit according to its data (e.g., author, sha, etc.)

        :param commit: a Perceval commit item
        :param paths: a list of paths to drive the filtering

        :returns: a boolean value
        """
        return False

    def _analyse(self, commit, paths=None):
        """Analyse a commit and the corresponding
        checkout version of the repository

        :param commit: a Perceval commit item
        :param paths: a list of paths to narrow the analysis
        """
        return {}

    def _post(self, commit):
        """Perform operation (e.g., removing attributes) on the Graal item obtained

        :param commit: a Graal commit item
        """
        return commit

    def __create_graal_repository(self):
        if not os.path.exists(self.gitpath):
            repo = GraalRepository.clone(self.uri, self.gitpath)
        elif os.path.isdir(self.gitpath):
            repo = GraalRepository(self.uri, self.gitpath)

        if os.path.exists(self.worktreepath):
            shutil.rmtree(self.worktreepath)

        repo.worktree(self.worktreepath)
        return repo


class GraalRepository(GitRepository):
    """Manage a Graal repository.

    This class extends the GitRepository class. Thus, it provides some
    additional commands such as `worktree`, `create_tar` or `untar`.

    :param uri: URI of the repository
    :param dirpath: local directory where the repository is stored
    """

    def __init__(self, uri, dirpath):
        super().__init__(uri, dirpath)
        self.worktreepath = None

    def worktree(self, worktreepath, branch=None):
        """Create a working tree of the cloned repository with the active branch
        set to `branch`

        :param worktreepath: the path where the working tree will be located
        :param branch: the name of the branch. If None, the branch is set to `master`
        """
        self.worktreepath = worktreepath

        if not branch:
            branch = 'master'

        cmd_worktree = ['git', 'worktree', 'add', self.worktreepath, branch]

        try:
            self._exec(cmd_worktree, cwd=self.dirpath, env=self.gitenv)
        except Exception:
            cause = "Impossible to create the worktree %s" % (self.worktreepath)
            raise RepositoryError(cause=cause)

    def prune(self):
        """Delete a working tree from disk

        :param worktreepath: directory where the working tree is located
        """
        shutil.rmtree(self.worktreepath)
        cmd_worktree = ['git', 'worktree', 'prune']
        try:
            self._exec(cmd_worktree, cwd=self.dirpath, env=self.gitenv)
        except Exception:
            cause = "Impossible to delete the worktree %s" % (self.worktreepath)
            raise RepositoryError(cause=cause)

    def checkout(self, hash):
        """Checkout a Git repository at a given commit

        :param hash: the hash of a commit
        """
        cmd_checkout = ['git', 'checkout', hash]
        try:
            self._exec(cmd_checkout, cwd=self.worktreepath, env=self.gitenv)
        except Exception:
            cause = "Impossible to checkout the worktree %s at %s" % (self.worktreepath, hash)
            raise RepositoryError(cause=cause)

    def archive(self, hash):
        """Create an archive using the git archive command

        :param hash: the hash of a commit

        :returns: a byte string
        """
        cmd_archive = ['git', 'archive', '--format=tar', hash]

        outs = self._exec(cmd_archive, cwd=self.dirpath, env=self.gitenv)
        return outs

    def snapshot(self, hash, paths=None, dest=None):
        """Creates a snapshot from the tree pointed by the commit
        `hash`. If `paths` is not null, the snapshot will contained
        only the files and directories in those paths.

        By default the snapshot is returned as tar object. If `dest`
        is given, the snapshot is saved to the directory `dest` as
        a tar file.

        :param hash: the hash of a commit
        :param paths: a list of paths to reduce the size of the snapshot
        :param dest: a destination folder

        :returns: the tar object or the path on the disk
        """
        outs = self.archive(hash)
        file_obj = io.BytesIO(outs)

        snapshot_obj = GraalRepository.tar_obj(file_obj)
        if not snapshot_obj:
            logger.warning("Snapshot not created for %s" % hash)
            return None

        if paths:
            snapshot_obj = self.filter_tar(snapshot_obj, paths)

            if not snapshot_obj:
                logger.warning("Snapshot %s is empty after filtering" % hash)
                return None

        if not dest:
            # return a tar file object
            return snapshot_obj

        snapshot_path = os.path.join(dest, hash + '.tar.gz')
        GraalRepository.tar(snapshot_obj, snapshot_path)

        return snapshot_path

    @staticmethod
    def filter_tar(tar_obj, paths):
        """Create a tar object from a BytesIO object.

        :param tar_obj: a BytesIO object
        :param paths: a list of paths to be included in the tar
        """
        selected_members = [member for member in tar_obj.getmembers() if member.name in paths]
        tar_obj.members = selected_members

        if not tar_obj.members:
            return None

        return tar_obj

    @staticmethod
    def extension(file_path):
        """Get the extension of a file"""

        ext = file_path.split(".")[-1]
        return ext

    @staticmethod
    def files(dir_path):
        """List all files in a target dir

        :param dir_path: the path of the target directory
        """
        if not dir_path or not os.path.exists(dir_path):
            return []

        onlyfiles = glob(dir_path + '/**/*.*', recursive=True)
        return onlyfiles

    @staticmethod
    def delete(target_path):
        """Delete a a file or directory from disk

        :param target_path: the path of the target to be deleted
        """
        if not target_path or not os.path.exists(target_path):
            logger.warning("The path %s does not exist!" % target_path)
            return

        if os.path.isdir(target_path):
            shutil.rmtree(target_path)
        else:
            os.remove(target_path)

        logger.info("%s deleted!" % target_path)

    @staticmethod
    def tar_obj(file_obj):
        """Create a tar object from a BytesIO object.

        :param file_obj: a BytesIO object
        """
        try:
            tar_obj = tarfile.open(fileobj=file_obj)
        except tarfile.ReadError:
            # this may happen because file_like_object is empty
            logger.warning("Tar object was not created")
            return None

        return tar_obj

    @staticmethod
    def tar(tar_obj, dest):
        """Save a tar object to the `dest` path

        :param tar_obj: a tar object
        :param dest: a destination path
        """
        tar = tarfile.open(dest, "w:gz")
        for member in tar_obj.getmembers():
            tar.addfile(member)
        tar.close()

        logger.info("Tar file created at %s" % dest)

    @staticmethod
    def untar(tar_file, dest):
        """Untar a tar file to the `dest` directory

        :param tar_file: a tar file
        :param dest: a destination folder
        """
        if not os.path.exists(dest):
            os.mkdir(dest)

        tar_file.extractall(path=dest)
        logger.info("Tar file untarred at %s" % dest)


class GraalCommand(GitCommand):
    """Class to run GraalRepository backend from the command line."""

    BACKEND = Graal

    def _pre_init(self):
        """Initialize repositories directory path"""

        git_path = self.parsed_args.git_path
        setattr(self.parsed_args, 'gitpath', git_path)

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

        # Required arguments
        parser.parser.add_argument('uri',
                                   help="URI of the Git log repository")
        parser.parser.add_argument('--git-path', dest='git_path',
                                   help="Path where the Git repository will be cloned")

        return parser
