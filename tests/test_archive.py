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
#     Valerio Cosentino <valcos@bitergia.com>
#     Santiago Dueñas <sduenas@bitergia.com>
#     Miguel Ángel Fernández <mafesan@bitergia.com>
#     Jesus M. Gonzalez-Barahona <jgb@gsyc.es>
#

import os
import pickle
import shutil
import sqlite3
import tempfile
import unittest
import unittest.mock

import httpretty
import requests

from grimoirelab_toolkit.datetime import datetime_utcnow, datetime_to_utc

from perceval.archive import Archive, ArchiveManager
from perceval.errors import ArchiveError, ArchiveManagerError


def count_number_rows(db, table_name):
    conn = sqlite3.connect(db)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM " + table_name)
    nrows = cursor.fetchone()[0]
    cursor.close()
    return nrows


class TestArchive(unittest.TestCase):
    """Archive tests"""

    def setUp(self):
        self.test_path = tempfile.mkdtemp(prefix='perceval_')

    def tearDown(self):
        shutil.rmtree(self.test_path)

    def test_create(self):
        """Test a new an empty archive is created"""

        archive_path = os.path.join(self.test_path, 'myarchive')
        archive = Archive.create(archive_path)

        # Archive file was created
        self.assertEqual(archive.archive_path, archive_path)
        self.assertEqual(os.path.exists(archive.archive_path), True)

        # Properties are initialized
        self.assertEqual(archive.created_on, None)
        self.assertEqual(archive.origin, None)
        self.assertEqual(archive.backend_name, None)
        self.assertEqual(archive.backend_version, None)
        self.assertEqual(archive.category, None)
        self.assertEqual(archive.backend_params, None)

        # Tables are empty
        nrows = count_number_rows(archive_path, Archive.ARCHIVE_TABLE)
        self.assertEqual(nrows, 0)

        nrows = count_number_rows(archive_path, Archive.METADATA_TABLE)
        self.assertEqual(nrows, 0)

    def test_create_existing_archive(self):
        """Test if create method fails when the given archive path already exists"""

        archive_path = os.path.join(self.test_path, 'myarchive')
        Archive.create(archive_path)

        with self.assertRaisesRegex(ArchiveError, "archive %s already exists" % archive_path):
            Archive.create(archive_path)

    def test_init(self):
        """Test whether an archive is propertly initialized"""

        archive_path = os.path.join(self.test_path, 'myarchive')
        _ = Archive.create(archive_path)

        archive = Archive(archive_path)
        self.assertEqual(archive.archive_path, archive_path)
        self.assertEqual(archive.created_on, None)
        self.assertEqual(archive.origin, None)
        self.assertEqual(archive.backend_name, None)
        self.assertEqual(archive.backend_version, None)
        self.assertEqual(archive.category, None)
        self.assertEqual(archive.backend_params, None)

    def test_init_not_existing_archive(self):
        """Test if an exception is raised when the given archive does not exist"""

        archive_path = os.path.join(self.test_path, 'myarchive')

        with self.assertRaisesRegex(ArchiveError, "archive %s does not exist" % archive_path):
            _ = Archive(archive_path)

    def test_init_not_valid_archive(self):
        """Test if an exception is raised when the file is an invalid archive"""

        archive_path = os.path.join(self.test_path, 'invalid_archive')

        with open(archive_path, 'w') as fd:
            fd.write("Invalid archive file")

        with self.assertRaisesRegex(ArchiveError, "invalid archive file"):
            _ = Archive(archive_path)

    def test_init_metadata(self):
        """Test whether metadata information is properly initialized"""

        archive_path = os.path.join(self.test_path, 'myarchive')
        archive = Archive.create(archive_path)

        before_dt = datetime_to_utc(datetime_utcnow())
        archive.init_metadata('marvel.com', 'marvel-comics-backend', '0.1.0',
                              'issue', {'from_date': before_dt})
        after_dt = datetime_to_utc(datetime_utcnow())

        archive_copy = Archive(archive_path)

        # Both copies should have the same parameters
        for arch in [archive, archive_copy]:
            self.assertEqual(arch.origin, 'marvel.com')
            self.assertEqual(arch.backend_name, 'marvel-comics-backend')
            self.assertEqual(arch.backend_version, '0.1.0')
            self.assertEqual(arch.category, 'issue')
            self.assertGreaterEqual(arch.created_on, before_dt)
            self.assertLessEqual(arch.created_on, after_dt)
            self.assertDictEqual(arch.backend_params, {'from_date': before_dt})

    @httpretty.activate
    def test_store(self):
        """Test whether data is properly stored in the archive"""

        data_requests = [
            ("https://example.com/", {'q': 'issues', 'date': '2017-01-10'}, {}),
            ("https://example.com/", {'q': 'issues', 'date': '2018-01-01'}, {}),
            ("https://example.com/tasks", {'task_id': 10}, {'Accept': 'application/json'}),
        ]

        httpretty.register_uri(httpretty.GET,
                               "https://example.com/",
                               body='{"hey": "there"}',
                               status=200)
        httpretty.register_uri(httpretty.GET,
                               "https://example.com/tasks",
                               body='{"task": "my task"}',
                               status=200)

        archive_path = os.path.join(self.test_path, 'myarchive')
        archive = Archive.create(archive_path)

        # Store data in the archive
        responses = []

        for dr in data_requests:
            response = requests.get(dr[0], params=dr[1], headers=dr[2])
            archive.store(dr[0], dr[1], dr[2], response)
            responses.append(response)

        db = sqlite3.connect(archive.archive_path)
        cursor = db.cursor()
        cursor.execute("SELECT hashcode, data, uri, payload, headers FROM archive")
        data_stored = cursor.fetchall()
        cursor.close()

        self.assertEqual(len(data_stored), len(data_requests))

        ds = data_stored[0]
        dr = data_requests[0]
        self.assertEqual(ds[0], '0fa4ce047340780f08efca92f22027514263521d')
        self.assertEqual(pickle.loads(ds[1]).url, responses[0].url)
        self.assertEqual(ds[2], dr[0])
        self.assertEqual(pickle.loads(ds[3]), dr[1])
        self.assertEqual(pickle.loads(ds[4]), dr[2])

        ds = data_stored[1]
        dr = data_requests[1]
        self.assertEqual(ds[0], '3879a6f12828b7ac3a88b7167333e86168f2f5d2')
        self.assertEqual(pickle.loads(ds[1]).url, responses[1].url)
        self.assertEqual(ds[2], dr[0])
        self.assertEqual(pickle.loads(ds[3]), dr[1])
        self.assertEqual(pickle.loads(ds[4]), dr[2])

        ds = data_stored[2]
        dr = data_requests[2]
        self.assertEqual(ds[0], 'ef38f574a0745b63a056e7befdb7a06e7cf1549b')
        self.assertEqual(pickle.loads(ds[1]).url, responses[2].url)
        self.assertEqual(ds[2], dr[0])
        self.assertEqual(pickle.loads(ds[3]), dr[1])
        self.assertEqual(pickle.loads(ds[4]), dr[2])

    @httpretty.activate
    def test_store_duplicate(self):
        """Test whether the insertion of duplicated data throws an error"""

        url = "https://example.com/tasks"
        payload = {'task_id': 10}
        headers = {'Accept': 'application/json'}

        httpretty.register_uri(httpretty.GET,
                               url,
                               body='{"hey": "there"}',
                               status=200)
        response = requests.get(url, params=payload, headers=headers)

        archive_path = os.path.join(self.test_path, 'myarchive')
        archive = Archive.create(archive_path)

        archive.store(url, payload, headers, response)

        # check the unique index filters duplicated API calls
        with self.assertRaisesRegex(ArchiveError, "duplicated entry"):
            archive.store(url, payload, headers, response)

    @httpretty.activate
    def test_retrieve(self):
        """Test whether data is properly retrieved from the archive"""

        url = "https://example.com/tasks"
        payload = {'task_id': 10}
        headers = {'Accept': 'application/json'}

        httpretty.register_uri(httpretty.GET,
                               url,
                               body='{"hey": "there"}',
                               status=200)
        response = requests.get(url, params=payload, headers=headers)

        archive_path = os.path.join(self.test_path, 'myarchive')
        archive = Archive.create(archive_path)
        archive.store(url, payload, headers, response)

        data = archive.retrieve(url, payload, headers)

        self.assertEqual(data.url, response.url)

    def test_retrieve_missing(self):
        """Test whether the retrieval of non archived data throws an error

        In the exceptional case of a failure in retrieving data from an archive (e.g., manual modification),
        an exception is thrown to stop the retrieval from the archive
        """

        archive_path = os.path.join(self.test_path, 'myarchive')
        archive = Archive.create(archive_path)

        with self.assertRaisesRegex(ArchiveError, "not found in archive"):
            _ = archive.retrieve("http://wrong", payload={}, headers={})


