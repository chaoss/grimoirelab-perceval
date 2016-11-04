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

import argparse
import datetime
import shutil
import sys
import tempfile
import unittest

import httpretty

if not '..' in sys.path:
    sys.path.insert(0, '..')

from perceval.cache import Cache
from perceval.errors import CacheError
from perceval.backends.redmine import (Redmine,
                                       RedmineCommand,
                                       RedmineClient)


REDMINE_URL = 'http://example.com'
REDMINE_ISSUES_URL = REDMINE_URL + '/issues.json'
REDMINE_ISSUE_2_URL = REDMINE_URL + '/issues/2.json'
REDMINE_ISSUE_5_URL = REDMINE_URL + '/issues/5.json'
REDMINE_ISSUE_9_URL = REDMINE_URL + '/issues/9.json'
REDMINE_ISSUE_7311_URL = REDMINE_URL + '/issues/7311.json'
REDMINE_USER_3_URL = REDMINE_URL + '/users/3.json'
REDMINE_USER_4_URL = REDMINE_URL + '/users/4.json'
REDMINE_USER_24_URL = REDMINE_URL + '/users/24.json'
REDMINE_USER_25_URL = REDMINE_URL + '/users/25.json'
REDMINE_NOT_FOUND_USER_URL = REDMINE_URL + '/users/99.json'

REDMINE_URL_LIST = [
    REDMINE_ISSUES_URL, REDMINE_ISSUE_2_URL, REDMINE_ISSUE_5_URL,
    REDMINE_ISSUE_9_URL, REDMINE_ISSUE_7311_URL, REDMINE_USER_3_URL,
    REDMINE_USER_4_URL, REDMINE_USER_24_URL, REDMINE_USER_25_URL,
    REDMINE_NOT_FOUND_USER_URL
]


def read_file(filename, mode='r'):
    with open(filename, mode) as f:
        content = f.read()
    return content


def setup_http_server():
    """Setup a mock HTTP server"""

    http_requests = []

    issues_body = read_file('data/redmine/redmine_issues.json', 'rb')
    issues_next_body = read_file('data/redmine/redmine_issues_next.json', 'rb')
    issues_empty_body = read_file('data/redmine/redmine_issues_empty.json', 'rb')
    issue_2_body = read_file('data/redmine/redmine_issue_2.json', 'rb')
    issue_5_body = read_file('data/redmine/redmine_issue_5.json', 'rb')
    issue_9_body = read_file('data/redmine/redmine_issue_9.json', 'rb')
    issue_7311_body = read_file('data/redmine/redmine_issue_7311.json', 'rb')
    user_3_body = read_file('data/redmine/redmine_user_3.json', 'rb')
    user_4_body = read_file('data/redmine/redmine_user_4.json', 'rb')
    user_24_body = read_file('data/redmine/redmine_user_24.json', 'rb')
    user_25_body = read_file('data/redmine/redmine_user_25.json', 'rb')

    def request_callback(method, uri, headers):
        last_request = httpretty.last_request()
        params = last_request.querystring

        status = 200

        if uri.startswith(REDMINE_ISSUES_URL):
            if params['updated_on'][0] == '>=1970-01-01T00:00:00Z' and \
                params['offset'][0] == '0':
                body = issues_body
            elif params['updated_on'][0] == '>=1970-01-01T00:00:00Z' and \
                params['offset'][0] == '3':
                body = issues_next_body
            elif params['updated_on'][0] == '>=2016-07-27T00:00:00Z' and \
                params['offset'][0] == '0':
                body = issues_next_body
            else:
                body = issues_empty_body
        elif uri.startswith(REDMINE_ISSUE_2_URL):
            body = issue_2_body
        elif uri.startswith(REDMINE_ISSUE_5_URL):
            body = issue_5_body
        elif uri.startswith(REDMINE_ISSUE_9_URL):
            body = issue_9_body
        elif uri.startswith(REDMINE_ISSUE_7311_URL):
            body = issue_7311_body
        elif uri.startswith(REDMINE_USER_3_URL):
            body = user_3_body
        elif uri.startswith(REDMINE_USER_4_URL):
            body = user_4_body
        elif uri.startswith(REDMINE_USER_24_URL):
            body = user_24_body
        elif uri.startswith(REDMINE_USER_25_URL):
            body = user_25_body
        elif uri.startswith(REDMINE_NOT_FOUND_USER_URL):
            body = "Not Found"
            status = 404
        else:
            raise

        http_requests.append(last_request)

        return (status, headers, body)

    for url in REDMINE_URL_LIST:
        httpretty.register_uri(httpretty.GET,
                               url,
                               responses=[
                                    httpretty.Response(body=request_callback)
                               ])
    return http_requests


