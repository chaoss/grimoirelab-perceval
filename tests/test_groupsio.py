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
#     Valerio Cosentino <valcos@bitergia.com>
#     Harshal Mittal <harshalmittal4@gmail.com>
#     Santiago Dueñas <sduenas@bitergia.com>
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
import zipfile

pkg_resources.declare_namespace('perceval.backends')

from perceval.backend import BackendCommandArgumentParser
from perceval.errors import BackendError
from perceval.utils import DEFAULT_DATETIME
from perceval.backends.core.groupsio import (MBOX_FILE,
                                             Groupsio,
                                             GroupsioClient,
                                             GroupsioCommand,
                                             logger)


GROUPSIO_API_URL = 'https://groups.io/api/v1/'


def setup_http_server(empty_mbox=False, http_status_download=200, http_status_subscriptions=200):
    groupsio_mbox_archive = read_file('data/groupsio/messages.zip')
    groupsio_mbox_empty = read_file('data/groupsio/empty.zip')
    login = read_file('data/groupsio/login')
    subscriptions_page_1 = read_file('data/groupsio/subscriptions_page_1')
    subscriptions_page_2 = read_file('data/groupsio/subscriptions_page_2')

    if empty_mbox:
        httpretty.register_uri(httpretty.GET,
                               GROUPSIO_API_URL + GroupsioClient.RDOWNLOAD_ARCHIVES,
                               body=groupsio_mbox_empty,
                               status=http_status_download)
    else:
        httpretty.register_uri(httpretty.GET,
                               GROUPSIO_API_URL + GroupsioClient.RDOWNLOAD_ARCHIVES,
                               body=groupsio_mbox_archive,
                               status=http_status_download)

    httpretty.register_uri(httpretty.POST,
                           GROUPSIO_API_URL + GroupsioClient.RLOGIN,
                           body=login,
                           params={'email': 'jsmith@example.com', 'password': 'aaaaa'},
                           status=200)

    httpretty.register_uri(httpretty.GET,
                           GROUPSIO_API_URL + GroupsioClient.RGET_SUBSCRIPTIONS,
                           body=subscriptions_page_2,
                           params={"limit": 1, "next_page_token": 1},
                           status=http_status_subscriptions)

    httpretty.register_uri(httpretty.GET,
                           GROUPSIO_API_URL + GroupsioClient.RGET_SUBSCRIPTIONS,
                           body=subscriptions_page_1,
                           params={"limit": 1},
                           status=http_status_subscriptions)


def read_file(filename):
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), filename), 'rb') as f:
        content = f.read()
    return content


class GroupsioClientMocked(GroupsioClient):

    @staticmethod
    def _write_archive(r, filepath):
        raise OSError


