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
import json
import shutil
import sys
import tempfile
import unittest

import httpretty
import pkg_resources
import requests

# Hack to make sure that tests import the right packages
# due to setuptools behaviour
sys.path.insert(0, '..')
pkg_resources.declare_namespace('perceval.backends')

from perceval.backend import BackendCommandArgumentParser
from perceval.cache import Cache
from perceval.errors import CacheError
from perceval.utils import DEFAULT_DATETIME
from perceval.backends.core.phabricator import (Phabricator,
                                                PhabricatorCommand,
                                                ConduitClient,
                                                ConduitError)

PHABRICATOR_URL = 'http://example.com'
PHABRICATOR_API_URL = PHABRICATOR_URL + '/api'
PHABRICATOR_API_ERROR_URL = PHABRICATOR_API_URL + '/error'
PHABRICATOR_TASKS_URL = PHABRICATOR_API_URL + '/maniphest.search'
PHABRICATOR_TRANSACTIONS_URL = PHABRICATOR_API_URL + '/maniphest.gettasktransactions'
PHABRICATOR_PHIDS_URL = PHABRICATOR_API_URL + '/phid.query'
PHABRICATOR_USERS_URL = PHABRICATOR_API_URL + '/user.query'


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
    tasks_empty_body = read_file('data/phabricator/phabricator_tasks_empty.json')
    tasks_trans_body = read_file('data/phabricator/phabricator_transactions.json', 'rb')
    tasks_trans_next_body = read_file('data/phabricator/phabricator_transactions_next.json', 'rb')
    users_body = read_file('data/phabricator/phabricator_users.json', 'rb')
    jane_body = read_file('data/phabricator/phabricator_user_jane.json', 'rb')
    janes_body = read_file('data/phabricator/phabricator_user_janesmith.json', 'rb')
    jdoe_body = read_file('data/phabricator/phabricator_user_jdoe.json', 'rb')
    jrae_body = read_file('data/phabricator/phabricator_user_jrae.json', 'rb')
    jsmith_body = read_file('data/phabricator/phabricator_user_jsmith.json', 'rb')
    phids_body = read_file('data/phabricator/phabricator_phids.json', 'rb')
    herald_body = read_file('data/phabricator/phabricator_phid_herald.json', 'rb')
    bugreport_body = read_file('data/phabricator/phabricator_project_bugreport.json', 'rb')
    teamdevel_body = read_file('data/phabricator/phabricator_project_devel.json', 'rb')

    phids_users = {
        'PHID-USER-ojtcpympsmwenszuef7p': jane_body,
        'PHID-USER-mjr7pnwpg6slsnjcqki7': janes_body,
        'PHID-USER-2uk52xorcqb6sjvp467y': jdoe_body,
        'PHID-USER-pr5fcxy4xk5ofqsfqcfc': jrae_body,
        'PHID-USER-bjxhrstz5fb5gkrojmev': jsmith_body
    }

    phids = {
        'PHID-APPS-PhabricatorHeraldApplication': herald_body,
        'PHID-PROJ-2qnt6thbrd7qnx5bitzy': bugreport_body,
        'PHID-PROJ-zi2ndtoy3fh5pnbqzfdo': teamdevel_body
    }

    def request_callback(method, uri, headers):
        last_request = httpretty.last_request()
        params = json.loads(last_request.parsed_body['params'][0])

        if uri == PHABRICATOR_TASKS_URL:
            if params['constraints']['modifiedStart'] == 1467158400:
                body = tasks_next_body
            elif params['constraints']['modifiedStart'] == 1483228800:
                body = tasks_empty_body
            elif 'after' not in params:
                body = tasks_body
            else:
                body = tasks_next_body
        elif uri == PHABRICATOR_TRANSACTIONS_URL:
            if 69 in params['ids']:
                body = tasks_trans_body
            else:
                body = tasks_trans_next_body
        elif uri == PHABRICATOR_USERS_URL:
            if len(params['phids']) == 4:
                body = users_body
            else:
                body = phids_users[params['phids'][0]]
        elif uri == PHABRICATOR_PHIDS_URL:
            if len(params['phids']) == 2:
                body = phids_body
            else:
                body = phids[params['phids'][0]]
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
                           PHABRICATOR_USERS_URL,
                           responses=[
                               httpretty.Response(body=request_callback)
                           ])
    httpretty.register_uri(httpretty.POST,
                           PHABRICATOR_PHIDS_URL,
                           responses=[
                               httpretty.Response(body=request_callback)
                           ])
    httpretty.register_uri(httpretty.POST,
                           PHABRICATOR_API_ERROR_URL,
                           responses=[
                               httpretty.Response(body=request_callback)
                           ])

    return http_requests


