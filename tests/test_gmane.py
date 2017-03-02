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

import os
import shutil
import sys
import tempfile
import unittest
import unittest.mock

import httpretty
import pkg_resources

# Hack to make sure that tests import the right packages
# due to setuptools behaviour
sys.path.insert(0, '..')
pkg_resources.declare_namespace('perceval.backends')

from perceval.backend import BackendCommandArgumentParser
from perceval.errors import RepositoryError
from perceval.backends.core.gmane import (Gmane,
                                          GmaneClient,
                                          GmaneCommand,
                                          GmaneMailingList)
from perceval.backends.core.mbox import MailingList


GMANE_LIST_URL = 'http://list.gmane.org/mylist@example.com'
GMANE_MYLIST_URL = 'http://dir.gmane.org/gmane.comp.example.mylist'
GMANE_INVALID_LIST_URL = 'http://list.gmane.org/invalidlist@example.com'
GMAME_DOWNLOAD_LIST_URL = 'http://download.gmane.org/gmane.comp.example.mylist'


def read_file(filename, mode='r'):
    with open(filename, mode) as f:
        content = f.read()
    return content


def setup_http_server():
    bodies = [read_file('data/gmane_messages.mbox', 'rb'),
              read_file('data/gmane_messages_2000.mbox', 'rb'),
              read_file('data/gmane_messages_4000.mbox', 'rb'),
              read_file('data/gmane_messages_empty.mbox', 'rb')]

    httpretty.register_uri(httpretty.GET, GMANE_LIST_URL,
                           status=301,
                           location=GMANE_MYLIST_URL)
    httpretty.register_uri(httpretty.GET, GMANE_MYLIST_URL,
                           status=200,
                           body="")
    httpretty.register_uri(httpretty.GET, GMAME_DOWNLOAD_LIST_URL + '/0/2000',
                           status=200,
                           body=bodies[0])
    httpretty.register_uri(httpretty.GET, GMAME_DOWNLOAD_LIST_URL + '/2000/4000',
                           status=200,
                           body=bodies[1])
    httpretty.register_uri(httpretty.GET, GMAME_DOWNLOAD_LIST_URL + '/4000/6000',
                           status=200,
                           body=bodies[2])
    httpretty.register_uri(httpretty.GET, GMAME_DOWNLOAD_LIST_URL + '/6000/8000',
                           status=200,
                           body=bodies[3])


