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
#     Quan Zhou <quan@bitergia.com>
#     Stephan Barth <stephan.barth@gmail.com>
#     Valerio Cosentino <valcos@bitergia.com>
#     Miguel Ángel Fernández <mafesan@bitergia.com>
#     Harshal Mittal <harshalmittal4@gmail.com>
#

import datetime
import httpretty
import os
import pkg_resources
import requests
import shutil
import tempfile
import unittest
import unittest.mock

pkg_resources.declare_namespace('perceval.backends')

from perceval.backend import BackendCommandArgumentParser
from perceval.utils import DEFAULT_DATETIME
from perceval.backends.core.mbox import MailingList
from perceval.backends.core.pipermail import (Pipermail,
                                              PipermailCommand,
                                              PipermailList)


PIPERMAIL_URL = 'http://example.com/'


def read_file(filename, mode='r'):
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), filename), mode) as f:
        content = f.read()
    return content


class PipermailListMocked(PipermailList):

    @staticmethod
    def _write_archive(r, filepath):
        raise OSError


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
        self.assertTrue(pmls.ssl_verify)

        pmls = PipermailList(PIPERMAIL_URL, self.tmp_path, ssl_verify=False)

        self.assertIsInstance(pmls, MailingList)
        self.assertEqual(pmls.uri, PIPERMAIL_URL)
        self.assertEqual(pmls.dirpath, self.tmp_path)
        self.assertEqual(pmls.url, PIPERMAIL_URL)
        self.assertFalse(pmls.ssl_verify)

    @httpretty.activate
    def test_fetch(self):
        """Test whether archives are fetched"""

        pipermail_index = read_file('data/pipermail/pipermail_index.html')
        mbox_nov = read_file('data/pipermail/pipermail_2015_november.mbox')
        mbox_march = read_file('data/pipermail/pipermail_2016_march.mbox')
        mbox_april = read_file('data/pipermail/pipermail_2016_april.mbox')

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
    def test_fetch_http_403_error(self):
        """Test whether 403 HTTP errors are properly handled"""

        pipermail_index = read_file('data/pipermail/pipermail_index.html')
        mbox_nov = read_file('data/pipermail/pipermail_2015_november.mbox')
        mbox_march = read_file('data/pipermail/pipermail_2016_march.mbox')
        mbox_april = read_file('data/pipermail/pipermail_2016_april.mbox')

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
                               body=mbox_april,
                               status=403)

        pmls = PipermailList('http://example.com/', self.tmp_path)
        links = pmls.fetch()

        self.assertEqual(len(links), 2)

    @httpretty.activate
    def test_fetch_os_error(self):
        """Test whether OS errors are properly handled"""

        pipermail_index = read_file('data/pipermail/pipermail_index.html')
        mbox_nov = read_file('data/pipermail/pipermail_2015_november.mbox')
        mbox_march = read_file('data/pipermail/pipermail_2016_march.mbox')
        mbox_april = read_file('data/pipermail/pipermail_2016_april.mbox')

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

        pmls = PipermailListMocked('http://example.com/', self.tmp_path)
        links = pmls.fetch()

        self.assertEqual(len(links), 0)

    @httpretty.activate
    def test_fetch_http_errors(self):
        """Test whether an exception is thrown when the HTTP error is not 403"""

        pipermail_index = read_file('data/pipermail/pipermail_index.html')
        mbox_april = read_file('data/pipermail/pipermail_2016_april.mbox')

        httpretty.register_uri(httpretty.GET,
                               PIPERMAIL_URL,
                               body=pipermail_index)
        httpretty.register_uri(httpretty.GET,
                               PIPERMAIL_URL + '2016-April.txt',
                               body=mbox_april,
                               status=404)

        pmls = PipermailList('http://example.com/', self.tmp_path)

        with self.assertRaises(requests.exceptions.HTTPError):
            links = pmls.fetch()

    @httpretty.activate
    def test_fetch_no_existing_dir(self):
        """Test whether the dir_path where to store the archives is created if it doesn't exist"""

        pipermail_index = read_file('data/pipermail/pipermail_index_empty.html')
        httpretty.register_uri(httpretty.GET,
                               PIPERMAIL_URL,
                               body=pipermail_index)

        # delete the dir path
        os.removedirs(self.tmp_path)

        self.assertFalse(os.path.exists(self.tmp_path))
        pmls = PipermailList('http://example.com/', self.tmp_path)
        _ = pmls.fetch()
        self.assertTrue(os.path.exists(self.tmp_path))

    @httpretty.activate
    def test_fetch_empty(self):
        """Test whether it does not store anything when the list of archives is empty"""

        pipermail_index = read_file('data/pipermail/pipermail_index_empty.html')
        httpretty.register_uri(httpretty.GET,
                               PIPERMAIL_URL,
                               body=pipermail_index)

        pmls = PipermailList('http://example.com/', self.tmp_path)
        links = pmls.fetch()

        self.assertEqual(len(links), 0)

    @httpretty.activate
    def test_fetch_from_date(self):
        """Test whether it only downloads archives after a given date"""

        pipermail_index = read_file('data/pipermail/pipermail_index.html')
        mbox_nov = read_file('data/pipermail/pipermail_2015_november.mbox')
        mbox_march = read_file('data/pipermail/pipermail_2016_march.mbox')
        mbox_april = read_file('data/pipermail/pipermail_2016_april.mbox')

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
        shutil.copy(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 'data/pipermail/pipermail_2015_november.mbox'),
                    os.path.join(self.tmp_path, '2015-November.txt.gz'))
        shutil.copy(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 'data/pipermail/pipermail_2016_march.mbox'),
                    os.path.join(self.tmp_path, '2016-March.txt'))
        shutil.copy(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 'data/pipermail/pipermail_2016_april.mbox'),
                    os.path.join(self.tmp_path, '2016-April.txt'))

        pmls = PipermailList('http://example.com/', self.tmp_path)

        mboxes = pmls.mboxes
        self.assertEqual(mboxes[0].filepath, os.path.join(self.tmp_path, '2015-November.txt.gz'))
        self.assertEqual(mboxes[1].filepath, os.path.join(self.tmp_path, '2016-March.txt'))
        self.assertEqual(mboxes[2].filepath, os.path.join(self.tmp_path, '2016-April.txt'))


