#!/usr/bin/env python3
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
#     Jesus M. Gonzalez-Barahona <jgb@gsyc.es>
#     Miguel Ángel Fernández <mafesan@bitergia.com>
#     anveshc05 <anveshc10047@gmail.com>
#     Harshal Mittal <harshalmittal4@gmail.com>
#     Victor Morales <victor.morales@intel.com>
#

import datetime
import os
import shutil
import subprocess
import tempfile
import unittest
import unittest.mock

import dateutil.tz

from perceval.backend import BackendCommandArgumentParser, uuid
from perceval.errors import RepositoryError
from perceval.utils import DEFAULT_DATETIME, DEFAULT_LAST_DATETIME
from perceval.backends.core.git import (EmptyRepositoryError,
                                        Git,
                                        GitCommand,
                                        GitParser,
                                        GitRepository)


class TestCaseGit(unittest.TestCase):
    """Base case for Git tests"""

    def setUp(self):
        patcher = unittest.mock.patch('os.getenv')
        self.addCleanup(patcher.stop)
        self.mock_getenv = patcher.start()
        self.mock_getenv.return_value = ''


class TestGitBackend(TestCaseGit):
    """Git backend tests"""

    @classmethod
    def setUpClass(cls):
        cls.tmp_path = tempfile.mkdtemp(prefix='perceval_')
        cls.tmp_repo_path = os.path.join(cls.tmp_path, 'repos')
        os.mkdir(cls.tmp_repo_path)

        cls.git_path = os.path.join(cls.tmp_path, 'gittest')
        cls.git_detached_path = os.path.join(cls.tmp_path, 'gitdetached')
        cls.git_empty_path = os.path.join(cls.tmp_path, 'gittestempty')
        cls.git_submodules_path = os.path.join(cls.tmp_path, 'gittest-sub')
        cls.git_top_submodules_path = os.path.join(cls.tmp_path, 'gittest-top-sub')
        cls.git_alternates_path = os.path.join(cls.tmp_path, 'gitalternates')

        data_path = os.path.dirname(os.path.abspath(__file__))
        data_path = os.path.join(data_path, 'data/git')

        repos = [
            ('gittest', cls.git_path),
            ('gitdetached', cls.git_detached_path),
            ('gittestempty', cls.git_empty_path),
            ('gittest-sub', cls.git_submodules_path),
            ('gittest-top-sub', cls.git_top_submodules_path),
            ('gitalternates', cls.git_alternates_path)
        ]

        fdout, _ = tempfile.mkstemp(dir=cls.tmp_path)

        for repo_name, repo_path in repos:
            tar_path = os.path.join(data_path, repo_name + '.tar.gz')
            subprocess.check_call(['tar', '-xzf', tar_path, '-C', cls.tmp_repo_path])

            origin_path = os.path.join(cls.tmp_repo_path, repo_name)
            subprocess.check_call(['git', 'clone', '-q', '--bare', origin_path, repo_path],
                                  stderr=fdout)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp_path)

    def test_initialization(self):
        """Test whether attributes are initializated"""

        git = Git('http://example.com', self.git_path, tag='test')

        self.assertEqual(git.uri, 'http://example.com')
        self.assertEqual(git.gitpath, self.git_path)
        self.assertEqual(git.origin, 'http://example.com')
        self.assertEqual(git.tag, 'test')

        # When tag is empty or None it will be set to
        # the value in uri
        git = Git('http://example.com', self.git_path)
        self.assertEqual(git.origin, 'http://example.com')
        self.assertEqual(git.tag, 'http://example.com')

        git = Git('http://example.com', self.git_path, tag='')
        self.assertEqual(git.origin, 'http://example.com')
        self.assertEqual(git.tag, 'http://example.com')

    def test_has_archiving(self):
        """Test if it returns False when has_archiving is called"""

        self.assertEqual(Git.has_archiving(), False)

    def test_has_resuming(self):
        """Test if it returns True when has_resuming is called"""

        self.assertEqual(Git.has_resuming(), True)

    def test_fetch_submodules(self):
        """Test whether repositories with submodules are correctly fetched"""

        new_path_top = os.path.join(self.tmp_path, 'topgit')
        new_path_sub = os.path.join(self.tmp_path, 'subgit')
        top = Git(self.git_top_submodules_path, new_path_top)
        sub = Git(self.git_submodules_path, new_path_sub)

        t_commits = [commit for commit in top.fetch()]
        s_commits = [commit for commit in sub.fetch()]

        self.assertEqual(len(t_commits), 9)
        self.assertEqual(len(s_commits), 10)

        shutil.rmtree(new_path_top)
        shutil.rmtree(new_path_sub)

    def test_fetch(self):
        """Test whether commits are fetched from a Git repository"""

        new_path = os.path.join(self.tmp_path, 'newgit')

        git = Git(self.git_path, new_path)
        commits = [commit for commit in git.fetch()]

        expected = [('bc57a9209f096a130dcc5ba7089a8663f758a703', 1344965413.0),
                    ('87783129c3f00d2c81a3a8e585eb86a47e39891a', 1344965535.0),
                    ('7debcf8a2f57f86663809c58b5c07a398be7674c', 1344965607.0),
                    ('c0d66f92a95e31c77be08dc9d0f11a16715d1885', 1344965702.0),
                    ('c6ba8f7a1058db3e6b4bc6f1090e932b107605fb', 1344966351.0),
                    ('589bb080f059834829a2a5955bebfd7c2baa110a', 1344967441.0),
                    ('ce8e0b86a1e9877f42fe9453ede418519115f367', 1392185269.0),
                    ('51a3b654f252210572297f47597b31527c475fb8', 1392185366.0),
                    ('456a68ee1407a77f3e804a30dff245bb6c6b872f', 1392185439.0)]

        self.assertEqual(len(commits), len(expected))

        for x in range(len(commits)):
            expected_uuid = uuid(self.git_path, expected[x][0])
            commit = commits[x]
            self.assertEqual(commit['data']['commit'], expected[x][0])
            self.assertEqual(commit['origin'], self.git_path)
            self.assertEqual(commit['uuid'], expected_uuid)
            self.assertEqual(commit['updated_on'], expected[x][1])
            self.assertEqual(commit['category'], 'commit')
            self.assertEqual(commit['tag'], self.git_path)

        shutil.rmtree(new_path)

    def test_search_fields(self):
        """Test whether the search_fields is properly set"""

        new_path = os.path.join(self.tmp_path, 'newgit')

        git = Git(self.git_path, new_path)
        commits = [commit for commit in git.fetch()]

        for commit in commits:
            self.assertEqual(git.metadata_id(commit['data']), commit['search_fields']['item_id'])

        shutil.rmtree(new_path)

    def test_fetch_till_date(self):
        """Test whether commits are fetched from a Git repository before the given date"""

        new_path = os.path.join(self.tmp_path, 'newgit')

        to_date = datetime.datetime(2014, 2, 11, 22, 7, 49)
        git = Git(self.git_path, new_path)
        commits = [commit for commit in git.fetch(to_date=to_date)]

        expected = [('bc57a9209f096a130dcc5ba7089a8663f758a703', 1344965413.0),
                    ('87783129c3f00d2c81a3a8e585eb86a47e39891a', 1344965535.0),
                    ('7debcf8a2f57f86663809c58b5c07a398be7674c', 1344965607.0),
                    ('c0d66f92a95e31c77be08dc9d0f11a16715d1885', 1344965702.0),
                    ('c6ba8f7a1058db3e6b4bc6f1090e932b107605fb', 1344966351.0),
                    ('589bb080f059834829a2a5955bebfd7c2baa110a', 1344967441.0)]

        self.assertEqual(len(commits), len(expected))

        for x in range(len(commits)):
            expected_uuid = uuid(self.git_path, expected[x][0])
            commit = commits[x]
            self.assertEqual(commit['data']['commit'], expected[x][0])
            self.assertEqual(commit['origin'], self.git_path)
            self.assertEqual(commit['uuid'], expected_uuid)
            self.assertEqual(commit['updated_on'], expected[x][1])
            self.assertEqual(commit['category'], 'commit')
            self.assertEqual(commit['tag'], self.git_path)

        # Test it using a datetime that includes the timezone
        to_date = datetime.datetime(2012, 8, 14, 14, 30, 00,
                                    tzinfo=dateutil.tz.tzoffset(None, -36000))
        git = Git(self.git_path, new_path)
        commits = [commit for commit in git.fetch(to_date=to_date)]

        self.assertEqual(len(commits), len(expected))

        for x in range(len(commits)):
            expected_uuid = uuid(self.git_path, expected[x][0])
            commit = commits[x]
            self.assertEqual(commit['data']['commit'], expected[x][0])
            self.assertEqual(commit['origin'], self.git_path)
            self.assertEqual(commit['uuid'], expected_uuid)
            self.assertEqual(commit['updated_on'], expected[x][1])
            self.assertEqual(commit['category'], 'commit')
            self.assertEqual(commit['tag'], self.git_path)

        shutil.rmtree(new_path)

    def test_fetch_since_date(self):
        """Test whether commits are fetched from a Git repository since the given date"""

        new_path = os.path.join(self.tmp_path, 'newgit')

        from_date = datetime.datetime(2014, 2, 11, 22, 7, 49)
        git = Git(self.git_path, new_path)
        commits = [commit for commit in git.fetch(from_date=from_date)]

        expected = [('ce8e0b86a1e9877f42fe9453ede418519115f367', 1392185269.0),
                    ('51a3b654f252210572297f47597b31527c475fb8', 1392185366.0),
                    ('456a68ee1407a77f3e804a30dff245bb6c6b872f', 1392185439.0)]

        self.assertEqual(len(commits), len(expected))

        for x in range(len(commits)):
            expected_uuid = uuid(self.git_path, expected[x][0])
            commit = commits[x]
            self.assertEqual(commit['data']['commit'], expected[x][0])
            self.assertEqual(commit['origin'], self.git_path)
            self.assertEqual(commit['uuid'], expected_uuid)
            self.assertEqual(commit['updated_on'], expected[x][1])
            self.assertEqual(commit['category'], 'commit')
            self.assertEqual(commit['tag'], self.git_path)

        # Test it using a datetime that includes the timezone
        from_date = datetime.datetime(2012, 8, 14, 14, 30, 00,
                                      tzinfo=dateutil.tz.tzoffset(None, -36000))
        git = Git(self.git_path, new_path)
        commits = [commit for commit in git.fetch(from_date=from_date)]

        self.assertEqual(len(commits), len(expected))

        for x in range(len(commits)):
            expected_uuid = uuid(self.git_path, expected[x][0])
            commit = commits[x]
            self.assertEqual(commit['data']['commit'], expected[x][0])
            self.assertEqual(commit['origin'], self.git_path)
            self.assertEqual(commit['uuid'], expected_uuid)
            self.assertEqual(commit['updated_on'], expected[x][1])
            self.assertEqual(commit['category'], 'commit')
            self.assertEqual(commit['tag'], self.git_path)

        shutil.rmtree(new_path)

    def test_fetch_between_dates(self):
        """Test whether commits are fetched between given start and end dates"""
        new_path = os.path.join(self.tmp_path, 'newgit')

        from_date = datetime.datetime(2012, 8, 14, 17, 34, 0)
        to_date = datetime.datetime(2014, 2, 11, 22, 7, 49)
        git = Git(self.git_path, new_path)
        commits = [commit for commit in git.fetch(from_date=from_date, to_date=to_date)]

        expected = [('c0d66f92a95e31c77be08dc9d0f11a16715d1885', 1344965702.0),
                    ('c6ba8f7a1058db3e6b4bc6f1090e932b107605fb', 1344966351.0),
                    ('589bb080f059834829a2a5955bebfd7c2baa110a', 1344967441.0)]

        self.assertEqual(len(commits), len(expected))

        for x in range(len(commits)):
            expected_uuid = uuid(self.git_path, expected[x][0])
            commit = commits[x]
            self.assertEqual(commit['data']['commit'], expected[x][0])
            self.assertEqual(commit['origin'], self.git_path)
            self.assertEqual(commit['uuid'], expected_uuid)
            self.assertEqual(commit['updated_on'], expected[x][1])
            self.assertEqual(commit['category'], 'commit')
            self.assertEqual(commit['tag'], self.git_path)

        # Test it using a datetime that includes the timezone
        from_date = datetime.datetime(2012, 8, 14, 7, 34, 00,
                                      tzinfo=dateutil.tz.tzoffset(None, -36000))
        to_date = datetime.datetime(2012, 8, 14, 14, 30, 00,
                                    tzinfo=dateutil.tz.tzoffset(None, -36000))
        git = Git(self.git_path, new_path)
        commits = [commit for commit in git.fetch(from_date=from_date, to_date=to_date)]

        self.assertEqual(len(commits), len(expected))

        for x in range(len(commits)):
            expected_uuid = uuid(self.git_path, expected[x][0])
            commit = commits[x]
            self.assertEqual(commit['data']['commit'], expected[x][0])
            self.assertEqual(commit['origin'], self.git_path)
            self.assertEqual(commit['uuid'], expected_uuid)
            self.assertEqual(commit['updated_on'], expected[x][1])
            self.assertEqual(commit['category'], 'commit')
            self.assertEqual(commit['tag'], self.git_path)

        shutil.rmtree(new_path)

    def test_fetch_branch(self):
        """Test whether commits are fetched from a Git repository for a given branch"""

        new_path = os.path.join(self.tmp_path, 'newgit')

        from_date = datetime.datetime(2014, 2, 11, 22, 7, 49)
        git = Git(self.git_path, new_path)
        # Let's fetch master
        commits = [commit for commit in git.fetch(branches=['master'])]

        expected = ['bc57a9209f096a130dcc5ba7089a8663f758a703',
                    '87783129c3f00d2c81a3a8e585eb86a47e39891a',
                    '7debcf8a2f57f86663809c58b5c07a398be7674c',
                    'c0d66f92a95e31c77be08dc9d0f11a16715d1885',
                    'c6ba8f7a1058db3e6b4bc6f1090e932b107605fb',
                    '589bb080f059834829a2a5955bebfd7c2baa110a',
                    'ce8e0b86a1e9877f42fe9453ede418519115f367',
                    '51a3b654f252210572297f47597b31527c475fb8',
                    '456a68ee1407a77f3e804a30dff245bb6c6b872f']

        self.assertEqual(len(commits), len(expected))

        for x in range(len(commits)):
            expected_uuid = uuid(self.git_path, expected[x])
            commit = commits[x]
            self.assertEqual(commit['data']['commit'], expected[x])
            self.assertEqual(commit['origin'], self.git_path)
            self.assertEqual(commit['uuid'], expected_uuid)
            self.assertEqual(commit['category'], 'commit')
            self.assertEqual(commit['tag'], self.git_path)

        # Now let's fetch lzp
        commits = [commit for commit in git.fetch(branches=['lzp'])]

        expected = ['bc57a9209f096a130dcc5ba7089a8663f758a703',
                    '87783129c3f00d2c81a3a8e585eb86a47e39891a',
                    '7debcf8a2f57f86663809c58b5c07a398be7674c',
                    'c0d66f92a95e31c77be08dc9d0f11a16715d1885',
                    'c6ba8f7a1058db3e6b4bc6f1090e932b107605fb',
                    '589bb080f059834829a2a5955bebfd7c2baa110a',
                    '51a3b654f252210572297f47597b31527c475fb8']

        self.assertEqual(len(commits), len(expected))

        for x in range(len(commits)):
            expected_uuid = uuid(self.git_path, expected[x])
            commit = commits[x]
            self.assertEqual(commit['data']['commit'], expected[x])
            self.assertEqual(commit['origin'], self.git_path)
            self.assertEqual(commit['uuid'], expected_uuid)
            self.assertEqual(commit['category'], 'commit')
            self.assertEqual(commit['tag'], self.git_path)

        # Now, let's fech master and lzp
        commits = [commit for commit in git.fetch(branches=['master', 'lzp'])]

        expected = ['bc57a9209f096a130dcc5ba7089a8663f758a703',
                    '87783129c3f00d2c81a3a8e585eb86a47e39891a',
                    '7debcf8a2f57f86663809c58b5c07a398be7674c',
                    'c0d66f92a95e31c77be08dc9d0f11a16715d1885',
                    'c6ba8f7a1058db3e6b4bc6f1090e932b107605fb',
                    '589bb080f059834829a2a5955bebfd7c2baa110a',
                    'ce8e0b86a1e9877f42fe9453ede418519115f367',
                    '51a3b654f252210572297f47597b31527c475fb8',
                    '456a68ee1407a77f3e804a30dff245bb6c6b872f']

        self.assertEqual(len(commits), len(expected))

        for x in range(len(commits)):
            expected_uuid = uuid(self.git_path, expected[x])
            commit = commits[x]
            self.assertEqual(commit['data']['commit'], expected[x])
            self.assertEqual(commit['origin'], self.git_path)
            self.assertEqual(commit['uuid'], expected_uuid)
            self.assertEqual(commit['category'], 'commit')
            self.assertEqual(commit['tag'], self.git_path)

        # Now, let's fetch None, which means "all commits"
        commits = [commit for commit in git.fetch(branches=None)]

        expected = ['bc57a9209f096a130dcc5ba7089a8663f758a703',
                    '87783129c3f00d2c81a3a8e585eb86a47e39891a',
                    '7debcf8a2f57f86663809c58b5c07a398be7674c',
                    'c0d66f92a95e31c77be08dc9d0f11a16715d1885',
                    'c6ba8f7a1058db3e6b4bc6f1090e932b107605fb',
                    '589bb080f059834829a2a5955bebfd7c2baa110a',
                    'ce8e0b86a1e9877f42fe9453ede418519115f367',
                    '51a3b654f252210572297f47597b31527c475fb8',
                    '456a68ee1407a77f3e804a30dff245bb6c6b872f']

        self.assertEqual(len(commits), len(expected))

        for x in range(len(commits)):
            expected_uuid = uuid(self.git_path, expected[x])
            commit = commits[x]
            self.assertEqual(commit['data']['commit'], expected[x])
            self.assertEqual(commit['origin'], self.git_path)
            self.assertEqual(commit['uuid'], expected_uuid)
            self.assertEqual(commit['category'], 'commit')
            self.assertEqual(commit['tag'], self.git_path)

        # Now, let's fetch [], which means "no commits"
        commits = [commit for commit in git.fetch(branches=[])]

        expected = []

        self.assertEqual(len(commits), len(expected))

        shutil.rmtree(new_path)

    def test_fetch_empty_log(self):
        """Test whether it parsers an empty log"""

        new_path = os.path.join(self.tmp_path, 'newgit')

        from_date = datetime.datetime(2020, 1, 1, 1, 1, 1)
        git = Git(self.git_path, new_path)
        commits = [commit for commit in git.fetch(from_date=from_date)]

        self.assertListEqual(commits, [])

        to_date = datetime.datetime(1970, 1, 1, 1, 1, 1)
        git = Git(self.git_path, new_path)
        commits = [commit for commit in git.fetch(to_date=to_date)]

        self.assertListEqual(commits, [])

        shutil.rmtree(new_path)

    def test_fetch_from_detached_repository(self):
        """Test whether commits are fetched from a repository in detached state"""

        new_path = os.path.join(self.tmp_path, 'newgit')

        git = Git(self.git_detached_path, new_path)
        commits = [commit for commit in git.fetch()]

        expected = [('bc57a9209f096a130dcc5ba7089a8663f758a703', 1344965413.0),
                    ('87783129c3f00d2c81a3a8e585eb86a47e39891a', 1344965535.0),
                    ('7debcf8a2f57f86663809c58b5c07a398be7674c', 1344965607.0),
                    ('c0d66f92a95e31c77be08dc9d0f11a16715d1885', 1344965702.0),
                    ('c6ba8f7a1058db3e6b4bc6f1090e932b107605fb', 1344966351.0),
                    ('589bb080f059834829a2a5955bebfd7c2baa110a', 1344967441.0),
                    ('ce8e0b86a1e9877f42fe9453ede418519115f367', 1392185269.0),
                    ('51a3b654f252210572297f47597b31527c475fb8', 1392185366.0),
                    ('456a68ee1407a77f3e804a30dff245bb6c6b872f', 1392185439.0)]

        self.assertEqual(len(commits), len(expected))

        for x in range(len(commits)):
            expected_uuid = uuid(self.git_detached_path, expected[x][0])
            commit = commits[x]
            self.assertEqual(commit['data']['commit'], expected[x][0])
            self.assertEqual(commit['origin'], self.git_detached_path)
            self.assertEqual(commit['uuid'], expected_uuid)
            self.assertEqual(commit['updated_on'], expected[x][1])
            self.assertEqual(commit['category'], 'commit')
            self.assertEqual(commit['tag'], self.git_detached_path)

        shutil.rmtree(new_path)

    def test_fetch_from_empty_repository(self):
        """Test whether it parses from empty repository"""

        new_path = os.path.join(self.tmp_path, 'newgit')

        git = Git(self.git_empty_path, new_path)
        commits = [commit for commit in git.fetch()]

        self.assertListEqual(commits, [])

        shutil.rmtree(new_path)

    def test_fetch_latest_items(self):
        """Test whether latest commits are fetched from a Git repository"""

        origin_path = os.path.join(self.tmp_repo_path, 'gittest')
        editable_path = os.path.join(self.tmp_path, 'editgit')
        new_path = os.path.join(self.tmp_path, 'newgit')
        new_file = os.path.join(editable_path, 'newfile')

        shutil.copytree(origin_path, editable_path)

        git = Git(editable_path, new_path)
        commits = [commit for commit in git.fetch(latest_items=True)]

        # Count the number of commits before adding some new
        expected = [('bc57a9209f096a130dcc5ba7089a8663f758a703', 1344965413.0),
                    ('87783129c3f00d2c81a3a8e585eb86a47e39891a', 1344965535.0),
                    ('7debcf8a2f57f86663809c58b5c07a398be7674c', 1344965607.0),
                    ('c0d66f92a95e31c77be08dc9d0f11a16715d1885', 1344965702.0),
                    ('c6ba8f7a1058db3e6b4bc6f1090e932b107605fb', 1344966351.0),
                    ('589bb080f059834829a2a5955bebfd7c2baa110a', 1344967441.0),
                    ('ce8e0b86a1e9877f42fe9453ede418519115f367', 1392185269.0),
                    ('51a3b654f252210572297f47597b31527c475fb8', 1392185366.0),
                    ('456a68ee1407a77f3e804a30dff245bb6c6b872f', 1392185439.0)]

        self.assertEqual(len(commits), len(expected))

        for x in range(len(commits)):
            expected_uuid = uuid(editable_path, expected[x][0])
            commit = commits[x]
            self.assertEqual(commit['data']['commit'], expected[x][0])
            self.assertEqual(commit['origin'], editable_path)
            self.assertEqual(commit['uuid'], expected_uuid)
            self.assertEqual(commit['updated_on'], expected[x][1])
            self.assertEqual(commit['category'], 'commit')
            self.assertEqual(commit['tag'], editable_path)

        # Create some new commits
        cmd = ['git', 'checkout', '-b', 'mybranch']
        subprocess.check_output(cmd, stderr=subprocess.STDOUT,
                                cwd=editable_path, env={'LANG': 'C'})

        with open(new_file, 'w') as f:
            f.write("Testing sync method")

        cmd = ['git', 'add', new_file]
        subprocess.check_output(cmd, stderr=subprocess.STDOUT,
                                cwd=editable_path, env={'LANG': 'C'})

        cmd = ['git', '-c', 'user.name="mock"',
               '-c', 'user.email="mock@example.com"',
               'commit', '-m', 'Testing sync']
        subprocess.check_output(cmd, stderr=subprocess.STDOUT,
                                cwd=editable_path, env={'LANG': 'C'})

        cmd = ['git', 'rm', new_file]
        subprocess.check_output(cmd, stderr=subprocess.STDOUT,
                                cwd=editable_path, env={'LANG': 'C'})

        cmd = ['git', '-c', 'user.name="mock"',
               '-c', 'user.email="mock@example.com"',
               'commit', '-m', 'Removing testing file for sync']
        subprocess.check_output(cmd, stderr=subprocess.STDOUT,
                                cwd=editable_path, env={'LANG': 'C'})

        # Two new commits should have been fetched
        commits = [commit for commit in git.fetch(latest_items=True)]
        self.assertEqual(len(commits), 2)

        # Remove 'lzp' branch and check that the number of new commits is 0
        cmd = ['git', 'branch', '-D', 'lzp']
        subprocess.check_output(cmd, stderr=subprocess.STDOUT,
                                cwd=editable_path, env={'LANG': 'C'})

        commits = [commit for commit in git.fetch(latest_items=True)]
        self.assertEqual(len(commits), 0)

        # Cleanup
        shutil.rmtree(editable_path)
        shutil.rmtree(new_path)

    def test_fetch_latest_items_from_empty_repository(self):
        """Test whether it fetches no items from an empty repository"""

        new_path = os.path.join(self.tmp_path, 'newgit')

        git = Git(self.git_empty_path, new_path)

        # First time, latest items are fetched using 'git log'
        commits = [commit for commit in git.fetch(latest_items=True)]
        self.assertListEqual(commits, [])

        # Further times, latest items are fetched using 'git fetch-pack'
        # and 'git show'
        commits = [commit for commit in git.fetch(latest_items=True)]
        self.assertListEqual(commits, [])

        shutil.rmtree(new_path)

    def test_fetch_no_update(self):
        """Test whether new commits aren't fetched when no_update flag is set"""

        origin_path = os.path.join(self.tmp_repo_path, 'gittest')
        editable_path = os.path.join(self.tmp_path, 'editgit')
        new_path = os.path.join(self.tmp_path, 'newgit')
        new_file = os.path.join(editable_path, 'newfile')

        shutil.copytree(origin_path, editable_path)

        git = Git(editable_path, new_path)
        commits = [commit for commit in git.fetch()]

        # Count the number of commits before adding some new
        expected = [('bc57a9209f096a130dcc5ba7089a8663f758a703', 1344965413.0),
                    ('87783129c3f00d2c81a3a8e585eb86a47e39891a', 1344965535.0),
                    ('7debcf8a2f57f86663809c58b5c07a398be7674c', 1344965607.0),
                    ('c0d66f92a95e31c77be08dc9d0f11a16715d1885', 1344965702.0),
                    ('c6ba8f7a1058db3e6b4bc6f1090e932b107605fb', 1344966351.0),
                    ('589bb080f059834829a2a5955bebfd7c2baa110a', 1344967441.0),
                    ('ce8e0b86a1e9877f42fe9453ede418519115f367', 1392185269.0),
                    ('51a3b654f252210572297f47597b31527c475fb8', 1392185366.0),
                    ('456a68ee1407a77f3e804a30dff245bb6c6b872f', 1392185439.0)]

        self.assertEqual(len(commits), len(expected))

        for x in range(len(commits)):
            expected_uuid = uuid(editable_path, expected[x][0])
            commit = commits[x]
            self.assertEqual(commit['data']['commit'], expected[x][0])
            self.assertEqual(commit['origin'], editable_path)
            self.assertEqual(commit['uuid'], expected_uuid)
            self.assertEqual(commit['updated_on'], expected[x][1])
            self.assertEqual(commit['category'], 'commit')
            self.assertEqual(commit['tag'], editable_path)

        # Create some new commits
        cmd = ['git', 'checkout', '-b', 'mybranch']
        subprocess.check_output(cmd, stderr=subprocess.STDOUT,
                                cwd=editable_path, env={'LANG': 'C'})

        with open(new_file, 'w') as f:
            f.write("Testing sync method")

        cmd = ['git', 'add', new_file]
        subprocess.check_output(cmd, stderr=subprocess.STDOUT,
                                cwd=editable_path, env={'LANG': 'C'})

        cmd = ['git', '-c', 'user.name="mock"',
               '-c', 'user.email="mock@example.com"',
               'commit', '-m', 'Testing sync']
        subprocess.check_output(cmd, stderr=subprocess.STDOUT,
                                cwd=editable_path, env={'LANG': 'C'})

        cmd = ['git', 'rm', new_file]
        subprocess.check_output(cmd, stderr=subprocess.STDOUT,
                                cwd=editable_path, env={'LANG': 'C'})

        cmd = ['git', '-c', 'user.name="mock"',
               '-c', 'user.email="mock@example.com"',
               'commit', '-m', 'Removing testing file for sync']
        subprocess.check_output(cmd, stderr=subprocess.STDOUT,
                                cwd=editable_path, env={'LANG': 'C'})

        # Two new commits are added to the repo but are not fetched
        commits = [commit for commit in git.fetch(no_update=True)]
        self.assertEqual(len(commits), 9)

        commits = [commit for commit in git.fetch()]
        self.assertEqual(len(commits), 11)

        # Cleanup
        shutil.rmtree(editable_path)
        shutil.rmtree(new_path)

    def test_fetch_from_file(self):
        """Test whether commits are fetched from a Git log file"""

        git = Git('http://example.com.git', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data/git/git_log.txt'))
        commits = [commit for commit in git.fetch()]

        expected = [('456a68ee1407a77f3e804a30dff245bb6c6b872f', 1392185439.0),
                    ('51a3b654f252210572297f47597b31527c475fb8', 1392185366.0),
                    ('ce8e0b86a1e9877f42fe9453ede418519115f367', 1392185269.0),
                    ('589bb080f059834829a2a5955bebfd7c2baa110a', 1344967441.0),
                    ('c6ba8f7a1058db3e6b4bc6f1090e932b107605fb', 1344966351.0),
                    ('c0d66f92a95e31c77be08dc9d0f11a16715d1885', 1344965702.0),
                    ('7debcf8a2f57f86663809c58b5c07a398be7674c', 1344965607.0),
                    ('87783129c3f00d2c81a3a8e585eb86a47e39891a', 1344965535.0),
                    ('bc57a9209f096a130dcc5ba7089a8663f758a703', 1344965413.0),
                    ('49345fe87bd1dfad7e682f6554f7472c5576a8c7', 1515508249.0)]

        self.assertEqual(len(commits), len(expected))

        for x in range(len(commits)):
            expected_uuid = uuid('http://example.com.git', expected[x][0])
            commit = commits[x]
            self.assertEqual(commit['data']['commit'], expected[x][0])
            self.assertEqual(commit['origin'], 'http://example.com.git')
            self.assertEqual(commit['uuid'], expected_uuid)
            self.assertEqual(commit['updated_on'], expected[x][1])
            self.assertEqual(commit['category'], 'commit')
            self.assertEqual(commit['tag'], 'http://example.com.git')

    def test_git_parser(self):
        """Test if the static method parses a git log file"""

        commits = Git.parse_git_log_from_file(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                           "data/git/git_log.txt"))
        result = [commit['commit'] for commit in commits]

        expected = ['456a68ee1407a77f3e804a30dff245bb6c6b872f',
                    '51a3b654f252210572297f47597b31527c475fb8',
                    'ce8e0b86a1e9877f42fe9453ede418519115f367',
                    '589bb080f059834829a2a5955bebfd7c2baa110a',
                    'c6ba8f7a1058db3e6b4bc6f1090e932b107605fb',
                    'c0d66f92a95e31c77be08dc9d0f11a16715d1885',
                    '7debcf8a2f57f86663809c58b5c07a398be7674c',
                    '87783129c3f00d2c81a3a8e585eb86a47e39891a',
                    'bc57a9209f096a130dcc5ba7089a8663f758a703',
                    '49345fe87bd1dfad7e682f6554f7472c5576a8c7']

        self.assertListEqual(result, expected)

    def test_git_encoding_error(self):
        """Test if encoding errors are escaped when a git log is parsed"""

        commits = Git.parse_git_log_from_file(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                           "data/git/git_bad_encoding.txt"))
        result = [commit for commit in commits]

        self.assertEqual(len(result), 1)

        commit = result[0]
        self.assertEqual(commit['commit'], 'cb24e4f2f7b2a7f3450bfb15d1cbaa97371e93fb')
        self.assertEqual(commit['message'],
                         'Calling \udc93Open Type\udc94 (CTRL+SHIFT+T) after startup - performance improvement.')

    def test_git_cr_error(self):
        """Test if mislocated carriage return chars do not break lines

        In some commit messages, carriage return characters (\r) are found
        in weird places. They should not be misconsidered as end of line.

        Before fixing, this test raises an exception:
        "perceval.errors.ParseError: commit expected on line 10"

        """
        commits = Git.parse_git_log_from_file(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                           "data/git/git_bad_cr.txt"))
        result = [commit for commit in commits]
        self.assertEqual(len(result), 1)

    def test_git_parser_from_iter(self):
        """Test if the static method parses a git log from a repository"""

        repo = GitRepository(self.git_path, self.git_path)
        commits = Git.parse_git_log_from_iter(repo.log())
        result = [commit['commit'] for commit in commits]

        expected = ['bc57a9209f096a130dcc5ba7089a8663f758a703',
                    '87783129c3f00d2c81a3a8e585eb86a47e39891a',
                    '7debcf8a2f57f86663809c58b5c07a398be7674c',
                    'c0d66f92a95e31c77be08dc9d0f11a16715d1885',
                    'c6ba8f7a1058db3e6b4bc6f1090e932b107605fb',
                    '589bb080f059834829a2a5955bebfd7c2baa110a',
                    'ce8e0b86a1e9877f42fe9453ede418519115f367',
                    '51a3b654f252210572297f47597b31527c475fb8',
                    '456a68ee1407a77f3e804a30dff245bb6c6b872f']

        self.assertListEqual(result, expected)


