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

import sys
import unittest

import httpretty
import pkg_resources

# Hack to make sure that tests import the right packages
# due to setuptools behaviour
sys.path.insert(0, '..')
pkg_resources.declare_namespace('perceval.backends')

from perceval.backends.core.dockerhub import DockerHubClient


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