class TestPhabricatorBackend(unittest.TestCase):
    """Phabricator backend unit tests"""

    def test_initialization(self):
        """Test whether attributes are initializated"""

        phab = Phabricator(PHABRICATOR_URL, 'AAAA', tag='test')

        self.assertEqual(phab.url, PHABRICATOR_URL)
        self.assertEqual(phab.origin, PHABRICATOR_URL)
        self.assertEqual(phab.tag, 'test')
        self.assertIsInstance(phab.client, ConduitClient)

        # When tag is empty or None it will be set to
        # the value in url
        phab = Phabricator(PHABRICATOR_URL, 'AAAA')
        self.assertEqual(phab.url, PHABRICATOR_URL)
        self.assertEqual(phab.origin, PHABRICATOR_URL)
        self.assertEqual(phab.tag, PHABRICATOR_URL)

        phab = Phabricator(PHABRICATOR_URL, 'AAAA', tag='')
        self.assertEqual(phab.url, PHABRICATOR_URL)
        self.assertEqual(phab.origin, PHABRICATOR_URL)
        self.assertEqual(phab.tag, PHABRICATOR_URL)

    def test_has_caching(self):
        """Test if it returns True when has_caching is called"""

        self.assertEqual(Phabricator.has_caching(), True)

    def test_has_resuming(self):
        """Test if it returns True when has_resuming is called"""

        self.assertEqual(Phabricator.has_resuming(), True)

    @httpretty.activate
    def test_fetch(self):
        """Test whether it fetches a set of tasks"""

        http_requests = setup_http_server()

        phab = Phabricator(PHABRICATOR_URL, 'AAAA')
        tasks = [task for task in phab.fetch()]

        expected = [(69, 16, 'jdoe', 'jdoe', '1b4c15d26068efcae83cd920bcada6003d2c4a6c', 1462306027.0),
                    (73, 20, 'jdoe', 'janesmith', '5487fc704f2d3c4e83ab0cd065512a181c1726cc', 1462464642.0),
                    (78, 17, 'jdoe', None, 'fa971157c4d0155652f94b673866abd83b929b27', 1462792338.0),
                    (296, 18, 'jane', 'jrae', 'e8fa3e4a4381d6fea3bcf5c848f599b87e7dc4a6', 1467196707.0)]

        self.assertEqual(len(tasks), len(expected))

        for x in range(len(tasks)):
            task = tasks[x]
            expc = expected[x]
            self.assertEqual(task['data']['id'], expc[0])
            self.assertEqual(len(task['data']['transactions']), expc[1])
            self.assertEqual(task['data']['fields']['authorData']['userName'], expc[2])

            # Check owner data; when it is null owner is not included
            if not expc[3]:
                self.assertNotIn('ownerData', task['data']['fields'])
            else:
                self.assertEqual(task['data']['fields']['ownerData']['userName'], expc[3])

            self.assertEqual(task['uuid'], expc[4])
            self.assertEqual(task['origin'], PHABRICATOR_URL)
            self.assertEqual(task['updated_on'], expc[5])
            self.assertEqual(task['category'], 'task')
            self.assertEqual(task['tag'], PHABRICATOR_URL)

        # Check some authors info on transactions
        trans = tasks[0]['data']['transactions']
        self.assertEqual(trans[0]['authorData']['userName'], 'jdoe')
        self.assertEqual(trans[15]['authorData']['userName'], 'jdoe')

        # Check authors that weren't found on the server: jsmith
        trans = tasks[1]['data']['transactions']
        self.assertEqual(trans[3]['authorData'], None)

        trans = tasks[3]['data']['transactions']
        self.assertEqual(trans[0]['authorData']['userName'], 'jrae')
        self.assertEqual(trans[15]['authorData']['userName'], 'jane')
        self.assertEqual(trans[16]['authorData']['name'], 'Herald')

        # Check some info about projects
        prjs = tasks[0]['data']['projects']
        self.assertEqual(len(prjs), 0)

        prjs = tasks[3]['data']['projects']
        self.assertEqual(len(prjs), 2)
        self.assertEqual(prjs[0]['phid'], 'PHID-PROJ-zi2ndtoy3fh5pnbqzfdo')
        self.assertEqual(prjs[0]['name'], 'Team: Devel')
        self.assertEqual(prjs[1]['phid'], 'PHID-PROJ-2qnt6thbrd7qnx5bitzy')
        self.assertEqual(prjs[1]['name'], 'Bug report')

        # Check requests
        expected = [
            {
                '__conduit__': ['True'],
                'output': ['json'],
                'params': {
                    '__conduit__': {'token': 'AAAA'},
                    'attachments': {'projects': True},
                    'constraints': {'modifiedStart': 1},
                    'order': 'outdated'
                }
            },
            {
                '__conduit__': ['True'],
                'output': ['json'],
                'params': {
                    '__conduit__': {'token': 'AAAA'},
                    'ids': [69, 73, 78]
                }
            },
            {
                '__conduit__': ['True'],
                'output': ['json'],
                'params': {
                    '__conduit__': {'token': 'AAAA'},
                    'phids': ['PHID-USER-2uk52xorcqb6sjvp467y']
                }
            },
            {
                '__conduit__': ['True'],
                'output': ['json'],
                'params': {
                    '__conduit__': {'token': 'AAAA'},
                    'phids': ['PHID-USER-bjxhrstz5fb5gkrojmev']
                }
            },
            {
                '__conduit__': ['True'],
                'output': ['json'],
                'params': {
                    '__conduit__': {'token': 'AAAA'},
                    'phids': ['PHID-USER-mjr7pnwpg6slsnjcqki7']
                }
            },
            {
                '__conduit__': ['True'],
                'output': ['json'],
                'params': {
                    '__conduit__': {'token': 'AAAA'},
                    'after': '335',
                    'attachments': {'projects': True},
                    'constraints': {'modifiedStart': 1},
                    'order': 'outdated'
                }
            },
            {
                '__conduit__': ['True'],
                'output': ['json'],
                'params': {
                    '__conduit__': {'token': 'AAAA'},
                    'ids': [296]
                }
            },
            {
                '__conduit__': ['True'],
                'output': ['json'],
                'params': {
                    '__conduit__': {'token': 'AAAA'},
                    'phids': ['PHID-USER-pr5fcxy4xk5ofqsfqcfc']
                }
            },
            {
                '__conduit__': ['True'],
                'output': ['json'],
                'params': {
                    '__conduit__': {'token': 'AAAA'},
                    'phids': ['PHID-USER-ojtcpympsmwenszuef7p']
                }
            },
            {
                '__conduit__': ['True'],
                'output': ['json'],
                'params': {
                    '__conduit__': {'token': 'AAAA'},
                    'phids': ['PHID-APPS-PhabricatorHeraldApplication']
                }
            },
            {
                '__conduit__': ['True'],
                'output': ['json'],
                'params': {
                    '__conduit__': {'token': 'AAAA'},
                    'phids': ['PHID-PROJ-zi2ndtoy3fh5pnbqzfdo']
                }
            },
            {
                '__conduit__': ['True'],
                'output': ['json'],
                'params': {
                    '__conduit__': {'token': 'AAAA'},
                    'phids': ['PHID-PROJ-2qnt6thbrd7qnx5bitzy']
                }
            }
        ]

        self.assertEqual(len(http_requests), len(expected))

        for i in range(len(expected)):
            rparams = http_requests[i].parsed_body
            rparams['params'] = json.loads(rparams['params'][0])
            self.assertDictEqual(rparams, expected[i])

    @httpretty.activate
    def test_fetch_from_date(self):
        """Test wether if fetches a set of tasks from the given date"""

        http_requests = setup_http_server()

        from_date = datetime.datetime(2016, 6, 29, 0, 0, 0)

        phab = Phabricator(PHABRICATOR_URL, 'AAAA')
        tasks = [task for task in phab.fetch(from_date=from_date)]

        self.assertEqual(len(tasks), 1)

        task = tasks[0]
        self.assertEqual(task['data']['id'], 296)
        self.assertEqual(task['data']['fields']['authorData']['userName'], 'jane')
        self.assertEqual(task['data']['fields']['ownerData']['userName'], 'jrae')
        self.assertEqual(len(task['data']['transactions']), 18)
        self.assertEqual(task['uuid'], 'e8fa3e4a4381d6fea3bcf5c848f599b87e7dc4a6')
        self.assertEqual(task['origin'], PHABRICATOR_URL)
        self.assertEqual(task['updated_on'], 1467196707.0)
        self.assertEqual(task['category'], 'task')
        self.assertEqual(task['tag'], PHABRICATOR_URL)

        # Check requests
        expected = [
            {
                '__conduit__': ['True'],
                'output': ['json'],
                'params': {
                    '__conduit__': {'token': 'AAAA'},
                    'attachments': {'projects': True},
                    'constraints': {'modifiedStart': 1467158400},
                    'order': 'outdated'
                }
            },
            {
                '__conduit__': ['True'],
                'output': ['json'],
                'params': {
                    '__conduit__': {'token': 'AAAA'},
                    'ids': [296]
                }
            },
            {
                '__conduit__': ['True'],
                'output': ['json'],
                'params': {
                    '__conduit__': {'token': 'AAAA'},
                    'phids': ['PHID-USER-pr5fcxy4xk5ofqsfqcfc']
                }
            },
            {
                '__conduit__': ['True'],
                'output': ['json'],
                'params': {
                    '__conduit__': {'token': 'AAAA'},
                    'phids': ['PHID-USER-ojtcpympsmwenszuef7p']
                }
            },
            {
                '__conduit__': ['True'],
                'output': ['json'],
                'params': {
                    '__conduit__': {'token': 'AAAA'},
                    'phids': ['PHID-APPS-PhabricatorHeraldApplication']
                }
            },
            {
                '__conduit__': ['True'],
                'output': ['json'],
                'params': {
                    '__conduit__': {'token': 'AAAA'},
                    'phids': ['PHID-PROJ-zi2ndtoy3fh5pnbqzfdo']
                }
            },
            {
                '__conduit__': ['True'],
                'output': ['json'],
                'params': {
                    '__conduit__': {'token': 'AAAA'},
                    'phids': ['PHID-PROJ-2qnt6thbrd7qnx5bitzy']
                }
            }
        ]

        self.assertEqual(len(http_requests), len(expected))

        for i in range(len(expected)):
            rparams = http_requests[i].parsed_body
            rparams['params'] = json.loads(rparams['params'][0])
            self.assertDictEqual(rparams, expected[i])

    @httpretty.activate
    def test_fetch_empty(self):
        """Test if nothing is returnerd when there are no tasks"""

        http_requests = setup_http_server()

        from_date = datetime.datetime(2017, 1, 1, 0, 0, 0)

        phab = Phabricator(PHABRICATOR_URL, 'AAAA')
        tasks = [task for task in phab.fetch(from_date=from_date)]

        self.assertEqual(len(tasks), 0)

        # Check requests
        expected = {
            '__conduit__': ['True'],
            'output': ['json'],
            'params': {
                '__conduit__': {'token': 'AAAA'},
                'attachments': {'projects': True},
                'constraints': {'modifiedStart': 1483228800},
                'order': 'outdated'
            }
        }

        self.assertEqual(len(http_requests), 1)

        rparams = http_requests[0].parsed_body
        rparams['params'] = json.loads(rparams['params'][0])
        self.assertDictEqual(rparams, expected)

    def test_parse_tasks(self):
        """Test if it parses a tasks stream"""

        raw_json = read_file('data/phabricator/phabricator_tasks.json')

        tasks = Phabricator.parse_tasks(raw_json)
        results = [task for task in tasks]

        self.assertEqual(len(results), 3)
        self.assertEqual(results[0]['id'], 69)
        self.assertEqual(results[1]['id'], 73)
        self.assertEqual(results[2]['id'], 78)

        # Parse a file without results
        raw_json = read_file('data/phabricator/phabricator_tasks_empty.json')

        tasks = Phabricator.parse_tasks(raw_json)
        results = [task for task in tasks]

        self.assertEqual(len(results), 0)

    def test_parse_tasks_transactions(self):
        """Test if it parses a tasks transactions stream"""

        raw_json = read_file('data/phabricator/phabricator_transactions.json')

        results = Phabricator.parse_tasks_transactions(raw_json)

        self.assertEqual(len(results), 3)
        self.assertEqual(len(results['69']), 16)
        self.assertEqual(len(results['73']), 20)
        self.assertEqual(len(results['78']), 17)

    def test_parse_users(self):
        """Test if it parses a users stream"""

        raw_json = read_file('data/phabricator/phabricator_users.json')

        users = Phabricator.parse_users(raw_json)
        results = [user for user in users]

        self.assertEqual(len(results), 4)
        self.assertEqual(results[0]['userName'], 'jrae')
        self.assertEqual(results[1]['userName'], 'jsmith')
        self.assertEqual(results[2]['userName'], 'jdoe')
        self.assertEqual(results[3]['userName'], 'jane')

    def test_parse_phids(self):
        """Test if it parses a phids stream"""

        raw_json = read_file('data/phabricator/phabricator_phids.json')

        phids = Phabricator.parse_phids(raw_json)
        results = [phid for phid in phids]
        results.sort(key=lambda x: x['fullName'])

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]['fullName'], 'Herald')
        self.assertEqual(results[1]['fullName'], 'Mock')


