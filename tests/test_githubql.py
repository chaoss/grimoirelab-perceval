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
#     Valerio Cosentino <valcos@bitergia.com>
#

import datetime
import json
import os
import unittest.mock

import httpretty

from perceval.client import RateLimitHandler
from perceval.utils import DEFAULT_DATETIME
from perceval.backends.core.githubql import (logger,
                                             GitHubQL,
                                             GitHubQLCommand,
                                             GitHubQLClient,
                                             CATEGORY_EVENT,
                                             MAX_CATEGORY_ITEMS_PER_PAGE)
from base import TestCaseBackendArchive


GITHUB_API_URL = "https://api.github.com"
GITHUB_API_GRAPHQL_URL = GITHUB_API_URL + "/graphql"
GITHUB_RATE_LIMIT = GITHUB_API_URL + "/rate_limit"
GITHUB_REPO_URL = GITHUB_API_URL + "/repos/zhquan_example/repo"
GITHUB_ISSUES_URL = GITHUB_REPO_URL + "/issues"
GITHUB_ENTERPRISE_URL = "https://example.com"
GITHUB_ENTERPRISE_API_URL = "https://example.com/api/v3"
GITHUB_ENTERPRISE_API_GRAPHQL_URL = GITHUB_ENTERPRISE_URL + "/api/graphql"
GITHUB_ENTREPRISE_RATE_LIMIT = GITHUB_ENTERPRISE_API_URL + "/rate_limit"
GITHUB_ENTREPRISE_REPO_URL = GITHUB_ENTERPRISE_API_URL + "/repos/zhquan_example/repo"
GITHUB_ENTERPRISE_ISSUES_URL = GITHUB_ENTREPRISE_REPO_URL + "/issues"
GITHUB_APP_INSTALLATION_URL = GITHUB_API_URL + '/app/installations'
GITHUB_APP_ACCESS_TOKEN_URL = GITHUB_APP_INSTALLATION_URL + '/1/access_tokens'
GITHUB_APP_AUTH_URL = GITHUB_API_URL + '/installation/repositories'


def read_file(filename, mode='r'):
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), filename), mode) as f:
        content = f.read()
    return content


