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
#     Miguel Ángel Fernández <mafesan@bitergia.com>
#     Harshal Mittal <harshalmittal4@gmail.com>
#

import datetime
import os
import shutil
import tempfile
import unittest
import unittest.mock

import dateutil.tz
import httpretty

from perceval.backend import BackendCommandArgumentParser
from perceval.utils import DEFAULT_DATETIME
from perceval.backends.core.mbox import MailingList
from perceval.backends.core.hyperkitty import (HyperKitty,
                                               HyperKittyCommand,
                                               HyperKittyList)


HYPERKITTY_URL = 'http://example.com/archives/list/test@example.com/'
HYPERKITTY_MARCH_MBOX_URL = HYPERKITTY_URL + '/export/2016-03.mbox.gz'
HYPERKITTY_APRIL_MBOX_URL = HYPERKITTY_URL + '/export/2016-04.mbox.gz'


def read_file(filename, mode='r'):
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), filename), mode) as f:
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
        self.assertEqual(hkls.client.base_url, HYPERKITTY_URL)

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

        # to_date
        to_date = datetime.datetime(2016, 4, 1)
        hkls = HyperKittyList('http://example.com/archives/list/test@example.com/',
                              self.tmp_path)
        fetched = hkls.fetch(from_date=from_date, to_date=to_date)

        self.assertEqual(len(fetched), 1)

        self.assertEqual(fetched[0][0], HYPERKITTY_URL + 'export/2016-03.mbox.gz')
        self.assertEqual(fetched[0][1], os.path.join(self.tmp_path, '2016-03.mbox.gz'))

        mboxes = hkls.mboxes
        self.assertEqual(mboxes[0].filepath, os.path.join(self.tmp_path, '2016-03.mbox.gz'))

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

    @httpretty.activate
    def test_fetch_to_date_before_that_day(self):
        """Test if it does not store anything when to_date is until this date"""

        httpretty.register_uri(httpretty.GET,
                               HYPERKITTY_URL,
                               body="")

        from_date = datetime.datetime(2016, 1, 10)
        to_date = datetime.datetime(2015, 1, 10)

        hkls = HyperKittyList('http://example.com/archives/list/test@example.com/',
                              self.tmp_path)
        fetched = hkls.fetch(from_date=from_date, to_date=to_date)

        self.assertEqual(len(fetched), 0)

    def test_mboxes(self):
        """Test whether it returns the mboxes ordered by the date on their filenames"""

        # Simulate the fetch process copying the files
        shutil.copy(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data/hyperkitty/hyperkitty_2016_march.mbox'),
                    os.path.join(self.tmp_path, '2016-03.mbox.gz'))
        shutil.copy(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data/hyperkitty/hyperkitty_2016_april.mbox'),
                    os.path.join(self.tmp_path, '2016-04.mbox.gz'))

        hkls = HyperKittyList('http://example.com/archives/list/test@example.com/',
                              self.tmp_path)

        mboxes = hkls.mboxes
        self.assertEqual(mboxes[0].filepath, os.path.join(self.tmp_path, '2016-03.mbox.gz'))
        self.assertEqual(mboxes[1].filepath, os.path.join(self.tmp_path, '2016-04.mbox.gz'))


