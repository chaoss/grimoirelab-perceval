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

import sys
import os.path
import shutil
import tempfile
import unittest

import bz2
import gzip

if not '..' in sys.path:
    sys.path.insert(0, '..')

from perceval.utils import check_compressed_file_type
from perceval.backends.mbox import MBoxArchive


class TestMBoxArchive(unittest.TestCase):
    """MBoxArchive tests"""

    @classmethod
    def setUpClass(cls):
        cls.tmp_path = tempfile.mkdtemp(prefix='perceval_')

        cls.files = {'bz2' : os.path.join(cls.tmp_path, 'bz2'),
                     'gz'  : os.path.join(cls.tmp_path, 'gz')}

        # Copy compressed files
        for ftype, fname in cls.files.items():
            if ftype == 'bz2':
                mod = bz2
            else:
                mod = gzip

            with open('data/mbox_single.mbox', 'rb') as f_in:
                with mod.open(fname, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)

        # Copy a plain file
        shutil.copy('data/mbox_single.mbox', cls.tmp_path)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp_path)

    def test_filepath(self):
        """Test filepath property"""

        mbox = MBoxArchive(self.files['gz'])
        self.assertEqual(mbox.filepath, self.files['gz'])

    def test_compressed(self):
        """Test compressed properties"""

        mbox = MBoxArchive(self.files['bz2'])
        self.assertEqual(mbox.compressed_type, 'bz2')
        self.assertEqual(mbox.is_compressed(), True)

        mbox = MBoxArchive(self.files['gz'])
        self.assertEqual(mbox.compressed_type, 'gz')
        self.assertEqual(mbox.is_compressed(), True)

    def test_not_compressed(self):
        """Check the properties of a non-compressed archive"""

        fpath = os.path.join(self.tmp_path, 'mbox_single.mbox')
        mbox = MBoxArchive(fpath)
        self.assertEqual(mbox.compressed_type, None)
        self.assertEqual(mbox.is_compressed(), False)

    def test_container(self):
        """Check the type of the container of an archive"""

        mbox = MBoxArchive(self.files['bz2'])
        container = mbox.container
        self.assertIsInstance(container, bz2.BZ2File)
        container.close()

        mbox = MBoxArchive(self.files['gz'])
        container = mbox.container
        self.assertIsInstance(container, gzip.GzipFile)
        container.close()

        import _io
        fpath = os.path.join(self.tmp_path, 'mbox_single.mbox')
        mbox = MBoxArchive(fpath)
        container = mbox.container
        self.assertIsInstance(container, _io.BufferedReader)
        container.close()


if __name__ == "__main__":
    unittest.main()
