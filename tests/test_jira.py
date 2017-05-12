#!/usr/bin/env python3
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
#     Alberto Martín <alberto.martin@bitergia.com>
#     Quan Zhou <quan@bitergia.com>
#

import json
import unittest
import shutil
import sys
import tempfile

import httpretty
import pkg_resources

from grimoirelab.toolkit.datetime import str_to_datetime

# Hack to make sure that tests import the right packages
# due to setuptools behaviour
sys.path.insert(0, '..')
pkg_resources.declare_namespace('perceval.backends')

from perceval.backend import BackendCommandArgumentParser
from perceval.cache import Cache
from perceval.errors import CacheError
from perceval.utils import DEFAULT_DATETIME
from perceval.backends.core.jira import (Jira,
                                         JiraClient,
                                         JiraCommand,
                                         filter_custom_fields,
                                         map_custom_field)


JIRA_SERVER_URL = 'http://example.com'
JIRA_SEARCH_URL = JIRA_SERVER_URL + '/rest/api/2/search'
JIRA_FIELDS_URL = JIRA_SERVER_URL + '/rest/api/2/field'


def read_file(filename, mode='r'):
    with open(filename, mode) as f:
        content = f.read()
    return content


class TestJiraCustomFields(unittest.TestCase):

    def test_map_custom_field(self):

        """Test that all the fields are correctly mapped"""

        page = read_file('data/jira/jira_issues_page_1.json')

        page_json = json.loads(page)

        issues = page_json['issues']

        fields = read_file('data/jira/jira_fields.json')

        fields_json = json.loads(fields)

        custom_fields = filter_custom_fields(fields_json)

        for issue in issues:
            mapping = map_custom_field(custom_fields, issue['fields'])
            for k, v in mapping.items():
                issue['fields'][k] = v

        self.assertEqual(issues[0]['fields']['customfield_10301']['id'],
                         custom_fields['customfield_10301']['id'])
        self.assertEqual(issues[0]['fields']['customfield_10301']['name'],
                         custom_fields['customfield_10301']['name'])
        self.assertEqual(issues[0]['fields']['customfield_10400']['id'],
                         custom_fields['customfield_10400']['id'])
        self.assertEqual(issues[0]['fields']['customfield_10400']['name'],
                         custom_fields['customfield_10400']['name'])
        self.assertEqual(issues[0]['fields']['customfield_10600']['id'],
                         custom_fields['customfield_10600']['id'])
        self.assertEqual(issues[0]['fields']['customfield_10600']['name'],
                         custom_fields['customfield_10600']['name'])
        self.assertEqual(issues[0]['fields']['customfield_10603']['id'],
                         custom_fields['customfield_10603']['id'])
        self.assertEqual(issues[0]['fields']['customfield_10603']['name'],
                         custom_fields['customfield_10603']['name'])

        self.assertEqual(issues[1]['fields']['customfield_10301']['id'],
                         custom_fields['customfield_10301']['id'])
        self.assertEqual(issues[1]['fields']['customfield_10301']['name'],
                         custom_fields['customfield_10301']['name'])
        self.assertEqual(issues[1]['fields']['customfield_10400']['id'],
                         custom_fields['customfield_10400']['id'])
        self.assertEqual(issues[1]['fields']['customfield_10400']['name'],
                         custom_fields['customfield_10400']['name'])
        self.assertEqual(issues[1]['fields']['customfield_10600']['id'],
                         custom_fields['customfield_10600']['id'])
        self.assertEqual(issues[1]['fields']['customfield_10600']['name'],
                         custom_fields['customfield_10600']['name'])
        self.assertEqual(issues[1]['fields']['customfield_10603']['id'],
                         custom_fields['customfield_10603']['id'])
        self.assertEqual(issues[1]['fields']['customfield_10603']['name'],
                         custom_fields['customfield_10603']['name'])

    @httpretty.activate
    def test_filter_custom_fields(self):
        """Test that all the fields returned are just custom"""
        body = read_file('data/jira/jira_fields.json')

        httpretty.register_uri(httpretty.GET,
                               JIRA_FIELDS_URL,
                               body=body, status=200)

        body_json = json.loads(body)

        custom_fields = filter_custom_fields(body_json)

        for key in custom_fields.keys():
            self.assertEqual(custom_fields[key]['custom'], True)