class TestGmaneBackend(unittest.TestCase):
    """Test for Gmance backend class"""

    def setUp(self):
        self.tmp_path = tempfile.mkdtemp(prefix='perceval_')

    def tearDown(self):
        shutil.rmtree(self.tmp_path)

    @httpretty.activate
    def test_initialization(self):
        """Test whether attributes are initializated"""

        setup_http_server()

        backend = Gmane('mylist@example.com', self.tmp_path, tag='test')

        self.assertEqual(backend.url, GMANE_MYLIST_URL)
        self.assertEqual(backend.uri, GMANE_MYLIST_URL)
        self.assertEqual(backend.dirpath, self.tmp_path)
        self.assertEqual(backend.origin, GMANE_MYLIST_URL)
        self.assertEqual(backend.tag, 'test')

        # When origin is empty or None it will be set to
        # the value of the Gmane mailing list
        backend = Gmane('mylist@example.com', self.tmp_path)
        self.assertEqual(backend.origin, GMANE_MYLIST_URL)
        self.assertEqual(backend.tag, GMANE_MYLIST_URL)

        backend = Gmane('mylist@example.com', self.tmp_path, tag='')
        self.assertEqual(backend.origin, GMANE_MYLIST_URL)
        self.assertEqual(backend.tag, GMANE_MYLIST_URL)

    def test_has_caching(self):
        """Test if it returns False when has_caching is called"""

        self.assertEqual(Gmane.has_caching(), False)

    def test_has_resuming(self):
        """Test if it returns True when has_resuming is called"""

        self.assertEqual(Gmane.has_resuming(), True)

    @httpretty.activate
    def test_fetch(self):
        """Test whether it fetches and parses messages"""

        setup_http_server()

        backend = Gmane('mylist@example.com', self.tmp_path)
        messages = [m for m in backend.fetch()]

        expected = [('<CACRHdMaObu7Dc0FWTWEesvRCzUNDG=7oA7KFqAgtOs_UKjb3Og@mail.gmail.com>',
                     '57f2a6c029df5e5f1b1698aa7f9d430613a87e00', 1447532968.0, 0),
                    ('<1447627429.3593.319.camel@example.com>',
                     '734ecfbb6fe751b372d88bdd8b5ab27b2774e389', 1447627429.0, 1),
                    ('<CACRHdMZaZtkM9h_=p_HH1Yz9pTJwh6nwU0PmeqQX=kemD8LCjw@example.com>',
                     'ec9de08e0904e10c64c225d1ae453a06afd1d2e2', 1448107551.0, 2),
                    ('<CACRHdMbPdoLoUCeKrA4Cm6Gya77JuEO0NUe_XJq5hUkznTzisA@example.com>',
                     '7443147416e72a109dc4c34f6933c019619135da', 1448742330.0, 3),
                    ('<1457025635.7479.7.camel@calcifer.org>',
                     '22d57bd93e0696392fbd8edde96e60116aca9e06', 1457025635.0, 4),
                    ('<1460624816.5581.114.camel@example.com>',
                     '50501282d7c3178e946b46d5e557924d08d11df2', 1460624816.0, 5),
                    ('<CACRHdMZgAgzyhewu_aAJ2f2DWHVZdNH6J7zd2S=YWQuf-2yZDw@example.com>',
                     '40feb0bd9206ffc325cec9ede16f6c6638c93b58', 1461428336.0, 6),
                    ('<1461621607.19185.342.camel@example.com>',
                     'b022328e2fe72985e543712cf4f359e9daa80349', 1461621607.0, 7)]

        self.assertEqual(len(messages), 8)

        for x in range(len(messages)):
            message = messages[x]
            self.assertEqual(message['data']['Message-ID'], expected[x][0])
            self.assertEqual(message['origin'], GMANE_MYLIST_URL)
            self.assertEqual(message['uuid'], expected[x][1])
            self.assertEqual(message['updated_on'], expected[x][2])
            self.assertEqual(message['offset'], expected[x][3])
            self.assertEqual(message['category'], 'message')
            self.assertEqual(message['tag'], GMANE_MYLIST_URL)

    @httpretty.activate
    def test_fetch_from_offset(self):
        """Test whether it fetches and parses messages from the given offset"""

        setup_http_server()

        backend = Gmane('mylist@example.com', self.tmp_path)
        messages = [m for m in backend.fetch(offset=4000)]

        # For this test, only one mbox should be downloaded because the
        # offset starts at 0
        mboxes_downloaded = []

        for root, _, files in os.walk(self.tmp_path):
            for filename in sorted(files):
                location = os.path.join(root, filename)
                mboxes_downloaded.append(location)

        self.assertListEqual(mboxes_downloaded,
                             [os.path.join(self.tmp_path, '4000')])

        expected = [('<1460624816.5581.114.camel@example.com>',
                     '50501282d7c3178e946b46d5e557924d08d11df2', 1460624816.0, 4000),
                    ('<CACRHdMZgAgzyhewu_aAJ2f2DWHVZdNH6J7zd2S=YWQuf-2yZDw@example.com>',
                     '40feb0bd9206ffc325cec9ede16f6c6638c93b58', 1461428336.0, 4001),
                    ('<1461621607.19185.342.camel@example.com>',
                     'b022328e2fe72985e543712cf4f359e9daa80349', 1461621607.0, 4002)]

        self.assertEqual(len(messages), 3)

        for x in range(len(messages)):
            message = messages[x]
            self.assertEqual(message['data']['Message-ID'], expected[x][0])
            self.assertEqual(message['origin'], GMANE_MYLIST_URL)
            self.assertEqual(message['uuid'], expected[x][1])
            self.assertEqual(message['updated_on'], expected[x][2])
            self.assertEqual(message['offset'], expected[x][3])
            self.assertEqual(message['category'], 'message')
            self.assertEqual(message['tag'], GMANE_MYLIST_URL)

    @httpretty.activate
    def test_fetch_empty(self):
        """Test whether it works when there are not any messages"""

        setup_http_server()

        backend = Gmane('mylist@example.com', self.tmp_path)
        messages = [m for m in backend.fetch(offset=6000)]

        self.assertListEqual(messages, [])