class TestGitCommand(TestCaseGit):
    """GitCommand tests"""

    def setUp(self):
        super().setUp()
        self.tmp_path = tempfile.mkdtemp(prefix='perceval_')

    def tearDown(self):
        super().tearDown()
        shutil.rmtree(self.tmp_path)

    def test_backend_class(self):
        """Test if the backend class is Git"""

        self.assertIs(GitCommand.BACKEND, Git)

    @unittest.mock.patch('os.path.expanduser')
    def test_gitpath_init(self, mock_expanduser):
        """Test gitpath initialization"""

        mock_expanduser.return_value = os.path.join(self.tmp_path, 'testpath')

        args = ['http://example.com/']

        cmd = GitCommand(*args)
        self.assertEqual(cmd.parsed_args.gitpath,
                         os.path.join(self.tmp_path, 'testpath/http://example.com/-git'))

        args = ['http://example.com/',
                '--git-log', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data/git/git_log.txt')]

        cmd = GitCommand(*args)
        self.assertEqual(cmd.parsed_args.gitpath, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                               'data/git/git_log.txt'))

        args = ['http://example.com/',
                '--git-path', '/tmp/gitpath']

        cmd = GitCommand(*args)
        self.assertEqual(cmd.parsed_args.gitpath, '/tmp/gitpath')

        args = ['http://example.com/',
                '--base-path', '/tmp/basepath']

        cmd = GitCommand(*args)
        self.assertEqual(cmd.parsed_args.gitpath, '/tmp/basepath/http://example.com/-git')

        args = ['/tmp/gitpath/']

        cmd = GitCommand(*args)
        self.assertEqual(cmd.parsed_args.gitpath,
                         os.path.join(self.tmp_path, 'testpath/tmp/gitpath/-git'))

    def test_setup_cmd_parser(self):
        """Test if it parser object is correctly initialized"""

        parser = GitCommand.setup_cmd_parser()
        self.assertIsInstance(parser, BackendCommandArgumentParser)
        self.assertEqual(parser._backend, Git)

        args = ['http://example.com/',
                '--git-log', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data/git/git_log.txt'),
                '--tag', 'test',
                '--from-date', '1970-01-01',
                '--to-date', '2100-01-01',
                '--no-update']

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.uri, 'http://example.com/')
        self.assertEqual(parsed_args.git_log, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                           'data/git/git_log.txt'))
        self.assertEqual(parsed_args.tag, 'test')
        self.assertEqual(parsed_args.from_date, DEFAULT_DATETIME)
        self.assertEqual(parsed_args.to_date, DEFAULT_LAST_DATETIME)
        self.assertEqual(parsed_args.branches, None)
        self.assertTrue(parsed_args.no_update)
        self.assertTrue(parsed_args.ssl_verify)

        args = ['http://example.com/',
                '--git-path', '/tmp/gitpath',
                '--branches', 'master', 'testing']

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.git_path, '/tmp/gitpath')
        self.assertEqual(parsed_args.uri, 'http://example.com/')
        self.assertEqual(parsed_args.branches, ['master', 'testing'])
        self.assertFalse(parsed_args.no_update)
        self.assertTrue(parsed_args.ssl_verify)

        args = ['http://example.com/',
                '--base-path', '/tmp/basepath',
                '--no-ssl-verify']

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.base_path, '/tmp/basepath')
        self.assertEqual(parsed_args.uri, 'http://example.com/')
        self.assertFalse(parsed_args.ssl_verify)

    def test_mutual_exclusive_update(self):
        """Test whether an exception is thrown when no-update and latest-items flags are set"""

        parser = GitCommand.setup_cmd_parser()
        args = ['http://example.com/',
                '--git-path', '/tmp/gitpath',
                '--branches', 'master', 'testing',
                '--no-update', '--latest-items']

        with self.assertRaises(SystemExit):
            _ = parser.parse(*args)