class TestRedmineBackend(unittest.TestCase):
    """Redmine backend unit tests"""

    def test_initialization(self):
        """Test whether attributes are initializated"""

        redmine = Redmine(REDMINE_URL, api_token='AAAA', max_issues=5,
                          tag='test')

        self.assertEqual(redmine.url, REDMINE_URL)
        self.assertEqual(redmine.max_issues, 5)
        self.assertEqual(redmine.origin, REDMINE_URL)
        self.assertEqual(redmine.tag, 'test')
        self.assertIsInstance(redmine.client, RedmineClient)
        self.assertEqual(redmine.client.api_token, 'AAAA')

        # When tag is empty or None it will be set to
        # the value in url
        redmine = Redmine(REDMINE_URL)
        self.assertEqual(redmine.url, REDMINE_URL)
        self.assertEqual(redmine.origin, REDMINE_URL)
        self.assertEqual(redmine.tag, REDMINE_URL)

        redmine = Redmine(REDMINE_URL, tag='')
        self.assertEqual(redmine.url, REDMINE_URL)
        self.assertEqual(redmine.origin, REDMINE_URL)
        self.assertEqual(redmine.tag, REDMINE_URL)

    def test_has_caching(self):
        """Test if it returns True when has_caching is called"""

        self.assertEqual(Redmine.has_caching(), True)

    def test_has_resuming(self):
        """Test if it returns True when has_resuming is called"""

        self.assertEqual(Redmine.has_resuming(), True)

    @httpretty.activate
    def test_fetch(self):
        """Test whether it fetches a set of issues"""

        http_requests = setup_http_server()

        redmine = Redmine(REDMINE_URL, api_token='AAAA',
                          max_issues=3)
        issues = [issue for issue in redmine.fetch()]

        expected = [(9, '91a8349c2f6ebffcccc49409529c61cfd3825563', 1323367020.0, 3, 3),
                    (5, 'c4aeb9e77fec8e4679caa23d4012e7cc36ae8b98', 1323367075.0, 3, 3),
                    (2, '3c3d67925b108a37f88cc6663f7f7dd493fa818c', 1323367117.0, 3, 3),
                    (7311, '4ab289ab60aee93a66e5490529799cf4a2b4d94c', 1469607427.0, 24, 4)]

        self.assertEqual(len(issues), len(expected))

        for x in range(len(issues)):
            issue = issues[x]
            expc = expected[x]
            self.assertEqual(issue['data']['id'], expc[0])
            self.assertEqual(issue['uuid'], expc[1])
            self.assertEqual(issue['origin'], REDMINE_URL)
            self.assertEqual(issue['updated_on'], expc[2])
            self.assertEqual(issue['category'], 'issue')
            self.assertEqual(issue['tag'], REDMINE_URL)
            self.assertEqual(issue['data']['author_data']['id'], expc[3])
            self.assertEqual(issue['data']['journals'][0]['user_data']['id'], expc[4])

        # Check requests
        expected = [{
                     'key' : ['AAAA'],
                     'status_id' : ['*'],
                     'sort' : ['updated_on'],
                     'updated_on' : ['>=1970-01-01T00:00:00Z'],
                     'offset' : ['0'],
                     'limit' : ['3']
                    },
                    {
                     'key' : ['AAAA'],
                     'include' : ['attachments,changesets,children,journals,relations,watchers']
                    },
                    {
                     'key' : ['AAAA']
                    },
                    {
                     'key' : ['AAAA'],
                     'include' : ['attachments,changesets,children,journals,relations,watchers']
                    },
                    {
                     'key' : ['AAAA'],
                     'include' : ['attachments,changesets,children,journals,relations,watchers']
                    },
                    {
                     'key' : ['AAAA'],
                     'status_id' : ['*'],
                     'sort' : ['updated_on'],
                     'updated_on' : ['>=1970-01-01T00:00:00Z'],
                     'offset' : ['3'],
                     'limit' : ['3']
                    },
                    {
                     'key' : ['AAAA'],
                     'include' : ['attachments,changesets,children,journals,relations,watchers']
                    },
                    {
                     'key' : ['AAAA']
                    },
                    {
                     'key' : ['AAAA']
                    },
                    {
                     'key' : ['AAAA']
                    },
                    {
                     'key' : ['AAAA']
                    },
                    {
                     'key' : ['AAAA'],
                     'status_id' : ['*'],
                     'sort' : ['updated_on'],
                     'updated_on' : ['>=1970-01-01T00:00:00Z'],
                     'offset' : ['6'],
                     'limit' : ['3']
                    }]

        self.assertEqual(len(http_requests), len(expected))

        for i in range(len(expected)):
            self.assertDictEqual(http_requests[i].querystring, expected[i])

    @httpretty.activate
    def test_fetch_from_date(self):
        """Test wether if fetches a set of issues from the given date"""

        http_requests = setup_http_server()

        from_date = datetime.datetime(2016, 7, 27)

        redmine = Redmine(REDMINE_URL, api_token='AAAA',
                          max_issues=3)
        issues = [issue for issue in redmine.fetch(from_date=from_date)]

        self.assertEqual(len(issues), 1)

        issue = issues[0]
        self.assertEqual(issue['data']['id'], 7311)
        self.assertEqual(issue['uuid'], '4ab289ab60aee93a66e5490529799cf4a2b4d94c')
        self.assertEqual(issue['origin'], REDMINE_URL)
        self.assertEqual(issue['updated_on'], 1469607427.0)
        self.assertEqual(issue['category'], 'issue')
        self.assertEqual(issue['tag'], REDMINE_URL)
        self.assertEqual(issue['data']['author_data']['id'], 24)
        self.assertEqual(issue['data']['journals'][0]['user_data']['id'], 4)

        expected = [{
                     'key' : ['AAAA'],
                     'status_id' : ['*'],
                     'sort' : ['updated_on'],
                     'updated_on' : ['>=2016-07-27T00:00:00Z'],
                     'offset' : ['0'],
                     'limit' : ['3']
                    },
                    {
                     'key' : ['AAAA'],
                     'include' : ['attachments,changesets,children,journals,relations,watchers']
                    },
                    {
                     'key' : ['AAAA']
                    },
                    {
                     'key' : ['AAAA']
                    },
                    {
                     'key' : ['AAAA']
                    },
                    {
                     'key' : ['AAAA']
                    },
                    {
                     'key' : ['AAAA'],
                     'status_id' : ['*'],
                     'sort' : ['updated_on'],
                     'updated_on' : ['>=2016-07-27T00:00:00Z'],
                     'offset' : ['3'],
                     'limit' : ['3']
                    }]

        self.assertEqual(len(http_requests), len(expected))

        for i in range(len(expected)):
            self.assertDictEqual(http_requests[i].querystring, expected[i])

    @httpretty.activate
    def test_not_found_user(self):
        """Test if it works when a user is not found"""

        http_requests = setup_http_server()

        from_date = datetime.datetime(2016, 7, 27)

        redmine = Redmine(REDMINE_URL, api_token='AAAA',
                          max_issues=3)
        issues = [issue for issue in redmine.fetch(from_date=from_date)]

        self.assertEqual(len(issues), 1)

        # The user 99 does not have information
        self.assertEqual(issues[0]['data']['journals'][1]['user']['id'], 99)
        self.assertDictEqual(issues[0]['data']['journals'][1]['user_data'], {})

    @httpretty.activate
    def test_fetch_empty(self):
        """Test if nothing is returnerd when there are no issues"""

        http_requests = setup_http_server()

        from_date = datetime.datetime(2017, 1, 1)

        redmine = Redmine(REDMINE_URL, api_token='AAAA',
                          max_issues=3)
        issues = [issue for issue in redmine.fetch(from_date=from_date)]

        self.assertEqual(len(issues), 0)

        expected = {
                    'key' : ['AAAA'],
                    'status_id' : ['*'],
                    'sort' : ['updated_on'],
                    'updated_on' : ['>=2017-01-01T00:00:00Z'],
                    'offset' : ['0'],
                    'limit' : ['3']
                   }

        self.assertEqual(len(http_requests), 1)
        self.assertDictEqual(http_requests[0].querystring, expected)

    def test_parse_issues(self):
        """Test if it parses a issues stream"""

        raw_json = read_file('data/redmine/redmine_issues.json')

        issues = Redmine.parse_issues(raw_json)
        results = [issue for issue in issues]

        self.assertEqual(len(results), 3)
        self.assertEqual(results[0]['id'], 9)
        self.assertEqual(results[1]['id'], 5)
        self.assertEqual(results[2]['id'], 2)

        # Parse a file without results
        raw_json = read_file('data/redmine/redmine_issues_empty.json')

        issues = Redmine.parse_issues(raw_json)
        results = [issue for issue in issues]

        self.assertEqual(len(results), 0)

    def test_parse_issue_data(self):
        """Test if it parses a issue stream"""

        raw_json = read_file('data/redmine/redmine_issue_7311.json')

        issue = Redmine.parse_issue_data(raw_json)

        self.assertEqual(issue['id'], 7311)
        self.assertEqual(len(issue['journals']), 22)
        self.assertEqual(len(issue['changesets']), 0)

    def test_parse_user_data(self):
        """"Test if it parses a user stream"""

        raw_json = read_file('data/redmine/redmine_user_3.json')

        user = Redmine.parse_user_data(raw_json)

        self.assertEqual(user['id'], 3)
        self.assertEqual(user['lastname'], 'User')
        self.assertEqual(user['login'], 'generic')


