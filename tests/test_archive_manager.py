#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2015-2017 Bitergia
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
#     Santiago Dueñas <sduenas@bitergia.com>
#

import datetime
import os
import shutil
import sys
import time
import tempfile
import unittest.mock

from grimoirelab.toolkit.datetime import datetime_utcnow, datetime_to_utc

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from perceval.archive_manager import ArchiveManager


class TestArchiveManager(unittest.TestCase):
    """ArchiveManager tests"""

    def setUp(self):
        self.test_path = tempfile.mkdtemp(prefix='perceval_')

    def tearDown(self):
        shutil.rmtree(self.test_path)

    def test_initialization(self):
        """Test whether the archive manager parameters are properly initialized"""

        path = os.path.join(self.test_path, 'myarchivemanager')
        manager = ArchiveManager(path)

        self.assertEqual(manager.archive_folder_path, path)
        self.assertTrue(os.path.exists(manager.archive_folder_path))

    def test_create_archive(self):
        """Test whether a new archive is created"""

        path = os.path.join(self.test_path, 'myarchivemanager')
        manager = ArchiveManager(path)

        archive = manager.create_archive()

        self.assertTrue(os.path.exists(archive.archive_path))

    def test_load_archive(self):
        """Test whether an existing archive is loaded"""

        path = os.path.join(self.test_path, 'myarchivemanager')
        manager = ArchiveManager(path)

        archive_created = manager.create_archive()
        archive_created.init_metadata("a", "b", "c", "d", {"a": 1})

        archive_loaded = manager.load_archive(archive_created.origin, archive_created.backend_name,
                                              archive_created.backend_version, archive_created.item_category,
                                              archive_created.created_on)

        self.assertEqual(archive_created.origin, archive_loaded.origin)
        self.assertEqual(archive_created.backend_name, archive_loaded.backend_name)
        self.assertEqual(archive_created.backend_version, archive_loaded.backend_version)
        self.assertEqual(archive_created.item_category, archive_loaded.item_category)
        self.assertEqual(archive_created.created_on, archive_loaded.created_on)

    def test_delete_archive(self):
        """Test whether an existing archive is correctly deleted"""

        path = os.path.join(self.test_path, 'myarchivemanager')
        manager = ArchiveManager(path)

        archive = manager.create_archive()
        archive.init_metadata("a", "b", "c", "d", {"a": 1})

        self.assertTrue(os.path.exists(archive.archive_path))

        manager.delete_archive(archive)

        self.assertFalse(os.path.exists(archive.archive_path))

    def test_delete_archives(self):
        """Test whether all existing archives are correctly deleted"""

        path = os.path.join(self.test_path, 'myarchivemanager')
        manager = ArchiveManager(path)

        manager.create_archive()
        manager.create_archive()

        total = len(ArchiveManager._stored_archives(manager.archive_folder_path))
        self.assertEqual(total, 2)

        manager.delete_archives()

        total = len(ArchiveManager._stored_archives(manager.archive_folder_path))
        self.assertEqual(total, 0)

    def test_collect_archives(self):
        """Test whether archives are correctly listed"""

        path = os.path.join(self.test_path, 'myarchivemanager')
        manager = ArchiveManager(path)

        archive_1 = manager.create_archive()
        archive_1.init_metadata("a", "b", "c", "d", {"a": 1})
        time.sleep(1)
        now = datetime_to_utc(datetime_utcnow())
        archive_2 = manager.create_archive()
        archive_2.init_metadata("a", "b", "c", "d", {"a": 1})

        total_archives = len(manager.collect_archives("a", "b", "c", "d",
                                                      datetime_to_utc(datetime.datetime(1970, 1, 1, 00, 00, 00))))
        self.assertEqual(total_archives, 2)

        total_archives = len(manager.collect_archives("a", "b", "c", "d", now))
        self.assertEqual(total_archives, 1)