class TestGmaneCommand(unittest.TestCase):
    """Tests for GmaneCommand class"""

    def setUp(self):
        self.tmp_path = tempfile.mkdtemp(prefix='perceval_')

    def tearDown(self):
        shutil.rmtree(self.tmp_path)

    def test_backend_class(self):
        """Test if the backend class is Gmane"""

        self.assertIs(GmaneCommand.BACKEND, Gmane)

    @httpretty.activate
    @unittest.mock.patch('os.path.expanduser')
    def test_mboxes_path_init(self, mock_expanduser):
        """Test dirpath initialization"""

        mock_expanduser.return_value = os.path.join(self.tmp_path, 'testpath')
        setup_http_server()

        args = ['mylist@example.com']

        cmd = GmaneCommand(*args)
        self.assertEqual(cmd.parsed_args.dirpath,
                         os.path.join(self.tmp_path, 'testpath/mylist@example.com'))

        args = ['mylist@example.com',
                '--mboxes-path', '/tmp/perceval/']

        cmd = GmaneCommand(*args)
        self.assertEqual(cmd.parsed_args.dirpath, '/tmp/perceval/')

    def test_setup_cmd_parser(self):
        """Test if it parser object is correctly initialized"""

        parser = GmaneCommand.setup_cmd_parser()
        self.assertIsInstance(parser, BackendCommandArgumentParser)

        args = ['mylist@example.com',
                '--mboxes-path', '/tmp/perceval/',
                '--offset', '10',
                '--tag', 'test',
                '--no-cache']

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.mailing_list_address, 'mylist@example.com')
        self.assertEqual(parsed_args.mboxes_path, '/tmp/perceval/')
        self.assertEqual(parsed_args.offset, 10)
        self.assertEqual(parsed_args.tag, 'test')
        self.assertEqual(parsed_args.no_cache, True)