class TestRedmineBackendCache(unittest.TestCase):
    """Redmine backend tests using a cache"""

    def setUp(self):
        self.tmp_path = tempfile.mkdtemp(prefix='perceval_')

    def tearDown(self):
        shutil.rmtree(self.tmp_path)

    @httpretty.activate
    def test_fetch_from_cache(self):
        """Test whether the cache works"""

        http_requests = setup_http_server()

        # First, we fetch the issues from the server,
        # storing them in a cache
        cache = Cache(self.tmp_path)
        redmine = Redmine(REDMINE_URL, api_token='AAAA',
                          max_issues=3, cache=cache)

        issues = [issue for issue in redmine.fetch()]
        self.assertEqual(len(http_requests), 12)

        # Now, we get the issues from the cache.
        # The issues should be the same and there won't be
        # any new request to the server
        cached_issues = [issue for issue in redmine.fetch_from_cache()]
        self.assertEqual(len(cached_issues), len(issues))

        expected = [(9, '91a8349c2f6ebffcccc49409529c61cfd3825563', 1323367020.0, 3, 3),
                    (5, 'c4aeb9e77fec8e4679caa23d4012e7cc36ae8b98', 1323367075.0, 3, 3),
                    (2, '3c3d67925b108a37f88cc6663f7f7dd493fa818c', 1323367117.0, 3, 3),
                    (7311, '4ab289ab60aee93a66e5490529799cf4a2b4d94c', 1469607427.0, 24, 4)]

        self.assertEqual(len(cached_issues), len(expected))

        for x in range(len(cached_issues)):
            issue = cached_issues[x]
            expc = expected[x]
            self.assertEqual(issue['data']['id'], expc[0])
            self.assertEqual(issue['uuid'], expc[1])
            self.assertEqual(issue['origin'], REDMINE_URL)
            self.assertEqual(issue['updated_on'], expc[2])
            self.assertEqual(issue['category'], 'issue')
            self.assertEqual(issue['tag'], REDMINE_URL)
            self.assertEqual(issue['data']['author_data']['id'], expc[3])
            self.assertEqual(issue['data']['journals'][0]['user_data']['id'], expc[4])
            self.assertDictEqual(issue['data'], issues[x]['data'])

        # The user 99 does not have information
        self.assertEqual(issues[3]['data']['journals'][1]['user']['id'], 99)
        self.assertDictEqual(issues[3]['data']['journals'][1]['user_data'], {})

        # No more requests were sent
        self.assertEqual(len(http_requests), 12)

    def test_fetch_from_empty_cache(self):
        """Test if there are not any issue returned when the cache is empty"""

        cache = Cache(self.tmp_path)
        redmine = Redmine(REDMINE_URL, api_token='AAAA', cache=cache)
        cached_issues = [issue for issue in redmine.fetch_from_cache()]
        self.assertEqual(len(cached_issues), 0)

    def test_fetch_from_non_set_cache(self):
        """Test if a error is raised when the cache was not set"""

        redmine = Redmine(REDMINE_URL, api_token='AAAA')

        with self.assertRaises(CacheError):
            _ = [issue for issue in redmine.fetch_from_cache()]