class TestGitParser(TestCaseGit):
    """Git parser tests"""

    def test_parser(self):
        """Test if it parsers a git log stream"""

        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "data/git/git_log.txt"), 'r') as f:
            parser = GitParser(f)
            commits = [commit for commit in parser.parse()]

        self.assertEqual(len(commits), 10)

        expected = {
            'commit': '456a68ee1407a77f3e804a30dff245bb6c6b872f',
            'parents': [
                'ce8e0b86a1e9877f42fe9453ede418519115f367',
                '51a3b654f252210572297f47597b31527c475fb8'],
            'refs': ['HEAD -> refs/heads/master'],
            'Merge': 'ce8e0b8 51a3b65',
            'Author': 'Zhongpeng Lin (林中鹏) <lin.zhp@example.com>',
            'AuthorDate': 'Tue Feb 11 22:10:39 2014 -0800',
            'Commit': 'Zhongpeng Lin (林中鹏) <lin.zhp@example.com>',
            'CommitDate': 'Tue Feb 11 22:10:39 2014 -0800',
            'message': "Merge branch 'lzp'\n\nConflicts:\n\taaa/otherthing",
            'files': [
                {
                    'file': "aaa/otherthing.renamed",
                    'added': '1',
                    'removed': '0',
                    'modes': ['100644', '100644', '100644'],
                    'indexes': ['e69de29...', '58a6c75...', '58a6c75...'],
                    'action': 'MR'
                }
            ]
        }
        self.assertDictEqual(commits[0], expected)

        expected = {
            'commit': 'c0d66f92a95e31c77be08dc9d0f11a16715d1885',
            'parents': ['7debcf8a2f57f86663809c58b5c07a398be7674c'],
            'refs': [],
            'Author': 'Eduardo Morais <companheiro.vermelho@example.com>',
            'AuthorDate': 'Tue Aug 14 14:35:02 2012 -0300',
            'Commit': 'Eduardo Morais <companheiro.vermelho@example.com>',
            'CommitDate': 'Tue Aug 14 14:35:02 2012 -0300',
            'message': 'Deleted and renamed file',
            'files': [
                {
                    'file': 'bbb/bthing',
                    'added': '0',
                    'removed': '0',
                    'modes': ['100644', '000000'],
                    'indexes': ['e69de29...', '0000000...'],
                    'action': 'D'
                },
                {
                    'file': 'bbb/something',
                    'newfile': 'bbb/something.renamed',
                    'added': '0',
                    'removed': '0',
                    'modes': ['100644', '100644'],
                    'indexes': ['e69de29...', 'e69de29...'],
                    'action': 'R100'
                }
            ]
        }
        self.assertDictEqual(commits[5], expected)

        expected = {
            'commit': '49345fe87bd1dfad7e682f6554f7472c5576a8c7',
            'parents': [],
            'refs': [],
            'Author': 'Eduardo Morais <companheiro.vermelho@example.com>',
            'AuthorDate': 'Tue Jan 9 15:30:49 2018 +0100',
            'Commit': 'Eduardo Morais <companheiro.vermelho@example.com>',
            'CommitDate': 'Tue Jan 9 15:30:49 2018 +0100',
            'message': 'Moving things around',
            'files': [
                {
                    'file': 'src1/file3.txt',
                    'newfile': 'src3/file3.txt',
                    'added': '0',
                    'removed': '0',
                    'modes': ['100644', '100644'],
                    'indexes': ['802992c...', '802992c...'],
                    'action': 'R100'
                },
                {
                    'file': 'src2/file2.txt',
                    'newfile': 'src3/file4.txt',
                    'added': '0',
                    'removed': '0',
                    'modes': ['100644', '100644'],
                    'indexes': ['802992c...', '802992c...'],
                    'action': 'R100'
                }
            ]
        }

        self.assertDictEqual(commits[9], expected)

    def test_parser_merge_commit(self):
        """Test if it parses all the available data on a merge commit"""

        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "data/git/git_log_merge.txt"), 'r') as f:
            parser = GitParser(f)
            commits = [commit for commit in parser.parse()]

        self.assertEqual(len(commits), 2)

        expected = {
            'commit': '8cbdd85bda499d028b8f128191f392d701e8e41d',
            'parents': [
                '72b5ac54d620b29cae23d25f0405f2765b466f72',
                '302f0493f0bfaabd6f77ce7bfaa12620abf74948'
            ],
            'refs': [],
            'Merge': '72b5ac5 302f049',
            'Author': 'Linus Torvalds <torvalds@linux-foundation.org>',
            'AuthorDate': 'Tue Aug 2 19:47:06 2016 -0400',
            'Commit': 'Linus Torvalds <torvalds@linux-foundation.org>',
            'CommitDate': 'Tue Aug 2 19:47:06 2016 -0400',
            'message': "Merge tag 'for-linus-v4.8' of git://github.com/martinbrandenburg/linux",
            'files': [
                {
                    'file': "Documentation/filesystems/orangefs.txt",
                    'added': '46',
                    'removed': '4'
                },
                {
                    'file': "fs/orangefs/dcache.c",
                    'added': '4',
                    'removed': '0'
                },
                {
                    'file': "fs/orangefs/inode.c",
                    'added': '3',
                    'removed': '3'
                }
            ]
        }
        self.assertDictEqual(commits[0], expected)

        expected = {
            'commit': '456a68ee1407a77f3e804a30dff245bb6c6b872f',
            'parents': [
                'ce8e0b86a1e9877f42fe9453ede418519115f367',
                '51a3b654f252210572297f47597b31527c475fb8'
            ],
            'refs': ['HEAD -> refs/heads/master'],
            'Merge': 'ce8e0b8 51a3b65',
            'Author': 'Zhongpeng Lin (林中鹏) <lin.zhp@example.com>',
            'AuthorDate': 'Tue Feb 11 22:10:39 2014 -0800',
            'Commit': 'Zhongpeng Lin (林中鹏) <lin.zhp@example.com>',
            'CommitDate': 'Tue Feb 11 22:10:39 2014 -0800',
            'message': "Merge branch 'lzp'\n\nConflicts:\n\taaa/otherthing",
            'files': [
                {
                    'file': "aaa/otherthing.renamed",
                    'added': '1',
                    'removed': '0',
                    'modes': ['100644', '100644', '100644'],
                    'indexes': ['e69de29...', '58a6c75...', '58a6c75...'],
                    'action': 'MR'
                }
            ]
        }
        self.assertDictEqual(commits[1], expected)

    def test_parser_trailers_commit(self):
        """Test if it parses all the available data of commits with trailers"""

        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "data/git/git_log_trailers.txt"), 'r') as f:
            parser = GitParser(f)
            commits = [commit for commit in parser.parse()]

        self.assertEqual(len(commits), 3)

        expected = {
            'commit': '7debcf8a2f57f86663809c58b5c07a398be7674c',
            'parents': ['87783129c3f00d2c81a3a8e585eb86a47e39891a'],
            'refs': [],
            'Author': 'Eduardo Morais <companheiro.vermelho@example.com>',
            'AuthorDate': 'Tue Aug 14 14:33:27 2012 -0300',
            'Commit': 'Eduardo Morais <companheiro.vermelho@example.com>',
            'CommitDate': 'Tue Aug 14 14:33:27 2012 -0300',
            'Signed-off-by': [
                'John Smith <jsmith@example.com>',
                'John Doe <jdoe@example.com>'
            ],
            'message': "Commit with a list of trailers\n"
                       "\n"
                       "Signed-off-by: John Smith <jsmith@example.com>\n"
                       "MyTrailer: this is my trailer\n"
                       "Signed-off-by: John Doe <jdoe@example.com>",
            'files': [
                {
                    'file': 'bbb/ccc/yet_anotherthing',
                    'added': '0',
                    'removed': '0',
                    'modes': ['000000', '100644'],
                    'indexes': ['0000000...', 'e69de29...'],
                    'action': 'A'
                }
            ]
        }

        self.assertDictEqual(commits[0], expected)

    def test_parser_empty_log(self):
        """Test if it parsers an empty git log stream"""

        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "data/git/git_log_empty.txt"), 'r') as f:
            parser = GitParser(f)
            commits = [commit for commit in parser.parse()]

        self.assertListEqual(commits, [])

    def test_commit_pattern(self):
        """Test commit pattern"""

        pattern = GitParser.GIT_COMMIT_REGEXP

        s = "commit bc57a9209f096a130dcc5ba7089a8663f758a703"
        m = pattern.match(s)
        self.assertEqual(m.group('commit'), "bc57a9209f096a130dcc5ba7089a8663f758a703")

        s = "commit ce8e0b86a1e9877f42fe9453ede418519115f367 589bb080f059834829a2a5955bebfd7c2baa110a"
        m = pattern.match(s)
        self.assertEqual(m.group('commit'), "ce8e0b86a1e9877f42fe9453ede418519115f367")
        self.assertEqual(m.group('parents'), "589bb080f059834829a2a5955bebfd7c2baa110a")

        s = "commit 51a3b654f252210572297f47597b31527c475fb8 589bb080f059834829a2a5955bebfd7c2baa110a (refs/heads/lzp)"
        m = pattern.match(s)
        self.assertEqual(m.group('commit'), "51a3b654f252210572297f47597b31527c475fb8")
        self.assertEqual(m.group('parents'), "589bb080f059834829a2a5955bebfd7c2baa110a")
        self.assertEqual(m.group('refs'), "refs/heads/lzp")

        s = "commit 456a68ee1407a77f3e804a30dff245bb6c6b872f ce8e0b86a1e9877f42fe9453ede418519115f367" + \
            " 51a3b654f252210572297f47597b31527c475fb8 (HEAD -> refs/heads/master)"
        m = pattern.match(s)
        self.assertEqual(m.group('commit'), "456a68ee1407a77f3e804a30dff245bb6c6b872f")
        self.assertEqual(m.group('parents'), "ce8e0b86a1e9877f42fe9453ede418519115f367 51a3b654f252210572297f47597b31527c475fb8")
        self.assertEqual(m.group('refs'), "HEAD -> refs/heads/master")

    def test_header_trailer_pattern(self):
        """Test header pattern"""

        pattern = GitParser.GIT_HEADER_TRAILER_REGEXP

        s = "Merge: ce8e0b8 51a3b65"
        m = pattern.match(s)
        self.assertEqual(m.group('name'), "Merge")
        self.assertEqual(m.group('value'), "ce8e0b8 51a3b65")

        s = "Author:     Eduardo Morais <companheiro.vermelho@example.com>"
        m = pattern.match(s)
        self.assertEqual(m.group('name'), "Author")
        self.assertEqual(m.group('value'), "Eduardo Morais <companheiro.vermelho@example.com>")

        s = "CommitDate: Tue Feb 11 22:07:49 2014 -0800"
        m = pattern.match(s)
        self.assertEqual(m.group('name'), "CommitDate")
        self.assertEqual(m.group('value'), "Tue Feb 11 22:07:49 2014 -0800")

        s = "Signed-off-by:    Jonh Doe <jdoe@example.com>"
        m = pattern.match(s)
        self.assertEqual(m.group('name'), "Signed-off-by")
        self.assertEqual(m.group('value'), "Jonh Doe <jdoe@example.com>")

    def test_message_line_pattern(self):
        """Test message line pattern"""

        pattern = GitParser.GIT_MESSAGE_REGEXP

        s = "    \trename aaa/otherthing"
        m = pattern.match(s)
        self.assertEqual(m.group('msg'), "\trename aaa/otherthing")

        s = "    "
        m = pattern.match(s)
        self.assertEqual(m.group('msg'), "")

    def test_action_pattern(self):
        """Test action pattern"""

        pattern = GitParser.GIT_ACTION_REGEXP

        s = ":100644 000000 e69de29... 0000000... D\tbbb/bthing"
        m = pattern.match(s)
        self.assertEqual(m.group('modes'), "100644 000000 ")
        self.assertEqual(m.group('indexes'), "e69de29... 0000000... ")
        self.assertEqual(m.group('action'), "D")
        self.assertEqual(m.group('file'), "bbb/bthing")

        s = ":100644 100644 e69de29... e69de29... R100\taaa/otherthing\taaa/otherthing.renamed"
        m = pattern.match(s)
        self.assertEqual(m.group('modes'), "100644 100644 ")
        self.assertEqual(m.group('indexes'), "e69de29... e69de29... ")
        self.assertEqual(m.group('action'), "R100")
        self.assertEqual(m.group('file'), "aaa/otherthing")
        self.assertEqual(m.group('newfile'), "aaa/otherthing.renamed")

    def test_stats_pattern(self):
        """Test stats pattern"""

        pattern = GitParser.GIT_STATS_REGEXP

        s = "8\t7\tperceval/backends/gerrit.py"
        m = pattern.match(s)
        self.assertEqual(m.group('added'), "8")
        self.assertEqual(m.group('removed'), "7")
        self.assertEqual(m.group('file'), "perceval/backends/gerrit.py")

        s = "0\t0\t{aaa => bbb}/something"
        m = pattern.match(s)
        self.assertEqual(m.group('added'), "0")
        self.assertEqual(m.group('removed'), "0")
        self.assertEqual(m.group('file'), "{aaa => bbb}/something")

        s = "1\t0\tbbb/{something => something.renamed}"
        m = pattern.match(s)
        self.assertEqual(m.group('added'), "1")
        self.assertEqual(m.group('removed'), "0")
        self.assertEqual(m.group('file'), "bbb/{something => something.renamed}")

    def test_empty_line(self):
        """Test empty line pattern"""

        pattern = GitParser.GIT_NEXT_STATE_REGEXP

        s = ""
        m = pattern.match(s)
        self.assertIsNotNone(m)


