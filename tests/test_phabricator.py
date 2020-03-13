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
#     Stephan Barth <stephan.barth@gmail.com>
#     Valerio Cosentino <valcos@bitergia.com>
#     Miguel Ángel Fernández <mafesan@bitergia.com>
#     Harshal Mittal <harshalmittal4@gmail.com>
#

import copy
import datetime
import httpretty
import json
import os
import pkg_resources
import requests
import unittest

pkg_resources.declare_namespace('perceval.backends')

from perceval.backend import BackendCommandArgumentParser
from perceval.utils import DEFAULT_DATETIME
from perceval.backends.core.phabricator import (DEFAULT_SLEEP_TIME,
                                                MAX_RETRIES,
                                                Phabricator,
                                                PhabricatorCommand,
                                                ConduitClient,
                                                ConduitError)
from base import TestCaseBackendArchive

PHABRICATOR_URL = 'http://example.com'
PHABRICATOR_API_URL = PHABRICATOR_URL + '/api'
PHABRICATOR_API_ERROR_URL = PHABRICATOR_API_URL + '/error'
PHABRICATOR_TASKS_URL = PHABRICATOR_API_URL + '/maniphest.search'
PHABRICATOR_TRANSACTIONS_URL = PHABRICATOR_API_URL + '/maniphest.gettasktransactions'
PHABRICATOR_PHIDS_URL = PHABRICATOR_API_URL + '/phid.query'
PHABRICATOR_USERS_URL = PHABRICATOR_API_URL + '/user.query'


def read_file(filename, mode='r'):
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), filename), mode) as f:
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
        self.assertIsNone(phab.client)
        self.assertTrue(phab.ssl_verify)

        # When tag is empty or None it will be set to
        # the value in url
        phab = Phabricator(PHABRICATOR_URL, 'AAAA')
        self.assertEqual(phab.url, PHABRICATOR_URL)
        self.assertEqual(phab.origin, PHABRICATOR_URL)
        self.assertEqual(phab.tag, PHABRICATOR_URL)

        phab = Phabricator(PHABRICATOR_URL, 'AAAA', tag='', ssl_verify=False)
        self.assertEqual(phab.url, PHABRICATOR_URL)
        self.assertEqual(phab.origin, PHABRICATOR_URL)
        self.assertEqual(phab.tag, PHABRICATOR_URL)
        self.assertEqual(phab.max_retries, MAX_RETRIES)
        self.assertEqual(phab.sleep_time, DEFAULT_SLEEP_TIME)
        self.assertFalse(phab.ssl_verify)

        phab = Phabricator(PHABRICATOR_URL, 'AAAA', None, None, 3, 25)
        self.assertEqual(phab.url, PHABRICATOR_URL)
        self.assertEqual(phab.origin, PHABRICATOR_URL)
        self.assertEqual(phab.tag, PHABRICATOR_URL)
        self.assertEqual(phab.max_retries, 3)
        self.assertEqual(phab.sleep_time, 25)

        phab = Phabricator(PHABRICATOR_URL, 'AAAA', tag='', max_retries=3, sleep_time=25)
        self.assertEqual(phab.url, PHABRICATOR_URL)
        self.assertEqual(phab.origin, PHABRICATOR_URL)
        self.assertEqual(phab.tag, PHABRICATOR_URL)
        self.assertEqual(phab.max_retries, 3)
        self.assertEqual(phab.sleep_time, 25)

    def test_has_archiving(self):
        """Test if it returns True when has_archiving is called"""

        self.assertEqual(Phabricator.has_archiving(), True)

    def test_has_resuming(self):
        """Test if it returns True when has_resuming is called"""

        self.assertEqual(Phabricator.has_resuming(), True)

    @httpretty.activate
    def test_fetch(self):
        """Test whether it fetches a set of tasks"""

        http_requests = setup_http_server()

        phab = Phabricator(PHABRICATOR_URL, 'AAAA')
        tasks = [task for task in phab.fetch(from_date=None)]

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

        # Check that subscribers data is included for core:subscribers type transactions
        trans = tasks[0]['data']['transactions'][6]
        self.assertEqual(trans['transactionType'], 'core:subscribers')
        self.assertEqual(trans['oldValue'], [])
        self.assertEqual(trans['oldValue'], trans['oldValue_data'])
        self.assertEqual(len(trans['newValue']), len(trans['newValue_data']))
        self.assertDictEqual(trans['newValue_data'][0], trans['authorData'])

        # Check that project data is included for core:edge type transactions
        trans = tasks[0]['data']['transactions'][7]
        self.assertEqual(trans['transactionType'], 'core:edge')
        self.assertEqual(trans['newValue_data'][0]['phid'],
                         trans['newValue'][trans['newValue_data'][0]['phid']]['dst'])

        # Check that policy data is include for core:edit-policy type transactions
        trans = tasks[0]['data']['transactions'][8]
        self.assertEqual(trans['transactionType'], 'core:edit-policy')
        self.assertIsNotNone(trans['newValue_data'])
        self.assertIsNone(trans['oldValue_data'])

        # Check that policy data is include for core:view-policy type transactions
        trans = tasks[0]['data']['transactions'][9]
        self.assertEqual(trans['transactionType'], 'core:view-policy')
        self.assertIsNotNone(trans['newValue_data'])
        self.assertIsNone(trans['oldValue_data'])

        # Check that project data is include for core:columns type transactions
        trans = tasks[3]['data']['transactions'][15]
        self.assertEqual(trans['transactionType'], 'core:columns')
        self.assertEqual(trans['newValue'][0]['boardPHID_data']['name'], 'Team: Devel')
        self.assertIsNone(trans['oldValue'])

        # Check that reassign data is include for reassign type transactions
        trans = tasks[0]['data']['transactions'][13]
        self.assertEqual(trans['transactionType'], 'reassign')
        self.assertDictEqual(trans['newValue_data'], trans['authorData'])
        self.assertIsNone(trans['oldValue_data'])

        # Check authors that weren't found on the server: jsmith
        trans = tasks[1]['data']['transactions']
        self.assertEqual(trans[3]['authorData'], None)

        trans = tasks[3]['data']['transactions']
        self.assertEqual(trans[0]['authorData']['userName'], 'jdoe')
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
            }
        ]

        self.assertEqual(len(http_requests), len(expected))

        for i in range(len(expected)):
            rparams = http_requests[i].parsed_body
            rparams['params'] = json.loads(rparams['params'][0])
            self.assertIn(rparams, expected)

    @httpretty.activate
    def test_search_fields(self):
        """Test whether the search_fields is properly set"""

        setup_http_server()

        phab = Phabricator(PHABRICATOR_URL, 'AAAA')
        tasks = [task for task in phab.fetch(from_date=None)]

        task = tasks[0]
        self.assertEqual(phab.metadata_id(task['data']), task['search_fields']['item_id'])

        task = tasks[1]
        self.assertEqual(phab.metadata_id(task['data']), task['search_fields']['item_id'])

        task = tasks[2]
        self.assertEqual(phab.metadata_id(task['data']), task['search_fields']['item_id'])

        task = tasks[3]
        self.assertEqual(phab.metadata_id(task['data']), task['search_fields']['item_id'])

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

        # Check subscribers transaction type
        trans = task['data']['transactions'][4]
        self.assertEqual(trans['newValue_data'][0]['userName'], 'jdoe')

        # Check reassign transaction type
        trans = task['data']['transactions'][11]
        self.assertEqual(trans['newValue_data']['userName'], 'jdoe')

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
                    'phids': ['PHID-USER-2uk52xorcqb6sjvp467y']
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
                    'phids': ['PHID-USER-pr5fcxy4xk5ofqsfqcfc']
                }
            },
            {
                '__conduit__': ['True'],
                'output': ['json'],
                'params': {
                    "__conduit__": {"token": "AAAA"},
                    "phids": ["PHID-PROJ-2qnt6thbrd7qnx5bitzy"]
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
        json_content = json.loads(raw_json)
        phids = Phabricator.parse_phids(json_content)
        results = [phid for phid in phids]
        results.sort(key=lambda x: x['fullName'])

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]['fullName'], 'Herald')
        self.assertEqual(results[1]['fullName'], 'Mock')


