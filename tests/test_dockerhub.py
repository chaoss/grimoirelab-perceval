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
import shutil
import sys
import tempfile
import unittest
import unittest.mock

import dateutil
import httpretty
import pkg_resources

from grimoirelab.toolkit.uris import urijoin

# Hack to make sure that tests import the right packages
# due to setuptools behaviour
sys.path.insert(0, '..')
pkg_resources.declare_namespace('perceval.backends')

from perceval.backend import BackendCommandArgumentParser
from perceval.cache import Cache
from perceval.errors import CacheError
from perceval.backends.core.dockerhub import (DockerHub,
                                              DockerHubClient,
                                              DockerHubCommand)


def read_file(filename, mode='r'):
    with open(filename, mode) as f:
        content = f.read()
    return content


DOCKERHUB_URL = "https://hub.docker.com/"
DOCKERHUB_API_URL = DOCKERHUB_URL + 'v2'
DOCKERHUB_RESPOSITORY_URL = DOCKERHUB_API_URL + '/repositories/grimoirelab/perceval'


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
        self.assertIsInstance(dockerhub.client, DockerHubClient)

        # When tag is empty or None it will be set to
        # the value in
        dockerhub = DockerHub('grimoirelab', 'perceval')
        self.assertEqual(dockerhub.origin, expected_origin)
        self.assertEqual(dockerhub.tag, expected_origin)

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

    def test_has_caching(self):
        """Test if it returns True when has_caching is called"""

        self.assertEqual(DockerHub.has_caching(), True)

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

    def test_parse_json(self):
        """Test if it parses a JSON stream"""

        raw_json = read_file('data/dockerhub/dockerhub_repository_1.json')

        item = DockerHub.parse_json(raw_json)
        self.assertEqual(item['user'], 'grimoirelab')
        self.assertEqual(item['name'], 'perceval')


class TestDockerHubBackendCache(unittest.TestCase):
    """DockerHub backend tests using a cache"""

    def setUp(self):
        self.tmp_path = tempfile.mkdtemp(prefix='perceval_')

    def tearDown(self):
        shutil.rmtree(self.tmp_path)

    @httpretty.activate
    @unittest.mock.patch('perceval.backends.core.dockerhub.datetime_utcnow')
    def test_fetch_from_cache(self, mock_utcnow):
        """Test whether the cache works"""

        setup_http_server()

        # First, we fetch the items from the server,
        # storing them in a cache. We do it twice as each call
        # to fetch only returns one item.
        cache = Cache(self.tmp_path)
        dockerhub = DockerHub('grimoirelab', 'perceval', cache=cache)

        mock_utcnow.return_value = datetime.datetime(2017, 1, 1,
                                                     tzinfo=dateutil.tz.tzutc())
        items = [item for item in dockerhub.fetch()]

        mock_utcnow.return_value = datetime.datetime(2017, 1, 2,
                                                     tzinfo=dateutil.tz.tzutc())
        aux = [item for item in dockerhub.fetch()]
        items.extend(aux)

        self.assertEqual(len(httpretty.httpretty.latest_requests), 2)

        # Now, we get the items from the cache.
        # The items should be the same and there won't be
        # any new request to the server
        cached_items = [item for item in dockerhub.fetch_from_cache()]
        self.assertEqual(len(cached_items), len(items))

        expected = [(1483228800.0, '0fa16dc4edab9130a14914a8d797f634d13b4ff4', 1483228800.0),
                    (1483315200.0, '0ce2bdf5ddeef42886d9ce4b573c98345e6f1b9a', 1483315200.0)]

        self.assertEqual(len(cached_items), len(expected))

        for x in range(len(cached_items)):
            item = cached_items[x]
            expc = expected[x]
            self.assertEqual(item['data']['fetched_on'], expc[0])
            self.assertEqual(item['uuid'], expc[1])
            self.assertEqual(item['origin'], 'https://hub.docker.com/grimoirelab/perceval')
            self.assertEqual(item['updated_on'], expc[2])
            self.assertEqual(item['category'], 'dockerhub-data')
            self.assertEqual(item['tag'], 'https://hub.docker.com/grimoirelab/perceval')

            # Compare chached and fetched task
            self.assertDictEqual(item['data'], items[x]['data'])

        # No more requests were sent
        self.assertEqual(len(httpretty.httpretty.latest_requests), 2)

    def test_fetch_from_empty_cache(self):
        """Test if there are not any event returned when the cache is empty"""

        cache = Cache(self.tmp_path)
        dockerhub = DockerHub('grimoirelab', 'perceval', cache=cache)
        cached_items = [item for item in dockerhub.fetch_from_cache()]
        self.assertEqual(len(cached_items), 0)

    def test_fetch_from_non_set_cache(self):
        """Test if a error is raised when the cache was not set"""

        dockerhub = DockerHub('grimoirelab', 'perceval')

        with self.assertRaises(CacheError):
            _ = [item for item in dockerhub.fetch_from_cache()]


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

        args = ['grimoirelab', 'perceval', '--no-cache']

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.owner, 'grimoirelab')
        self.assertEqual(parsed_args.repository, 'perceval')


if __name__ == "__main__":
    unittest.main(warnings='ignore')