class TestPipermailBackend(unittest.TestCase):
    """Tests for Pipermail backend class"""

    def setUp(self):
        self.tmp_path = tempfile.mkdtemp(prefix='perceval_')

    def tearDown(self):
        shutil.rmtree(self.tmp_path)

    def test_initialization(self):
        """Test whether attributes are initializated"""

        backend = Pipermail('http://example.com/', self.tmp_path, tag='test')

        self.assertEqual(backend.url, 'http://example.com/')
        self.assertEqual(backend.uri, 'http://example.com/')
        self.assertEqual(backend.dirpath, self.tmp_path)
        self.assertEqual(backend.origin, 'http://example.com/')
        self.assertEqual(backend.tag, 'test')
        self.assertTrue(backend.ssl_verify)

        # When tag is empty or None it will be set to
        # the value in uri
        backend = Pipermail('http://example.com/', self.tmp_path)
        self.assertEqual(backend.origin, 'http://example.com/')
        self.assertEqual(backend.tag, 'http://example.com/')

        backend = Pipermail('http://example.com/', self.tmp_path, tag='')
        self.assertEqual(backend.origin, 'http://example.com/')
        self.assertEqual(backend.tag, 'http://example.com/')

        backend = Pipermail('http://example.com/', self.tmp_path, ssl_verify=True, tag='')
        self.assertEqual(backend.origin, 'http://example.com/')
        self.assertEqual(backend.tag, 'http://example.com/')
        self.assertTrue(backend.ssl_verify)

    def test_has_archiving(self):
        """Test if it returns False when has_archiving is called"""

        self.assertEqual(Pipermail.has_archiving(), False)

    def test_has_resuming(self):
        """Test if it returns True when has_resuming is called"""

        self.assertEqual(Pipermail.has_resuming(), True)

    @httpretty.activate
    def test_fetch(self):
        """Test whether it fetches and parses messages"""

        pipermail_index = read_file('data/pipermail/pipermail_index.html')
        mbox_nov = read_file('data/pipermail/pipermail_2015_november.mbox')
        mbox_march = read_file('data/pipermail/pipermail_2016_march.mbox')
        mbox_april = read_file('data/pipermail/pipermail_2016_april.mbox')

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

        backend = Pipermail('http://example.com/', self.tmp_path)
        messages = [m for m in backend.fetch()]

        expected = [('<CACRHdMaObu7Dc0FWTWEesvRCzUNDG=7oA7KFqAgtOs_UKjb3Og@mail.gmail.com>',
                     '9221eb7884be6f6b91fccd5d64107ce6c7f15e4d', 1447532968.0),
                    ('<1447627429.3593.319.camel@example.com>',
                     'd1b79ef1562b7caf4e4a99e3b7c391e5f733c0ff', 1447627429.0),
                    ('<CACRHdMZaZtkM9h_=p_HH1Yz9pTJwh6nwU0PmeqQX=kemD8LCjw@example.com>',
                     '48d348ef11e8ad3f7688b645dc71d93ecde9ae57', 1448107551.0),
                    ('<CACRHdMbPdoLoUCeKrA4Cm6Gya77JuEO0NUe_XJq5hUkznTzisA@example.com>',
                     '8c057f129fe161452ed2192ef5dce9bcfa10928a', 1448742330.0),
                    ('<1457025635.7479.7.camel@calcifer.org>',
                     '61d76ca22803b22937aa98f0b7d551ba6bfc7fb1', 1457025635.0),
                    ('<1460624816.5581.114.camel@example.com>',
                     'b5320132f853e08d587fc24e46827b0084e0c752', 1460624816.0),
                    ('<CACRHdMZgAgzyhewu_aAJ2f2DWHVZdNH6J7zd2S=YWQuf-2yZDw@example.com>',
                     '7a30847c497645d773d7ceb73b414887153bdbd3', 1461428336.0),
                    ('<1461621607.19185.342.camel@example.com>',
                     '8aa40b01acbdd987208fab4d724b9ddddf5e60fe', 1461621607.0)]

        self.assertEqual(len(messages), 8)

        for x in range(len(messages)):
            message = messages[x]
            self.assertEqual(message['data']['Message-ID'], expected[x][0])
            self.assertEqual(message['origin'], 'http://example.com/')
            self.assertEqual(message['uuid'], expected[x][1])
            self.assertEqual(message['updated_on'], expected[x][2])
            self.assertEqual(message['category'], 'message')
            self.assertEqual(message['tag'], 'http://example.com/')

    @httpretty.activate
    def test_fetch_apache(self):
        """Test whether it fetches and parses apache's messages"""

        pipermail_index = read_file('data/pipermail/pipermail_apache_index.html')
        mbox_nov = read_file('data/pipermail/pipermail_2015_november.mbox')
        mbox_march = read_file('data/pipermail/pipermail_2016_march.mbox')
        mbox_april = read_file('data/pipermail/pipermail_2016_april.mbox')

        httpretty.register_uri(httpretty.GET,
                               PIPERMAIL_URL,
                               body=pipermail_index)
        httpretty.register_uri(httpretty.GET,
                               PIPERMAIL_URL + '201511.mbox',
                               body=mbox_nov)
        httpretty.register_uri(httpretty.GET,
                               PIPERMAIL_URL + '201603.mbox',
                               body=mbox_march)
        httpretty.register_uri(httpretty.GET,
                               PIPERMAIL_URL + '201604.mbox',
                               body=mbox_april)

        backend = Pipermail('http://example.com/', self.tmp_path)
        messages = [m for m in backend.fetch()]

        expected = [('<CACRHdMaObu7Dc0FWTWEesvRCzUNDG=7oA7KFqAgtOs_UKjb3Og@mail.gmail.com>',
                     '9221eb7884be6f6b91fccd5d64107ce6c7f15e4d', 1447532968.0),
                    ('<1447627429.3593.319.camel@example.com>',
                     'd1b79ef1562b7caf4e4a99e3b7c391e5f733c0ff', 1447627429.0),
                    ('<CACRHdMZaZtkM9h_=p_HH1Yz9pTJwh6nwU0PmeqQX=kemD8LCjw@example.com>',
                     '48d348ef11e8ad3f7688b645dc71d93ecde9ae57', 1448107551.0),
                    ('<CACRHdMbPdoLoUCeKrA4Cm6Gya77JuEO0NUe_XJq5hUkznTzisA@example.com>',
                     '8c057f129fe161452ed2192ef5dce9bcfa10928a', 1448742330.0),
                    ('<1457025635.7479.7.camel@calcifer.org>',
                     '61d76ca22803b22937aa98f0b7d551ba6bfc7fb1', 1457025635.0),
                    ('<1460624816.5581.114.camel@example.com>',
                     'b5320132f853e08d587fc24e46827b0084e0c752', 1460624816.0),
                    ('<CACRHdMZgAgzyhewu_aAJ2f2DWHVZdNH6J7zd2S=YWQuf-2yZDw@example.com>',
                     '7a30847c497645d773d7ceb73b414887153bdbd3', 1461428336.0),
                    ('<1461621607.19185.342.camel@example.com>',
                     '8aa40b01acbdd987208fab4d724b9ddddf5e60fe', 1461621607.0)]

        self.assertEqual(len(messages), 8)

        for x in range(len(messages)):
            message = messages[x]
            self.assertEqual(message['data']['Message-ID'], expected[x][0])
            self.assertEqual(message['origin'], 'http://example.com/')
            self.assertEqual(message['uuid'], expected[x][1])
            self.assertEqual(message['updated_on'], expected[x][2])
            self.assertEqual(message['category'], 'message')
            self.assertEqual(message['tag'], 'http://example.com/')

    @httpretty.activate
    def test_fetch_from_date(self):
        """Test whether it fetches and parses messages since the given date"""

        pipermail_index = read_file('data/pipermail/pipermail_index.html')
        mbox_nov = read_file('data/pipermail/pipermail_2015_november.mbox')
        mbox_march = read_file('data/pipermail/pipermail_2016_march.mbox')
        mbox_april = read_file('data/pipermail/pipermail_2016_april.mbox')

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

        from_date = datetime.datetime(2016, 3, 4)

        backend = Pipermail('http://example.com/', self.tmp_path)
        messages = [m for m in backend.fetch(from_date=from_date)]

        # For this test, mboxes from March and April should be downloaded.
        expected_downloads = []

        for root, _, files in os.walk(self.tmp_path):
            for filename in sorted(files):
                location = os.path.join(root, filename)
                expected_downloads.append(location)

        self.assertListEqual(expected_downloads,
                             [os.path.join(self.tmp_path, '2016-April.txt'),
                              os.path.join(self.tmp_path, '2016-March.txt')])

        # Although there is a message in the mbox from March, this message
        # was sent previous to the given date, so it is not included
        # into the expected result
        expected = [('<1460624816.5581.114.camel@example.com>',
                     'b5320132f853e08d587fc24e46827b0084e0c752', 1460624816.0),
                    ('<CACRHdMZgAgzyhewu_aAJ2f2DWHVZdNH6J7zd2S=YWQuf-2yZDw@example.com>',
                     '7a30847c497645d773d7ceb73b414887153bdbd3', 1461428336.0),
                    ('<1461621607.19185.342.camel@example.com>',
                     '8aa40b01acbdd987208fab4d724b9ddddf5e60fe', 1461621607.0)]

        self.assertEqual(len(messages), 3)

        for x in range(len(messages)):
            message = messages[x]
            self.assertEqual(message['data']['Message-ID'], expected[x][0])
            self.assertEqual(message['origin'], 'http://example.com/')
            self.assertEqual(message['uuid'], expected[x][1])
            self.assertEqual(message['updated_on'], expected[x][2])
            self.assertEqual(message['category'], 'message')
            self.assertEqual(message['tag'], 'http://example.com/')

    @httpretty.activate
    def test_fetch_empty(self):
        """Test whether it works when pipermail does not store any mbox"""

        pipermail_index = read_file('data/pipermail/pipermail_index_empty.html')

        httpretty.register_uri(httpretty.GET,
                               PIPERMAIL_URL,
                               body=pipermail_index)

        backend = Pipermail('http://example.com/', self.tmp_path)
        messages = [m for m in backend.fetch()]

        self.assertListEqual(messages, [])

    @httpretty.activate
    def test_search_fields(self):
        """Test whether the search_fields is properly set"""

        pipermail_index = read_file('data/pipermail/pipermail_index.html')
        mbox_nov = read_file('data/pipermail/pipermail_2015_november.mbox')
        mbox_march = read_file('data/pipermail/pipermail_2016_march.mbox')
        mbox_april = read_file('data/pipermail/pipermail_2016_april.mbox')

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

        backend = Pipermail('http://example.com/', self.tmp_path)
        messages = [m for m in backend.fetch()]

        self.assertEqual(len(messages), 8)

        for msg in messages:
            self.assertEqual(backend.metadata_id(msg['data']), msg['search_fields']['item_id'])