class TestGroupsioBackend(unittest.TestCase):
    """Tests for Groupsio backend class"""

    def setUp(self):
        self.tmp_path = tempfile.mkdtemp(prefix='perceval_')

    def tearDown(self):
        shutil.rmtree(self.tmp_path)

    def test_initialization(self):
        """Test whether attributes are initializated"""

        backend = Groupsio('beta+api', self.tmp_path, 'jsmith@example.com', 'aaaaa', tag='test')

        self.assertEqual(backend.group_name, 'beta+api')
        self.assertEqual(backend.email, 'jsmith@example.com')
        self.assertEqual(backend.password, "aaaaa")
        self.assertEqual(backend.uri, 'https://groups.io/g/beta+api')
        self.assertEqual(backend.dirpath, self.tmp_path)
        self.assertEqual(backend.origin, 'https://groups.io/g/beta+api')
        self.assertEqual(backend.tag, 'test')
        self.assertTrue(backend.ssl_verify)

        # When tag is empty or None it will be set to
        # the value in uri
        backend = Groupsio('beta+api', self.tmp_path, 'jsmith@example.com', 'aaaaa')
        self.assertEqual(backend.origin, 'https://groups.io/g/beta+api')
        self.assertEqual(backend.tag, 'https://groups.io/g/beta+api')

        backend = Groupsio('beta+api', self.tmp_path, 'jsmith@example.com', 'aaaaa', tag='')
        self.assertEqual(backend.origin, 'https://groups.io/g/beta+api')
        self.assertEqual(backend.tag, 'https://groups.io/g/beta+api')

        backend = Groupsio('beta+api', self.tmp_path, 'jsmith@example.com', 'aaaaa', ssl_verify=False, tag='')
        self.assertEqual(backend.origin, 'https://groups.io/g/beta+api')
        self.assertEqual(backend.tag, 'https://groups.io/g/beta+api')
        self.assertFalse(backend.ssl_verify)

    def test_has_archiving(self):
        """Test if it returns False when has_archiving is called"""

        self.assertEqual(Groupsio.has_archiving(), False)

    def test_has_resuming(self):
        """Test if it returns True when has_resuming is called"""

        self.assertEqual(Groupsio.has_resuming(), True)

    @httpretty.activate
    def test_fetch(self):
        """Test whether it fetches and parses messages"""

        setup_http_server()

        backend = Groupsio('beta+api', self.tmp_path, 'jsmith@example.com', 'aaaaa')
        messages = [m for m in backend.fetch()]

        self.assertEqual(len(messages), 49)

        message = messages[0]
        self.assertEqual(message['data']['Message-ID'], '<1411493115994433684.27523@groups.io>')
        self.assertEqual(message['origin'], 'https://groups.io/g/beta+api')
        self.assertEqual(message['uuid'], 'ee0a9d612a20cd359a0492685e2f6db90aaa637f')
        self.assertEqual(message['updated_on'], 1411493115.0)
        self.assertEqual(message['category'], 'message')
        self.assertEqual(message['tag'], 'https://groups.io/g/beta+api')

        message = messages[25]
        self.assertEqual(message['data']['Message-ID'], '<1515301791792840617.19948@groups.io>')
        self.assertEqual(message['origin'], 'https://groups.io/g/beta+api')
        self.assertEqual(message['uuid'], 'cb9119226ab58fe0f06f83b6178b217ccbaa28bf')
        self.assertEqual(message['updated_on'], 1515301791.0)
        self.assertEqual(message['category'], 'message')
        self.assertEqual(message['tag'], 'https://groups.io/g/beta+api')

        message = messages[45]
        self.assertEqual(message['data']['Message-ID'], '<1528518785616723298.15102@groups.io>')
        self.assertEqual(message['origin'], 'https://groups.io/g/beta+api')
        self.assertEqual(message['uuid'], '73e23136f519e3534ae8372da9457e7f8967b526')
        self.assertEqual(message['updated_on'], 1528518785.0)
        self.assertEqual(message['category'], 'message')
        self.assertEqual(message['tag'], 'https://groups.io/g/beta+api')

    @httpretty.activate
    def test_search_fields(self):
        """Test whether the search_fields is properly set"""

        setup_http_server()

        backend = Groupsio('beta+api', self.tmp_path, 'jsmith@example.com', 'aaaaa')
        messages = [m for m in backend.fetch()]

        for message in messages:
            self.assertEqual(backend.metadata_id(message['data']), message['search_fields']['item_id'])
            self.assertEqual(message['search_fields']['group_name'], 'beta+api')

    @httpretty.activate
    def test_fetch_from_date(self):
        """Test whether it fetches and parses messages since the given date"""

        setup_http_server()

        from_date = datetime.datetime(2018, 5, 5)

        backend = Groupsio('beta+api', self.tmp_path, 'jsmith@example.com', 'aaaaa')
        messages = [m for m in backend.fetch(from_date=from_date)]

        self.assertEqual(len(messages), 8)

        message = messages[0]
        self.assertEqual(message['data']['Message-ID'], '<1526087603011004609.30544@groups.io>')
        self.assertEqual(message['origin'], 'https://groups.io/g/beta+api')
        self.assertEqual(message['uuid'], 'fe0b6b64b4b297796c6139c821ff3d10dee1dc92')
        self.assertEqual(message['updated_on'], 1526087603.0)
        self.assertEqual(message['category'], 'message')
        self.assertEqual(message['tag'], 'https://groups.io/g/beta+api')

        message = messages[3]
        self.assertEqual(message['data']['Message-ID'], '<1527915246656874452.2546@groups.io>')
        self.assertEqual(message['origin'], 'https://groups.io/g/beta+api')
        self.assertEqual(message['uuid'], 'bd02e439127edf51df9ecbb15f3e57d473f6418f')
        self.assertEqual(message['updated_on'], 1527915246.0)
        self.assertEqual(message['category'], 'message')
        self.assertEqual(message['tag'], 'https://groups.io/g/beta+api')

        message = messages[7]
        self.assertEqual(message['data']['Message-ID'], '<1530334100637290090.7026@groups.io>')
        self.assertEqual(message['origin'], 'https://groups.io/g/beta+api')
        self.assertEqual(message['uuid'], '397508a441b878459cd9deabba034171bce9058d')
        self.assertEqual(message['updated_on'], 1530334100.0)
        self.assertEqual(message['category'], 'message')
        self.assertEqual(message['tag'], 'https://groups.io/g/beta+api')

    @httpretty.activate
    def test_fetch_empty(self):
        """Test whether an empty mbox is stored when the group is empty"""

        setup_http_server(empty_mbox=True)

        backend = Groupsio('beta+api', self.tmp_path, 'jsmith@example.com', 'aaaaa')
        messages = [m for m in backend.fetch()]

        self.assertListEqual(messages, [])


