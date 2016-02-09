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
from perceval.backends.mbox import MBoxArchive, MailingList


class TestBaseMBox(unittest.TestCase):
    """MBox base case class"""

    @classmethod
    def setUpClass(cls):
        cls.tmp_path = tempfile.mkdtemp(prefix='perceval_')

        cls.cfiles = {'bz2' : os.path.join(cls.tmp_path, 'bz2'),
                      'gz'  : os.path.join(cls.tmp_path, 'gz')}

        # Copy compressed files
        for ftype, fname in cls.cfiles.items():
            if ftype == 'bz2':
                mod = bz2
            else:
                mod = gzip

            with open('data/mbox_single.mbox', 'rb') as f_in:
                with mod.open(fname, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)

        # Copy a plain file
        cls.files = {'single' : os.path.join(cls.tmp_path, 'mbox_single.mbox')}

        shutil.copy('data/mbox_single.mbox', cls.tmp_path)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp_path)


class TestMBoxArchive(TestBaseMBox):
    """Tests for MBoxArchive class"""

    def test_filepath(self):
        """Test filepath property"""

        mbox = MBoxArchive(self.cfiles['gz'])
        self.assertEqual(mbox.filepath, self.cfiles['gz'])

    def test_compressed(self):
        """Test compressed properties"""

        mbox = MBoxArchive(self.cfiles['bz2'])
        self.assertEqual(mbox.compressed_type, 'bz2')
        self.assertEqual(mbox.is_compressed(), True)

        mbox = MBoxArchive(self.cfiles['gz'])
        self.assertEqual(mbox.compressed_type, 'gz')
        self.assertEqual(mbox.is_compressed(), True)

    def test_not_compressed(self):
        """Check the properties of a non-compressed archive"""

        mbox = MBoxArchive(self.files['single'])
        self.assertEqual(mbox.compressed_type, None)
        self.assertEqual(mbox.is_compressed(), False)

    def test_container(self):
        """Check the type of the container of an archive"""

        mbox = MBoxArchive(self.cfiles['bz2'])
        container = mbox.container
        self.assertIsInstance(container, bz2.BZ2File)
        container.close()

        mbox = MBoxArchive(self.cfiles['gz'])
        container = mbox.container
        self.assertIsInstance(container, gzip.GzipFile)
        container.close()

        import _io
        mbox = MBoxArchive(self.files['single'])
        container = mbox.container
        self.assertIsInstance(container, _io.BufferedReader)
        container.close()


class TestMailingList(TestBaseMBox):
    """Tests for MailingList class"""

    def test_init(self):
        """Check attributes initialization"""

        mls = MailingList('test', self.tmp_path)

        self.assertEqual(mls.origin, 'test')
        self.assertEqual(mls.dirpath, self.tmp_path)

    def test_mboxes(self):
        """Check whether it gets a list of mboxes"""

        mls = MailingList('test', self.tmp_path)

        mboxes = mls.mboxes
        self.assertEqual(len(mboxes), 3)
        self.assertEqual(mboxes[0].filepath, self.cfiles['bz2'])
        self.assertEqual(mboxes[1].filepath, self.cfiles['gz'])
        self.assertEqual(mboxes[2].filepath, self.files['single'])


if __name__ == "__main__":
    unittest.main()