class TestPipermailCommand(unittest.TestCase):
    """Tests for PipermailCommand class"""

    def setUp(self):
        self.tmp_path = tempfile.mkdtemp(prefix='perceval_')

    def tearDown(self):
        shutil.rmtree(self.tmp_path)

    def test_backend_class(self):
        """Test if the backend class is Pipermail"""

        self.assertIs(PipermailCommand.BACKEND, Pipermail)

    @httpretty.activate
    @unittest.mock.patch('os.path.expanduser')
    def test_mboxes_path_init(self, mock_expanduser):
        """Test dirpath initialization"""

        mock_expanduser.return_value = os.path.join(self.tmp_path, 'testpath')

        args = ['http://example.com/']

        cmd = PipermailCommand(*args)
        self.assertEqual(cmd.parsed_args.dirpath,
                         os.path.join(self.tmp_path, 'testpath/http://example.com/'))

        args = ['http://example.com/',
                '--mboxes-path', '/tmp/perceval/']

        cmd = PipermailCommand(*args)
        self.assertEqual(cmd.parsed_args.dirpath, '/tmp/perceval/')

    def test_parsing_on_init(self):
        """Test if the class is initialized"""

        args = ['http://example.com/',
                '--mboxes-path', '/tmp/perceval/',
                '--tag', 'test']

        cmd = PipermailCommand(*args)
        self.assertEqual(cmd.parsed_args.url, 'http://example.com/')
        self.assertEqual(cmd.parsed_args.mboxes_path, '/tmp/perceval/')
        self.assertEqual(cmd.parsed_args.tag, 'test')

    def test_setup_cmd_parser(self):
        """Test if it parser object is correctly initialized"""

        parser = PipermailCommand.setup_cmd_parser()
        self.assertIsInstance(parser, BackendCommandArgumentParser)
        self.assertEqual(parser._backend, Pipermail)

        args = ['http://example.com/',
                '--mboxes-path', '/tmp/perceval/',
                '--tag', 'test',
                '--from-date', '1970-01-01']

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.url, 'http://example.com/')
        self.assertEqual(parsed_args.mboxes_path, '/tmp/perceval/')
        self.assertEqual(parsed_args.tag, 'test')
        self.assertEqual(parsed_args.from_date, DEFAULT_DATETIME)
        self.assertTrue(parsed_args.ssl_verify)

        args = ['http://example.com/',
                '--mboxes-path', '/tmp/perceval/',
                '--tag', 'test',
                '--from-date', '1970-01-01',
                '--no-ssl-verify']

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.url, 'http://example.com/')
        self.assertEqual(parsed_args.mboxes_path, '/tmp/perceval/')
        self.assertEqual(parsed_args.tag, 'test')
        self.assertEqual(parsed_args.from_date, DEFAULT_DATETIME)
        self.assertFalse(parsed_args.ssl_verify)


if __name__ == "__main__":
    unittest.main(warnings='ignore')