class TestJiraBackend(unittest.TestCase):
    """Jira backend tests"""

    def test_initialization(self):
        """Test whether attributes are initializated"""

        jira = Jira(JIRA_SERVER_URL, tag='test',
                    max_issues=5)

        self.assertEqual(jira.url, JIRA_SERVER_URL)
        self.assertEqual(jira.origin, JIRA_SERVER_URL)
        self.assertEqual(jira.tag, 'test')
        self.assertEqual(jira.max_issues, 5)
        self.assertIsInstance(jira.client, JiraClient)

        # When tag is empty or None it will be set to
        # the value in url
        jira = Jira(JIRA_SERVER_URL)
        self.assertEqual(jira.url, JIRA_SERVER_URL)
        self.assertEqual(jira.origin, JIRA_SERVER_URL)
        self.assertEqual(jira.tag, JIRA_SERVER_URL)

        jira = Jira(JIRA_SERVER_URL, tag='')
        self.assertEqual(jira.url, JIRA_SERVER_URL)
        self.assertEqual(jira.origin, JIRA_SERVER_URL)
        self.assertEqual(jira.tag, JIRA_SERVER_URL)

    def test_has_caching(self):
        """Test if it returns True when has_caching is called"""

        self.assertEqual(Jira.has_caching(), True)

    def test_has_resuming(self):
        """Test if it returns True when has_resuming is called"""

        self.assertEqual(Jira.has_resuming(), True)

    @httpretty.activate
    def test_fetch(self):
        """Test whether a list of issues is returned"""

        requests = []

        bodies_json = [read_file('data/jira/jira_issues_page_1.json'),
                       read_file('data/jira/jira_issues_page_2.json')]

        body = read_file('data/jira/jira_fields.json')

        def request_callback(method, uri, headers):
            body = bodies_json.pop(0)
            requests.append(httpretty.last_request())
            return (200, headers, body)

        httpretty.register_uri(httpretty.GET,
                               JIRA_SEARCH_URL,
                               responses=[httpretty.Response(body=request_callback)
                                          for _ in range(2)])

        httpretty.register_uri(httpretty.GET,
                               JIRA_FIELDS_URL,
                               body=body, status=200)

        jira = Jira(JIRA_SERVER_URL)

        issues = [issue for issue in jira.fetch()]

        body_json = json.loads(body)

        custom_fields = filter_custom_fields(body_json)

        expected_req = [
            {
                'expand': ['renderedFields,transitions,operations,changelog'],
                'jql': ['updated > 0 order by updated asc'],
                'startAt': ['0']
            },
            {
                'expand': ['renderedFields,transitions,operations,changelog'],
                'jql': ['updated > 0 order by updated asc'],
                'startAt': ['2']
            }
        ]

        for i in range(len(expected_req)):
            self.assertEqual(requests[i].method, 'GET')
            self.assertRegex(requests[i].path, '/rest/api/2/search')
            self.assertDictEqual(requests[i].querystring, expected_req[i])

        self.assertEqual(len(issues), 3)

        self.assertEqual(issues[0]['origin'], 'http://example.com')
        self.assertEqual(issues[0]['uuid'], 'dfe008e19e2b720d1d377607680e90c250134164')
        self.assertEqual(issues[0]['updated_on'], 1457015567)
        self.assertEqual(issues[0]['category'], 'issue')
        self.assertEqual(issues[0]['tag'], 'http://example.com')
        self.assertEqual(issues[0]['data']['key'], 'HELP-6043')
        self.assertEqual(issues[0]['data']['fields']['issuetype']['name'], 'extRequest')
        self.assertEqual(issues[0]['data']['fields']['creator']['name'], 'user2')
        self.assertEqual(issues[0]['data']['fields']['assignee']['name'], 'user1')
        self.assertEqual(issues[0]['data']['fields']['assignee']['name'], 'user1')
        self.assertEqual(issues[0]['data']['fields']['assignee']['name'], 'user1')
        self.assertEqual(issues[0]['data']['fields']['assignee']['name'], 'user1')
        self.assertEqual(issues[0]['data']['fields']['customfield_10301']['id'],
                         custom_fields['customfield_10301']['id'])
        self.assertEqual(issues[0]['data']['fields']['customfield_10301']['name'],
                         custom_fields['customfield_10301']['name'])
        self.assertEqual(issues[0]['data']['fields']['customfield_10400']['id'],
                         custom_fields['customfield_10400']['id'])
        self.assertEqual(issues[0]['data']['fields']['customfield_10400']['name'],
                         custom_fields['customfield_10400']['name'])
        self.assertEqual(issues[0]['data']['fields']['customfield_10600']['id'],
                         custom_fields['customfield_10600']['id'])
        self.assertEqual(issues[0]['data']['fields']['customfield_10600']['name'],
                         custom_fields['customfield_10600']['name'])
        self.assertEqual(issues[0]['data']['fields']['customfield_10603']['id'],
                         custom_fields['customfield_10603']['id'])
        self.assertEqual(issues[0]['data']['fields']['customfield_10603']['name'],
                         custom_fields['customfield_10603']['name'])

        self.assertEqual(issues[1]['origin'], 'http://example.com')
        self.assertEqual(issues[1]['uuid'], '830747ed8cc9af800fcd6284e9dccfdb11daf15b')
        self.assertEqual(issues[1]['updated_on'], 1457015417)
        self.assertEqual(issues[1]['category'], 'issue')
        self.assertEqual(issues[1]['tag'], 'http://example.com')
        self.assertEqual(issues[1]['data']['key'], 'HELP-6042')
        self.assertEqual(issues[1]['data']['fields']['issuetype']['name'], 'extRequest')
        self.assertEqual(issues[1]['data']['fields']['creator']['name'], 'user2')
        self.assertEqual(issues[1]['data']['fields']['assignee']['name'], 'user1')
        self.assertEqual(issues[1]['data']['fields']['customfield_10301']['id'],
                         custom_fields['customfield_10301']['id'])
        self.assertEqual(issues[1]['data']['fields']['customfield_10301']['name'],
                         custom_fields['customfield_10301']['name'])
        self.assertEqual(issues[1]['data']['fields']['customfield_10400']['id'],
                         custom_fields['customfield_10400']['id'])
        self.assertEqual(issues[1]['data']['fields']['customfield_10400']['name'],
                         custom_fields['customfield_10400']['name'])
        self.assertEqual(issues[1]['data']['fields']['customfield_10600']['id'],
                         custom_fields['customfield_10600']['id'])
        self.assertEqual(issues[1]['data']['fields']['customfield_10600']['name'],
                         custom_fields['customfield_10600']['name'])
        self.assertEqual(issues[1]['data']['fields']['customfield_10603']['id'],
                         custom_fields['customfield_10603']['id'])
        self.assertEqual(issues[1]['data']['fields']['customfield_10603']['name'],
                         custom_fields['customfield_10603']['name'])

        self.assertEqual(issues[2]['origin'], 'http://example.com')
        self.assertEqual(issues[2]['uuid'], '2e988d555915991228d81144b018c8321d628265')
        self.assertEqual(issues[2]['updated_on'], 1457006245)
        self.assertEqual(issues[2]['category'], 'issue')
        self.assertEqual(issues[2]['tag'], 'http://example.com')
        self.assertEqual(issues[2]['data']['key'], 'HELP-6041')
        self.assertEqual(issues[2]['data']['fields']['issuetype']['name'], 'extRequest')
        self.assertEqual(issues[2]['data']['fields']['creator']['name'], 'user2')
        self.assertEqual(issues[2]['data']['fields']['assignee']['name'], 'user3')
        self.assertEqual(issues[2]['data']['fields']['customfield_10301']['id'],
                         custom_fields['customfield_10301']['id'])
        self.assertEqual(issues[2]['data']['fields']['customfield_10301']['name'],
                         custom_fields['customfield_10301']['name'])
        self.assertEqual(issues[2]['data']['fields']['customfield_10400']['id'],
                         custom_fields['customfield_10400']['id'])
        self.assertEqual(issues[2]['data']['fields']['customfield_10400']['name'],
                         custom_fields['customfield_10400']['name'])
        self.assertEqual(issues[2]['data']['fields']['customfield_10600']['id'],
                         custom_fields['customfield_10600']['id'])
        self.assertEqual(issues[2]['data']['fields']['customfield_10600']['name'],
                         custom_fields['customfield_10600']['name'])
        self.assertEqual(issues[2]['data']['fields']['customfield_10603']['id'],
                         custom_fields['customfield_10603']['id'])
        self.assertEqual(issues[2]['data']['fields']['customfield_10603']['name'],
                         custom_fields['customfield_10603']['name'])

    @httpretty.activate
    def test_fetch_from_date(self):
        """Test whether a list of issues is returned from a given date"""

        from_date = str_to_datetime('2015-01-01')

        bodies_json = read_file('data/jira/jira_issues_page_2.json')

        body = read_file('data/jira/jira_fields.json')

        httpretty.register_uri(httpretty.GET,
                               JIRA_SEARCH_URL,
                               body=bodies_json, status=200)

        httpretty.register_uri(httpretty.GET,
                               JIRA_FIELDS_URL,
                               body=body, status=200)

        jira = Jira(JIRA_SERVER_URL)

        issues = [issue for issue in jira.fetch(from_date)]

        expected_req = {
            'expand': ['renderedFields,transitions,operations,changelog'],
            'jql': ['updated > 1420070400000 order by updated asc'],
            'startAt': ['0']
        }

        self.assertEqual(len(issues), 1)

        self.assertEqual(issues[0]['origin'], 'http://example.com')
        self.assertEqual(issues[0]['uuid'], '2e988d555915991228d81144b018c8321d628265')
        self.assertEqual(issues[0]['updated_on'], 1457006245)
        self.assertEqual(issues[0]['category'], 'issue')
        self.assertEqual(issues[0]['tag'], 'http://example.com')

        request = httpretty.last_request()
        self.assertEqual(request.method, 'GET')
        self.assertRegex(request.path, '/rest/api/2/search')
        self.assertDictEqual(request.querystring, expected_req)

    @httpretty.activate
    def test_fetch_empty(self):
        """Test whether it works when no issues are fetched"""

        bodies_json = read_file('data/jira/jira_issues_page_empty.json')

        body = read_file('data/jira/jira_fields.json')

        httpretty.register_uri(httpretty.GET,
                               JIRA_SEARCH_URL,
                               body=bodies_json, status=200)

        httpretty.register_uri(httpretty.GET,
                               JIRA_FIELDS_URL,
                               body=body, status=200)

        jira = Jira(JIRA_SERVER_URL)

        issues = [issue for issue in jira.fetch()]

        expected_req = {
            'expand': ['renderedFields,transitions,operations,changelog'],
            'jql': ['updated > 0 order by updated asc'],
            'startAt': ['0']
        }

        self.assertEqual(len(issues), 0)

        request = httpretty.last_request()
        self.assertEqual(request.method, 'GET')
        self.assertRegex(request.path, '/rest/api/2/search')
        self.assertDictEqual(request.querystring, expected_req)