class TestGmaneMailingList(unittest.TestCase):
    """Tests for GmaneMailingList class"""

    def setUp(self):
        self.tmp_path = tempfile.mkdtemp(prefix='perceval_')

    def tearDown(self):
        shutil.rmtree(self.tmp_path)

    @httpretty.activate
    def test_init(self):
        """Test if the mailing list values were initialized"""

        setup_http_server()

        gmls = GmaneMailingList('mylist@example.com', self.tmp_path)
        self.assertIsInstance(gmls, MailingList)
        self.assertEqual(gmls.uri, GMANE_MYLIST_URL)
        self.assertEqual(gmls.dirpath, self.tmp_path)
        self.assertEqual(gmls.url, GMANE_MYLIST_URL)

    @httpretty.activate
    def test_init_url_not_found(self):
        """Test whether it raises an exception when a mailing list is not found"""

        httpretty.register_uri(httpretty.GET, GMANE_INVALID_LIST_URL,
                               status=200,
                               body="No such list")

        with self.assertRaises(RepositoryError):
            _ = GmaneMailingList('invalidlist@example.com', self.tmp_path)

    @httpretty.activate
    def test_fetch(self):
        """Test whether it fetches a set of messages"""

        setup_http_server()

        gmls = GmaneMailingList('mylist@example.com', self.tmp_path)

        archives = gmls.fetch()
        self.assertEqual(len(archives), 3)
        self.assertEqual(archives[0][0], 0)
        self.assertEqual(archives[0][1], os.path.join(self.tmp_path, '0'))
        self.assertEqual(archives[1][0], 2000)
        self.assertEqual(archives[1][1], os.path.join(self.tmp_path, '2000'))
        self.assertEqual(archives[2][0], 4000)
        self.assertEqual(archives[2][1], os.path.join(self.tmp_path, '4000'))

        mboxes = gmls.mboxes
        self.assertEqual(len(mboxes), 3)
        self.assertEqual(mboxes[0].filepath, os.path.join(self.tmp_path, '0'))
        self.assertEqual(mboxes[1].filepath, os.path.join(self.tmp_path, '2000'))
        self.assertEqual(mboxes[2].filepath, os.path.join(self.tmp_path, '4000'))

    @httpretty.activate
    def test_fetch_from_offset(self):
        """Test whether it fetches a set of messages from a given offset"""

        setup_http_server()

        gmls = GmaneMailingList('mylist@example.com', self.tmp_path)

        archives = gmls.fetch(offset=4000)
        self.assertEqual(len(archives), 1)
        self.assertEqual(archives[0][0], 4000)
        self.assertEqual(archives[0][1], os.path.join(self.tmp_path, '4000'))

        mboxes = gmls.mboxes
        self.assertEqual(len(mboxes), 1)
        self.assertEqual(mboxes[0].filepath, os.path.join(self.tmp_path, '4000'))

    @httpretty.activate
    def test_fetch_empty(self):
        """Test whether it does nothing when a response is empty"""

        setup_http_server()

        gmls = GmaneMailingList('mylist@example.com', self.tmp_path)

        archives = gmls.fetch(offset=6000)
        self.assertEqual(len(archives), 0)

        mboxes = gmls.mboxes
        self.assertEqual(len(mboxes), 0)

    @httpretty.activate
    def test_mboxes(self):
        """Test whether it returns the mboxes ordered by the offset on their filenames"""

        setup_http_server()

        # Simulate the fetch process copying the files
        shutil.copy('data/gmane_messages.mbox',
                    os.path.join(self.tmp_path, '0'))
        shutil.copy('data/gmane_messages_2000.mbox',
                    os.path.join(self.tmp_path, '2000'))
        shutil.copy('data/gmane_messages_4000.mbox',
                    os.path.join(self.tmp_path, '4000'))
        shutil.copy('data/gmane_messages_empty.mbox',
                    os.path.join(self.tmp_path, 'gmane_messages_empty.mbox'))

        gmls = GmaneMailingList('mylist@example.com', self.tmp_path)

        mboxes = gmls.mboxes
        self.assertEqual(mboxes[0].filepath, os.path.join(self.tmp_path, '0'))
        self.assertEqual(mboxes[1].filepath, os.path.join(self.tmp_path, '2000'))
        self.assertEqual(mboxes[2].filepath, os.path.join(self.tmp_path, '4000'))


class TestGmaneClient(unittest.TestCase):
    """Tests for GmaneClient class"""

    @httpretty.activate
    def test_messages(self):
        """Test if a set of messages is fetched"""

        body = read_file('data/gmane_messages.mbox', 'rb')

        url = GMAME_DOWNLOAD_LIST_URL + '/888/898'

        httpretty.register_uri(httpretty.GET, url,
                               status=200,
                               body=body)

        client = GmaneClient()

        response = client.messages('gmane.comp.example.mylist', 888, 10)
        self.assertEqual(response, body)

    @httpretty.activate
    def test_mailing_list_url(self):
        """Test whether it returns the URL of a mailing list in Gmane"""

        setup_http_server()

        client = GmaneClient()

        url = client.mailing_list_url('mylist@example.com')
        self.assertEqual(url, GMANE_MYLIST_URL)

    @httpretty.activate
    def test_mailing_list_url_not_found(self):
        """Test whether it raises an exception when a mailing list is not found"""

        httpretty.register_uri(httpretty.GET, GMANE_INVALID_LIST_URL,
                               status=200,
                               body="No such list")

        client = GmaneClient()

        with self.assertRaises(RepositoryError):
            client.mailing_list_url('invalidlist@example.com')


if __name__ == "__main__":
    unittest.main(warnings='ignore')