class TestRedmineCommand(unittest.TestCase):
    """Tests for RedmineCommand class"""

    def test_parsing_on_init(self):
        """Test if the class is initialized"""

        args = ['http://example.com',
                '--backend-token', '12345678',
                '--max-issues', '5',
                '--tag', 'test']

        cmd = RedmineCommand(*args)
        self.assertIsInstance(cmd.parsed_args, argparse.Namespace)
        self.assertEqual(cmd.parsed_args.url, 'http://example.com')
        self.assertEqual(cmd.parsed_args.backend_token, '12345678')
        self.assertEqual(cmd.parsed_args.max_issues, 5)
        self.assertEqual(cmd.parsed_args.tag, 'test')
        self.assertIsInstance(cmd.backend, Redmine)

    def test_argument_parser(self):
        """Test if it returns a argument parser object"""

        parser = RedmineCommand.create_argument_parser()
        self.assertIsInstance(parser, argparse.ArgumentParser)


class TestRedmineClient(unittest.TestCase):
    """Redmine client unit tests.

    These tests do not check the body of the response, only if the call
    was well formed and if a response was obtained.
    """
    def test_init(self):
        """Test initialization parameters"""

        client = RedmineClient(REDMINE_URL, 'aaaa')
        self.assertEqual(client.base_url, REDMINE_URL)
        self.assertEqual(client.api_token, 'aaaa')

    @httpretty.activate
    def test_issues(self):
        """Test if issues call works"""

        body = read_file('data/redmine/redmine_issues_next.json')

        httpretty.register_uri(httpretty.GET,
                               REDMINE_ISSUES_URL,
                               body=body, status=200)

        client = RedmineClient(REDMINE_URL, 'aaaa')
        dt = datetime.datetime(2016, 7, 1, 0, 0, 0)

        result = client.issues(from_date=dt, offset=10, max_issues=200)

        self.assertEqual(result, body)

        expected = {
                    'key' : ['aaaa'],
                    'status_id' : ['*'],
                    'sort' : ['updated_on'],
                    'updated_on' : ['>=2016-07-01T00:00:00Z'],
                    'offset' : ['10'],
                    'limit' : ['200']
                   }

        req = httpretty.last_request()

        self.assertEqual(req.method, 'GET')
        self.assertRegex(req.path, '/issues.json')
        self.assertDictEqual(req.querystring, expected)

    @httpretty.activate
    def test_issue(self):
        """Test if issue call works"""

        body = read_file('data/redmine/redmine_issue_7311.json')

        httpretty.register_uri(httpretty.GET,
                               REDMINE_ISSUE_7311_URL,
                               body=body, status=200)

        client = RedmineClient(REDMINE_URL, 'aaaa')

        result = client.issue(7311)

        self.assertEqual(result, body)

        expected = {
                    'key' : ['aaaa'],
                    'include' : ['attachments,changesets,children,journals,relations,watchers']
                   }

        req = httpretty.last_request()

        self.assertEqual(req.method, 'GET')
        self.assertRegex(req.path, '/issues/7311.json')
        self.assertDictEqual(req.querystring, expected)

    @httpretty.activate
    def test_user(self):
        """Test if user call works"""

        body = read_file('data/redmine/redmine_user_3.json')

        httpretty.register_uri(httpretty.GET,
                               REDMINE_USER_3_URL,
                               body=body, status=200)

        client = RedmineClient(REDMINE_URL, 'aaaa')

        result = client.user(3)

        self.assertEqual(result, body)

        expected = {
                    'key' : ['aaaa']
                   }

        req = httpretty.last_request()

        self.assertEqual(req.method, 'GET')
        self.assertRegex(req.path, '/users/3.json')
        self.assertDictEqual(req.querystring, expected)


if __name__ == "__main__":
    unittest.main(warnings='ignore')