class TestJiraBackendCache(unittest.TestCase):
    """Jira backend tests using a cache"""

    def setUp(self):
        self.tmp_path = tempfile.mkdtemp(prefix='perceval_')

    def tearDown(self):
        shutil.rmtree(self.tmp_path)

    @httpretty.activate
    def test_fetch_from_cache(self):
        """Test whether a list of issues is returned from cache"""

        requests = []

        bodies_json = [read_file('data/jira/jira_issues_page_1.json'),
                       read_file('data/jira/jira_issues_page_2.json')]

        body = read_file('data/jira/jira_fields.json')

        def request_callback(method, uri, headers):
            body = bodies_json.pop(0)
            requests.append(httpretty.last_request())
            return (200, headers, body)

        httpretty.register_uri(httpretty.GET,
                               JIRA_SEARCH_URL,
                               responses=[httpretty.Response(body=request_callback)
                                          for _ in range(2)])
        httpretty.register_uri(httpretty.GET,
                               JIRA_FIELDS_URL,
                               body=body, status=200)

        # First, we fetch the issues from the server, storing them
        # in a cache
        cache = Cache(self.tmp_path)
        jira = Jira(JIRA_SERVER_URL, cache=cache)

        issues = [issue for issue in jira.fetch()]
        del issues[0]['timestamp']

        # Now, we get the issues from the cache.
        # The contents should be the same and there won't be
        # any new request to the server
        cache_issues = [cache_issue for cache_issue in jira.fetch_from_cache()]

        expected_req = [
            {
                'expand': ['renderedFields,transitions,operations,changelog'],
                'jql': ['updated > 0 order by updated asc'],
                'startAt': ['0']
            },
            {
                'expand': ['renderedFields,transitions,operations,changelog'],
                'jql': ['updated > 0 order by updated asc'],
                'startAt': ['2']
            }
        ]

        for i in range(len(expected_req)):
            self.assertEqual(requests[i].method, 'GET')
            self.assertRegex(requests[i].path, '/rest/api/2/search')
            self.assertDictEqual(requests[i].querystring, expected_req[i])

        self.assertEqual(len(issues), len(cache_issues))

        for i in range(len(cache_issues)):
            self.assertEqual(issues[i]['origin'], cache_issues[i]['origin'])
            self.assertEqual(issues[i]['uuid'], cache_issues[i]['uuid'])
            self.assertEqual(issues[i]['updated_on'], cache_issues[i]['updated_on'])
            self.assertEqual(issues[i]['category'], cache_issues[i]['category'])
            self.assertEqual(issues[1]['tag'], cache_issues[i]['tag'])
            self.assertEqual(issues[i]['data']['key'], cache_issues[i]['data']['key'])
            self.assertEqual(issues[i]['data']['fields']['issuetype']['name'],
                             cache_issues[i]['data']['fields']['issuetype']['name'])
            self.assertEqual(issues[i]['data']['fields']['creator']['name'],
                             cache_issues[i]['data']['fields']['creator']['name'])
            self.assertEqual(issues[i]['data']['fields']['assignee']['name'],
                             cache_issues[i]['data']['fields']['assignee']['name'])

    def test_fetch_from_cache_empty(self):
        """Test if there are not any issues returned when the cache is empty"""

        cache = Cache(self.tmp_path)

        jira = Jira(JIRA_SERVER_URL, cache=cache)
        cache_issues = [cache_issue for cache_issue in jira.fetch_from_cache()]

        self.assertEqual(len(cache_issues), 0)

    def test_fetch_from_non_set_cache(self):
        """Test if a error is raised when the cache was not set"""

        jira = Jira(JIRA_SERVER_URL)

        with self.assertRaises(CacheError):
            _ = cache_issues = [cache_issue for cache_issue in jira.fetch_from_cache()]