class TestGroupsioClient(unittest.TestCase):
    """Tests for GroupsioClient class"""

    def setUp(self):
        self.tmp_path = tempfile.mkdtemp(prefix='perceval_')

    def tearDown(self):
        shutil.rmtree(self.tmp_path)

    def test_init(self):
        """Check attributes initialization"""

        client = GroupsioClient('beta+api', self.tmp_path, 'jsmith@example.com', 'aaaaa')
        self.assertIsInstance(client, GroupsioClient)
        self.assertEqual(client.uri, 'https://groups.io/g/beta+api')
        self.assertEqual(client.dirpath, self.tmp_path)
        self.assertEqual(client.group_name, 'beta+api')
        self.assertTrue(client.ssl_verify)

        client = GroupsioClient('beta+api', self.tmp_path, 'jsmith@example.com', 'aaaaa', ssl_verify=False)
        self.assertIsInstance(client, GroupsioClient)
        self.assertEqual(client.uri, 'https://groups.io/g/beta+api')
        self.assertEqual(client.dirpath, self.tmp_path)
        self.assertEqual(client.group_name, 'beta+api')
        self.assertFalse(client.ssl_verify)

    @httpretty.activate
    def test_fetch(self):
        """Test whether archives are fetched"""

        setup_http_server(empty_mbox=True)

        client = GroupsioClient('beta+api', self.tmp_path, 'jsmith@example.com', 'aaaaa', ssl_verify=False)
        success = client.fetch()

        # Check requests
        expected = [
            {
                'email': ['jsmith@example.com'],
                'password': ['aaaaa']
            },
            {
                'limit': ['100'],
            },
            {
                'limit': ['100'],
                'page_token': ['1']
            },
            {
                'group_id': ['7769']
            }
        ]

        http_requests = httpretty.httpretty.latest_requests

        self.assertEqual(len(http_requests), len(expected))

        for i in range(len(expected)):
            self.assertDictEqual(http_requests[i].querystring, expected[i])

        self.assertEqual(client.mboxes[0].filepath, os.path.join(self.tmp_path, MBOX_FILE))
        self.assertTrue(success)

    @httpretty.activate
    def test_fetch_from_date(self):
        """Test whether archives are fetched after a given date"""

        setup_http_server()

        client = GroupsioClient('beta+api', self.tmp_path, 'jsmith@example.com', 'aaaaa', ssl_verify=False)
        from_date = datetime.datetime(2019, 1, 1)
        success = client.fetch(from_date=from_date)

        # Check requests
        expected = [
            {
                'email': ['jsmith@example.com'],
                'password': ['aaaaa']
            },
            {
                'limit': ['100'],
            },
            {
                'limit': ['100'],
                'page_token': ['1']
            },
            {
                'group_id': ['7769'],
                'start_time': ['2019-01-01T00:00:00 00:00']
            }
        ]

        http_requests = httpretty.httpretty.latest_requests

        self.assertEqual(len(http_requests), len(expected))

        for i in range(len(expected)):
            self.assertDictEqual(http_requests[i].querystring, expected[i])

        self.assertEqual(client.mboxes[0].filepath, os.path.join(self.tmp_path, MBOX_FILE))
        self.assertTrue(success)

    @httpretty.activate
    def test_fetch_group_id_not_found(self):
        """Test whether an error is thrown when the group id is not found"""

        setup_http_server(empty_mbox=True)

        client = GroupsioClient('beta/api', self.tmp_path, 'jsmith@example.com', 'aaaaa', ssl_verify=False)
        with self.assertRaises(BackendError):
            client.fetch()

    @httpretty.activate
    def test_fetch_http_error(self):
        """Test whether HTTP errors are thrown"""

        setup_http_server(empty_mbox=True, http_status_download=400)

        client = GroupsioClient('beta+api', self.tmp_path, 'jsmith@example.com', 'aaaaa', ssl_verify=False)
        with self.assertRaises(requests.exceptions.HTTPError):
            client.fetch()

    @httpretty.activate
    def test_fetch_download_archive_error(self):
        """Test whether Backend error is thrown when download archive is False for a group"""

        setup_http_server(empty_mbox=True, http_status_download=400)

        client = GroupsioClientMocked('beta', self.tmp_path, 'jsmith@example.com', 'aaaaa', ssl_verify=False)
        with self.assertLogs(logger, level='ERROR') as cm:
            with self.assertRaises(BackendError):
                _ = client.fetch()
            self.assertEqual(cm.output[0], 'ERROR:perceval.backends.core.groupsio:'
                                           'Download archive permission disabled for the group beta')

    @httpretty.activate
    def test_fetch_os_error(self):
        """Test whether OS errors are properly handled"""

        setup_http_server(empty_mbox=True)

        client = GroupsioClientMocked('beta+api', self.tmp_path, 'jsmith@example.com', 'aaaaa', ssl_verify=False)
        success = client.fetch()

        self.assertFalse(success)

    @httpretty.activate
    def test_fetch_no_existing_dir(self):
        """Test whether the dir_path where to store the archives is created if it doesn't exist"""

        setup_http_server(empty_mbox=True)

        # delete the dir path
        os.removedirs(self.tmp_path)

        self.assertFalse(os.path.exists(self.tmp_path))
        client = GroupsioClient('beta+api', self.tmp_path, 'jsmith@example.com', 'aaaaa', ssl_verify=False)
        _ = client.fetch()
        self.assertTrue(os.path.exists(self.tmp_path))

    @httpretty.activate
    def test_fetch_empty(self):
        """Test whether it does not store anything when the list of archives is empty"""

        setup_http_server(empty_mbox=True)

        client = GroupsioClient('beta+api', self.tmp_path, 'jsmith@example.com', 'aaaaa', ssl_verify=False)
        success = client.fetch()

        self.assertEqual(client.mboxes[0].filepath, os.path.join(self.tmp_path, MBOX_FILE))

        _zip = zipfile.ZipFile(client.mboxes[0].filepath)
        with _zip.open(_zip.infolist()[0].filename) as _file:
            content = _file.read()

        self.assertEqual(content, b'')
        self.assertTrue(success)

    @httpretty.activate
    def test_subscriptions(self):
        """Test whether the method subscriptions works properly"""

        setup_http_server()

        client = GroupsioClient('beta+api', self.tmp_path, 'jsmith@example.com', 'aaaaa', ssl_verify=False)
        subs = [subs for subs in client.subscriptions(per_page=1)]
        self.assertEqual(len(subs), 2)

    @httpretty.activate
    def test_subscriptions_http_error(self):
        """Test whether HTTP errors are thrown"""

        setup_http_server(http_status_subscriptions=400)

        client = GroupsioClient('beta+api', self.tmp_path, 'jsmith@example.com', 'aaaaa', ssl_verify=False)

        with self.assertRaises(requests.exceptions.HTTPError):
            _ = [subs for subs in client.subscriptions(per_page=1)]