class TestPhabricatorBackendCache(unittest.TestCase):
    """Phabricator backend tests using a cache"""

    def setUp(self):
        self.tmp_path = tempfile.mkdtemp(prefix='perceval_')

    def tearDown(self):
        shutil.rmtree(self.tmp_path)

    @httpretty.activate
    def test_fetch_from_cache(self):
        """Test whether the cache works"""

        http_requests = setup_http_server()

        # First, we fetch the tasks from the server,
        # storing them in a cache
        cache = Cache(self.tmp_path)
        phab = Phabricator(PHABRICATOR_URL, 'AAAA', cache=cache)

        tasks = [task for task in phab.fetch()]
        self.assertEqual(len(http_requests), 12)

        # Now, we get the tasks from the cache.
        # The tasks should be the same and there won't be
        # any new request to the server
        cached_tasks = [task for task in phab.fetch_from_cache()]
        self.assertEqual(len(cached_tasks), len(tasks))

        expected = [(69, 16, 0, 'jdoe', 'jdoe', '1b4c15d26068efcae83cd920bcada6003d2c4a6c', 1462306027.0),
                    (73, 20, 0, 'jdoe', 'janesmith', '5487fc704f2d3c4e83ab0cd065512a181c1726cc', 1462464642.0),
                    (78, 17, 0, 'jdoe', None, 'fa971157c4d0155652f94b673866abd83b929b27', 1462792338.0),
                    (296, 18, 2, 'jane', 'jrae', 'e8fa3e4a4381d6fea3bcf5c848f599b87e7dc4a6', 1467196707.0)]

        self.assertEqual(len(cached_tasks), len(expected))

        for x in range(len(cached_tasks)):
            task = cached_tasks[x]
            expc = expected[x]
            self.assertEqual(task['data']['id'], expc[0])
            self.assertEqual(len(task['data']['transactions']), expc[1])
            self.assertEqual(len(task['data']['projects']), expc[2])
            self.assertEqual(task['data']['fields']['authorData']['userName'], expc[3])

            # Check owner data; when it is null owner is not included
            if not expc[4]:
                self.assertNotIn('ownerData', task['data']['fields'])
            else:
                self.assertEqual(task['data']['fields']['ownerData']['userName'], expc[4])

            self.assertEqual(task['uuid'], expc[5])
            self.assertEqual(task['origin'], PHABRICATOR_URL)
            self.assertEqual(task['updated_on'], expc[6])
            self.assertEqual(task['category'], 'task')
            self.assertEqual(task['tag'], PHABRICATOR_URL)

            # Compare chached and fetched task
            self.assertDictEqual(task['data'], tasks[x]['data'])

        # No more requests were sent
        self.assertEqual(len(http_requests), 12)

    def test_fetch_from_empty_cache(self):
        """Test if there are not any task returned when the cache is empty"""

        cache = Cache(self.tmp_path)
        phab = Phabricator(PHABRICATOR_URL, 'AAAA', cache=cache)
        cached_tasks = [task for task in phab.fetch_from_cache()]
        self.assertEqual(len(cached_tasks), 0)

    def test_fetch_from_non_set_cache(self):
        """Test if a error is raised when the cache was not set"""

        phab = Phabricator(PHABRICATOR_URL, 'AAAA')

        with self.assertRaises(CacheError):
            _ = [task for task in phab.fetch_from_cache()]