class TestJiraBackendParsers(unittest.TestCase):
    """Jira backend parsers tests"""

    def test_parse_issues(self):
        """Test issues parsing"""

        raw_parse_json = read_file('data/jira/jira_issues_page_1.json')
        parse_json = read_file('data/jira/jira_issues_parse_expected.json')

        issues = Jira.parse_issues(raw_parse_json)

        result = [issue for issue in issues]

        parse = json.loads(parse_json)

        self.assertTrue(len(result), 2)

        self.assertEqual(result[0]["id"], "35851")
        self.assertEqual(result[0]["key"], "HELP-6043")
        self.assertEqual(result[0]["self"], "https://jira.fiware.org/rest/api/2/issue/35851")
        self.assertEqual(result[0]["expand"],
                         "operations,editmeta,changelog,transitions,renderedFields")
        self.assertEqual(len(result[0]["fields"]), 27)
        self.assertDictEqual(result[0]["fields"], parse[0]["fields"])

        self.assertEqual(result[1]["id"], "35850")
        self.assertEqual(result[1]["key"], "HELP-6042")
        self.assertEqual(result[1]["self"], "https://jira.fiware.org/rest/api/2/issue/35850")
        self.assertEqual(result[1]["expand"],
                         "operations,editmeta,changelog,transitions,renderedFields")
        self.assertEqual(len(result[1]["fields"]), 27)
        self.assertDictEqual(result[1]["fields"], parse[1]["fields"])