class TestEmptyRepositoryError(TestCaseGit):
    """EmptyRepositoryError tests"""

    def test_message(self):
        """Make sure that prints the correct error"""

        e = EmptyRepositoryError(repository='gittest')
        self.assertEqual('gittest is empty', str(e))


def count_commits(gitpath):
    """Get the number of commits counting the entries on the log"""

    cmd = ['git', 'log', '--oneline', '--all']
    gitlog = subprocess.check_output(cmd, stderr=subprocess.STDOUT,
                                     cwd=gitpath,
                                     env={'LANG': 'C', 'PAGER': ''})
    commits = gitlog.strip(b'\n').split(b'\n')
    return len(commits)


def discover_refs(gitpath):
    """Get the references of local repository"""

    cmd = ['git', 'show-ref']
    gitrefs = subprocess.check_output(cmd, stderr=subprocess.STDOUT,
                                      cwd=gitpath,
                                      env={'LANG': 'C', 'PAGER': ''})
    outs = gitrefs.decode('utf-8', errors='surrogateescape').rstrip()

    refs = {}

    for line in outs.split('\n'):
        data = line.split(' ')
        refs[data[1]] = data[0]
    return refs


class TestGitRepository(TestCaseGit):
    """GitRepository tests"""

    @classmethod
    def setUpClass(cls):
        cls.tmp_path = tempfile.mkdtemp(prefix='perceval_')
        cls.tmp_repo_path = os.path.join(cls.tmp_path, 'repos')
        os.mkdir(cls.tmp_repo_path)

        cls.git_path = os.path.join(cls.tmp_path, 'gittest')
        cls.git_detached_path = os.path.join(cls.tmp_path, 'gitdetached')
        cls.git_empty_path = os.path.join(cls.tmp_path, 'gittestempty')
        cls.git_no_refs_path = os.path.join(cls.tmp_path, 'gitnorefs')
        cls.git_alternates_path = os.path.join(cls.tmp_path, 'gitalternates')

        data_path = os.path.dirname(os.path.abspath(__file__))
        data_path = os.path.join(data_path, 'data/git')

        repos = [
            ('gittest', cls.git_path),
            ('gitdetached', cls.git_detached_path),
            ('gittestempty', cls.git_empty_path),
            ('gittest_no_refs', cls.git_no_refs_path),
            ('gitalternates', cls.git_alternates_path)
        ]

        fdout, _ = tempfile.mkstemp(dir=cls.tmp_path)

        for repo_name, repo_path in repos:
            tar_path = os.path.join(data_path, repo_name + '.tar.gz')
            subprocess.check_call(['tar', '-xzf', tar_path, '-C', cls.tmp_repo_path])

            origin_path = os.path.join(cls.tmp_repo_path, repo_name)
            subprocess.check_call(['git', 'clone', '-q', '--bare', origin_path, repo_path],
                                  stderr=fdout)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp_path)

    def test_init(self):
        """Test initialization"""

        repo = GitRepository('http://example.git', self.git_path)

        self.assertIsInstance(repo, GitRepository)
        self.assertEqual(repo.uri, 'http://example.git')
        self.assertEqual(repo.dirpath, self.git_path)

        # Check command environment variables
        expected = {
            'LANG': 'C',
            'PAGER': '',
            'HTTP_PROXY': '',
            'HTTPS_PROXY': '',
            'NO_PROXY': '',
            'HOME': ''
        }
        self.assertDictEqual(repo.gitenv, expected)

    def test_not_existing_repo_on_init(self):
        """Test if init fails when the repos does not exists"""

        expected = "directory '%s' is not a Git mirror of repository '%s'" \
            % (self.tmp_path, 'http://example.org')

        with self.assertRaisesRegex(RepositoryError, expected):
            _ = GitRepository('http://example.org', self.tmp_path)

    def test_clone(self):
        """Test if a git repository is cloned"""

        new_path = os.path.join(self.tmp_path, 'newgit')

        repo = GitRepository.clone(self.git_path, new_path)

        self.assertIsInstance(repo, GitRepository)
        self.assertEqual(repo.uri, self.git_path)
        self.assertEqual(repo.dirpath, new_path)
        self.assertTrue(os.path.exists(new_path))
        self.assertTrue(os.path.exists(os.path.join(new_path, 'HEAD')))

        shutil.rmtree(new_path)

        # Disabling SSL verification must have the same behavior
        repo = GitRepository.clone(self.git_path, new_path, ssl_verify=False)

        self.assertIsInstance(repo, GitRepository)
        self.assertEqual(repo.uri, self.git_path)
        self.assertEqual(repo.dirpath, new_path)
        self.assertTrue(os.path.exists(new_path))
        self.assertTrue(os.path.exists(os.path.join(new_path, 'HEAD')))

        shutil.rmtree(new_path)

    def test_not_git(self):
        """Test if a supposed git repo is not a git repo"""

        new_path = os.path.join(self.tmp_path, 'falsegit')

        expected = "directory '%s' for Git repository '%s' does not exist" \
            % (new_path, '')

        with self.assertRaisesRegex(RepositoryError, expected):
            _ = GitRepository(uri="", dirpath=new_path)

        if not os.path.isdir(new_path):
            os.makedirs(new_path)

        expected = "directory '%s' is not a Git mirror of repository '%s'" \
            % (new_path, '')

        with self.assertRaisesRegex(RepositoryError, expected):
            _ = GitRepository(uri="", dirpath=new_path)

        shutil.rmtree(new_path)

    def test_clone_error(self):
        """Test if it raises an exception when an error occurs cloning a repository"""

        # Clone a non-git repository
        new_path = os.path.join(self.tmp_path, 'newgit')

        expected = "git command - fatal: repository '%s' does not exist" \
            % self.tmp_path

        with self.assertRaisesRegex(RepositoryError, expected):
            _ = GitRepository.clone(self.tmp_path, new_path)

    def test_clone_existing_directory(self):
        """Test if it raises an exception when tries to clone an existing directory"""

        expected = "git command - fatal: destination path '%s' already exists" \
            % (self.tmp_path)

        with self.assertRaisesRegex(RepositoryError, expected):
            _ = GitRepository.clone(self.git_path, self.tmp_path)

    def test_count_objects(self):
        """Test if it gets the number of objects in a repository"""

        new_path = os.path.join(self.tmp_path, 'newgit')
        repo = GitRepository.clone(self.git_path, new_path)

        nobjs = repo.count_objects()
        self.assertEqual(nobjs, 42)

        shutil.rmtree(new_path)

    def test_count_objects_invalid_output(self):
        """Test if an exception is raised when count_objects output is invalid"""

        new_path = os.path.join(self.tmp_path, 'newgit')
        repo = GitRepository.clone(self.git_path, new_path)

        # Check missing value
        expected = "unable to parse 'count-objects' output;" + \
            " reason: 'in-pack' entry not found"

        with unittest.mock.patch('perceval.backends.core.git.GitRepository._exec') as mock_exec:
            mock_exec.return_value = b'count: 69\n:sze: 900\n'

            with self.assertRaises(RepositoryError) as e:
                _ = repo.count_objects()

        self.assertEqual(str(e.exception), expected)

        # Check invalid output
        with unittest.mock.patch('perceval.backends.core.git.GitRepository._exec') as mock_exec:
            mock_exec.return_value = b'invalid value'

            with self.assertRaises(RepositoryError) as e:
                _ = repo.count_objects()

        shutil.rmtree(new_path)

    def test_is_detached(self):
        """Test if a repository is in detached state or not"""

        new_path = os.path.join(self.tmp_path, 'newgit')
        repo = GitRepository.clone(self.git_path, new_path)

        is_detached = repo.is_detached()
        self.assertEqual(is_detached, False)

        shutil.rmtree(new_path)

        new_path = os.path.join(self.tmp_path, 'newgit')
        repo = GitRepository.clone(self.git_detached_path, new_path)

        is_detached = repo.is_detached()
        self.assertEqual(is_detached, True)

        shutil.rmtree(new_path)

    def test_is_empty(self):
        """Test if a repository is empty or not"""

        new_path = os.path.join(self.tmp_path, 'newgit')
        repo = GitRepository.clone(self.git_path, new_path)

        is_empty = repo.is_empty()
        self.assertEqual(is_empty, False)

        shutil.rmtree(new_path)

        new_path = os.path.join(self.tmp_path, 'newgit')
        repo = GitRepository.clone(self.git_empty_path, new_path)

        is_empty = repo.is_empty()
        self.assertEqual(is_empty, True)

        shutil.rmtree(new_path)

    def test_has_alternates(self):
        """Test if a repository has alternates objects or not"""

        new_path = os.path.join(self.tmp_path, 'newgit')
        repo = GitRepository.clone(self.git_path, new_path)

        alternates = repo.has_alternates()
        self.assertEqual(alternates, False)

        shutil.rmtree(new_path)

        new_path = os.path.join(self.tmp_path, 'alternatesgit')
        repo = GitRepository.clone(self.git_alternates_path, new_path)

        alternates = repo.has_alternates()
        self.assertEqual(alternates, True)

        shutil.rmtree(new_path)

    def test_update(self):
        """Test if the repository is updated to 'origin' status"""

        new_path = os.path.join(self.tmp_path, 'newgit')
        repo = GitRepository.clone(self.git_path, new_path)

        # Check the reference of 'refs/heads/master'
        refs = discover_refs(new_path)
        self.assertEqual(refs['refs/heads/master'],
                         '456a68ee1407a77f3e804a30dff245bb6c6b872f')

        cmd = ['git', 'update-ref',
               'refs/heads/master',
               '589bb080f059834829a2a5955bebfd7c2baa110a']
        subprocess.check_output(cmd, stderr=subprocess.STDOUT,
                                cwd=new_path, env={'LANG': 'C'})

        # Check the new reference of 'refs/heads/master'
        refs = discover_refs(new_path)
        self.assertEqual(refs['refs/heads/master'],
                         '589bb080f059834829a2a5955bebfd7c2baa110a')

        # Update the repository to its original status
        repo.update()

        # The reference should be updated to its original value
        refs = discover_refs(new_path)
        self.assertEqual(refs['refs/heads/master'],
                         '456a68ee1407a77f3e804a30dff245bb6c6b872f')

        shutil.rmtree(new_path)

    def test_update_empty_repository(self):
        """Test if no exception is raised when the repository is empty"""

        new_path = os.path.join(self.tmp_path, 'newgit')
        repo = GitRepository.clone(self.git_empty_path, new_path)
        repo.update()

        shutil.rmtree(new_path)

    def test_sync(self):
        """Test if the repository is synchonized with its remote repo"""

        origin_path = os.path.join(self.tmp_repo_path, 'gittest')
        editable_path = os.path.join(self.tmp_path, 'editgit')
        new_path = os.path.join(self.tmp_path, 'newgit')
        new_file = os.path.join(editable_path, 'newfile')

        shutil.copytree(origin_path, editable_path)

        repo = GitRepository.clone(editable_path, new_path)
        repo.sync()

        # Count the number of commits before adding some new
        ncommits = count_commits(new_path)
        self.assertEqual(ncommits, 9)

        cmd = ['git', 'checkout', '-b', 'mybranch']
        subprocess.check_output(cmd, stderr=subprocess.STDOUT,
                                cwd=editable_path, env={'LANG': 'C'})

        # Create a new file and commit it to the repository
        with open(new_file, 'w') as f:
            f.write("Testing sync method")

        cmd = ['git', 'add', new_file]
        subprocess.check_output(cmd, stderr=subprocess.STDOUT,
                                cwd=editable_path, env={'LANG': 'C'})

        cmd = ['git', '-c', 'user.name="mock"',
               '-c', 'user.email="mock@example.com"',
               'commit', '-m', 'Testing sync']
        subprocess.check_output(cmd, stderr=subprocess.STDOUT,
                                cwd=editable_path, env={'LANG': 'C'})

        cmd = ['git', 'rm', new_file]
        subprocess.check_output(cmd, stderr=subprocess.STDOUT,
                                cwd=editable_path, env={'LANG': 'C'})

        cmd = ['git', '-c', 'user.name="mock"',
               '-c', 'user.email="mock@example.com"',
               'commit', '-m', 'Removing testing file for sync']
        subprocess.check_output(cmd, stderr=subprocess.STDOUT,
                                cwd=editable_path, env={'LANG': 'C'})

        # Count the number of commits and refs after adding
        # the branch and the file
        new_commits = repo.sync()
        ncommits = count_commits(new_path)
        self.assertEqual(ncommits, 11)
        self.assertEqual(len(new_commits), 2)

        expected = [
            'refs/heads/lzp',
            'refs/heads/master',
            'refs/heads/mybranch'
        ]
        refs = [ref for ref in discover_refs(new_path).keys()]
        refs.sort()
        self.assertListEqual(refs, expected)

        # Remove 'lzp' branch and check the number of commits and refs
        cmd = ['git', 'branch', '-D', 'lzp']
        subprocess.check_output(cmd, stderr=subprocess.STDOUT,
                                cwd=editable_path, env={'LANG': 'C'})

        new_commits = repo.sync()
        ncommits = count_commits(new_path)
        self.assertEqual(ncommits, 11)
        self.assertEqual(len(new_commits), 0)

        expected = [
            'refs/heads/master',
            'refs/heads/mybranch'
        ]
        refs = [ref for ref in discover_refs(new_path).keys()]
        refs.sort()
        self.assertListEqual(refs, expected)

        # Cleanup
        shutil.rmtree(editable_path)
        shutil.rmtree(new_path)

    def test_sync_from_empty_repos(self):
        """Test sync process on empty repositories"""

        new_path = os.path.join(self.tmp_path, 'newgit')

        repo = GitRepository.clone(self.git_empty_path, new_path)

        with self.assertRaises(EmptyRepositoryError):
            repo.sync()

        shutil.rmtree(new_path)

    def test_sync_from_repos_without_refs(self):
        """Test sync process on repositories with no refs"""

        new_path = os.path.join(self.tmp_path, 'norefs')

        repo = GitRepository.clone(self.git_no_refs_path, new_path)
        new_commits = repo.sync()
        self.assertListEqual(new_commits, [])

        shutil.rmtree(new_path)

    def test_rev_list(self):
        """Test rev-list command"""

        new_path = os.path.join(self.tmp_path, 'newgit')

        repo = GitRepository.clone(self.git_path, new_path)
        gitrev = repo.rev_list()
        gitrev = [line for line in gitrev]

        expected = ['456a68ee1407a77f3e804a30dff245bb6c6b872f',
                    '51a3b654f252210572297f47597b31527c475fb8',
                    'ce8e0b86a1e9877f42fe9453ede418519115f367',
                    '589bb080f059834829a2a5955bebfd7c2baa110a',
                    'c6ba8f7a1058db3e6b4bc6f1090e932b107605fb',
                    'c0d66f92a95e31c77be08dc9d0f11a16715d1885',
                    '7debcf8a2f57f86663809c58b5c07a398be7674c',
                    '87783129c3f00d2c81a3a8e585eb86a47e39891a',
                    'bc57a9209f096a130dcc5ba7089a8663f758a703',
                    '49345fe87bd1dfad7e682f6554f7472c5576a8c7']

        self.assertTrue(len(gitrev), len(expected))
        for i in range(len(gitrev)):
            self.assertEqual(gitrev[i], expected[i])

        shutil.rmtree(new_path)

    def test_rev_list_branch(self):
        """Test whether the rev-list command returns the commits of a branch, when the latter is given"""

        new_path = os.path.join(self.tmp_path, 'newgit')

        repo = GitRepository.clone(self.git_path, new_path)
        gitrev = repo.rev_list(branches=['lzp'])
        gitrev = [line for line in gitrev]

        expected = ['51a3b654f252210572297f47597b31527c475fb8',
                    '589bb080f059834829a2a5955bebfd7c2baa110a',
                    'c6ba8f7a1058db3e6b4bc6f1090e932b107605fb',
                    'c0d66f92a95e31c77be08dc9d0f11a16715d1885',
                    '7debcf8a2f57f86663809c58b5c07a398be7674c',
                    '87783129c3f00d2c81a3a8e585eb86a47e39891a',
                    'bc57a9209f096a130dcc5ba7089a8663f758a703']

        self.assertTrue(len(gitrev), len(expected))
        for i in range(len(gitrev)):
            self.assertEqual(gitrev[i], expected[i])

        shutil.rmtree(new_path)

    def test_rev_list_no_branch(self):
        """Test whether the rev-list command returns an empty list when no branch is given"""

        new_path = os.path.join(self.tmp_path, 'newgit')

        repo = GitRepository.clone(self.git_path, new_path)
        gitrev = repo.rev_list(branches=[])
        gitrev = [line for line in gitrev]

        expected = []

        self.assertListEqual(gitrev, expected)
        shutil.rmtree(new_path)

    def test_rev_list_from_empty_repository(self):
        """Test if an exception is raised when the repository is empty"""

        new_path = os.path.join(self.tmp_path, 'newgit')

        repo = GitRepository.clone(self.git_empty_path, new_path)
        gitrev = repo.rev_list()

        with self.assertRaises(EmptyRepositoryError):
            _ = [line for line in gitrev]

        shutil.rmtree(new_path)

    def test_log(self):
        """Test log command"""

        new_path = os.path.join(self.tmp_path, 'newgit')

        repo = GitRepository.clone(self.git_path, new_path)
        gitlog = repo.log()
        gitlog = [line for line in gitlog]
        self.assertEqual(len(gitlog), 108)
        self.assertEqual(gitlog[0][:14], "commit bc57a92")

        shutil.rmtree(new_path)

    def test_log_to_date(self):
        """Test if commits are returned before the given date"""

        new_path = os.path.join(self.tmp_path, 'newgit')

        repo = GitRepository.clone(self.git_path, new_path)
        gitlog = repo.log(to_date=datetime.datetime(2014, 2, 11, 22, 7, 49))
        gitlog = [line for line in gitlog]

        self.assertEqual(len(gitlog), 71)
        self.assertEqual(gitlog[0][:14], "commit bc57a92")

        shutil.rmtree(new_path)

    def test_log_from_date(self):
        """Test if commits are returned from the given date"""

        new_path = os.path.join(self.tmp_path, 'newgit')

        repo = GitRepository.clone(self.git_path, new_path)
        gitlog = repo.log(from_date=datetime.datetime(2014, 2, 11, 22, 7, 49))
        gitlog = [line for line in gitlog]

        self.assertEqual(len(gitlog), 36)
        self.assertEqual(gitlog[0][:14], "commit ce8e0b8")

        # Use a timezone, it will return an empty line
        from_date = datetime.datetime(2014, 2, 11, 22, 7, 49,
                                      tzinfo=dateutil.tz.tzoffset(None, -36000))
        gitlog = repo.log(from_date=from_date)
        gitlog = [line for line in gitlog]

        self.assertEqual(gitlog, [])

        shutil.rmtree(new_path)

    def test_log_empty(self):
        """Test if no line is returned when the log is empty"""

        new_path = os.path.join(self.tmp_path, 'newgit')

        repo = GitRepository.clone(self.git_path, new_path)
        gitlog = repo.log(from_date=datetime.datetime(2020, 1, 1, 1, 1, 1))
        gitlog = [line for line in gitlog]

        self.assertListEqual(gitlog, [])

        shutil.rmtree(new_path)

    def test_log_from_empty_repository(self):
        """Test if an exception is raised when the repository is empty"""

        new_path = os.path.join(self.tmp_path, 'newgit')

        repo = GitRepository.clone(self.git_empty_path, new_path)
        gitlog = repo.log()

        with self.assertRaises(EmptyRepositoryError):
            _ = [line for line in gitlog]

        shutil.rmtree(new_path)

    def test_log_alternates(self):
        """Test log command with alternate objects"""

        repo_path = os.path.join(self.tmp_path, 'newrepo')
        repo = GitRepository.clone(self.git_alternates_path, repo_path)

        # Logs are from 'gittest' repository, 'gitalternates' is empty
        self.assertTrue(repo.is_empty())
        self.assertTrue(repo.has_alternates())

        gitlog = repo.log()
        gitlog = [line for line in gitlog]
        self.assertEqual(len(gitlog), 108)
        self.assertEqual(gitlog[0][:14], "commit bc57a92")

        expected_path = os.path.join(self.git_path, 'objects')
        alternates_path = os.path.join(repo_path, 'objects/info/alternates')
        with open(alternates_path, 'r') as f:
            self.assertEqual(f.readline()[:-1], expected_path)

        shutil.rmtree(repo_path)

    def test_git_show(self):
        """Test show command"""

        new_path = os.path.join(self.tmp_path, 'newgit')

        repo = GitRepository.clone(self.git_path, new_path)
        gitshow = repo.show()
        gitshow = [line for line in gitshow]
        self.assertEqual(len(gitshow), 14)
        self.assertEqual(gitshow[0][:14], "commit 456a68e")

        shutil.rmtree(new_path)

    def test_show_alternates(self):
        """Test show command with alternate objects"""

        repo_path = os.path.join(self.tmp_path, 'newrepo')
        repo = GitRepository.clone(self.git_alternates_path, repo_path)

        # Show is from 'gittest' repository, 'gitalternates' is empty
        self.assertTrue(repo.is_empty())
        self.assertTrue(repo.has_alternates())

        commits = ['51a3b65', '8778312']
        gitshow = repo.show(commits=commits)
        gitshow = [line for line in gitshow]
        self.assertEqual(len(gitshow), 21)
        self.assertEqual(gitshow[0][:14], "commit 51a3b65")
        self.assertEqual(gitshow[11][:14], "commit 8778312")

        expected_path = os.path.join(self.git_path, 'objects')
        alternates_path = os.path.join(repo_path, 'objects/info/alternates')
        with open(alternates_path, 'r') as f:
            self.assertEqual(f.readline()[:-1], expected_path)

        shutil.rmtree(repo_path)

    def test_show_commit_list(self):
        """Test show command using a list of commits"""

        new_path = os.path.join(self.tmp_path, 'newgit')

        repo = GitRepository.clone(self.git_path, new_path)
        commits = ['51a3b65', '8778312']
        gitshow = repo.show(commits=commits)
        gitshow = [line for line in gitshow]
        self.assertEqual(len(gitshow), 21)
        self.assertEqual(gitshow[0][:14], "commit 51a3b65")
        self.assertEqual(gitshow[11][:14], "commit 8778312")

        # When an empty list is given, the output is the
        # data from the last commit
        gitshow = repo.show(commits=[])
        gitshow = [line for line in gitshow]
        self.assertEqual(len(gitshow), 14)
        self.assertEqual(gitshow[0][:14], "commit 456a68e")

        shutil.rmtree(new_path)

    def test_git_show_from_emtpy_repository(self):
        """Test if an exception is raised when the repository is empty"""

        new_path = os.path.join(self.tmp_path, 'newgit')

        repo = GitRepository.clone(self.git_empty_path, new_path)
        gitshow = repo.show()

        with self.assertRaises(EmptyRepositoryError):
            _ = [line for line in gitshow]

        shutil.rmtree(new_path)


if __name__ == "__main__":
    unittest.main()
