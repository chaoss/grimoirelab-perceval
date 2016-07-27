# -*- coding: utf-8 -*-
#
# Copyright (C) 2015-2016 Bitergia
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
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
#
# Authors:
#     Santiago Dueñas <sduenas@bitergia.com>
#

import datetime
import json
import sys
import unittest

import httpretty

if not '..' in sys.path:
    sys.path.insert(0, '..')

from perceval.backends.phabricator import (ConduitClient,
                                           ConduitError)

PHABRICATOR_URL = 'http://example.com'
PHABRICATOR_API_URL = PHABRICATOR_URL + '/api'
PHABRICATOR_API_ERROR_URL = PHABRICATOR_API_URL + '/error'
PHABRICATOR_TASKS_URL = PHABRICATOR_API_URL + '/maniphest.search'
PHABRICATOR_TRANSACTIONS_URL = PHABRICATOR_API_URL + '/maniphest.gettasktransactions'


def read_file(filename, mode='r'):
    with open(filename, mode) as f:
        content = f.read()
    return content


def setup_http_server():
    """Setup a mock HTTP server"""

    http_requests = []

    error_body = read_file('data/phabricator/phabricator_error.json', 'rb')
    tasks_body = read_file('data/phabricator/phabricator_tasks.json', 'rb')
    tasks_next_body = read_file('data/phabricator/phabricator_tasks_next.json', 'rb')
    tasks_trans_body = read_file('data/phabricator/phabricator_transactions.json', 'rb')
    tasks_trans_next_body = read_file('data/phabricator/phabricator_transactions_next.json', 'rb')

    def request_callback(method, uri, headers):
        last_request = httpretty.last_request()
        params = json.loads(last_request.parsed_body['params'][0])

        if uri == PHABRICATOR_TASKS_URL:
            if 'after' not in params:
                body = tasks_body
            else:
                body = tasks_next_body
        elif uri == PHABRICATOR_TRANSACTIONS_URL:
            if 69 in params['ids']:
                body = tasks_trans_body
            else:
                body = tasks_trans_next_body
        elif uri == PHABRICATOR_API_ERROR_URL:
            body = error_body
        else:
            raise

        http_requests.append(last_request)

        return (200, headers, body)

    httpretty.register_uri(httpretty.POST,
                           PHABRICATOR_TASKS_URL,
                           responses=[
                                httpretty.Response(body=request_callback)
                           ])
    httpretty.register_uri(httpretty.POST,
                           PHABRICATOR_TRANSACTIONS_URL,
                           responses=[
                                httpretty.Response(body=request_callback)
                           ])
    httpretty.register_uri(httpretty.POST,
                           PHABRICATOR_API_ERROR_URL,
                           responses=[
                                httpretty.Response(body=request_callback)
                           ])

    return http_requests


class TestConduitClient(unittest.TestCase):
    """Confluence client unit tests.

    These tests do not check the body of the response, only if the call
    was well formed and if a response was obtained.
    """
    def test_init(self):
        """Test initialization parameters"""

        client = ConduitClient(PHABRICATOR_URL, 'aaaa')
        self.assertEqual(client.base_url, PHABRICATOR_URL)
        self.assertEqual(client.api_token, 'aaaa')

    @httpretty.activate
    def test_tasks(self):
        """Test if a set of tasks is returned"""

        http_requests = setup_http_server()

        client = ConduitClient(PHABRICATOR_URL, 'aaaa')
        dt = datetime.datetime(2016, 5, 3, 0, 0, 0)

        result = client.tasks(from_date=dt)
        result = [r for r in result]

        self.assertEqual(len(result), 2)

        expected = [{
                     '__conduit__' : ['True'],
                     'output' : ['json'],
                     'params' : {
                                  '__conduit__' : {'token': 'aaaa'},
                                  'constraints' : {'modifiedStart' : 1462233600},
                                  'order' : 'outdated'
                                }
                    },
                    {
                     '__conduit__' : ['True'],
                     'output' : ['json'],
                     'params' : {
                                  '__conduit__' : {'token': 'aaaa'},
                                  'after' : '335',
                                  'constraints' : {'modifiedStart' : 1462233600},
                                  'order' : 'outdated'
                                }
                    }]

        self.assertEqual(len(http_requests), len(expected))

        for i in range(len(expected)):
            rparams = http_requests[i].parsed_body
            rparams['params'] = json.loads(rparams['params'][0])
            self.assertDictEqual(rparams, expected[i])

    @httpretty.activate
    def test_transactions(self):
        """Test if a set of transactions is returned"""

        http_requests = setup_http_server()

        client = ConduitClient(PHABRICATOR_URL, 'aaaa')
        _ = client.transactions(69, 73, 78)

        expected = [{
                     '__conduit__' : ['True'],
                     'output' : ['json'],
                     'params' : {
                                 '__conduit__' : {'token': 'aaaa'},
                                 'ids' : [69, 73, 78]
                                }
                   }]

        self.assertEqual(len(http_requests), len(expected))

        for i in range(len(expected)):
            rparams = http_requests[i].parsed_body
            rparams['params'] = json.loads(rparams['params'][0])
            self.assertDictEqual(rparams, expected[i])

    @httpretty.activate
    def test_phabricator_error(self):
        """Test if an exception is raised when an error is returned by the server"""

        setup_http_server()

        client = ConduitClient(PHABRICATOR_URL, 'aaaa')

        with self.assertRaises(ConduitError):
            _ = client._call('error', {})


if __name__ == "__main__":
    unittest.main(warnings='ignore')
