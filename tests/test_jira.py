#!/usr/bin/env python3
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
#     Alberto Martín <alberto.martin@bitergia.com>
#     Quan Zhou <quan@bitergia.com>
#

import argparse
import json
import unittest
import shutil
import sys
import tempfile

import httpretty

from perceval.cache import Cache
from perceval.errors import BackendError, CacheError, ParseError
from perceval.backends.jira import Jira, JiraClient, JiraCommand
from perceval.utils import str_to_datetime

if not '..' in sys.path:
    sys.path.insert(0, '..')

JIRA_SERVER_URL = 'http://example.com'
JIRA_SEARCH_URL = JIRA_SERVER_URL + '/rest/api/2/search'


def read_file(filename, mode='r'):
    with open(filename, mode) as f:
        content = f.read()
    return content


class TestJiraBAckend(unittest.TestCase):
    @httpretty.activate
    def test_fetch(self):

        requests = []

        bodies_json = [read_file('data/jira/jira_issues_page_1.json'),
                       read_file('data/jira/jira_issues_page_2.json')]
        expected_json = [read_file('data/jira/jira_issues_fetch_expected_page_1.json'),
                         read_file('data/jira/jira_issues_fetch_expected_page_2.json'),
                         read_file('data/jira/jira_issues_fetch_expected_page_3.json')]

        def request_callback(method, uri, headers):
            body = bodies_json.pop(0)
            requests.append(httpretty.last_request())
            return (200, headers, body)

        httpretty.register_uri(httpretty.GET,
                               JIRA_SEARCH_URL,
                               responses=[httpretty.Response(body=request_callback) \
                                          for _ in range(2)])

        jira = Jira(JIRA_SERVER_URL)

        issues = [issue for issue in jira.fetch()]

        del issues[0]['timestamp']
        del issues[1]['timestamp']
        del issues[2]['timestamp']

        expected_req_0 = {
                            'expand': ['renderedFields,transitions,operations,changelog'],
                            'jql': [' updated > 0'],
                            'startAt': ['0']
                        }
        expected_req_1 = {
                            'expand': ['renderedFields,transitions,operations,changelog'],
                            'jql': [' updated > 0'],
                            'startAt': ['2']
                        }

        self.assertEqual(len(issues), 3)

        self.assertDictEqual(issues[0], json.loads(expected_json[0]))
        self.assertDictEqual(issues[1], json.loads(expected_json[1]))
        self.assertDictEqual(issues[2], json.loads(expected_json[2]))

        self.assertEqual(requests[0].method, 'GET')
        self.assertRegex(requests[0].path, '/rest/api/2/search')
        self.assertDictEqual(requests[0].querystring, expected_req_0)

        self.assertEqual(requests[1].method, 'GET')
        self.assertRegex(requests[1].path, '/rest/api/2/search')
        self.assertDictEqual(requests[1].querystring, expected_req_1)

    @httpretty.activate
    def test_fetch_from_date(self):

        from_date = str_to_datetime('2015-01-01')

        bodies_json = read_file('data/jira/jira_issues_page_2.json')
        expected_json = [read_file('data/jira/jira_issues_fetch_expected_page_3.json')]

        httpretty.register_uri(httpretty.GET,
                               JIRA_SEARCH_URL,
                               body=bodies_json, status=200)

        jira = Jira(JIRA_SERVER_URL)

        issues = [issue for issue in jira.fetch(from_date)]

        del issues[0]['timestamp']

        expected_req = {
                            'expand': ['renderedFields,transitions,operations,changelog'],
                            'jql': [' updated > 1420070400000'],
                            'startAt': ['0']
                        }

        self.assertEqual(len(issues), 1)

        self.assertDictEqual(issues[0], json.loads(expected_json[0]))

        request = httpretty.last_request()
        self.assertEqual(request.method, 'GET')
        self.assertRegex(request.path, '/rest/api/2/search')
        self.assertDictEqual(request.querystring, expected_req)

    @httpretty.activate
    def test_fetch_empty(self):

        bodies_json = read_file('data/jira/jira_issues_page_empty.json')

        httpretty.register_uri(httpretty.GET,
                               JIRA_SEARCH_URL,
                               body=bodies_json, status=200)

        jira = Jira(JIRA_SERVER_URL)

        issues = [issue for issue in jira.fetch()]

        expected_req = {
                            'expand': ['renderedFields,transitions,operations,changelog'],
                            'jql': [' updated > 0'],
                            'startAt': ['0']
                        }

        self.assertEqual(len(issues), 0)

        request = httpretty.last_request()
        self.assertEqual(request.method, 'GET')
        self.assertRegex(request.path, '/rest/api/2/search')
        self.assertDictEqual(request.querystring, expected_req)