class TestPhabricatorCommand(unittest.TestCase):
    """Tests for PhabricatorCommand class"""

    def test_backend_class(self):
        """Test if the backend class is Phabricator"""

        self.assertIs(PhabricatorCommand.BACKEND, Phabricator)

    def test_setup_cmd_parser(self):
        """Test if it parser object is correctly initialized"""

        parser = PhabricatorCommand.setup_cmd_parser()
        self.assertIsInstance(parser, BackendCommandArgumentParser)

        args = ['http://example.com',
                '--api-token', '12345678',
                '--tag', 'test',
                '--no-cache',
                '--from-date', '1970-01-01']

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.url, 'http://example.com')
        self.assertEqual(parsed_args.api_token, '12345678')
        self.assertEqual(parsed_args.tag, 'test')
        self.assertEqual(parsed_args.no_cache, True)
        self.assertEqual(parsed_args.from_date, DEFAULT_DATETIME)


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

        expected = [
            {
                '__conduit__': ['True'],
                'output': ['json'],
                'params': {
                    '__conduit__': {'token': 'aaaa'},
                    'attachments': {'projects': True},
                    'constraints': {'modifiedStart': 1462233600},
                    'order': 'outdated'
                }
            },
            {
                '__conduit__': ['True'],
                'output': ['json'],
                'params': {
                    '__conduit__': {'token': 'aaaa'},
                    'after': '335',
                    'attachments': {'projects': True},
                    'constraints': {'modifiedStart': 1462233600},
                    'order': 'outdated'
                }
            }
        ]

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

        expected = [
            {
                '__conduit__': ['True'],
                'output': ['json'],
                'params': {
                    '__conduit__': {'token': 'aaaa'},
                    'ids': [69, 73, 78]
                }
            }
        ]

        self.assertEqual(len(http_requests), len(expected))

        for i in range(len(expected)):
            rparams = http_requests[i].parsed_body
            rparams['params'] = json.loads(rparams['params'][0])
            self.assertDictEqual(rparams, expected[i])

    @httpretty.activate
    def test_users(self):
        """Test if a set of users is returned"""

        http_requests = setup_http_server()

        client = ConduitClient(PHABRICATOR_URL, 'aaaa')
        _ = client.users("PHID-USER-2uk52xorcqb6sjvp467y",
                         "PHID-USER-bjxhrstz5fb5gkrojmev",
                         "PHID-USER-pr5fcxy4xk5ofqsfqcfc",
                         "PHID-USER-ojtcpympsmwenszuef7p")
        expected = [
            {
                '__conduit__': ['True'],
                'output': ['json'],
                'params': {
                    '__conduit__': {'token': 'aaaa'},
                    'phids': [
                        "PHID-USER-2uk52xorcqb6sjvp467y",
                        "PHID-USER-bjxhrstz5fb5gkrojmev",
                        "PHID-USER-pr5fcxy4xk5ofqsfqcfc",
                        "PHID-USER-ojtcpympsmwenszuef7p"
                    ]
                }
            }
        ]

        self.assertEqual(len(http_requests), len(expected))

        for i in range(len(expected)):
            rparams = http_requests[i].parsed_body
            rparams['params'] = json.loads(rparams['params'][0])
            self.assertDictEqual(rparams, expected[i])

    @httpretty.activate
    def test_phids(self):
        """Test if a set of PHIDs is returned"""

        http_requests = setup_http_server()

        client = ConduitClient(PHABRICATOR_URL, 'aaaa')
        _ = client.phids("PHID-APPS-PhabricatorHeraldApplication",
                         "PHID-APPS-PhabricatorMockApplication")
        expected = [
            {
                '__conduit__': ['True'],
                'output': ['json'],
                'params': {
                    '__conduit__': {'token': 'aaaa'},
                    'phids': [
                        "PHID-APPS-PhabricatorHeraldApplication",
                        "PHID-APPS-PhabricatorMockApplication"
                    ]
                }
            }
        ]

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

    @httpretty.activate
    def test_retry_on_server_errors(self):
        """Test if the client retries when some HTTP errors are found"""

        reqs = []
        body = read_file('data/phabricator/phabricator_tasks_empty.json', 'rb')

        responses = {
            PHABRICATOR_TASKS_URL: [(502, 'error'), (503, 'error'), (200, body)],
            PHABRICATOR_USERS_URL: [(503, 'error'), (503, 'error'), (503, 'error'), (503, 'error')],
            PHABRICATOR_PHIDS_URL: [(404, 'not found')]
        }

        def request_callback(method, uri, headers):
            reqs.append(httpretty.last_request())
            resp = responses[uri].pop(0)
            return (resp[0], headers, resp[1])

        httpretty.register_uri(httpretty.POST,
                               PHABRICATOR_TASKS_URL,
                               responses=[
                                   httpretty.Response(body=request_callback)
                                   for _ in range(3)
                               ])
        httpretty.register_uri(httpretty.POST,
                               PHABRICATOR_USERS_URL,
                               responses=[
                                   httpretty.Response(body=request_callback)
                                   for _ in range(4)
                               ])
        httpretty.register_uri(httpretty.POST,
                               PHABRICATOR_PHIDS_URL,
                               responses=[
                                   httpretty.Response(body=request_callback)
                                   for _ in range(1)
                               ])

        # These tests are based on the maximum number of retries,
        # set by default to 3. The client only retries 502 and 503
        # HTTP errors.
        client = ConduitClient(PHABRICATOR_URL, 'aaaa')

        # After 3 tries (request + 2 retries) it gets the result
        reqs = []
        _ = [r for r in client.tasks()]
        self.assertEqual(len(reqs), 3)

        # After 4 tries (request + 3 retries) it fails
        reqs = []
        with self.assertRaises(requests.exceptions.HTTPError):
            _ = client.users("PHID-USER-2uk52xorcqb6sjvp467y")
            self.assertEqual(len(reqs), 4)

        # After 1 trie if fails
        reqs = []
        with self.assertRaises(requests.exceptions.HTTPError):
            _ = client.phids("PHID-APPS-PhabricatorHeraldApplication")
            self.assertEqual(len(reqs), 1)


if __name__ == "__main__":
    unittest.main(warnings='ignore')
