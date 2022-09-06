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
#     Jesus M. Gonzalez-Barahona <jgb@gsyc.es>
#     Harshal Mittal <harshalmittal4@gmail.com>
#

import datetime
import os
import shutil
import unittest
import unittest.mock

import dateutil
import httpretty

from grimoirelab_toolkit.uris import urijoin

from perceval.backend import BackendCommandArgumentParser
from perceval.backends.core.dockerhub import (DockerHub,
                                              DockerHubClient,
                                              DockerHubCommand)
from base import TestCaseBackendArchive

DOCKERHUB_URL = "https://hub.docker.com/"
DOCKERHUB_API_URL = DOCKERHUB_URL + 'v2'
DOCKERHUB_RESPOSITORY_URL = DOCKERHUB_API_URL + '/repositories/grimoirelab/perceval'


def read_file(filename, mode='r'):
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), filename), mode) as f:
        content = f.read()
    return content


def setup_http_server():
    """Setup a mock HTTP server"""

    body = read_file('data/dockerhub/dockerhub_repository_1.json', 'rb')

    httpretty.register_uri(httpretty.GET,
                           DOCKERHUB_RESPOSITORY_URL,
                           body=body, status=200)


class TestDockerHubBackend(unittest.TestCase):
    """DockerHub backend tests"""

    def test_initialization(self):
        """Test whether attributes are initializated"""

        dockerhub = DockerHub('grimoirelab', 'perceval', tag='test')

        expected_origin = urijoin(DOCKERHUB_URL, 'grimoirelab', 'perceval')

        self.assertEqual(dockerhub.owner, 'grimoirelab')
        self.assertEqual(dockerhub.repository, 'perceval')
        self.assertEqual(dockerhub.origin, expected_origin)
        self.assertEqual(dockerhub.tag, 'test')
        self.assertIsNone(dockerhub.client)
        self.assertTrue(dockerhub.ssl_verify)

        # When tag is empty or None it will be set to
        # the value in
        dockerhub = DockerHub('grimoirelab', 'perceval', ssl_verify=False)
        self.assertEqual(dockerhub.origin, expected_origin)
        self.assertEqual(dockerhub.tag, expected_origin)
        self.assertFalse(dockerhub.ssl_verify)

        dockerhub = DockerHub('grimoirelab', 'perceval', tag='')
        self.assertEqual(dockerhub.origin, expected_origin)
        self.assertEqual(dockerhub.tag, expected_origin)

    def test_shortcut_official_owner(self):
        """Test if the shortcut owner is replaced when it is given on init"""

        # Value '_' should be replaced by 'library'
        dockerhub = DockerHub('_', 'redis', tag='test')

        expected_origin = urijoin(DOCKERHUB_URL, 'library', 'redis')

        self.assertEqual(dockerhub.owner, 'library')
        self.assertEqual(dockerhub.repository, 'redis')
        self.assertEqual(dockerhub.origin, expected_origin)

    def test_has_archiving(self):
        """Test if it returns True when has_archiving is called"""

        self.assertEqual(DockerHub.has_archiving(), True)

    def test_has_resuming(self):
        """Test if it returns True when has_resuming is called"""

        self.assertEqual(DockerHub.has_resuming(), True)

    @httpretty.activate
    @unittest.mock.patch('perceval.backends.core.dockerhub.datetime_utcnow')
    def test_fetch(self, mock_utcnow):
        """Test whether it fetches data from a repository"""

        mock_utcnow.return_value = datetime.datetime(2017, 1, 1,
                                                     tzinfo=dateutil.tz.tzutc())
        setup_http_server()

        dockerhub = DockerHub('grimoirelab', 'perceval')
        items = [item for item in dockerhub.fetch()]

        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item['data']['fetched_on'], 1483228800.0)
        self.assertEqual(item['uuid'], '0fa16dc4edab9130a14914a8d797f634d13b4ff4')
        self.assertEqual(item['origin'], 'https://hub.docker.com/grimoirelab/perceval')
        self.assertEqual(item['updated_on'], 1483228800.0)
        self.assertEqual(item['category'], 'dockerhub-data')
        self.assertEqual(item['tag'], 'https://hub.docker.com/grimoirelab/perceval')

        # Check requests
        self.assertEqual(len(httpretty.httpretty.latest_requests), 1)

    @httpretty.activate
    @unittest.mock.patch('perceval.backends.core.dockerhub.datetime_utcnow')
    def test_search_fields(self, mock_utcnow):
        """Test whether the search_fields is properly set"""

        mock_utcnow.return_value = datetime.datetime(2017, 1, 1,
                                                     tzinfo=dateutil.tz.tzutc())
        setup_http_server()

        dockerhub = DockerHub('grimoirelab', 'perceval')
        items = [item for item in dockerhub.fetch()]

        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(dockerhub.metadata_id(item['data']), item['search_fields']['item_id'])
        self.assertEqual(item['data']['name'], 'perceval')
        self.assertEqual(item['data']['name'], item['search_fields']['name'])
        self.assertEqual(item['data']['namespace'], 'grimoirelab')
        self.assertEqual(item['data']['namespace'], item['search_fields']['namespace'])

    def test_parse_json(self):
        """Test if it parses a JSON stream"""

        raw_json = read_file('data/dockerhub/dockerhub_repository_1.json')

        item = DockerHub.parse_json(raw_json)
        self.assertEqual(item['user'], 'grimoirelab')
        self.assertEqual(item['name'], 'perceval')


