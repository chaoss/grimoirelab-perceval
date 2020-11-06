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
#     Quan Zhou <quan@bitergia.com>
#

import os
import shutil
import tempfile
import unittest

from perceval.archive import Archive


class TestCaseBackendArchive(unittest.TestCase):
    """Unit tests for Backend using the archive"""

    def setUp(self):
        self.test_path = tempfile.mkdtemp(prefix='perceval-weblate')
        archive_path = os.path.join(self.test_path, 'myarchive')
        self.archive = Archive.create(archive_path)

    def tearDown(self):
        shutil.rmtree(self.test_path)

    def _test_fetch_from_archive(self, **kwargs):
        """Test whether the method fetch_from_archive works properly"""

        items = [items for items in self.backend_write_archive.fetch(**kwargs)]
        items_archived = [item for item in self.backend_write_archive.fetch_from_archive()]

        self.assertEqual(len(items), len(items_archived))

        for i in range(len(items)):
            item = items[i]
            archived_item = items_archived[i]

            del item['timestamp']
            del archived_item['timestamp']

            self.assertEqual(item, archived_item)