class TestPhabricatorBackendArchive(TestCaseBackendArchive):
    """Phabricator backend tests using an archive"""

    def setUp(self):
        super().setUp()
        self.backend_write_archive = Phabricator(PHABRICATOR_URL, 'AAAA', archive=self.archive)
        self.backend_read_archive = Phabricator(PHABRICATOR_URL, 'BBBB', archive=self.archive)

    @httpretty.activate
    def test_fetch_from_archive(self):
        """Test whether it fetches a set of tasks from archive"""

        setup_http_server()
        self._test_fetch_from_archive()

    @httpretty.activate
    def test_fetch_from_date_from_archive(self):
        """Test wether if fetches a set of tasks from the given date from archive"""

        setup_http_server()

        from_date = datetime.datetime(2016, 6, 29, 0, 0, 0)
        self._test_fetch_from_archive(from_date=from_date)

    @httpretty.activate
    def test_fetch_empty_from_archive(self):
        """Test if nothing is returned when there are no tasks in the archive"""

        setup_http_server()

        from_date = datetime.datetime(2017, 1, 1, 0, 0, 0)
        self._test_fetch_from_archive(from_date=from_date)


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
        self.assertEqual(client.max_retries, MAX_RETRIES)
        self.assertEqual(client.sleep_time, DEFAULT_SLEEP_TIME)
        self.assertTrue(client.ssl_verify)

        client = ConduitClient(PHABRICATOR_URL, 'aaaa', 2, 100, ssl_verify=False)
        self.assertEqual(client.base_url, PHABRICATOR_URL)
        self.assertEqual(client.api_token, 'aaaa')
        self.assertEqual(client.max_retries, 2)
        self.assertEqual(client.sleep_time, 100)
        self.assertFalse(client.ssl_verify)

        client = ConduitClient(PHABRICATOR_URL, 'aaaa', max_retries=2, sleep_time=100)
        self.assertEqual(client.base_url, PHABRICATOR_URL)
        self.assertEqual(client.api_token, 'aaaa')
        self.assertEqual(client.max_retries, 2)
        self.assertEqual(client.sleep_time, 100)

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
            PHABRICATOR_TASKS_URL: [(502, 'error'), (503, 'error'), (429, 'error'), (503, 'error'), (200, body)],
            PHABRICATOR_USERS_URL: [(503, 'error'), (503, 'error'), (503, 'error'),
                                    (503, 'error'), (503, 'error'), (503, 'error')],
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
        client = ConduitClient(PHABRICATOR_URL, 'aaaa', sleep_time=0.1)

        # After 5 tries (request + 4 retries) it gets the result
        reqs = []
        _ = [r for r in client.tasks()]
        self.assertEqual(len(reqs), 5)

        # After 6 tries (request + 5 retries) it fails
        reqs = []
        with self.assertRaises(requests.exceptions.RetryError):
            _ = client.users("PHID-USER-2uk52xorcqb6sjvp467y")
            self.assertEqual(len(reqs), 5)

        # After 1 try if fails
        reqs = []
        with self.assertRaises(requests.exceptions.HTTPError):
            _ = client.phids("PHID-APPS-PhabricatorHeraldApplication")
            self.assertEqual(len(reqs), 1)

    def test_sanitize_for_archive_no_token(self):
        """Test whether the sanitize method works properly when a token is not given"""

        url = "http://example.com"
        headers = "headers-information"
        payload = {'__conduit__': True,
                   'output': 'json',
                   'params': '{"phids": ["PHID-APPS-PhabricatorHeraldApplication"]}'}

        s_url, s_headers, s_payload = ConduitClient.sanitize_for_archive(url, headers, copy.deepcopy(payload))

        self.assertEqual(url, s_url)
        self.assertEqual(headers, s_headers)
        self.assertEqual(payload, s_payload)

    def test_sanitize_for_archive_token(self):
        """Test whether the sanitize method works properly when a token is given"""

        url = "http://example.com"
        headers = "headers-information"
        payload = {'__conduit__': True,
                   'output': 'json',
                   'params': '{"__conduit__": {"token": "aaaa"}, '
                             '"phids": ["PHID-APPS-PhabricatorHeraldApplication"]}'}

        s_url, s_headers, s_payload = ConduitClient.sanitize_for_archive(url, headers, copy.deepcopy(payload))
        params = json.loads(payload['params'])
        params.pop("__conduit__")
        payload['params'] = json.dumps(params, sort_keys=True)

        self.assertEqual(url, s_url)
        self.assertEqual(headers, s_headers)
        self.assertEqual(payload, s_payload)


