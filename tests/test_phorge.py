#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (C) Grimoirelab developers
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

import copy
import datetime
import httpretty
import json
import os
import requests
import unittest

from perceval.backend import BackendCommandArgumentParser
from perceval.utils import DEFAULT_DATETIME
from perceval.backends.core.phorge import (DEFAULT_SLEEP_TIME,
                                           MAX_RETRIES,
                                           Phorge,
                                           PhorgeCommand,
                                           ConduitClient,
                                           ConduitError)
from base import TestCaseBackendArchive


PHORGE_URL = 'http://example.com'
PHORGE_API_URL = PHORGE_URL + '/api'
PHORGE_API_ERROR_URL = PHORGE_API_URL + '/error'
PHORGE_TASKS_URL = PHORGE_API_URL + '/maniphest.search'
PHORGE_TRANSACTIONS_URL = PHORGE_API_URL + '/transaction.search'
PHORGE_PHIDS_URL = PHORGE_API_URL + '/phid.query'
PHORGE_USERS_URL = PHORGE_API_URL + '/user.search'


def read_file(filename, mode='r'):
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), filename), mode) as f:
        content = f.read()
    return content


def setup_http_server():
    """Setup a mock HTTP server"""

    http_requests = []

    error_body = read_file('data/phorge/phorge_error.json', 'rb')
    tasks_body = read_file('data/phorge/phorge_tasks.json', 'rb')
    tasks_next_body = read_file('data/phorge/phorge_tasks_next.json', 'rb')
    tasks_empty_body = read_file('data/phorge/phorge_tasks_empty.json')
    tasks_trans_t69_body = read_file('data/phorge/phorge_T69_transactions.json', 'rb')
    tasks_trans_t73_body = read_file('data/phorge/phorge_T73_transactions.json', 'rb')
    tasks_trans_t78_body = read_file('data/phorge/phorge_T78_transactions.json', 'rb')
    tasks_trans_t296_body = read_file('data/phorge/phorge_T296_transactions.json', 'rb')
    users_body = read_file('data/phorge/phorge_users.json', 'rb')
    jane_body = read_file('data/phorge/phorge_user_jane.json', 'rb')
    janes_body = read_file('data/phorge/phorge_user_janesmith.json', 'rb')
    jdoe_body = read_file('data/phorge/phorge_user_jdoe.json', 'rb')
    jrae_body = read_file('data/phorge/phorge_user_jrae.json', 'rb')
    jsmith_body = read_file('data/phorge/phorge_user_jsmith.json', 'rb')
    phids_body = read_file('data/phorge/phorge_phids.json', 'rb')
    herald_body = read_file('data/phorge/phorge_phid_herald.json', 'rb')
    bugreport_body = read_file('data/phorge/phorge_project_bugreport.json', 'rb')
    teamdevel_body = read_file('data/phorge/phorge_project_devel.json', 'rb')

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

        if uri == PHORGE_TASKS_URL:
            if params['constraints']['modifiedStart'] == 1467158400:
                body = tasks_next_body
            elif params['constraints']['modifiedStart'] == 1483228800:
                body = tasks_empty_body
            elif 'after' not in params:
                body = tasks_body
            else:
                body = tasks_next_body
        elif uri == PHORGE_TRANSACTIONS_URL:
            object_id = params['objectIdentifier']
            if object_id == 'T69':
                body = tasks_trans_t69_body
            elif object_id == 'T73':
                body = tasks_trans_t73_body
            elif object_id == 'T78':
                body = tasks_trans_t78_body
            elif object_id == 'T296':
                body = tasks_trans_t296_body
            else:
                raise
        elif uri == PHORGE_USERS_URL:
            if len(params['constraints']['phids']) == 4:
                body = users_body
            else:
                body = phids_users[params['constraints']['phids'][0]]
        elif uri == PHORGE_PHIDS_URL:
            if len(params['phids']) == 2:
                body = phids_body
            else:
                body = phids[params['phids'][0]]
        elif uri == PHORGE_API_ERROR_URL:
            body = error_body
        else:
            raise

        http_requests.append(last_request)

        return (200, headers, body)

    httpretty.register_uri(httpretty.POST,
                           PHORGE_TASKS_URL,
                           responses=[
                               httpretty.Response(body=request_callback)
                           ])
    httpretty.register_uri(httpretty.POST,
                           PHORGE_TRANSACTIONS_URL,
                           responses=[
                               httpretty.Response(body=request_callback)
                           ])
    httpretty.register_uri(httpretty.POST,
                           PHORGE_USERS_URL,
                           responses=[
                               httpretty.Response(body=request_callback)
                           ])
    httpretty.register_uri(httpretty.POST,
                           PHORGE_PHIDS_URL,
                           responses=[
                               httpretty.Response(body=request_callback)
                           ])
    httpretty.register_uri(httpretty.POST,
                           PHORGE_API_ERROR_URL,
                           responses=[
                               httpretty.Response(body=request_callback)
                           ])

    return http_requests


