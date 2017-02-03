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
#     Santiago Dueñas <sduenas@bitergia.com>
#

import datetime
import os
import shutil
import sys
import tempfile
import unittest
import unittest.mock

import dateutil.tz
import httpretty
import pkg_resources

# Hack to make sure that tests import the right packages
# due to setuptools behaviour
sys.path.insert(0, '..')
pkg_resources.declare_namespace('perceval.backends')

from perceval.backends.core.mbox import MailingList
from perceval.backends.core.hyperkitty import HyperKittyList


HYPERKITTY_URL = 'http://example.com/archives/list/test@example.com/'
HYPERKITTY_MARCH_MBOX_URL = HYPERKITTY_URL + '/export/2016-03.mbox.gz'
HYPERKITTY_APRIL_MBOX_URL = HYPERKITTY_URL + '/export/2016-04.mbox.gz'


def read_file(filename, mode='r'):
    with open(filename, mode) as f:
        content = f.read()
    return content


class TestHyperKittyList(unittest.TestCase):
    """Tests for HyperKittyList class"""

    def setUp(self):
        self.tmp_path = tempfile.mkdtemp(prefix='perceval_')

    def tearDown(self):
        shutil.rmtree(self.tmp_path)

    def test_init(self):
        """Check attributes initialization"""

        hkls = HyperKittyList(HYPERKITTY_URL, self.tmp_path)

        self.assertIsInstance(hkls, MailingList)
        self.assertEqual(hkls.uri, HYPERKITTY_URL)
        self.assertEqual(hkls.dirpath, self.tmp_path)
        self.assertEqual(hkls.url, HYPERKITTY_URL)

    @httpretty.activate
    @unittest.mock.patch('perceval.backends.core.hyperkitty.datetime_utcnow')
    def test_fetch(self, mock_utcnow):
        """Test whether archives are fetched"""

        mock_utcnow.return_value = datetime.datetime(2016, 4, 10,
                                                     tzinfo=dateutil.tz.tzutc())

        mbox_march = read_file('data/hyperkitty/hyperkitty_2016_march.mbox')
        mbox_april = read_file('data/hyperkitty/hyperkitty_2016_april.mbox')

        httpretty.register_uri(httpretty.GET,
                               HYPERKITTY_URL,
                               body="")
        httpretty.register_uri(httpretty.GET,
                               HYPERKITTY_URL + 'export/2016-03.mbox.gz',
                               body=mbox_march)
        httpretty.register_uri(httpretty.GET,
                               HYPERKITTY_URL + 'export/2016-04.mbox.gz',
                               body=mbox_april)

        from_date = datetime.datetime(2016, 3, 10)

        hkls = HyperKittyList('http://example.com/archives/list/test@example.com/',
                              self.tmp_path)
        fetched = hkls.fetch(from_date=from_date)

        self.assertEqual(len(fetched), 2)

        self.assertEqual(fetched[0][0], HYPERKITTY_URL + 'export/2016-03.mbox.gz')
        self.assertEqual(fetched[0][1], os.path.join(self.tmp_path, '2016-03.mbox.gz'))
        self.assertEqual(fetched[1][0], HYPERKITTY_URL + 'export/2016-04.mbox.gz')
        self.assertEqual(fetched[1][1], os.path.join(self.tmp_path, '2016-04.mbox.gz'))

        mboxes = hkls.mboxes
        self.assertEqual(mboxes[0].filepath, os.path.join(self.tmp_path, '2016-03.mbox.gz'))
        self.assertEqual(mboxes[1].filepath, os.path.join(self.tmp_path, '2016-04.mbox.gz'))

    @httpretty.activate
    @unittest.mock.patch('perceval.backends.core.hyperkitty.datetime_utcnow')
    def test_fetch_from_date_after_current_day(self, mock_utcnow):
        """Test if it does not store anything when from_date is a date from the future"""

        mock_utcnow.return_value = datetime.datetime(2016, 4, 10,
                                                     tzinfo=dateutil.tz.tzutc())

        httpretty.register_uri(httpretty.GET,
                               HYPERKITTY_URL,
                               body="")

        from_date = datetime.datetime(2017, 1, 10)

        hkls = HyperKittyList('http://example.com/archives/list/test@example.com/',
                              self.tmp_path)
        fetched = hkls.fetch(from_date=from_date)

        self.assertEqual(len(fetched), 0)

    def test_mboxes(self):
        """Test whether it returns the mboxes ordered by the date on their filenames"""

        # Simulate the fetch process copying the files
        shutil.copy('data/hyperkitty/hyperkitty_2016_march.mbox',
                    os.path.join(self.tmp_path, '2016-03.mbox.gz'))
        shutil.copy('data/hyperkitty/hyperkitty_2016_april.mbox',
                    os.path.join(self.tmp_path, '2016-04.mbox.gz'))

        hkls = HyperKittyList('http://example.com/archives/list/test@example.com/',
                              self.tmp_path)

        mboxes = hkls.mboxes
        self.assertEqual(mboxes[0].filepath, os.path.join(self.tmp_path, '2016-03.mbox.gz'))
        self.assertEqual(mboxes[1].filepath, os.path.join(self.tmp_path, '2016-04.mbox.gz'))


if __name__ == "__main__":
    unittest.main(warnings='ignore')