class TestJiraClient(unittest.TestCase):
    """JIRA API client tests"""

    def test_init(self):
        """Test initialization"""

        client = JiraClient(url='http://example.com', project='perceval',
                            user='user', password='password',
                            verify=False, cert=None, max_issues=100)

        self.assertEqual(client.url, 'http://example.com')
        self.assertEqual(client.project, 'perceval')
        self.assertEqual(client.user, 'user')
        self.assertEqual(client.password, 'password')
        self.assertEqual(client.verify, False)
        self.assertEqual(client.cert, None)
        self.assertEqual(client.max_issues, 100)

    @httpretty.activate
    def test_get_issues(self):
        """Test get issues API call"""

        from_date = str_to_datetime('2015-01-01')

        requests = []

        bodies_json = [read_file('data/jira/jira_issues_page_1.json'),
                       read_file('data/jira/jira_issues_page_2.json')]

        bodies = bodies_json[:]
        bodies = list(bodies_json)

        def request_callback(method, uri, headers):
            body = bodies.pop(0)
            requests.append(httpretty.last_request())
            return (200, headers, body)

        httpretty.register_uri(httpretty.GET,
                               JIRA_SEARCH_URL,
                               responses=[httpretty.Response(body=request_callback)
                                          for _ in range(2)])

        client = JiraClient(url='http://example.com', project='perceval',
                            user='user', password='password',
                            verify=False, cert=None, max_issues=2)

        pages = [page for page in client.get_issues(from_date)]

        expected_req = [
            {
                'expand': ['renderedFields,transitions,operations,changelog'],
                'jql': ['project = perceval AND updated > 1420070400000 order by updated asc'],
                'maxResults': ['2'],
                'startAt': ['0']
            },
            {
                'expand': ['renderedFields,transitions,operations,changelog'],
                'jql': ['project = perceval AND updated > 1420070400000 order by updated asc'],
                'maxResults': ['2'],
                'startAt': ['2']
            }
        ]

        self.assertEqual(len(pages), 2)

        self.assertEqual(requests[0].method, 'GET')
        self.assertRegex(requests[0].path, '/rest/api/2/search')
        self.assertDictEqual(requests[0].querystring, expected_req[0])

        self.assertEqual(requests[1].method, 'GET')
        self.assertRegex(requests[1].path, '/rest/api/2/search')
        self.assertDictEqual(requests[1].querystring, expected_req[1])

        self.assertEqual(pages[0], bodies_json[0])
        self.assertEqual(pages[1], bodies_json[1])

    @httpretty.activate
    def test_get_fields(self):
        """Test get fields API call"""

        body = read_file('data/jira/jira_fields.json')

        httpretty.register_uri(httpretty.GET,
                               JIRA_FIELDS_URL,
                               body=body, status=200)

        client = JiraClient(url='http://example.com', project=None,
                            user='user', password='password',
                            verify=False, cert=None, max_issues=None)

        page = client.get_fields()

        self.assertEqual(httpretty.last_request().method, 'GET')
        self.assertRegex(httpretty.last_request().path, '/rest/api/2/field')

        self.assertEqual(page, body)

    @httpretty.activate
    def test_get_issues_empty(self):
        """Test get when the issue is empty API call"""

        from_date = str_to_datetime('2015-01-01')

        body = '{"total": 0, "maxResults": 0, "startAt": 0}'

        httpretty.register_uri(httpretty.GET,
                               JIRA_SEARCH_URL,
                               body=body, status=200)

        client = JiraClient(url='http://example.com', project='perceval',
                            user='user', password='password',
                            verify=False, cert=None, max_issues=1)

        pages = [page for page in client.get_issues(from_date)]

        expected_req = {
            'expand': ['renderedFields,transitions,operations,changelog'],
            'jql': ['project = perceval AND updated > 1420070400000 order by updated asc'],
            'maxResults': ['1'],
            'startAt': ['0']
        }

        self.assertEqual(len(pages), 1)

        self.assertEqual(pages[0], body)

        self.assertDictEqual(httpretty.last_request().querystring, expected_req)