class TestPhorgeBackend(unittest.TestCase):
    """Phorge backend unit tests"""

    def test_initialization(self):
        """Test whether attributes are initializated"""

        phorge = Phorge(PHORGE_URL, 'AAAA', tag='test')

        self.assertEqual(phorge.url, PHORGE_URL)
        self.assertEqual(phorge.origin, PHORGE_URL)
        self.assertEqual(phorge.tag, 'test')
        self.assertIsNone(phorge.client)
        self.assertTrue(phorge.ssl_verify)
        self.assertListEqual(phorge.blacklist_ids, [])

        # When tag is empty or None it will be set to
        # the value in url
        phorge = Phorge(PHORGE_URL, 'AAAA')
        self.assertEqual(phorge.url, PHORGE_URL)
        self.assertEqual(phorge.origin, PHORGE_URL)
        self.assertEqual(phorge.tag, PHORGE_URL)
        self.assertListEqual(phorge.blacklist_ids, [])

        phorge = Phorge(PHORGE_URL, 'AAAA', tag='', ssl_verify=False)
        self.assertEqual(phorge.url, PHORGE_URL)
        self.assertEqual(phorge.origin, PHORGE_URL)
        self.assertEqual(phorge.tag, PHORGE_URL)
        self.assertEqual(phorge.max_retries, MAX_RETRIES)
        self.assertEqual(phorge.sleep_time, DEFAULT_SLEEP_TIME)
        self.assertFalse(phorge.ssl_verify)
        self.assertListEqual(phorge.blacklist_ids, [])

        phorge = Phorge(PHORGE_URL, 'AAAA', None, None, 3, 25)
        self.assertEqual(phorge.url, PHORGE_URL)
        self.assertEqual(phorge.origin, PHORGE_URL)
        self.assertEqual(phorge.tag, PHORGE_URL)
        self.assertEqual(phorge.max_retries, 3)
        self.assertEqual(phorge.sleep_time, 25)
        self.assertListEqual(phorge.blacklist_ids, [])

        phorge = Phorge(PHORGE_URL, 'AAAA', tag='', max_retries=3, sleep_time=25)
        self.assertEqual(phorge.url, PHORGE_URL)
        self.assertEqual(phorge.origin, PHORGE_URL)
        self.assertEqual(phorge.tag, PHORGE_URL)
        self.assertEqual(phorge.max_retries, 3)
        self.assertEqual(phorge.sleep_time, 25)
        self.assertListEqual(phorge.blacklist_ids, [])

        phorge = Phorge(PHORGE_URL, 'AAAA', blacklist_ids=[69])
        self.assertEqual(phorge.blacklist_ids, [69])

    def test_has_archiving(self):
        """Test if it returns True when has_archiving is called"""

        self.assertEqual(Phorge.has_archiving(), True)

    def test_has_resuming(self):
        """Test if it returns True when has_resuming is called"""

        self.assertEqual(Phorge.has_resuming(), True)

    @httpretty.activate
    def test_fetch(self):
        """Test whether it fetches a set of tasks"""

        http_requests = setup_http_server()

        phorge = Phorge(PHORGE_URL, 'AAAA')
        tasks = [task for task in phorge.fetch(from_date=None)]

        expected = [
            (69, 9, 'jdoe', 'jdoe', '1b4c15d26068efcae83cd920bcada6003d2c4a6c', 1462306027.0),
            (73, 9, 'jdoe', 'janesmith', '5487fc704f2d3c4e83ab0cd065512a181c1726cc', 1462464642.0),
            (78, 9, 'jdoe', None, 'fa971157c4d0155652f94b673866abd83b929b27', 1462792338.0),
            (296, 9, 'jane', 'jrae', 'e8fa3e4a4381d6fea3bcf5c848f599b87e7dc4a6', 1467196707.0)
        ]

        self.assertEqual(len(tasks), len(expected))

        for x in range(len(tasks)):
            task = tasks[x]
            expc = expected[x]
            self.assertEqual(task['data']['id'], expc[0])
            self.assertEqual(len(task['data']['transactions']), expc[1])
            self.assertEqual(task['data']['fields']['authorData']['fields']['username'], expc[2])

            # Check owner data; when it is null owner is not included
            if not expc[3]:
                self.assertNotIn('ownerData', task['data']['fields'])
            else:
                self.assertEqual(task['data']['fields']['ownerData']['fields']['username'], expc[3])

            self.assertEqual(task['uuid'], expc[4])
            self.assertEqual(task['origin'], PHORGE_URL)
            self.assertEqual(task['updated_on'], expc[5])
            self.assertEqual(task['category'], 'task')
            self.assertEqual(task['tag'], PHORGE_URL)

        # Check some authors info on transactions
        trans = tasks[0]['data']['transactions']
        self.assertEqual(trans[0]['authorData']['fields']['username'], 'jane')
        self.assertEqual(trans[8]['authorData']['fields']['username'], 'jdoe')

        # Check that operation data is included for project operations
        trans = tasks[0]['data']['transactions'][8]
        self.assertEqual(trans['type'], 'projects')
        self.assertIsNotNone(trans['fields']['operations'][0]['operation_data'])

        trans = tasks[3]['data']['transactions']
        self.assertEqual(trans[0]['authorData']['fields']['username'], 'jane')
        self.assertEqual(trans[8]['authorData']['fields']['username'], 'jdoe')

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
                    'objectIdentifier': 'T69'
                }
            },
            {
                '__conduit__': ['True'],
                'output': ['json'],
                'params': {
                    '__conduit__': {'token': 'AAAA'},
                    'constraints': {'phids': ['PHID-USER-2uk52xorcqb6sjvp467y']}
                }
            },
            {
                '__conduit__': ['True'],
                'output': ['json'],
                'params': {
                    '__conduit__': {'token': 'AAAA'},
                    'constraints': {'phids': ['PHID-USER-ojtcpympsmwenszuef7p']}
                }
            },
            {
                '__conduit__': ['True'],
                'output': ['json'],
                'params': {
                    '__conduit__': {'token': 'AAAA'},
                    'constraints': {'phids': ['PHID-USER-mjr7pnwpg6slsnjcqki7']}
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
                    'objectIdentifier': 'T73'
                }
            },
            {
                '__conduit__': ['True'],
                'output': ['json'],
                'params': {
                    '__conduit__': {'token': 'AAAA'},
                    'objectIdentifier': 'T78'
                }
            },
            {
                '__conduit__': ['True'],
                'output': ['json'],
                'params': {
                    '__conduit__': {'token': 'AAAA'},
                    'constraints': {'phids': ['PHID-USER-pr5fcxy4xk5ofqsfqcfc']}
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
                    'objectIdentifier': 'T296'
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

        phorge = Phorge(PHORGE_URL, 'AAAA')
        tasks = [task for task in phorge.fetch(from_date=None)]

        task = tasks[0]
        self.assertEqual(phorge.metadata_id(task['data']), task['search_fields']['item_id'])

        task = tasks[1]
        self.assertEqual(phorge.metadata_id(task['data']), task['search_fields']['item_id'])

        task = tasks[2]
        self.assertEqual(phorge.metadata_id(task['data']), task['search_fields']['item_id'])

        task = tasks[3]
        self.assertEqual(phorge.metadata_id(task['data']), task['search_fields']['item_id'])

    @httpretty.activate
    def test_fetch_from_date(self):
        """Test wether if fetches a set of tasks from the given date"""

        http_requests = setup_http_server()

        from_date = datetime.datetime(2016, 6, 29, 0, 0, 0)

        phorge = Phorge(PHORGE_URL, 'AAAA')
        tasks = [task for task in phorge.fetch(from_date=from_date)]

        self.assertEqual(len(tasks), 1)

        task = tasks[0]
        self.assertEqual(task['data']['id'], 296)
        self.assertEqual(task['data']['fields']['authorData']['fields']['username'], 'jane')
        self.assertEqual(task['data']['fields']['ownerData']['fields']['username'], 'jrae')
        self.assertEqual(len(task['data']['transactions']), 9)
        self.assertEqual(task['uuid'], 'e8fa3e4a4381d6fea3bcf5c848f599b87e7dc4a6')
        self.assertEqual(task['origin'], PHORGE_URL)
        self.assertEqual(task['updated_on'], 1467196707.0)
        self.assertEqual(task['category'], 'task')
        self.assertEqual(task['tag'], PHORGE_URL)

        trans = task['data']['transactions'][8]
        self.assertEqual(trans['type'], 'projects')
        self.assertEqual(trans['fields']['operations'][0]['operation_data']['phid'],
                         'PHID-PROJ-2qnt6thbrd7qnx5bitzy')

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
                    'constraints': {'phids': ['PHID-USER-ojtcpympsmwenszuef7p']}
                }
            },
            {
                '__conduit__': ['True'],
                'output': ['json'],
                'params': {
                    '__conduit__': {'token': 'AAAA'},
                    'constraints': {'phids': ['PHID-USER-pr5fcxy4xk5ofqsfqcfc']}
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
                    'objectIdentifier': 'T296'
                }
            },
            {
                '__conduit__': ['True'],
                'output': ['json'],
                'params': {
                    '__conduit__': {'token': 'AAAA'},
                    'constraints': {'phids': ['PHID-USER-mjr7pnwpg6slsnjcqki7']}
                }
            },
            {
                '__conduit__': ['True'],
                'output': ['json'],
                'params': {
                    '__conduit__': {'token': 'AAAA'},
                    'constraints': {'phids': ['PHID-USER-2uk52xorcqb6sjvp467y']}
                }
            }
        ]

        self.assertEqual(len(http_requests), len(expected))

        for i in range(len(expected)):
            rparams = http_requests[i].parsed_body
            rparams['params'] = json.loads(rparams['params'][0])
            self.assertDictEqual(rparams, expected[i])

    @httpretty.activate
    def test_fetch_id_blacklisted(self):
        http_requests = setup_http_server()

        phorge = Phorge(PHORGE_URL, 'AAAA', blacklist_ids=[296])
        tasks = [task for task in phorge.fetch(from_date=None)]

        expected = [
            (69, 9, 'jdoe', 'jdoe', '1b4c15d26068efcae83cd920bcada6003d2c4a6c', 1462306027.0),
            (73, 9, 'jdoe', 'janesmith', '5487fc704f2d3c4e83ab0cd065512a181c1726cc', 1462464642.0),
            (78, 9, 'jdoe', None, 'fa971157c4d0155652f94b673866abd83b929b27', 1462792338.0)
        ]

        self.assertEqual(len(tasks), len(expected))

        for x in range(len(tasks)):
            task = tasks[x]
            expc = expected[x]
            self.assertEqual(task['data']['id'], expc[0])
            self.assertEqual(len(task['data']['transactions']), expc[1])
            self.assertEqual(task['data']['fields']['authorData']['fields']['username'], expc[2])

            # Check owner data; when it is null owner is not included
            if not expc[3]:
                self.assertNotIn('ownerData', task['data']['fields'])
            else:
                self.assertEqual(task['data']['fields']['ownerData']['fields']['username'], expc[3])

            self.assertEqual(task['uuid'], expc[4])
            self.assertEqual(task['origin'], PHORGE_URL)
            self.assertEqual(task['updated_on'], expc[5])
            self.assertEqual(task['category'], 'task')
            self.assertEqual(task['tag'], PHORGE_URL)

        # Check some authors info on transactions
        trans = tasks[0]['data']['transactions']
        self.assertEqual(trans[0]['authorData']['fields']['username'], 'jane')
        self.assertEqual(trans[8]['authorData']['fields']['username'], 'jdoe')

        trans = tasks[0]['data']['transactions'][8]
        self.assertEqual(trans['type'], 'projects')
        self.assertIsNotNone(trans['fields']['operations'][0]['operation_data'])

        # Check some info about projects
        prjs = tasks[0]['data']['projects']
        self.assertEqual(len(prjs), 0)

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
                    'objectIdentifier': 'T69'
                }
            },
            {
                '__conduit__': ['True'],
                'output': ['json'],
                'params': {
                    '__conduit__': {'token': 'AAAA'},
                    'constraints': {'phids': ['PHID-USER-2uk52xorcqb6sjvp467y']}
                }
            },
            {
                '__conduit__': ['True'],
                'output': ['json'],
                'params': {
                    '__conduit__': {'token': 'AAAA'},
                    'constraints': {'phids': ['PHID-USER-ojtcpympsmwenszuef7p']}
                }
            },
            {
                '__conduit__': ['True'],
                'output': ['json'],
                'params': {
                    '__conduit__': {'token': 'AAAA'},
                    'constraints': {'phids': ['PHID-USER-mjr7pnwpg6slsnjcqki7']}
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
                    'objectIdentifier': 'T73'
                }
            },
            {
                '__conduit__': ['True'],
                'output': ['json'],
                'params': {
                    '__conduit__': {'token': 'AAAA'},
                    'objectIdentifier': 'T78'
                }
            }
        ]

        self.assertEqual(len(http_requests), len(expected))

        for i in range(len(expected)):
            rparams = http_requests[i].parsed_body
            rparams['params'] = json.loads(rparams['params'][0])
            self.assertIn(rparams, expected)

    @httpretty.activate
    def test_fetch_empty(self):
        """Test if nothing is returnerd when there are no tasks"""

        http_requests = setup_http_server()

        from_date = datetime.datetime(2017, 1, 1, 0, 0, 0)

        phorge = Phorge(PHORGE_URL, 'AAAA')
        tasks = [task for task in phorge.fetch(from_date=from_date)]

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

        raw_json = read_file('data/phorge/phorge_tasks.json')

        tasks = Phorge.parse_tasks(raw_json)
        results = [task for task in tasks]

        self.assertEqual(len(results), 3)
        self.assertEqual(results[0]['id'], 69)
        self.assertEqual(results[1]['id'], 73)
        self.assertEqual(results[2]['id'], 78)

        # Parse a file without results
        raw_json = read_file('data/phorge/phorge_tasks_empty.json')

        tasks = Phorge.parse_tasks(raw_json)
        results = [task for task in tasks]

        self.assertEqual(len(results), 0)

    def test_parse_tasks_transactions(self):
        """Test if it parses a tasks transactions stream"""

        raw_json = read_file('data/phorge/phorge_T69_transactions.json')

        results = Phorge.parse_tasks_transactions(raw_json)

        self.assertEqual(len(results['data']), 9)
        self.assertEqual(results['cursor']['after'], None)

    def test_parse_users(self):
        """Test if it parses a users stream"""

        raw_json = read_file('data/phorge/phorge_users.json')

        users = Phorge.parse_users(raw_json)
        results = [user for user in users]

        self.assertEqual(len(results), 4)
        self.assertEqual(results[0]['fields']['username'], 'jrae')
        self.assertEqual(results[1]['fields']['username'], 'jsmith')
        self.assertEqual(results[2]['fields']['username'], 'jdoe')
        self.assertEqual(results[3]['fields']['username'], 'jane')

    def test_parse_phids(self):
        """Test if it parses a phids stream"""

        raw_json = read_file('data/phorge/phorge_phids.json')
        json_content = json.loads(raw_json)
        phids = Phorge.parse_phids(json_content)
        results = [phid for phid in phids]
        results.sort(key=lambda x: x['fullName'])

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]['fullName'], 'Herald')
        self.assertEqual(results[1]['fullName'], 'Mock')


