#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2015-2016 Bitergia
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

import os
import shutil
import sys
import tempfile
import unittest

if not '..' in sys.path:
    sys.path.insert(0, '..')

from perceval.cache import Cache


CACHE_DIR = 'mockrepo'


class TestCache(unittest.TestCase):
    """Cache tests"""

    def setUp(self):
        self.test_path = tempfile.mkdtemp(prefix='perceval_')

    def tearDown(self):
        shutil.rmtree(self.test_path)

    def test_struct(self):
        """Test whether the structure of a cache directory is created"""

        cache_path = os.path.join(self.test_path, CACHE_DIR)

        cache = Cache(cache_path)

        self.assertEqual(cache.cache_path, cache_path)
        self.assertEqual(os.path.exists(cache.cache_path), True)

        items_path = os.path.join(cache_path, 'items')
        self.assertEqual(cache.items_path, items_path)
        self.assertEqual(os.path.exists(cache.items_path), True)

        recovery_path = os.path.join(cache_path, 'recovery')
        self.assertEqual(cache.recovery_path, recovery_path)
        self.assertEqual(os.path.exists(cache.recovery_path), True)

        cache_files = os.path.join(items_path, cache.CACHE_PREFIX)
        self.assertEqual(cache.cache_files, cache_files)

    def test_store_and_retrieve(self):
        """Test whether objects are stored and retrieved"""

        expected = ['a', 'b', 'c']

        cache_path = os.path.join(self.test_path, CACHE_DIR)
        cache = Cache(cache_path)
        cache.store(*expected)

        contents = [item for item in cache.retrieve()]
        self.assertListEqual(contents, expected)

    def test_backup(self):
        """Test backup method"""

        items = [1, 2, 3, 4, 5]

        cache_path = os.path.join(self.test_path, CACHE_DIR)
        cache = Cache(cache_path)
        cache.store(*items)
        cache.backup()

        expected = [f for f in os.listdir(cache.items_path)]
        rfiles = [f for f in os.listdir(cache.recovery_path)]
        self.assertEqual(rfiles, expected)
        self.assertNotEqual(len(rfiles), 0)

    def test_clean(self):
        """Test clean method"""

        items = [1, 2, 3, 4, 5]

        cache_path = os.path.join(self.test_path, CACHE_DIR)
        cache = Cache(cache_path)
        cache.store(*items)

        expected = [f for f in os.listdir(cache.items_path)]

        cache.clean()

        # Check the contents and the files stored in each directory
        contents = [item for item in cache.retrieve()]
        self.assertEqual(len(contents), 0)

        rfiles = [f for f in os.listdir(cache.recovery_path)]
        self.assertEqual(rfiles, expected)
        self.assertNotEqual(len(rfiles), 0)

        # Check erase mode
        cache.store(*items)
        cache.clean(erase=True)

        contents = [item for item in cache.retrieve()]
        self.assertEqual(len(contents), 0)

        rfiles = [f for f in os.listdir(cache.recovery_path)]
        self.assertEqual(len(rfiles), 0)

    def test_recover(self):
        """Test recover method"""

        expected = [1, 2, 3, 4, 5]

        cache_path = os.path.join(self.test_path, CACHE_DIR)
        cache = Cache(cache_path)
        cache.store(*expected)
        cache.backup()
        cache.clean()

        contents = [item for item in cache.retrieve()]
        self.assertEqual(len(contents), 0)

        cache.recover()
        contents = [item for item in cache.retrieve()]
        self.assertListEqual(contents, expected)


if __name__ == "__main__":
    unittest.main()