class TestJiraCommand(unittest.TestCase):
    """JiraCommand unit tests"""

    def test_backend_class(self):
        """Test if the backend class is Jira"""

        self.assertIs(JiraCommand.BACKEND, Jira)

    def test_setup_cmd_parser(self):
        """Test if it parser object is correctly initialized"""

        parser = JiraCommand.setup_cmd_parser()
        self.assertIsInstance(parser, BackendCommandArgumentParser)

        args = ['--backend-user', 'jsmith',
                '--backend-password', '1234',
                '--project', 'Perceval Jira',
                '--verify', False,
                '--cert', 'aaaa',
                '--max-issues', '1',
                '--tag', 'test',
                '--no-cache',
                '--from-date', '1970-01-01',
                JIRA_SERVER_URL]

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.user, 'jsmith')
        self.assertEqual(parsed_args.password, '1234')
        self.assertEqual(parsed_args.project, 'Perceval Jira')
        self.assertEqual(parsed_args.verify, False)
        self.assertEqual(parsed_args.cert, 'aaaa')
        self.assertEqual(parsed_args.max_issues, 1)
        self.assertEqual(parsed_args.tag, 'test')
        self.assertEqual(parsed_args.no_cache, True)
        self.assertEqual(parsed_args.from_date, DEFAULT_DATETIME)
        self.assertEqual(parsed_args.url, JIRA_SERVER_URL)


if __name__ == '__main__':
    unittest.main(warnings='ignore')