class TestPhorgeBackendArchive(TestCaseBackendArchive):
    """Phorge backend tests using an archive"""

    def setUp(self):
        super().setUp()
        self.backend_write_archive = Phorge(PHORGE_URL, 'AAAA', archive=self.archive)
        self.backend_read_archive = Phorge(PHORGE_URL, 'BBBB', archive=self.archive)

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

        client = ConduitClient(PHORGE_URL, 'aaaa')
        self.assertEqual(client.base_url, PHORGE_URL)
        self.assertEqual(client.api_token, 'aaaa')
        self.assertEqual(client.max_retries, MAX_RETRIES)
        self.assertEqual(client.sleep_time, DEFAULT_SLEEP_TIME)
        self.assertTrue(client.ssl_verify)

        client = ConduitClient(PHORGE_URL, 'aaaa', 2, 100, ssl_verify=False)
        self.assertEqual(client.base_url, PHORGE_URL)
        self.assertEqual(client.api_token, 'aaaa')
        self.assertEqual(client.max_retries, 2)
        self.assertEqual(client.sleep_time, 100)
        self.assertFalse(client.ssl_verify)

        client = ConduitClient(PHORGE_URL, 'aaaa', max_retries=2, sleep_time=100)
        self.assertEqual(client.base_url, PHORGE_URL)
        self.assertEqual(client.api_token, 'aaaa')
        self.assertEqual(client.max_retries, 2)
        self.assertEqual(client.sleep_time, 100)

    @httpretty.activate
    def test_tasks(self):
        """Test if a set of tasks is returned"""

        http_requests = setup_http_server()

        client = ConduitClient(PHORGE_URL, 'aaaa')
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

        client = ConduitClient(PHORGE_URL, 'aaaa')
        _ = client.transactions(69)
        _ = client.transactions(73)
        _ = client.transactions(78)

        expected = [
            {
                '__conduit__': ['True'],
                'output': ['json'],
                'params': {
                    '__conduit__': {'token': 'aaaa'},
                    'objectIdentifier': 'T69'
                }
            },
            {
                '__conduit__': ['True'],
                'output': ['json'],
                'params': {
                    '__conduit__': {'token': 'aaaa'},
                    'objectIdentifier': 'T73'
                }
            },
            {
                '__conduit__': ['True'],
                'output': ['json'],
                'params': {
                    '__conduit__': {'token': 'aaaa'},
                    'objectIdentifier': 'T78'
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

        client = ConduitClient(PHORGE_URL, 'aaaa')
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
                    'constraints': {
                        'phids': [
                            "PHID-USER-2uk52xorcqb6sjvp467y",
                            "PHID-USER-bjxhrstz5fb5gkrojmev",
                            "PHID-USER-pr5fcxy4xk5ofqsfqcfc",
                            "PHID-USER-ojtcpympsmwenszuef7p"
                        ]
                    }
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

        client = ConduitClient(PHORGE_URL, 'aaaa')
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
    def test_phorge_error(self):
        """Test if an exception is raised when an error is returned by the server"""

        setup_http_server()

        client = ConduitClient(PHORGE_URL, 'aaaa')

        with self.assertRaises(ConduitError):
            _ = client._call('error', {})

    @httpretty.activate
    def test_retry_on_server_errors(self):
        """Test if the client retries when some HTTP errors are found"""

        reqs = []
        body = read_file('data/phorge/phorge_tasks_empty.json', 'rb')

        responses = {
            PHORGE_TASKS_URL: [(502, 'error'), (503, 'error'), (429, 'error'), (503, 'error'), (200, body)],
            PHORGE_USERS_URL: [(503, 'error'), (503, 'error'), (503, 'error'),
                               (503, 'error'), (503, 'error'), (503, 'error')],
            PHORGE_PHIDS_URL: [(404, 'not found')]
        }

        def request_callback(method, uri, headers):
            reqs.append(httpretty.last_request())
            resp = responses[uri].pop(0)
            return (resp[0], headers, resp[1])

        httpretty.register_uri(httpretty.POST,
                               PHORGE_TASKS_URL,
                               responses=[
                                   httpretty.Response(body=request_callback)
                                   for _ in range(3)
                               ])
        httpretty.register_uri(httpretty.POST,
                               PHORGE_USERS_URL,
                               responses=[
                                   httpretty.Response(body=request_callback)
                                   for _ in range(4)
                               ])
        httpretty.register_uri(httpretty.POST,
                               PHORGE_PHIDS_URL,
                               responses=[
                                   httpretty.Response(body=request_callback)
                                   for _ in range(1)
                               ])

        # These tests are based on the maximum number of retries,
        # set by default to 3. The client only retries 502 and 503
        # HTTP errors.
        client = ConduitClient(PHORGE_URL, 'aaaa', sleep_time=0.1)

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


class TestPhorgeCommand(unittest.TestCase):
    """Tests for PhorgeCommand class"""

    def test_backend_class(self):
        """Test if the backend class is Phorge"""

        self.assertIs(PhorgeCommand.BACKEND, Phorge)

    def test_setup_cmd_parser(self):
        """Test if it parser object is correctly initialized"""

        parser = PhorgeCommand.setup_cmd_parser()
        self.assertIsInstance(parser, BackendCommandArgumentParser)
        self.assertEqual(parser._backend, Phorge)

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
