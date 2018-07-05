# -*- coding: utf-8 -*-
#
# Copyright (C) 2015-2018 Bitergia
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
#     Valerio Cosentino <valcos@bitergia.com>
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
from perceval.utils import DEFAULT_DATETIME
from perceval.backends.core.groupsio import (MBOX_FILE,
                                             Groupsio,
                                             GroupsioClient,
                                             GroupsioCommand)


GROUPSIO_API_URL = 'https://api.groups.io/v1/'


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

        backend = Groupsio('acme_group', self.tmp_path, 'aaaaa', tag='test')

        self.assertEqual(backend.group_name, 'acme_group')
        self.assertEqual(backend.api_token, 'aaaaa')
        self.assertEqual(backend.uri, 'https://groups.io/g/acme_group')
        self.assertEqual(backend.dirpath, self.tmp_path)
        self.assertEqual(backend.origin, 'https://groups.io/g/acme_group')
        self.assertEqual(backend.tag, 'test')
        self.assertTrue(backend.verify)

        # When tag is empty or None it will be set to
        # the value in uri
        backend = Groupsio('acme_group', self.tmp_path, 'aaaaa')
        self.assertEqual(backend.origin, 'https://groups.io/g/acme_group')
        self.assertEqual(backend.tag, 'https://groups.io/g/acme_group')

        backend = Groupsio('acme_group', self.tmp_path, 'aaaaa', tag='')
        self.assertEqual(backend.origin, 'https://groups.io/g/acme_group')
        self.assertEqual(backend.tag, 'https://groups.io/g/acme_group')

        backend = Groupsio('acme_group', self.tmp_path, 'aaaaa', verify=False, tag='')
        self.assertEqual(backend.origin, 'https://groups.io/g/acme_group')
        self.assertEqual(backend.tag, 'https://groups.io/g/acme_group')
        self.assertFalse(backend.verify)

    def test_has_archiving(self):
        """Test if it returns False when has_archiving is called"""

        self.assertEqual(Groupsio.has_archiving(), False)

    def test_has_resuming(self):
        """Test if it returns True when has_resuming is called"""

        self.assertEqual(Groupsio.has_resuming(), True)

    @httpretty.activate
    def test_fetch(self):
        """Test whether it fetches and parses messages"""

        groupsio_mbox_archive = read_file('data/groupsio/messages.zip')

        httpretty.register_uri(httpretty.GET,
                               GROUPSIO_API_URL + 'downloadarchives',
                               body=groupsio_mbox_archive)

        backend = Groupsio('acme_group', self.tmp_path, 'aaaaa')
        messages = [m for m in backend.fetch()]

        self.assertEqual(len(messages), 49)

        message = messages[0]
        self.assertEqual(message['data']['Message-ID'], '<1411493115994433684.27523@groups.io>')
        self.assertEqual(message['origin'], 'https://groups.io/g/acme_group')
        self.assertEqual(message['uuid'], '5d668945b4f339563f7bb1497ae097b00c1b2fc1')
        self.assertEqual(message['updated_on'], 1411493115.0)
        self.assertEqual(message['category'], 'message')
        self.assertEqual(message['tag'], 'https://groups.io/g/acme_group')

        message = messages[25]
        self.assertEqual(message['data']['Message-ID'], '<1515301791792840617.19948@groups.io>')
        self.assertEqual(message['origin'], 'https://groups.io/g/acme_group')
        self.assertEqual(message['uuid'], 'c4ebc4bdbe8d396302ba67306f9ff1fd51cf19cf')
        self.assertEqual(message['updated_on'], 1515301791.0)
        self.assertEqual(message['category'], 'message')
        self.assertEqual(message['tag'], 'https://groups.io/g/acme_group')

        message = messages[45]
        self.assertEqual(message['data']['Message-ID'], '<1528518785616723298.15102@groups.io>')
        self.assertEqual(message['origin'], 'https://groups.io/g/acme_group')
        self.assertEqual(message['uuid'], 'c1ab131763deb7b417e7f26cedb9ae17656ede15')
        self.assertEqual(message['updated_on'], 1528518785.0)
        self.assertEqual(message['category'], 'message')
        self.assertEqual(message['tag'], 'https://groups.io/g/acme_group')

    @httpretty.activate
    def test_fetch_from_date(self):
        """Test whether it fetches and parses messages since the given date"""

        groupsio_mbox_archive = read_file('data/groupsio/messages.zip')

        httpretty.register_uri(httpretty.GET,
                               GROUPSIO_API_URL + 'downloadarchives',
                               body=groupsio_mbox_archive)

        from_date = datetime.datetime(2018, 5, 5)

        backend = Groupsio('acme_group', self.tmp_path, 'aaaaa')
        messages = [m for m in backend.fetch(from_date=from_date)]

        self.assertEqual(len(messages), 8)

        message = messages[0]
        self.assertEqual(message['data']['Message-ID'], '<1526087603011004609.30544@groups.io>')
        self.assertEqual(message['origin'], 'https://groups.io/g/acme_group')
        self.assertEqual(message['uuid'], '078f740e54131b8833f69d605eae637b97797295')
        self.assertEqual(message['updated_on'], 1526087603.0)
        self.assertEqual(message['category'], 'message')
        self.assertEqual(message['tag'], 'https://groups.io/g/acme_group')

        message = messages[3]
        self.assertEqual(message['data']['Message-ID'], '<1527915246656874452.2546@groups.io>')
        self.assertEqual(message['origin'], 'https://groups.io/g/acme_group')
        self.assertEqual(message['uuid'], 'c4a8db34d926f231ac99f5cc0eb340ed6b404e06')
        self.assertEqual(message['updated_on'], 1527915246.0)
        self.assertEqual(message['category'], 'message')
        self.assertEqual(message['tag'], 'https://groups.io/g/acme_group')

        message = messages[7]
        self.assertEqual(message['data']['Message-ID'], '<1530334100637290090.7026@groups.io>')
        self.assertEqual(message['origin'], 'https://groups.io/g/acme_group')
        self.assertEqual(message['uuid'], '787835d4cc343299b8d1a427fa580365bb7feb0d')
        self.assertEqual(message['updated_on'], 1530334100.0)
        self.assertEqual(message['category'], 'message')
        self.assertEqual(message['tag'], 'https://groups.io/g/acme_group')

    @httpretty.activate
    def test_fetch_empty(self):
        """Test whether an empty mbox is stored when the group is empty"""

        groupsio_mbox_archive = read_file('data/groupsio/empty.zip')

        httpretty.register_uri(httpretty.GET,
                               GROUPSIO_API_URL + 'downloadarchives',
                               body=groupsio_mbox_archive)

        backend = Groupsio('acme_group', self.tmp_path, 'aaaaa')
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

        client = GroupsioClient('acme_group', self.tmp_path, 'aaaaa')

        self.assertIsInstance(client, GroupsioClient)
        self.assertEqual(client.uri, 'https://groups.io/g/acme_group')
        self.assertEqual(client.dirpath, self.tmp_path)
        self.assertEqual(client.group_name, 'acme_group')
        self.assertTrue(client.verify)

        client = GroupsioClient('acme_group', self.tmp_path, 'aaaaa', verify=False)

        self.assertIsInstance(client, GroupsioClient)
        self.assertEqual(client.uri, 'https://groups.io/g/acme_group')
        self.assertEqual(client.dirpath, self.tmp_path)
        self.assertEqual(client.group_name, 'acme_group')
        self.assertFalse(client.verify)

    @httpretty.activate
    def test_fetch(self):
        """Test whether archives are fetched"""

        groupsio_mbox_archive = read_file('data/groupsio/empty.zip')

        httpretty.register_uri(httpretty.GET,
                               GROUPSIO_API_URL + 'downloadarchives',
                               body=groupsio_mbox_archive)

        client = GroupsioClient('acme_group', self.tmp_path, 'aaaaa', verify=False)
        success = client.fetch()

        self.assertEqual(client.mboxes[0].filepath, os.path.join(self.tmp_path, MBOX_FILE))
        self.assertTrue(success)

    @httpretty.activate
    def test_fetch_http_error(self):
        """Test whether HTTP errors are thrown"""

        groupsio_mbox_archive = read_file('data/groupsio/empty.zip')

        httpretty.register_uri(httpretty.GET,
                               GROUPSIO_API_URL + 'downloadarchives',
                               body=groupsio_mbox_archive,
                               status=400)

        client = GroupsioClient('acme_group', self.tmp_path, 'aaaaa', verify=False)
        with self.assertRaises(requests.exceptions.HTTPError):
            client.fetch()

    @httpretty.activate
    def test_fetch_os_error(self):
        """Test whether OS errors are properly handled"""

        groupsio_mbox_archive = read_file('data/groupsio/empty.zip')

        httpretty.register_uri(httpretty.GET,
                               GROUPSIO_API_URL + 'downloadarchives',
                               body=groupsio_mbox_archive)

        client = GroupsioClientMocked('acme_group', self.tmp_path, 'aaaaa', verify=False)
        success = client.fetch()

        self.assertFalse(success)

    @httpretty.activate
    def test_fetch_no_existing_dir(self):
        """Test whether the dir_path where to store the archives is created if it doesn't exist"""

        groupsio_mbox_archive = read_file('data/groupsio/empty.zip')

        httpretty.register_uri(httpretty.GET,
                               GROUPSIO_API_URL + 'downloadarchives',
                               body=groupsio_mbox_archive)

        # delete the dir path
        os.removedirs(self.tmp_path)

        self.assertFalse(os.path.exists(self.tmp_path))
        client = GroupsioClient('acme_group', self.tmp_path, 'aaaaa', verify=False)
        _ = client.fetch()
        self.assertTrue(os.path.exists(self.tmp_path))

    @httpretty.activate
    def test_fetch_empty(self):
        """Test whether it does not store anything when the list of archives is empty"""

        groupsio_mbox_archive = read_file('data/groupsio/empty.zip')

        httpretty.register_uri(httpretty.GET,
                               GROUPSIO_API_URL + 'downloadarchives',
                               body=groupsio_mbox_archive)

        client = GroupsioClient('acme_group', self.tmp_path, 'aaaaa', verify=False)
        success = client.fetch()

        self.assertEqual(client.mboxes[0].filepath, os.path.join(self.tmp_path, MBOX_FILE))

        _zip = zipfile.ZipFile(client.mboxes[0].filepath)
        with _zip.open(_zip.infolist()[0].filename) as _file:
            content = _file.read()

        self.assertEqual(content, b'')
        self.assertTrue(success)


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

        args = ['acme_group', '-t', 'aaaaa']

        cmd = GroupsioCommand(*args)
        self.assertEqual(cmd.parsed_args.dirpath,
                         os.path.join(self.tmp_path, 'testpath/https://groups.io/g/acme_group'))
        self.assertEqual(cmd.parsed_args.group_name, 'acme_group')
        self.assertEqual(cmd.parsed_args.api_token, 'aaaaa')

        args = ['acme_group',
                '--mboxes-path', '/tmp/perceval/', '-t', 'aaaaa']

        cmd = GroupsioCommand(*args)
        self.assertEqual(cmd.parsed_args.dirpath, '/tmp/perceval/')
        self.assertEqual(cmd.parsed_args.group_name, 'acme_group')
        self.assertEqual(cmd.parsed_args.api_token, 'aaaaa')

    def test_parsing_on_init(self):
        """Test if the class is initialized"""

        args = ['acme_group', '-t', 'aaaaa',
                '--mboxes-path', '/tmp/perceval/',
                '--tag', 'test']

        cmd = GroupsioCommand(*args)
        self.assertEqual(cmd.parsed_args.mboxes_path, '/tmp/perceval/')
        self.assertEqual(cmd.parsed_args.group_name, 'acme_group')
        self.assertEqual(cmd.parsed_args.api_token, 'aaaaa')
        self.assertEqual(cmd.parsed_args.tag, 'test')

    def test_setup_cmd_parser(self):
        """Test if it parser object is correctly initialized"""

        parser = GroupsioCommand.setup_cmd_parser()
        self.assertIsInstance(parser, BackendCommandArgumentParser)

        args = ['acme_group',
                '--mboxes-path', '/tmp/perceval/',
                '--tag', 'test',
                '--from-date', '1970-01-01',
                '--no-verify',
                '--api-token', 'aaaaa']

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.group_name, 'acme_group')
        self.assertEqual(parsed_args.mboxes_path, '/tmp/perceval/')
        self.assertEqual(parsed_args.tag, 'test')
        self.assertEqual(parsed_args.from_date, DEFAULT_DATETIME)
        self.assertFalse(parsed_args.verify)
        self.assertEqual(parsed_args.api_token, 'aaaaa')


if __name__ == "__main__":
    unittest.main(warnings='ignore')