class TestHyperKittyBackend(unittest.TestCase):
    """Tests for HyperKitty backend class"""

    def setUp(self):
        self.tmp_path = tempfile.mkdtemp(prefix='perceval_')

    def tearDown(self):
        shutil.rmtree(self.tmp_path)

    def test_initialization(self):
        """Test whether attributes are initializated"""

        backend = HyperKitty('http://example.com/', self.tmp_path, tag='test')

        self.assertEqual(backend.url, 'http://example.com/')
        self.assertEqual(backend.uri, 'http://example.com/')
        self.assertEqual(backend.dirpath, self.tmp_path)
        self.assertEqual(backend.origin, 'http://example.com/')
        self.assertEqual(backend.tag, 'test')
        self.assertTrue(backend.ssl_verify)

        # When tag is empty or None it will be set to
        # the value in uri
        backend = HyperKitty('http://example.com/', self.tmp_path, ssl_verify=False)
        self.assertEqual(backend.origin, 'http://example.com/')
        self.assertEqual(backend.tag, 'http://example.com/')
        self.assertFalse(backend.ssl_verify)

        backend = HyperKitty('http://example.com/', self.tmp_path, tag='')
        self.assertEqual(backend.origin, 'http://example.com/')
        self.assertEqual(backend.tag, 'http://example.com/')

    def test_has_archiving(self):
        """Test if it returns False when has_archiving is called"""

        self.assertEqual(HyperKitty.has_archiving(), False)

    def test_has_resuming(self):
        """Test if it returns True when has_resuming is called"""

        self.assertEqual(HyperKitty.has_resuming(), True)

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

        backend = HyperKitty('http://example.com/archives/list/test@example.com/',
                             self.tmp_path)
        messages = [m for m in backend.fetch(from_date=from_date)]

        # Although there is a message in the mbox from March, this message
        # was sent previous to the given date, so it is not included
        # into the expected result
        expected = [('<1460624816.5581.114.camel@example.com>',
                     '26ad05669b2d2e6f6a8e244b2fd65cefafdb3d53', 1460624816.0),
                    ('<CACRHdMZgAgzyhewu_aAJ2f2DWHVZdNH6J7zd2S=YWQuf-2yZDw@example.com>',
                     'c785b05dd2a267d267e8497303157cea4a871838', 1461428336.0),
                    ('<1461621607.19185.342.camel@example.com>',
                     'fc3f60f140bba0e7f3fcad82890928e6b580a923', 1461621607.0)]

        self.assertEqual(len(messages), 3)

        for x in range(len(messages)):
            message = messages[x]
            self.assertEqual(message['data']['Message-ID'], expected[x][0])
            self.assertEqual(message['origin'], 'http://example.com/archives/list/test@example.com/')
            self.assertEqual(message['uuid'], expected[x][1])
            self.assertEqual(message['updated_on'], expected[x][2])
            self.assertEqual(message['category'], 'message')
            self.assertEqual(message['tag'], 'http://example.com/archives/list/test@example.com/')

        # to_date
        to_date = datetime.datetime(2016, 4, 15)
        messages = [m for m in backend.fetch(from_date=from_date, to_date=to_date)]

        expected = [('<1460624816.5581.114.camel@example.com>',
                     '26ad05669b2d2e6f6a8e244b2fd65cefafdb3d53', 1460624816.0)]

        self.assertEqual(len(messages), 1)

        for x in range(len(messages)):
            message = messages[x]
            self.assertEqual(message['data']['Message-ID'], expected[x][0])
            self.assertEqual(message['origin'], 'http://example.com/archives/list/test@example.com/')
            self.assertEqual(message['uuid'], expected[x][1])
            self.assertEqual(message['updated_on'], expected[x][2])
            self.assertEqual(message['category'], 'message')
            self.assertEqual(message['tag'], 'http://example.com/archives/list/test@example.com/')

    @httpretty.activate
    @unittest.mock.patch('perceval.backends.core.hyperkitty.datetime_utcnow')
    def test_search_fields(self, mock_utcnow):
        """Test whether the search_fields is properly set"""

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

        backend = HyperKitty('http://example.com/archives/list/test@example.com/',
                             self.tmp_path)
        messages = [m for m in backend.fetch(from_date=from_date)]

        for message in messages:
            self.assertEqual(backend.metadata_id(message['data']), message['search_fields']['item_id'])

    @httpretty.activate
    @unittest.mock.patch('perceval.backends.core.hyperkitty.datetime_utcnow')
    def test_fetch_from_date_after_current_day(self, mock_utcnow):
        """Test if it does not fetch anything when from_date is a date from the future"""

        mock_utcnow.return_value = datetime.datetime(2016, 4, 10,
                                                     tzinfo=dateutil.tz.tzutc())

        httpretty.register_uri(httpretty.GET,
                               HYPERKITTY_URL,
                               body="")

        from_date = datetime.datetime(2017, 1, 10)

        backend = HyperKitty('http://example.com/archives/list/test@example.com/',
                             self.tmp_path)
        messages = [m for m in backend.fetch(from_date=from_date)]

        self.assertEqual(len(messages), 0)

    @httpretty.activate
    def test_fetch_to_date_before_that_day(self):
        """Test if it does not store anything when to_date is until this date"""

        httpretty.register_uri(httpretty.GET,
                               HYPERKITTY_URL,
                               body="")

        from_date = datetime.datetime(2017, 1, 10)
        to_date = datetime.datetime(2016, 1, 10)

        backend = HyperKitty('http://example.com/archives/list/test@example.com/',
                             self.tmp_path)
        messages = [m for m in backend.fetch(from_date=from_date, to_date=to_date)]

        self.assertEqual(len(messages), 0)