class TestGroupsioCommand(unittest.TestCase):
    """Tests for GroupsioCommand class"""

    def setUp(self):
        self.tmp_path = tempfile.mkdtemp(prefix='perceval_')

    def tearDown(self):
        shutil.rmtree(self.tmp_path)

    def test_backend_class(self):
        """Test if the backend class is Groupsio"""

        self.assertIs(GroupsioCommand.BACKEND, Groupsio)

    @httpretty.activate
    @unittest.mock.patch('os.path.expanduser')
    def test_mboxes_path_init(self, mock_expanduser):
        """Test dirpath initialization"""

        mock_expanduser.return_value = os.path.join(self.tmp_path, 'testpath')

        args = ['acme_group', '-e', 'jsmith@example.com', '-p', 'aaaaa']

        cmd = GroupsioCommand(*args)
        self.assertEqual(cmd.parsed_args.dirpath,
                         os.path.join(self.tmp_path, 'testpath/https://groups.io/g/acme_group'))
        self.assertEqual(cmd.parsed_args.group_name, 'acme_group')
        self.assertEqual(cmd.parsed_args.email, 'jsmith@example.com')
        self.assertEqual(cmd.parsed_args.password, 'aaaaa')

        args = ['acme_group',
                '--mboxes-path', '/tmp/perceval/', '-e', 'jsmith@example.com', '-p', 'aaaaa']

        cmd = GroupsioCommand(*args)
        self.assertEqual(cmd.parsed_args.dirpath, '/tmp/perceval/')
        self.assertEqual(cmd.parsed_args.group_name, 'acme_group')
        self.assertEqual(cmd.parsed_args.email, 'jsmith@example.com')
        self.assertEqual(cmd.parsed_args.password, 'aaaaa')

    def test_parsing_on_init(self):
        """Test if the class is initialized"""

        args = ['acme_group', '-e', 'jsmith@example.com', '-p', 'aaaaa',
                '--mboxes-path', '/tmp/perceval/',
                '--tag', 'test']

        cmd = GroupsioCommand(*args)
        self.assertEqual(cmd.parsed_args.mboxes_path, '/tmp/perceval/')
        self.assertEqual(cmd.parsed_args.group_name, 'acme_group')
        self.assertEqual(cmd.parsed_args.email, 'jsmith@example.com')
        self.assertEqual(cmd.parsed_args.password, 'aaaaa')
        self.assertEqual(cmd.parsed_args.tag, 'test')

    def test_setup_cmd_parser(self):
        """Test if it parser object is correctly initialized"""

        parser = GroupsioCommand.setup_cmd_parser()
        self.assertIsInstance(parser, BackendCommandArgumentParser)
        self.assertEqual(parser._backend, Groupsio)

        args = ['acme_group',
                '--mboxes-path', '/tmp/perceval/',
                '--tag', 'test',
                '--from-date', '1970-01-01',
                '--email', 'jsmith@example.com',
                '--password', 'aaaaa']

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.group_name, 'acme_group')
        self.assertEqual(parsed_args.mboxes_path, '/tmp/perceval/')
        self.assertEqual(parsed_args.tag, 'test')
        self.assertEqual(parsed_args.from_date, DEFAULT_DATETIME)
        self.assertTrue(parsed_args.ssl_verify)
        self.assertEqual(parsed_args.email, 'jsmith@example.com')
        self.assertEqual(parsed_args.password, 'aaaaa')

        args = ['acme_group',
                '--mboxes-path', '/tmp/perceval/',
                '--tag', 'test',
                '--from-date', '1970-01-01',
                '--no-ssl-verify',
                '--email', 'jsmith@example.com',
                '--password', 'aaaaa']

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.group_name, 'acme_group')
        self.assertEqual(parsed_args.mboxes_path, '/tmp/perceval/')
        self.assertEqual(parsed_args.tag, 'test')
        self.assertEqual(parsed_args.from_date, DEFAULT_DATETIME)
        self.assertFalse(parsed_args.ssl_verify)
        self.assertEqual(parsed_args.email, 'jsmith@example.com')
        self.assertEqual(parsed_args.password, 'aaaaa')


if __name__ == "__main__":
    unittest.main(warnings='ignore')
