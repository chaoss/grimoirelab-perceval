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

import datetime
import os
import shutil
import sys
import tempfile
import unittest

import httpretty

if not '..' in sys.path:
    sys.path.insert(0, '..')

from perceval.backends.mbox import MailingList
from perceval.backends.pipermail import PipermailList


PIPERMAIL_URL = 'http://example.com/'


def read_file(filename, mode='r'):
    with open(filename, mode) as f:
        content = f.read()
    return content


class TestPipermailList(unittest.TestCase):
    """Tests for PipermailList class"""

    def setUp(self):
        self.tmp_path = tempfile.mkdtemp(prefix='perceval_')

    def tearDown(self):
        shutil.rmtree(self.tmp_path)

    def test_init(self):
        """Check attributes initialization"""

        pmls = PipermailList(PIPERMAIL_URL, self.tmp_path)

        self.assertIsInstance(pmls, MailingList)
        self.assertEqual(pmls.uri, PIPERMAIL_URL)
        self.assertEqual(pmls.dirpath, self.tmp_path)
        self.assertEqual(pmls.url, PIPERMAIL_URL)

    @httpretty.activate
    def test_fetch(self):
        """Test whether archives are fetched"""

        pipermail_index = read_file('data/pipermail_index.html')
        mbox_nov = read_file('data/pipermail_2015_november.mbox')
        mbox_march = read_file('data/pipermail_2016_march.mbox')
        mbox_april = read_file('data/pipermail_2016_april.mbox')

        httpretty.register_uri(httpretty.GET,
                               PIPERMAIL_URL,
                               body=pipermail_index)
        httpretty.register_uri(httpretty.GET,
                               PIPERMAIL_URL + '2015-November.txt.gz',
                               body=mbox_nov)
        httpretty.register_uri(httpretty.GET,
                               PIPERMAIL_URL + '2016-March.txt',
                               body=mbox_march)
        httpretty.register_uri(httpretty.GET,
                               PIPERMAIL_URL + '2016-April.txt',
                               body=mbox_april)

        pmls = PipermailList('http://example.com/', self.tmp_path)
        links = pmls.fetch()

        self.assertEqual(len(links), 3)

        self.assertEqual(links[0][0], PIPERMAIL_URL + '2016-April.txt')
        self.assertEqual(links[0][1], os.path.join(self.tmp_path, '2016-April.txt'))
        self.assertEqual(links[1][0], PIPERMAIL_URL + '2016-March.txt')
        self.assertEqual(links[1][1], os.path.join(self.tmp_path, '2016-March.txt'))
        self.assertEqual(links[2][0], PIPERMAIL_URL + '2015-November.txt.gz')
        self.assertEqual(links[2][1], os.path.join(self.tmp_path, '2015-November.txt.gz'))

        mboxes = pmls.mboxes
        self.assertEqual(mboxes[0].filepath, os.path.join(self.tmp_path, '2015-November.txt.gz'))
        self.assertEqual(mboxes[1].filepath, os.path.join(self.tmp_path, '2016-March.txt'))
        self.assertEqual(mboxes[2].filepath, os.path.join(self.tmp_path, '2016-April.txt'))

    @httpretty.activate
    def test_fetch_empty(self):
        """Test whether it do not stores anything when the list of archives is ampty"""

        pipermail_index = read_file('data/pipermail_index_empty.html')
        httpretty.register_uri(httpretty.GET,
                               PIPERMAIL_URL,
                               body=pipermail_index)

        pmls = PipermailList('http://example.com/', self.tmp_path)
        links = pmls.fetch()

        self.assertEqual(len(links), 0)

    @httpretty.activate
    def test_fetch_from_date(self):
        """Test whether it only downloads archives after a given date"""

        pipermail_index = read_file('data/pipermail_index.html')
        mbox_nov = read_file('data/pipermail_2015_november.mbox')
        mbox_march = read_file('data/pipermail_2016_march.mbox')
        mbox_april = read_file('data/pipermail_2016_april.mbox')

        httpretty.register_uri(httpretty.GET,
                               PIPERMAIL_URL,
                               body=pipermail_index)
        httpretty.register_uri(httpretty.GET,
                               PIPERMAIL_URL + '2015-November.txt.gz',
                               body=mbox_nov)
        httpretty.register_uri(httpretty.GET,
                               PIPERMAIL_URL + '2016-March.txt',
                               body=mbox_march)
        httpretty.register_uri(httpretty.GET,
                               PIPERMAIL_URL + '2016-April.txt',
                               body=mbox_april)

        pmls = PipermailList('http://example.com/', self.tmp_path)

        links = pmls.fetch(from_date=datetime.datetime(2016, 3, 30))

        self.assertEqual(len(links), 2)
        self.assertEqual(links[0][0], PIPERMAIL_URL + '2016-April.txt')
        self.assertEqual(links[0][1], os.path.join(self.tmp_path, '2016-April.txt'))
        self.assertEqual(links[1][0], PIPERMAIL_URL + '2016-March.txt')
        self.assertEqual(links[1][1], os.path.join(self.tmp_path, '2016-March.txt'))

        mboxes = pmls.mboxes
        self.assertEqual(mboxes[0].filepath, os.path.join(self.tmp_path, '2016-March.txt'))
        self.assertEqual(mboxes[1].filepath, os.path.join(self.tmp_path, '2016-April.txt'))

    def test_mboxes(self):
        """Test whether it returns the mboxes ordered by the date on their filenames"""

        # Simulate the fetch process copying the files
        shutil.copy('data/pipermail_2015_november.mbox',
                    os.path.join(self.tmp_path, '2015-November.txt.gz'))
        shutil.copy('data/pipermail_2016_march.mbox',
                    os.path.join(self.tmp_path, '2016-March.txt'))
        shutil.copy('data/pipermail_2016_april.mbox',
                    os.path.join(self.tmp_path, '2016-April.txt'))

        pmls = PipermailList('http://example.com/', self.tmp_path)

        mboxes = pmls.mboxes
        self.assertEqual(mboxes[0].filepath, os.path.join(self.tmp_path, '2015-November.txt.gz'))
        self.assertEqual(mboxes[1].filepath, os.path.join(self.tmp_path, '2016-March.txt'))
        self.assertEqual(mboxes[2].filepath, os.path.join(self.tmp_path, '2016-April.txt'))


if __name__ == "__main__":
    unittest.main(warnings='ignore')