class TestJiraBAckendCache(unittest.TestCase):
    """Jira backend tests using a cache"""

    def setUp(self):
        self.tmp_path = tempfile.mkdtemp(prefix='perceval_')

    def tearDown(self):
        shutil.rmtree(self.tmp_path)

    @httpretty.activate
    def test_fetch_from_cache(self):
        """ Test whether a list of issues is returned from cache """

        bodies_json = read_file('data/jira/jira_issues_page_2.json')
        expected_json = read_file('data/jira/jira_issues_fetch_expected_page_3.json')

        httpretty.register_uri(httpretty.GET,
                               JIRA_SEARCH_URL,
                               body=bodies_json, status=200)

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
        del cache_issues[0]['timestamp']

        expected_req = {
                            'expand': ['renderedFields,transitions,operations,changelog'],
                            'jql': [' updated > 0'],
                            'startAt': ['0']
                        }

        request = httpretty.last_request()
        self.assertEqual(request.method, 'GET')
        self.assertRegex(request.path, '/rest/api/2/search')
        self.assertDictEqual(request.querystring, expected_req)

        self.assertEqual(len(issues), 1)
        self.assertEqual(len(cache_issues), 1)

        self.assertEqual(cache_issues, issues)

        self.assertDictEqual(issues[0], json.loads(expected_json))

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
    """ Jira backend parsers tests"""

    def test_parse_questions(self):
        """ Test issue parsing """

        raw_parse_json = read_file('data/jira/jira_issues_page_1.json')
        parse_json = read_file('data/jira/jira_issues_parse_expected.json')

        issues = Jira.parse_issues(raw_parse_json)

        result = [issue for issue in issues]

        parse = json.loads(parse_json)
        self.assertDictEqual(result[0], parse[0])
        self.assertDictEqual(result[1], parse[1])


class TestJiraClient(unittest.TestCase):
    def test___init__(self):
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

        from_date = str_to_datetime('2015-01-01')

        requests = []

        bodies_json = [read_file('data/jira/jira_issues_page_1.json'),
                       read_file('data/jira/jira_issues_page_2.json')]
        expected_json = [read_file('data/jira/jira_issues_expected_page_1.json'),
                         read_file('data/jira/jira_issues_expected_page_2.json')]

        def request_callback(method, uri, headers):
            body = bodies_json.pop(0)
            requests.append(httpretty.last_request())
            return (200, headers, body)

        httpretty.register_uri(httpretty.GET,
                               JIRA_SEARCH_URL,
                               responses=[httpretty.Response(body=request_callback) \
                                          for _ in range(2)])

        client = JiraClient(url='http://example.com', project='perceval',
                            user='user', password='password',
                            verify=False, cert=None, max_issues=2)

        pages = [page for page in client.get_issues(from_date)]

        expected_req_0 = {
                            'expand': ['renderedFields,transitions,operations,changelog'],
                            'jql': [' project = perceval AND  updated > 1420070400000'],
                            'maxResults': ['2'],
                            'startAt': ['0']
                        }
        expected_req_1 = {
                            'expand': ['renderedFields,transitions,operations,changelog'],
                            'jql': [' project = perceval AND  updated > 1420070400000'],
                            'maxResults': ['2'],
                            'startAt': ['2']
                        }

        self.assertEqual(len(pages), 2)

        self.assertEqual(requests[0].method, 'GET')
        self.assertRegex(requests[0].path, '/rest/api/2/search')
        self.assertDictEqual(requests[0].querystring, expected_req_0)

        self.assertEqual(requests[1].method, 'GET')
        self.assertRegex(requests[1].path, '/rest/api/2/search')
        self.assertDictEqual(requests[1].querystring, expected_req_1)

        self.assertEqual(pages[0], expected_json[0])
        self.assertEqual(pages[1], expected_json[1])

    @httpretty.activate
    def test_get_issues_empty(self):
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
                            'jql': [' project = perceval AND  updated > 1420070400000'],
                            'maxResults': ['1'],
                            'startAt': ['0']
                        }

        self.assertEqual(len(pages), 1)

        self.assertEqual(pages[0], body)

        self.assertDictEqual(httpretty.last_request().querystring, expected_req)


class TestJiraCommand(unittest.TestCase):

    @httpretty.activate
    def test_parsing_on_init(self):
        """Test if the class is initialized"""

        args = ['--project', 'None',
                '--verify', False,
                '--cert', 'None',
                '--max-issues', '1',
                JIRA_SERVER_URL]

        cmd = JiraCommand(*args)
        self.assertIsInstance(cmd.parsed_args, argparse.Namespace)
        self.assertEqual(cmd.parsed_args.project, "None")
        self.assertEqual(cmd.parsed_args.verify, False)
        self.assertEqual(cmd.parsed_args.cert, "None")
        self.assertEqual(cmd.parsed_args.max_issues, 1)
        self.assertEqual(cmd.parsed_args.url, JIRA_SERVER_URL)

    def test_argument_parser(self):
        """Test if it returns a argument parser object"""

        parser = JiraCommand.create_argument_parser()
        self.assertIsInstance(parser, argparse.ArgumentParser)


if __name__ == '__main__':
    unittest.main(warnings='ignore')