class TestHyperKittyCommand(unittest.TestCase):
    """Tests for HyperKittyCommand class"""

    def setUp(self):
        self.tmp_path = tempfile.mkdtemp(prefix='perceval_')

    def tearDown(self):
        shutil.rmtree(self.tmp_path)

    def test_backend_class(self):
        """Test if the backend class is Pipermail"""

        self.assertIs(HyperKittyCommand.BACKEND, HyperKitty)

    @httpretty.activate
    @unittest.mock.patch('os.path.expanduser')
    def test_mboxes_path_init(self, mock_expanduser):
        """Test dirpath initialization"""

        mock_expanduser.return_value = os.path.join(self.tmp_path, 'testpath')

        args = ['http://example.com/archives/list/test@example.com/']

        cmd = HyperKittyCommand(*args)
        self.assertEqual(cmd.parsed_args.dirpath,
                         os.path.join(self.tmp_path,
                                      'testpath/http://example.com/archives/list/test@example.com/'))

        args = ['http://example.com/archives/list/test@example.com/',
                '--mboxes-path', '/tmp/perceval/']

        cmd = HyperKittyCommand(*args)
        self.assertEqual(cmd.parsed_args.dirpath, '/tmp/perceval/')

    def test_parsing_on_init(self):
        """Test if the class is initialized"""

        args = ['http://example.com/archives/list/test@example.com/',
                '--mboxes-path', '/tmp/perceval/',
                '--tag', 'test']

        cmd = HyperKittyCommand(*args)
        self.assertEqual(cmd.parsed_args.url, 'http://example.com/archives/list/test@example.com/')
        self.assertEqual(cmd.parsed_args.mboxes_path, '/tmp/perceval/')
        self.assertEqual(cmd.parsed_args.tag, 'test')

    def test_setup_cmd_parser(self):
        """Test if it parser object is correctly initialized"""

        parser = HyperKittyCommand.setup_cmd_parser()
        self.assertIsInstance(parser, BackendCommandArgumentParser)
        self.assertEqual(parser._backend, HyperKitty)

        args = ['http://example.com/archives/list/test@example.com/',
                '--mboxes-path', '/tmp/perceval/',
                '--tag', 'test',
                '--from-date', '1970-01-01']

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.url, 'http://example.com/archives/list/test@example.com/')
        self.assertEqual(parsed_args.mboxes_path, '/tmp/perceval/')
        self.assertEqual(parsed_args.tag, 'test')
        self.assertEqual(parsed_args.from_date, DEFAULT_DATETIME)
        self.assertIsNone(parsed_args.to_date)
        self.assertTrue(parsed_args.ssl_verify)

        args = ['http://example.com/archives/list/test@example.com/',
                '--mboxes-path', '/tmp/perceval/',
                '--tag', 'test', '--no-ssl-verify',
                '--from-date', '1970-01-01',
                '--to-date', '2016-01-01']

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.url, 'http://example.com/archives/list/test@example.com/')
        self.assertEqual(parsed_args.mboxes_path, '/tmp/perceval/')
        self.assertEqual(parsed_args.tag, 'test')
        self.assertEqual(parsed_args.from_date, DEFAULT_DATETIME)
        self.assertEqual(parsed_args.to_date, datetime.datetime(2016, 1, 1, 0, 0, 0,
                                                                tzinfo=dateutil.tz.tzutc()))
        self.assertFalse(parsed_args.ssl_verify)


if __name__ == "__main__":
    unittest.main(warnings='ignore')