ARCHIVE_TEST_DIR = 'archivedir'


class MockUUID:
    def __init__(self, uuid):
        self.hex = uuid


class TestArchiveManager(unittest.TestCase):
    """Archive Manager tests"""

    def setUp(self):
        self.test_path = tempfile.mkdtemp(prefix='perceval_')

    def tearDown(self):
        shutil.rmtree(self.test_path)

    def test_struct(self):
        """Test whether the structure of an archive manager directory is created"""

        archive_mng_path = os.path.join(self.test_path, ARCHIVE_TEST_DIR)

        # Directory does not exist yet
        self.assertEqual(os.path.isdir(archive_mng_path), False)

        # Object and directory are created
        manager = ArchiveManager(archive_mng_path)
        self.assertEqual(manager.dirpath, archive_mng_path)
        self.assertEqual(os.path.isdir(archive_mng_path), True)

        # A new object using the same directory does not create
        # a new directory
        alt_manager = ArchiveManager(archive_mng_path)
        self.assertEqual(alt_manager.dirpath, archive_mng_path)
        self.assertEqual(os.path.isdir(archive_mng_path), True)

    @unittest.mock.patch('uuid.uuid4')
    def test_create_archive(self, mock_uuid):
        """Test if a new archive is created"""

        mock_uuid.return_value = MockUUID('AB0123456789')

        archive_mng_path = os.path.join(self.test_path, ARCHIVE_TEST_DIR)
        manager = ArchiveManager(archive_mng_path)

        archive = manager.create_archive()
        self.assertIsInstance(archive, Archive)

        expected = os.path.join(archive_mng_path, 'AB', '0123456789.sqlite3')
        self.assertEqual(archive.archive_path, expected)
        self.assertEqual(os.path.exists(archive.archive_path), True)

    @unittest.mock.patch('uuid.uuid4')
    def test_create_existing_archive(self, mock_uuid):
        """Test if an exception is raised when the archive to create exists"""

        mock_uuid.return_value = MockUUID('AB0123456789')

        archive_mng_path = os.path.join(self.test_path, ARCHIVE_TEST_DIR)
        manager = ArchiveManager(archive_mng_path)

        # First we create the archive
        archive = manager.create_archive()
        self.assertIsInstance(archive, Archive)

        expected = os.path.join(archive_mng_path, 'AB', '0123456789.sqlite3')
        self.assertEqual(archive.archive_path, expected)

        # The archive already exist so it must raise an exception
        with self.assertRaisesRegex(ArchiveManagerError, 'archive .+ already exists'):
            _ = manager.create_archive()

    def test_remove_archive(self):
        """Test if an archive is removed by the archive manager"""

        archive_mng_path = os.path.join(self.test_path, ARCHIVE_TEST_DIR)
        manager = ArchiveManager(archive_mng_path)

        archive = manager.create_archive()
        self.assertEqual(os.path.exists(archive.archive_path), True)

        manager.remove_archive(archive.archive_path)
        self.assertEqual(os.path.exists(archive.archive_path), False)

    def test_remove_archive_not_found(self):
        """Test if an exception is raised when the archive is not found"""

        archive_mng_path = os.path.join(self.test_path, ARCHIVE_TEST_DIR)
        manager = ArchiveManager(archive_mng_path)

        with self.assertRaisesRegex(ArchiveManagerError, 'archive mockarchive does not exist'):
            manager.remove_archive('mockarchive')

    def test_search(self):
        """Test if a set of archives is found based on the given criteria"""

        archive_mng_path = os.path.join(self.test_path, ARCHIVE_TEST_DIR)
        manager = ArchiveManager(archive_mng_path)

        dt = datetime_utcnow()
        metadata = [
            {
                'origin': 'https://example.com',
                'backend_name': 'git',
                'backend_version': '0.8',
                'category': 'commit',
                'backend_params': {},
            },
            {
                'origin': 'https://example.com',
                'backend_name': 'gerrit',
                'backend_version': '0.1',
                'category': 'changes',
                'backend_params': {}
            },
            {
                'origin': 'https://example.org',
                'backend_name': 'git',
                'backend_version': '0.1',
                'category': 'commit',
                'backend_params': {}
            },
            {
                'origin': 'https://example.com',
                'backend_name': 'git',
                'backend_version': '0.1',
                'category': 'commit',
                'backend_params': {}
            }
        ]

        for meta in metadata:
            archive = manager.create_archive()
            archive.init_metadata(**meta)
            meta['filepath'] = archive.archive_path

        archives = manager.search('https://example.com', 'git', 'commit', dt)

        expected = [metadata[0]['filepath'], metadata[3]['filepath']]
        self.assertListEqual(archives, expected)

    def test_search_archived_after(self):
        """Check if a set of archives created after a given date are searched"""

        archive_mng_path = os.path.join(self.test_path, ARCHIVE_TEST_DIR)
        manager = ArchiveManager(archive_mng_path)

        # First set of archives to create
        metadata = [
            {
                'origin': 'https://example.com',
                'backend_name': 'git',
                'backend_version': '0.8',
                'category': 'commit',
                'backend_params': {},
            },
            {
                'origin': 'https://example.com',
                'backend_name': 'gerrit',
                'backend_version': '0.1',
                'category': 'changes',
                'backend_params': {}
            },
        ]

        for meta in metadata:
            archive = manager.create_archive()
            archive.init_metadata(**meta)

        # Second set, archived after the date we'll use to search
        after_dt = datetime_utcnow()
        metadata = [
            {
                'origin': 'https://example.org',
                'backend_name': 'git',
                'backend_version': '0.1',
                'category': 'commit',
                'backend_params': {}
            },
            {
                'origin': 'https://example.com',
                'backend_name': 'git',
                'backend_version': '0.1',
                'category': 'commit',
                'backend_params': {}
            }
        ]

        for meta in metadata:
            archive = manager.create_archive()
            archive.init_metadata(**meta)
            meta['filepath'] = archive.archive_path

        archives = manager.search('https://example.com', 'git', 'commit',
                                  after_dt)

        expected = [metadata[1]['filepath']]
        self.assertListEqual(archives, expected)

    def test_search_no_match(self):
        """Check if an empty set of archives is returned when none match the criteria"""

        archive_mng_path = os.path.join(self.test_path, ARCHIVE_TEST_DIR)
        manager = ArchiveManager(archive_mng_path)

        dt = datetime_utcnow()
        metadata = [
            {
                'origin': 'https://example.com',
                'backend_name': 'git',
                'backend_version': '0.8',
                'category': 'commit',
                'backend_params': {},
            },
            {
                'origin': 'https://example.com',
                'backend_name': 'gerrit',
                'backend_version': '0.1',
                'category': 'changes',
                'backend_params': {}
            },
            {
                'origin': 'https://example.org',
                'backend_name': 'git',
                'backend_version': '0.1',
                'category': 'commit',
                'backend_params': {}
            },
            {
                'origin': 'https://example.com',
                'backend_name': 'git',
                'backend_version': '0.1',
                'category': 'commit',
                'backend_params': {}
            }
        ]

        for meta in metadata:
            archive = manager.create_archive()
            archive.init_metadata(**meta)
            meta['filepath'] = archive.archive_path

        archives = manager.search('https://example.com', 'bugzilla', 'commit', dt)
        self.assertListEqual(archives, [])


if __name__ == "__main__":
    unittest.main()
