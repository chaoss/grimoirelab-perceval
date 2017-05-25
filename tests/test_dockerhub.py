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
import sys
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

from perceval.backends.core.dockerhub import DockerHub, DockerHubClient


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

    def test_has_caching(self):
        """Test if it returns False when has_caching is called"""

        self.assertEqual(DockerHub.has_caching(), False)

    def test_has_resuming(self):
        """Test if it returns True when has_resuming is called"""

        self.assertEqual(DockerHub.has_resuming(), True)

    @httpretty.activate
    @unittest.mock.patch('perceval.backends.core.dockerhub.datetime_utcnow')
    def test_fetch(self, mock_utcnow):
        """Test whether it fetches data from a repository"""

        mock_utcnow.return_value = datetime.datetime(2017, 1, 1,
                                                     tzinfo=dateutil.tz.tzutc())
        http_requests = setup_http_server()

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


if __name__ == "__main__":
    unittest.main(warnings='ignore')