class TestPhabricatorCommand(unittest.TestCase):
    """Tests for PhabricatorCommand class"""

    def test_backend_class(self):
        """Test if the backend class is Phabricator"""

        self.assertIs(PhabricatorCommand.BACKEND, Phabricator)

    def test_setup_cmd_parser(self):
        """Test if it parser object is correctly initialized"""

        parser = PhabricatorCommand.setup_cmd_parser()
        self.assertIsInstance(parser, BackendCommandArgumentParser)
        self.assertEqual(parser._backend, Phabricator)

        args = ['http://example.com',
                '--api-token', '12345678',
                '--tag', 'test',
                '--no-archive',
                '--from-date', '1970-01-01']

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.url, 'http://example.com')
        self.assertEqual(parsed_args.api_token, '12345678')
        self.assertEqual(parsed_args.tag, 'test')
        self.assertTrue(parsed_args.no_archive)
        self.assertTrue(parsed_args.ssl_verify)
        self.assertEqual(parsed_args.from_date, DEFAULT_DATETIME)
        self.assertEqual(parsed_args.max_retries, MAX_RETRIES)
        self.assertEqual(parsed_args.sleep_time, DEFAULT_SLEEP_TIME)

        args = ['http://example.com',
                '--api-token', '12345678',
                '--tag', 'test',
                '--no-archive',
                '--from-date', '1970-01-01',
                '--max-retries', '7',
                '--sleep-time', '43',
                '--no-ssl-verify']

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.url, 'http://example.com')
        self.assertEqual(parsed_args.api_token, '12345678')
        self.assertEqual(parsed_args.tag, 'test')
        self.assertEqual(parsed_args.no_archive, True)
        self.assertEqual(parsed_args.from_date, DEFAULT_DATETIME)
        self.assertEqual(parsed_args.max_retries, 7)
        self.assertEqual(parsed_args.sleep_time, 43)
        self.assertFalse(parsed_args.ssl_verify)


if __name__ == "__main__":
    unittest.main(warnings='ignore')