class TestGitHubQLBackend(unittest.TestCase):
    """ GitHubQL backend tests """

    @httpretty.activate
    def test_initialization(self):
        """Test whether attributes are initialized"""

        rate_limit = read_file('data/github/rate_limit')
        httpretty.register_uri(httpretty.GET,
                               GITHUB_RATE_LIMIT,
                               body=rate_limit,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        github = GitHubQL('zhquan_example', 'repo', ['aaa'], tag='test')

        self.assertEqual(github.owner, 'zhquan_example')
        self.assertEqual(github.repository, 'repo')
        self.assertEqual(github.origin, 'https://github.com/zhquan_example/repo')
        self.assertEqual(github.tag, 'test')
        self.assertEqual(github.max_items, MAX_CATEGORY_ITEMS_PER_PAGE)
        self.assertFalse(github.exclude_user_data)
        self.assertEqual(github.categories, [CATEGORY_EVENT])
        self.assertTrue(github.ssl_verify)

        # When tag is empty or None it will be set to the value in origin
        github = GitHubQL('zhquan_example', 'repo', ['aaa'], ssl_verify=False)
        self.assertEqual(github.owner, 'zhquan_example')
        self.assertEqual(github.repository, 'repo')
        self.assertEqual(github.origin, 'https://github.com/zhquan_example/repo')
        self.assertEqual(github.tag, 'https://github.com/zhquan_example/repo')
        self.assertFalse(github.ssl_verify)

        github = GitHubQL('zhquan_example', 'repo', ['aaa'], tag='')
        self.assertEqual(github.owner, 'zhquan_example')
        self.assertEqual(github.repository, 'repo')
        self.assertEqual(github.origin, 'https://github.com/zhquan_example/repo')
        self.assertEqual(github.tag, 'https://github.com/zhquan_example/repo')

    def test_has_resuming(self):
        """Test if it returns False when has_resuming is called"""

        self.assertEqual(GitHubQL.has_resuming(), False)

    def test_has_archiving(self):
        """Test if it returns True when has_archiving is called"""

        self.assertEqual(GitHubQL.has_archiving(), True)

    @httpretty.activate
    def test_fetch_events(self):
        """Test whether a list of events is returned"""

        events = read_file('data/github/github_events_page_2')
        issue = read_file('data/github/github_issue_2')
        rate_limit = read_file('data/github/rate_limit')

        httpretty.register_uri(httpretty.GET,
                               GITHUB_RATE_LIMIT,
                               body=rate_limit,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUES_URL,
                               body=issue,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        httpretty.register_uri(httpretty.POST,
                               GITHUB_API_GRAPHQL_URL,
                               body=events,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        github = GitHubQL("zhquan_example", "repo", ["aaa"])
        events = [events for events in github.fetch(from_date=None, to_date=None, category=CATEGORY_EVENT)]

        self.assertEqual(len(events), 2)

        event = events[0]
        self.assertEqual(event['origin'], 'https://github.com/zhquan_example/repo')
        self.assertEqual(event['uuid'], 'b46499fd01d2958d836241770063adff953b280e')
        self.assertEqual(event['updated_on'], 1586265768.0)
        self.assertEqual(event['category'], CATEGORY_EVENT)
        self.assertEqual(event['tag'], 'https://github.com/zhquan_example/repo')
        self.assertEqual(event['data']['actor']['login'], 'valeriocos')
        self.assertEqual(event['data']['createdAt'], '2020-04-07T13:22:48Z')
        self.assertEqual(event['data']['eventType'], 'MovedColumnsInProjectEvent')
        self.assertIn('issue', event['data'])

        event = events[1]
        self.assertEqual(event['origin'], 'https://github.com/zhquan_example/repo')
        self.assertEqual(event['uuid'], 'd05238b1254cf69deac49248ad8cc855482a6737')
        self.assertEqual(event['updated_on'], 1586265783.0)
        self.assertEqual(event['category'], CATEGORY_EVENT)
        self.assertEqual(event['tag'], 'https://github.com/zhquan_example/repo')
        self.assertEqual(event['data']['actor']['login'], 'valeriocos')
        self.assertEqual(event['data']['createdAt'], '2020-04-07T13:23:03Z')
        self.assertEqual(event['data']['eventType'], 'CrossReferencedEvent')
        self.assertIn('issue', event['data'])

    @httpretty.activate
    def test_fetch_events_github_app(self):
        """Test whether a list of events is returned using GitHub App"""

        events = read_file('data/github/github_events_page_2')
        issue = read_file('data/github/github_issue_2')
        rate_limit = read_file('data/github/rate_limit')
        installation = [
            {
                "account": {
                    "login": "zhquan_example"
                },
                "id": "1"
            }
        ]

        httpretty.register_uri(httpretty.GET,
                               GITHUB_RATE_LIMIT,
                               body=rate_limit,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUES_URL,
                               body=issue,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        httpretty.register_uri(httpretty.POST,
                               GITHUB_API_GRAPHQL_URL,
                               body=events,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        httpretty.register_uri(httpretty.GET,
                               GITHUB_APP_INSTALLATION_URL,
                               body=json.dumps(installation), status=200)

        httpretty.register_uri(httpretty.POST,
                               GITHUB_APP_ACCESS_TOKEN_URL,
                               body='{"token": "v1.aaa"}', status=200)

        httpretty.register_uri(httpretty.GET,
                               GITHUB_APP_AUTH_URL,
                               body='', status=200)

        github = GitHubQL("zhquan_example", "repo", github_app_id='1', github_app_pk_filepath='data/github/private.pem')
        events = [events for events in github.fetch(from_date=None, to_date=None, category=CATEGORY_EVENT)]

        self.assertEqual(len(events), 2)

        event = events[0]
        self.assertEqual(event['origin'], 'https://github.com/zhquan_example/repo')
        self.assertEqual(event['uuid'], 'b46499fd01d2958d836241770063adff953b280e')
        self.assertEqual(event['updated_on'], 1586265768.0)
        self.assertEqual(event['category'], CATEGORY_EVENT)
        self.assertEqual(event['tag'], 'https://github.com/zhquan_example/repo')
        self.assertEqual(event['data']['actor']['login'], 'valeriocos')
        self.assertEqual(event['data']['createdAt'], '2020-04-07T13:22:48Z')
        self.assertEqual(event['data']['eventType'], 'MovedColumnsInProjectEvent')
        self.assertIn('issue', event['data'])

        event = events[1]
        self.assertEqual(event['origin'], 'https://github.com/zhquan_example/repo')
        self.assertEqual(event['uuid'], 'd05238b1254cf69deac49248ad8cc855482a6737')
        self.assertEqual(event['updated_on'], 1586265783.0)
        self.assertEqual(event['category'], CATEGORY_EVENT)
        self.assertEqual(event['tag'], 'https://github.com/zhquan_example/repo')
        self.assertEqual(event['data']['actor']['login'], 'valeriocos')
        self.assertEqual(event['data']['createdAt'], '2020-04-07T13:23:03Z')
        self.assertEqual(event['data']['eventType'], 'CrossReferencedEvent')
        self.assertIn('issue', event['data'])

        self.assertEqual(httpretty.last_request().headers["Authorization"], "token v1.aaa")

    @httpretty.activate
    def test_fetch_events_pagination(self):
        """Test whether a list of paginated events is returned"""

        requests = []

        events_page_1 = read_file('data/github/github_events_page_1')
        events_page_2 = read_file('data/github/github_events_page_2')
        bodies_json = [events_page_1, events_page_2]

        def request_callback(method, uri, headers):
            body = bodies_json.pop(0)
            requests.append(httpretty.last_request())
            return 200, headers, body

        issue = read_file('data/github/github_issue_2')
        rate_limit = read_file('data/github/rate_limit')

        httpretty.register_uri(httpretty.GET,
                               GITHUB_RATE_LIMIT,
                               body=rate_limit,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUES_URL,
                               body=issue,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        httpretty.register_uri(httpretty.POST,
                               GITHUB_API_GRAPHQL_URL,
                               responses=[httpretty.Response(body=request_callback)
                                          for _ in range(2)],
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        github = GitHubQL("zhquan_example", "repo", ["aaa"])
        events = [events for events in github.fetch(from_date=None, to_date=None, category=CATEGORY_EVENT)]

        self.assertEqual(len(events), 4)

        event = events[0]
        self.assertEqual(event['origin'], 'https://github.com/zhquan_example/repo')
        self.assertEqual(event['uuid'], '116d709c3225b31f094218148d3fcceaf6737b37')
        self.assertEqual(event['updated_on'], 1586258472.0)
        self.assertEqual(event['category'], CATEGORY_EVENT)
        self.assertEqual(event['tag'], 'https://github.com/zhquan_example/repo')
        self.assertEqual(event['data']['actor']['login'], 'valeriocos')
        self.assertEqual(event['data']['createdAt'], '2020-04-07T11:21:12Z')
        self.assertEqual(event['data']['eventType'], 'LabeledEvent')
        self.assertIn('issue', event['data'])

        event = events[1]
        self.assertEqual(event['origin'], 'https://github.com/zhquan_example/repo')
        self.assertEqual(event['uuid'], 'a5e67dcb8ec7b722cc088c2e5f8bad0b3e285329')
        self.assertEqual(event['updated_on'], 1586258479.0)
        self.assertEqual(event['category'], CATEGORY_EVENT)
        self.assertEqual(event['tag'], 'https://github.com/zhquan_example/repo')
        self.assertEqual(event['data']['actor']['login'], 'valeriocos')
        self.assertEqual(event['data']['createdAt'], '2020-04-07T11:21:19Z')
        self.assertEqual(event['data']['eventType'], 'LabeledEvent')
        self.assertIn('issue', event['data'])

        event = events[2]
        self.assertEqual(event['origin'], 'https://github.com/zhquan_example/repo')
        self.assertEqual(event['uuid'], 'b46499fd01d2958d836241770063adff953b280e')
        self.assertEqual(event['updated_on'], 1586265768.0)
        self.assertEqual(event['category'], CATEGORY_EVENT)
        self.assertEqual(event['tag'], 'https://github.com/zhquan_example/repo')
        self.assertEqual(event['data']['actor']['login'], 'valeriocos')
        self.assertEqual(event['data']['createdAt'], '2020-04-07T13:22:48Z')
        self.assertEqual(event['data']['eventType'], 'MovedColumnsInProjectEvent')
        self.assertIn('issue', event['data'])

        event = events[3]
        self.assertEqual(event['origin'], 'https://github.com/zhquan_example/repo')
        self.assertEqual(event['uuid'], 'd05238b1254cf69deac49248ad8cc855482a6737')
        self.assertEqual(event['updated_on'], 1586265783.0)
        self.assertEqual(event['category'], CATEGORY_EVENT)
        self.assertEqual(event['tag'], 'https://github.com/zhquan_example/repo')
        self.assertEqual(event['data']['actor']['login'], 'valeriocos')
        self.assertEqual(event['data']['createdAt'], '2020-04-07T13:23:03Z')
        self.assertEqual(event['data']['eventType'], 'CrossReferencedEvent')
        self.assertIn('issue', event['data'])

    @httpretty.activate
    def test_fetch_events_until_date(self):
        """Test whether only the events after a given date are returned"""

        events = read_file('data/github/github_events_page_2')
        issue = read_file('data/github/github_issue_2')
        rate_limit = read_file('data/github/rate_limit')

        httpretty.register_uri(httpretty.GET,
                               GITHUB_RATE_LIMIT,
                               body=rate_limit,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUES_URL,
                               body=issue,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        httpretty.register_uri(httpretty.POST,
                               GITHUB_API_GRAPHQL_URL,
                               body=events,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        github = GitHubQL("zhquan_example", "repo", ["aaa"])
        to_date = datetime.datetime(2020, 4, 7, 13, 23, 00)
        events = [events for events in github.fetch(from_date=None, to_date=to_date, category=CATEGORY_EVENT)]

        self.assertEqual(len(events), 1)

        event = events[0]
        self.assertEqual(event['origin'], 'https://github.com/zhquan_example/repo')
        self.assertEqual(event['uuid'], 'b46499fd01d2958d836241770063adff953b280e')
        self.assertEqual(event['updated_on'], 1586265768.0)
        self.assertEqual(event['category'], CATEGORY_EVENT)
        self.assertEqual(event['tag'], 'https://github.com/zhquan_example/repo')
        self.assertEqual(event['data']['actor']['login'], 'valeriocos')
        self.assertEqual(event['data']['createdAt'], '2020-04-07T13:22:48Z')
        self.assertEqual(event['data']['eventType'], 'MovedColumnsInProjectEvent')
        self.assertIn('issue', event['data'])

    @httpretty.activate
    def test_search_fields_event(self):
        """Test whether the search_fields is properly set"""

        events = read_file('data/github/github_events_page_2')
        issue = read_file('data/github/github_issue_2')
        rate_limit = read_file('data/github/rate_limit')

        httpretty.register_uri(httpretty.GET,
                               GITHUB_RATE_LIMIT,
                               body=rate_limit,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUES_URL,
                               body=issue,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        httpretty.register_uri(httpretty.POST,
                               GITHUB_API_GRAPHQL_URL,
                               body=events,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        github = GitHubQL("zhquan_example", "repo", ["aaa"])
        events = [events for events in github.fetch(from_date=None, to_date=None, category=CATEGORY_EVENT)]

        self.assertEqual(len(events), 2)

        event = events[0]
        self.assertEqual(github.metadata_id(event['data']), event['search_fields']['item_id'])
        self.assertEqual(event['search_fields']['owner'], 'zhquan_example')
        self.assertEqual(event['search_fields']['repo'], 'repo')

        event = events[1]
        self.assertEqual(github.metadata_id(event['data']), event['search_fields']['item_id'])
        self.assertEqual(event['search_fields']['owner'], 'zhquan_example')
        self.assertEqual(event['search_fields']['repo'], 'repo')

    @httpretty.activate
    def test_fetch_events_enterprise(self):
        """Test if it fetches events from a GitHub Enterprise server"""

        events = read_file('data/github/github_events_page_2')
        issue = read_file('data/github/github_issue_2')
        rate_limit = read_file('data/github/rate_limit')

        httpretty.register_uri(httpretty.GET,
                               GITHUB_ENTREPRISE_RATE_LIMIT,
                               body=rate_limit,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        httpretty.register_uri(httpretty.GET,
                               GITHUB_ENTERPRISE_ISSUES_URL,
                               body=issue,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        httpretty.register_uri(httpretty.POST,
                               GITHUB_ENTERPRISE_API_GRAPHQL_URL,
                               body=events,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        github = GitHubQL("zhquan_example", "repo", ["aaa"], base_url=GITHUB_ENTERPRISE_URL)
        events = [events for events in github.fetch(from_date=None, to_date=None, category=CATEGORY_EVENT)]

        self.assertEqual(len(events), 2)

        event = events[0]
        self.assertEqual(event['origin'], 'https://example.com/zhquan_example/repo')
        self.assertEqual(event['uuid'], '7ae18a45805b971b46dba2874f6deb28e1fb3db1')
        self.assertEqual(event['updated_on'], 1586265768.0)
        self.assertEqual(event['category'], CATEGORY_EVENT)
        self.assertEqual(event['tag'], 'https://example.com/zhquan_example/repo')
        self.assertEqual(event['data']['actor']['login'], 'valeriocos')
        self.assertEqual(event['data']['createdAt'], '2020-04-07T13:22:48Z')
        self.assertEqual(event['data']['eventType'], 'MovedColumnsInProjectEvent')
        self.assertIn('issue', event['data'])

        event = events[1]
        self.assertEqual(event['origin'], 'https://example.com/zhquan_example/repo')
        self.assertEqual(event['uuid'], 'd0d1489be06622577843c91b70cb5543f48be918')
        self.assertEqual(event['updated_on'], 1586265783.0)
        self.assertEqual(event['category'], CATEGORY_EVENT)
        self.assertEqual(event['tag'], 'https://example.com/zhquan_example/repo')
        self.assertEqual(event['data']['actor']['login'], 'valeriocos')
        self.assertEqual(event['data']['createdAt'], '2020-04-07T13:23:03Z')
        self.assertEqual(event['data']['eventType'], 'CrossReferencedEvent')
        self.assertIn('issue', event['data'])

    @httpretty.activate
    def test_fetch_merged_event(self):
        """Test the MergedEvent is fetched properly"""

        events = read_file('data/github/github_events_page_3')
        issue = read_file('data/github/github_issue_1')
        rate_limit = read_file('data/github/rate_limit')

        httpretty.register_uri(httpretty.GET,
                               GITHUB_RATE_LIMIT,
                               body=rate_limit,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUES_URL,
                               body=issue,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        httpretty.register_uri(httpretty.POST,
                               GITHUB_API_GRAPHQL_URL,
                               body=events,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        github = GitHubQL("zhquan_example", "repo", ["aaa"])
        events = [events for events in github.fetch(from_date=None, to_date=None, category=CATEGORY_EVENT)]

        self.assertEqual(len(events), 1)

        event = events[0]
        self.assertEqual(event['origin'], 'https://github.com/zhquan_example/repo')
        self.assertEqual(event['uuid'], '5ad76253ec2e63e9d4431a8550386303012fd6ca')
        self.assertEqual(event['updated_on'], 1602094090.0)
        self.assertEqual(event['category'], CATEGORY_EVENT)
        self.assertEqual(event['tag'], 'https://github.com/zhquan_example/repo')
        self.assertEqual(event['data']['actor']['login'], 'zhquan')
        self.assertEqual(event['data']['createdAt'], '2020-10-07T18:08:10Z')
        self.assertEqual(event['data']['eventType'], 'MergedEvent')
        self.assertIn('issue', event['data'])


class TestGitHubQLBackendArchive(TestCaseBackendArchive):
    """GitHub backend tests using an archive"""

    def setUp(self):
        super().setUp()
        self.backend_write_archive = GitHubQL("zhquan_example", "repo", ["aaa"], archive=self.archive)
        self.backend_read_archive = GitHubQL("zhquan_example", "repo", ["aaa"], archive=self.archive)

    @httpretty.activate
    def test_fetch_events(self):
        """Test whether a list of events is returned from archive"""

        events = read_file('data/github/github_events_page_2')
        issue = read_file('data/github/github_issue_2')
        rate_limit = read_file('data/github/rate_limit')

        httpretty.register_uri(httpretty.GET,
                               GITHUB_RATE_LIMIT,
                               body=rate_limit,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUES_URL,
                               body=issue,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        httpretty.register_uri(httpretty.POST,
                               GITHUB_API_GRAPHQL_URL,
                               body=events,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        self._test_fetch_from_archive(category=CATEGORY_EVENT, from_date=None)


class TestGitHubQLClient(unittest.TestCase):
    """GitHubQL API client tests"""

    @httpretty.activate
    def test_init(self):
        rate_limit = read_file('data/github/rate_limit')
        httpretty.register_uri(httpretty.GET,
                               GITHUB_RATE_LIMIT,
                               body=rate_limit,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        client = GitHubQLClient('zhquan_example', 'repo', ['aaa'])

        self.assertEqual(client.owner, 'zhquan_example')
        self.assertEqual(client.repository, 'repo')
        self.assertEqual(client.max_retries, GitHubQLClient.MAX_RETRIES)
        self.assertEqual(client.sleep_time, GitHubQLClient.DEFAULT_SLEEP_TIME)
        self.assertEqual(client.max_retries, GitHubQLClient.MAX_RETRIES)
        self.assertEqual(client.base_url, 'https://api.github.com')
        self.assertTrue(client.ssl_verify)
        self.assertEqual(client.graphql_url, 'https://api.github.com/graphql')

        client = GitHubQLClient('zhquan_example', 'repo', ['aaa'], base_url=None,
                                sleep_for_rate=False, min_rate_to_sleep=3,
                                sleep_time=20, max_retries=2, max_items=1,
                                archive=None, from_archive=False, ssl_verify=False)
        self.assertEqual(client.owner, 'zhquan_example')
        self.assertEqual(client.repository, 'repo')
        self.assertEqual(client.tokens, ['aaa'])
        self.assertEqual(client.n_tokens, 1)
        self.assertEqual(client.current_token, 'aaa')
        self.assertEqual(client.base_url, GITHUB_API_URL)
        self.assertFalse(client.sleep_for_rate)
        self.assertEqual(client.min_rate_to_sleep, 3)
        self.assertEqual(client.sleep_time, 20)
        self.assertEqual(client.max_retries, 2)
        self.assertEqual(client.max_items, 1)
        self.assertIsNone(client.archive)
        self.assertFalse(client.from_archive)
        self.assertFalse(client.ssl_verify)
        self.assertEqual(client.graphql_url, 'https://api.github.com/graphql')

        client = GitHubQLClient('zhquan_example', 'repo', ['aaa'],
                                min_rate_to_sleep=RateLimitHandler.MAX_RATE_LIMIT + 1)
        self.assertEqual(client.min_rate_to_sleep, RateLimitHandler.MAX_RATE_LIMIT)

        client = GitHubQLClient('zhquan_example', 'repo', ['aaa'],
                                min_rate_to_sleep=RateLimitHandler.MAX_RATE_LIMIT - 1)
        self.assertEqual(client.min_rate_to_sleep, RateLimitHandler.MAX_RATE_LIMIT - 1)

        client = GitHubQLClient('zhquan_example', 'repo', ['aaa'])
        self.assertEqual(client.tokens, ['aaa'])
        self.assertEqual(client.n_tokens, 1)
        self.assertEqual(client.current_token, 'aaa')

        client = GitHubQLClient('zhquan_example', 'repo', ['aaa', 'bbb'])
        self.assertEqual(client.tokens, ['aaa', 'bbb'])
        self.assertEqual(client.n_tokens, 2)

        client = GitHubQLClient('zhquan_example', 'repo', [])
        self.assertEqual(client.tokens, [])
        self.assertEqual(client.current_token, None)
        self.assertEqual(client.n_tokens, 0)

    @httpretty.activate
    def test_events(self):
        """Test whether the GraphQL API call works properly"""

        events = read_file('data/github/github_events_page_2')
        rate_limit = read_file('data/github/rate_limit')

        httpretty.register_uri(httpretty.GET,
                               GITHUB_RATE_LIMIT,
                               body=rate_limit,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.POST,
                               GITHUB_API_GRAPHQL_URL,
                               body=events, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        client = GitHubQLClient("zhquan_example", "repo", ["aaa"], None)
        events = [event for event in client.events(issue_number=1, is_pull=False, from_date=DEFAULT_DATETIME)]
        self.assertEqual(len(events[0]), 2)
        self.assertEqual(httpretty.last_request().headers["Authorization"], "token aaa")

    @httpretty.activate
    def test_pull_request_review_event(self):
        """Test PullRequestReview event GraphQL API call works properly"""

        events = read_file('data/github/github_events_pull_request_review')
        rate_limit = read_file('data/github/rate_limit')

        httpretty.register_uri(httpretty.GET,
                               GITHUB_RATE_LIMIT,
                               body=rate_limit,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.POST,
                               GITHUB_API_GRAPHQL_URL,
                               body=events, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        client = GitHubQLClient("zhquan_example", "repo", ["aaa"], None)
        events = [event for event in client.events(issue_number=1, is_pull=True, from_date=DEFAULT_DATETIME)]
        self.assertEqual(len(events[0]), 3)
        self.assertEqual(events[0][0]['state'], 'CHANGES_REQUESTED')
        self.assertEqual(events[0][1]['state'], 'COMMENTED')
        self.assertEqual(events[0][2]['state'], 'APPROVED')
        self.assertEqual(httpretty.last_request().headers["Authorization"], "token aaa")

    @httpretty.activate
    def test_events_pagination(self):
        """Test whether the GraphQL API call works properly on paginated results"""

        requests = []

        events_page_1 = read_file('data/github/github_events_page_1')
        events_page_2 = read_file('data/github/github_events_page_2')
        bodies_json = [events_page_1, events_page_2]

        def request_callback(method, uri, headers):
            body = bodies_json.pop(0)
            requests.append(httpretty.last_request())
            return 200, headers, body

        rate_limit = read_file('data/github/rate_limit')

        httpretty.register_uri(httpretty.GET,
                               GITHUB_RATE_LIMIT,
                               body=rate_limit,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.POST,
                               GITHUB_API_GRAPHQL_URL,
                               responses=[httpretty.Response(body=request_callback)
                                          for _ in range(2)],
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        client = GitHubQLClient("zhquan_example", "repo", ["aaa"], None)
        events = [event for event in client.events(issue_number=1, is_pull=False, from_date=DEFAULT_DATETIME)]
        self.assertEqual(len(events[0]), 2)
        self.assertEqual(len(events[1]), 2)
        self.assertEqual(httpretty.last_request().headers["Authorization"], "token aaa")

    @httpretty.activate
    def test_events_error(self):
        """Test whether GraphQL API call"""

        events = read_file('data/github/github_events_error')
        rate_limit = read_file('data/github/rate_limit')

        httpretty.register_uri(httpretty.GET,
                               GITHUB_RATE_LIMIT,
                               body=rate_limit,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.POST,
                               GITHUB_API_GRAPHQL_URL,
                               body=events, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        client = GitHubQLClient("zhquan_example", "repo", ["aaa"], None)

        with self.assertLogs(logger, level='ERROR') as cm:
            events = [event for event in client.events(issue_number=1,
                                                       is_pull=False,
                                                       from_date=DEFAULT_DATETIME)]
            self.assertEqual(cm.output[0], 'ERROR:perceval.backends.core.githubql:Events not collected for issue 1'
                                           ' in zhquan_example/repo due to: Parse error on "=" (EQUALS) at [7, 80]')
            self.assertEqual(events, [])
            self.assertEqual(httpretty.last_request().headers["Authorization"], "token aaa")


class TestGitHubQLCommand(unittest.TestCase):
    """GitHubQLCommand unit tests"""

    def test_backend_class(self):
        """Test if the backend class is GitHubQL"""

        self.assertIs(GitHubQLCommand.BACKEND, GitHubQL)


if __name__ == "__main__":
    unittest.main(warnings='ignore')