class TestDockerHubBackendArchive(TestCaseBackendArchive):
    """DockerHub backend tests using an archive"""

    def setUp(self):
        super().setUp()
        self.backend_write_archive = DockerHub('grimoirelab', 'perceval', archive=self.archive)
        self.backend_read_archive = DockerHub('grimoirelab', 'perceval', archive=self.archive)

    def tearDown(self):
        shutil.rmtree(self.test_path)

    @httpretty.activate
    @unittest.mock.patch('perceval.backends.core.dockerhub.datetime_utcnow')
    def test_fetch_from_archive(self, mock_utcnow):
        """Test whether it fetches data from a repository"""

        mock_utcnow.return_value = datetime.datetime(2017, 1, 1,
                                                     tzinfo=dateutil.tz.tzutc())
        setup_http_server()
        self._test_fetch_from_archive()


class TestDockerHubClient(unittest.TestCase):
    """DockerHub API client tests.

    These tests do not check the body of the response, only if the call
    was well formed and if a response was obtained. Due to this, take
    into account that the body returned on each request might not
    match with the parameters from the request.
    """
    @httpretty.activate
    def test_repository(self):
        """Test repository API call"""

        # Set up a mock HTTP server
        setup_http_server()

        # Call API
        client = DockerHubClient()
        response = client.repository('grimoirelab', 'perceval')

        req = httpretty.last_request()

        self.assertEqual(req.method, 'GET')
        self.assertRegex(req.path, '/v2/repositories/grimoirelab/perceval')
        self.assertDictEqual(req.querystring, {})


class TestDockerHubCommand(unittest.TestCase):
    """Tests for DockerHubCommand class"""

    def test_backend_class(self):
        """Test if the backend class is DockerHub"""

        self.assertIs(DockerHubCommand.BACKEND, DockerHub)

    def test_setup_cmd_parser(self):
        """Test if it parser object is correctly initialized"""

        parser = DockerHubCommand.setup_cmd_parser()
        self.assertIsInstance(parser, BackendCommandArgumentParser)
        self.assertEqual(parser._backend, DockerHub)

        args = ['grimoirelab', 'perceval', '--no-archive']

        parsed_args = parser.parse(*args)
        self.assertTrue(parsed_args.no_archive)
        self.assertTrue(parsed_args.ssl_verify)
        self.assertEqual(parsed_args.owner, 'grimoirelab')
        self.assertEqual(parsed_args.repository, 'perceval')

        args = ['grimoirelab', 'perceval', '--no-ssl-verify']

        parsed_args = parser.parse(*args)
        self.assertFalse(parsed_args.ssl_verify)
        self.assertEqual(parsed_args.owner, 'grimoirelab')
        self.assertEqual(parsed_args.repository, 'perceval')


if __name__ == "__main__":
    unittest.main(warnings='ignore')
