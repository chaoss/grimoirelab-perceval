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
#     Alberto Martín <alberto.martin@bitergia.com>
#     Quan Zhou <quan@bitergia.com>
#     Santiago Dueñas <sduenas@bitergia.com>
#     Stephan Barth <stephan.barth@gmail.com>
#     Valerio Cosentino <valcos@bitergia.com>
#     Miguel Ángel Fernández <mafesan@bitergia.com>
#     Jesus M. Gonzalez-Barahona <jgb@gsyc.es>
#     Harshal Mittal <harshalmittal4@gmail.com>
#

import json
import os
import unittest

import httpretty

from grimoirelab_toolkit.datetime import str_to_datetime

from perceval.backend import BackendCommandArgumentParser
from perceval.utils import DEFAULT_DATETIME
from perceval.backends.core.jira import (Jira,
                                         JiraClient,
                                         JiraCommand,
                                         filter_custom_fields,
                                         map_custom_field)
from base import TestCaseBackendArchive


JIRA_SERVER_URL = 'http://example.com'
JIRA_SEARCH_URL = JIRA_SERVER_URL + '/rest/api/2/search'
JIRA_FIELDS_URL = JIRA_SERVER_URL + '/rest/api/2/field'
JIRA_ISSUE_1_COMMENTS_URL = JIRA_SERVER_URL + '/rest/api/2/issue/1/comment'
JIRA_ISSUE_2_COMMENTS_URL = JIRA_SERVER_URL + '/rest/api/2/issue/2/comment'
JIRA_ISSUE_3_COMMENTS_URL = JIRA_SERVER_URL + '/rest/api/2/issue/3/comment'


def read_file(filename, mode='r'):
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), filename), mode) as f:
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
        """Test whether attributes are initialized"""

        jira = Jira(JIRA_SERVER_URL, tag='test',
                    max_results=5)

        self.assertEqual(jira.url, JIRA_SERVER_URL)
        self.assertEqual(jira.origin, JIRA_SERVER_URL)
        self.assertEqual(jira.tag, 'test')
        self.assertEqual(jira.max_results, 5)
        self.assertIsNone(jira.client)
        self.assertTrue(jira.ssl_verify)

        # When tag is empty or None it will be set to
        # the value in url
        jira = Jira(JIRA_SERVER_URL)
        self.assertEqual(jira.url, JIRA_SERVER_URL)
        self.assertEqual(jira.origin, JIRA_SERVER_URL)
        self.assertEqual(jira.tag, JIRA_SERVER_URL)

        jira = Jira(JIRA_SERVER_URL, tag='', ssl_verify=False)
        self.assertEqual(jira.url, JIRA_SERVER_URL)
        self.assertEqual(jira.origin, JIRA_SERVER_URL)
        self.assertEqual(jira.tag, JIRA_SERVER_URL)
        self.assertFalse(jira.ssl_verify)

    def test_has_archiving(self):
        """Test if it returns True when has_archiving is called"""

        self.assertEqual(Jira.has_archiving(), True)

    def test_has_resuming(self):
        """Test if it returns True when has_resuming is called"""

        self.assertEqual(Jira.has_resuming(), True)

    @httpretty.activate
    def test_fetch(self):
        """Test whether a list of issues is returned"""

        requests = []

        bodies_json = [read_file('data/jira/jira_issues_page_1.json'),
                       read_file('data/jira/jira_issues_page_2.json')]
        comment_json = read_file('data/jira/jira_comments_issue_page_2.json')
        empty_comment = read_file('data/jira/jira_comments_issue_empty.json')

        body = read_file('data/jira/jira_fields.json')

        def request_callback(method, uri, headers):
            body = bodies_json.pop(0)
            requests.append(httpretty.last_request())
            return 200, headers, body

        httpretty.register_uri(httpretty.GET,
                               JIRA_SEARCH_URL,
                               responses=[httpretty.Response(body=request_callback)
                                          for _ in range(2)])

        httpretty.register_uri(httpretty.GET,
                               JIRA_ISSUE_1_COMMENTS_URL,
                               body=empty_comment,
                               status=200)

        httpretty.register_uri(httpretty.GET,
                               JIRA_ISSUE_2_COMMENTS_URL,
                               body=comment_json,
                               status=200)

        httpretty.register_uri(httpretty.GET,
                               JIRA_ISSUE_3_COMMENTS_URL,
                               body=empty_comment,
                               status=200)

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
                'startAt': ['0'],
                'maxResults': ['100']
            },
            {
                'expand': ['renderedFields,transitions,operations,changelog'],
                'jql': ['updated > 0 order by updated asc'],
                'startAt': ['2'],
                'maxResults': ['100']
            }
        ]

        for i in range(len(expected_req)):
            self.assertEqual(requests[i].method, 'GET')
            self.assertRegex(requests[i].path, '/rest/api/2/search')
            self.assertDictEqual(requests[i].querystring, expected_req[i])

        self.assertEqual(len(issues), 3)

        issue = issues[0]
        self.assertEqual(issue['origin'], 'http://example.com')
        self.assertEqual(issue['uuid'], '6a7ba2a01aee56603b9d8a5f6b40c843fc089b2f')
        self.assertEqual(issue['updated_on'], 1457015567)
        self.assertEqual(issue['category'], 'issue')
        self.assertEqual(issue['tag'], 'http://example.com')
        self.assertEqual(issue['data']['key'], 'HELP-6043')
        self.assertEqual(issue['data']['fields']['issuetype']['name'], 'extRequest')
        self.assertEqual(issue['data']['fields']['creator']['name'], 'user2')
        self.assertEqual(issue['data']['fields']['assignee']['name'], 'user1')
        self.assertEqual(issue['data']['fields']['assignee']['name'], 'user1')
        self.assertEqual(issue['data']['fields']['assignee']['name'], 'user1')
        self.assertEqual(issue['data']['fields']['assignee']['name'], 'user1')
        self.assertEqual(issue['data']['fields']['customfield_10301']['id'],
                         custom_fields['customfield_10301']['id'])
        self.assertEqual(issue['data']['fields']['customfield_10301']['name'],
                         custom_fields['customfield_10301']['name'])
        self.assertEqual(issue['data']['fields']['customfield_10400']['id'],
                         custom_fields['customfield_10400']['id'])
        self.assertEqual(issue['data']['fields']['customfield_10400']['name'],
                         custom_fields['customfield_10400']['name'])
        self.assertEqual(issue['data']['fields']['customfield_10600']['id'],
                         custom_fields['customfield_10600']['id'])
        self.assertEqual(issue['data']['fields']['customfield_10600']['name'],
                         custom_fields['customfield_10600']['name'])
        self.assertEqual(issue['data']['fields']['customfield_10603']['id'],
                         custom_fields['customfield_10603']['id'])
        self.assertEqual(issue['data']['fields']['customfield_10603']['name'],
                         custom_fields['customfield_10603']['name'])
        self.assertEqual(issue['data']['comments_data'], [])

        issue = issues[1]
        self.assertEqual(issue['origin'], 'http://example.com')
        self.assertEqual(issue['uuid'], '3c3d67925b108a37f88cc6663f7f7dd493fa818c')
        self.assertEqual(issue['updated_on'], 1457015417)
        self.assertEqual(issue['category'], 'issue')
        self.assertEqual(issue['tag'], 'http://example.com')
        self.assertEqual(issue['data']['key'], 'HELP-6042')
        self.assertEqual(issue['data']['fields']['issuetype']['name'], 'extRequest')
        self.assertEqual(issue['data']['fields']['creator']['name'], 'user2')
        self.assertEqual(issue['data']['fields']['assignee']['name'], 'user1')
        self.assertEqual(issue['data']['fields']['customfield_10301']['id'],
                         custom_fields['customfield_10301']['id'])
        self.assertEqual(issue['data']['fields']['customfield_10301']['name'],
                         custom_fields['customfield_10301']['name'])
        self.assertEqual(issue['data']['fields']['customfield_10400']['id'],
                         custom_fields['customfield_10400']['id'])
        self.assertEqual(issue['data']['fields']['customfield_10400']['name'],
                         custom_fields['customfield_10400']['name'])
        self.assertEqual(issue['data']['fields']['customfield_10600']['id'],
                         custom_fields['customfield_10600']['id'])
        self.assertEqual(issue['data']['fields']['customfield_10600']['name'],
                         custom_fields['customfield_10600']['name'])
        self.assertEqual(issue['data']['fields']['customfield_10603']['id'],
                         custom_fields['customfield_10603']['id'])
        self.assertEqual(issue['data']['fields']['customfield_10603']['name'],
                         custom_fields['customfield_10603']['name'])
        self.assertEqual(len(issue['data']['comments_data']), 2)
        self.assertEqual(issue['data']['comments_data'][0]['author']['displayName'], 'Tim Monks')
        self.assertEqual(issue['data']['comments_data'][1]['author']['displayName'], 'Scott Monks')

        issue = issues[2]
        self.assertEqual(issue['origin'], 'http://example.com')
        self.assertEqual(issue['uuid'], '1c7765e2a5d27495cf389f5f951c544693c4655f')
        self.assertEqual(issue['updated_on'], 1457006245)
        self.assertEqual(issue['category'], 'issue')
        self.assertEqual(issue['tag'], 'http://example.com')
        self.assertEqual(issue['data']['key'], 'HELP-6041')
        self.assertEqual(issue['data']['fields']['issuetype']['name'], 'extRequest')
        self.assertEqual(issue['data']['fields']['creator']['name'], 'user2')
        self.assertEqual(issue['data']['fields']['assignee']['name'], 'user3')
        self.assertEqual(issue['data']['fields']['customfield_10301']['id'],
                         custom_fields['customfield_10301']['id'])
        self.assertEqual(issue['data']['fields']['customfield_10301']['name'],
                         custom_fields['customfield_10301']['name'])
        self.assertEqual(issue['data']['fields']['customfield_10400']['id'],
                         custom_fields['customfield_10400']['id'])
        self.assertEqual(issue['data']['fields']['customfield_10400']['name'],
                         custom_fields['customfield_10400']['name'])
        self.assertEqual(issue['data']['fields']['customfield_10600']['id'],
                         custom_fields['customfield_10600']['id'])
        self.assertEqual(issue['data']['fields']['customfield_10600']['name'],
                         custom_fields['customfield_10600']['name'])
        self.assertEqual(issue['data']['fields']['customfield_10603']['id'],
                         custom_fields['customfield_10603']['id'])
        self.assertEqual(issue['data']['fields']['customfield_10603']['name'],
                         custom_fields['customfield_10603']['name'])
        self.assertEqual(issue['data']['comments_data'], [])

    @httpretty.activate
    def test_search_fields(self):
        """Test whether the search_fields is properly set"""

        bodies_json = [read_file('data/jira/jira_issues_page_1.json'),
                       read_file('data/jira/jira_issues_page_2.json')]
        comment_json = read_file('data/jira/jira_comments_issue_page_2.json')
        empty_comment = read_file('data/jira/jira_comments_issue_empty.json')

        body = read_file('data/jira/jira_fields.json')

        def request_callback(method, uri, headers):
            body = bodies_json.pop(0)
            return 200, headers, body

        httpretty.register_uri(httpretty.GET,
                               JIRA_SEARCH_URL,
                               responses=[httpretty.Response(body=request_callback)
                                          for _ in range(2)])

        httpretty.register_uri(httpretty.GET,
                               JIRA_ISSUE_1_COMMENTS_URL,
                               body=empty_comment,
                               status=200)

        httpretty.register_uri(httpretty.GET,
                               JIRA_ISSUE_2_COMMENTS_URL,
                               body=comment_json,
                               status=200)

        httpretty.register_uri(httpretty.GET,
                               JIRA_ISSUE_3_COMMENTS_URL,
                               body=empty_comment,
                               status=200)

        httpretty.register_uri(httpretty.GET,
                               JIRA_FIELDS_URL,
                               body=body, status=200)

        jira = Jira(JIRA_SERVER_URL)
        issues = [issue for issue in jira.fetch()]

        issue = issues[0]
        self.assertEqual(issue['origin'], 'http://example.com')
        self.assertEqual(issue['uuid'], '6a7ba2a01aee56603b9d8a5f6b40c843fc089b2f')
        self.assertEqual(issue['updated_on'], 1457015567)
        self.assertEqual(issue['category'], 'issue')
        self.assertEqual(issue['tag'], 'http://example.com')
        self.assertEqual(jira.metadata_id(issue['data']), issue['search_fields']['item_id'])
        self.assertEqual(issue['data']['fields']['project']['id'], '10841')
        self.assertEqual(issue['data']['fields']['project']['id'], issue['search_fields']['project_id'])
        self.assertEqual(issue['data']['fields']['project']['key'], 'HELP')
        self.assertEqual(issue['data']['fields']['project']['key'], issue['search_fields']['project_key'])
        self.assertEqual(issue['data']['fields']['project']['name'], 'Help-Desk')
        self.assertEqual(issue['data']['fields']['project']['name'], issue['search_fields']['project_name'])
        self.assertEqual(issue['data']['key'], 'HELP-6043')
        self.assertEqual(issue['data']['key'], issue['search_fields']['issue_key'])

        issue = issues[1]
        self.assertEqual(issue['origin'], 'http://example.com')
        self.assertEqual(issue['uuid'], '3c3d67925b108a37f88cc6663f7f7dd493fa818c')
        self.assertEqual(issue['updated_on'], 1457015417)
        self.assertEqual(issue['category'], 'issue')
        self.assertEqual(issue['tag'], 'http://example.com')
        self.assertEqual(jira.metadata_id(issue['data']), issue['search_fields']['item_id'])
        self.assertEqual(issue['data']['fields']['project']['id'], '10841')
        self.assertEqual(issue['data']['fields']['project']['id'], issue['search_fields']['project_id'])
        self.assertEqual(issue['data']['fields']['project']['key'], 'HELP')
        self.assertEqual(issue['data']['fields']['project']['key'], issue['search_fields']['project_key'])
        self.assertEqual(issue['data']['fields']['project']['name'], 'Help-Desk')
        self.assertEqual(issue['data']['fields']['project']['name'], issue['search_fields']['project_name'])
        self.assertEqual(issue['data']['key'], 'HELP-6042')
        self.assertEqual(issue['data']['key'], issue['search_fields']['issue_key'])

        issue = issues[2]
        self.assertEqual(issue['origin'], 'http://example.com')
        self.assertEqual(issue['uuid'], '1c7765e2a5d27495cf389f5f951c544693c4655f')
        self.assertEqual(issue['updated_on'], 1457006245)
        self.assertEqual(issue['category'], 'issue')
        self.assertEqual(issue['tag'], 'http://example.com')
        self.assertEqual(jira.metadata_id(issue['data']), issue['search_fields']['item_id'])
        self.assertEqual(issue['data']['fields']['project']['id'], '10843')
        self.assertEqual(issue['data']['fields']['project']['id'], issue['search_fields']['project_id'])
        self.assertEqual(issue['data']['fields']['project']['key'], 'HELP')
        self.assertEqual(issue['data']['fields']['project']['key'], issue['search_fields']['project_key'])
        self.assertEqual(issue['data']['fields']['project']['name'], 'Help-Desk')
        self.assertEqual(issue['data']['fields']['project']['name'], issue['search_fields']['project_name'])
        self.assertEqual(issue['data']['key'], 'HELP-6041')
        self.assertEqual(issue['data']['key'], issue['search_fields']['issue_key'])

    @httpretty.activate
    def test_fetch_from_date(self):
        """Test whether a list of issues is returned from a given date"""

        from_date = str_to_datetime('2015-01-01')

        bodies_json = read_file('data/jira/jira_issues_page_2.json')
        empty_comment = read_file('data/jira/jira_comments_issue_empty.json')

        body = read_file('data/jira/jira_fields.json')

        httpretty.register_uri(httpretty.GET,
                               JIRA_SEARCH_URL,
                               body=bodies_json, status=200)

        httpretty.register_uri(httpretty.GET,
                               JIRA_FIELDS_URL,
                               body=body, status=200)

        httpretty.register_uri(httpretty.GET,
                               JIRA_ISSUE_3_COMMENTS_URL,
                               body=empty_comment,
                               status=200)

        jira = Jira(JIRA_SERVER_URL)

        issues = [issue for issue in jira.fetch(from_date=from_date)]

        self.assertEqual(len(issues), 1)

        issue = issues[0]
        self.assertEqual(issue['origin'], 'http://example.com')
        self.assertEqual(issue['uuid'], '1c7765e2a5d27495cf389f5f951c544693c4655f')
        self.assertEqual(issue['updated_on'], 1457006245)
        self.assertEqual(issue['category'], 'issue')
        self.assertEqual(issue['tag'], 'http://example.com')
        self.assertEqual(issue['data']['comments_data'], [])

        requests = httpretty.HTTPretty.latest_requests
        request = requests[-2]
        expected_req = {
            'expand': ['renderedFields,transitions,operations,changelog'],
            'jql': ['updated > 1420070400000 order by updated asc'],
            'startAt': ['0'],
            'maxResults': ['100']
        }

        self.assertEqual(request.method, 'GET')
        self.assertRegex(request.path, '/rest/api/2/search')
        self.assertDictEqual(request.querystring, expected_req)

        request = requests[-1]
        expected_req = {
            'jql': ['updated > 0 order by updated asc'],
            'startAt': ['0'],
            'maxResults': ['100']
        }

        self.assertEqual(request.method, 'GET')
        self.assertRegex(request.path, '/rest/api/2/issue/3/comment')
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
            'startAt': ['0'],
            'maxResults': ['100']
        }

        self.assertEqual(len(issues), 0)

        request = httpretty.last_request()
        self.assertEqual(request.method, 'GET')
        self.assertRegex(request.path, '/rest/api/2/search')
        self.assertDictEqual(request.querystring, expected_req)


class TestJiraBackendArchive(TestCaseBackendArchive):
    """Jira backend tests using an archive"""

    def setUp(self):
        super().setUp()
        self.backend_write_archive = Jira(JIRA_SERVER_URL, user="test", password="test", archive=self.archive)
        self.backend_read_archive = Jira(JIRA_SERVER_URL, archive=self.archive)

    @httpretty.activate
    def test_fetch_from_archive(self):
        """Test whether a list of issues is returned from an archive"""

        requests = []

        bodies_json = [read_file('data/jira/jira_issues_page_1.json'),
                       read_file('data/jira/jira_issues_page_2.json')]
        comment_json = read_file('data/jira/jira_comments_issue_page_2.json')
        empty_comment = read_file('data/jira/jira_comments_issue_empty.json')
        body = read_file('data/jira/jira_fields.json')

        def request_callback(method, uri, headers):
            body = bodies_json.pop(0)
            requests.append(httpretty.last_request())
            return 200, headers, body

        httpretty.register_uri(httpretty.GET,
                               JIRA_SEARCH_URL,
                               responses=[httpretty.Response(body=request_callback)
                                          for _ in range(2)])

        httpretty.register_uri(httpretty.GET,
                               JIRA_ISSUE_1_COMMENTS_URL,
                               body=empty_comment,
                               status=200)

        httpretty.register_uri(httpretty.GET,
                               JIRA_ISSUE_2_COMMENTS_URL,
                               body=comment_json,
                               status=200)

        httpretty.register_uri(httpretty.GET,
                               JIRA_ISSUE_3_COMMENTS_URL,
                               body=empty_comment,
                               status=200)

        httpretty.register_uri(httpretty.GET,
                               JIRA_FIELDS_URL,
                               body=body, status=200)

        self._test_fetch_from_archive(from_date=None)

        self.assertEqual(("test", "test"), self.backend_write_archive.client.session.auth)
        self.assertIsNone(self.backend_read_archive.client.session.auth)

    @httpretty.activate
    def test_fetch_from_date_from_archive(self):
        """Test whether a list of issues is returned from a given date from archive"""

        bodies_json = read_file('data/jira/jira_issues_page_2.json')
        empty_comment = read_file('data/jira/jira_comments_issue_empty.json')

        body = read_file('data/jira/jira_fields.json')

        httpretty.register_uri(httpretty.GET,
                               JIRA_SEARCH_URL,
                               body=bodies_json, status=200)

        httpretty.register_uri(httpretty.GET,
                               JIRA_ISSUE_3_COMMENTS_URL,
                               body=empty_comment,
                               status=200)

        httpretty.register_uri(httpretty.GET,
                               JIRA_FIELDS_URL,
                               body=body, status=200)

        from_date = str_to_datetime('2015-01-01')
        self._test_fetch_from_archive(from_date=from_date)

    @httpretty.activate
    def test_fetch_empty_from_archive(self):
        """Test whether the fetch from archive works when no issues are present"""

        bodies_json = read_file('data/jira/jira_issues_page_empty.json')

        body = read_file('data/jira/jira_fields.json')

        httpretty.register_uri(httpretty.GET,
                               JIRA_SEARCH_URL,
                               body=bodies_json, status=200)

        httpretty.register_uri(httpretty.GET,
                               JIRA_FIELDS_URL,
                               body=body, status=200)

        self._test_fetch_from_archive(from_date=None)


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

        self.assertEqual(result[0]["id"], "1")
        self.assertEqual(result[0]["key"], "HELP-6043")
        self.assertEqual(result[0]["self"], "https://jira.fiware.org/rest/api/2/issue/35851")
        self.assertEqual(result[0]["expand"],
                         "operations,editmeta,changelog,transitions,renderedFields")
        self.assertEqual(len(result[0]["fields"]), 27)
        self.assertDictEqual(result[0]["fields"], parse[0]["fields"])

        self.assertEqual(result[1]["id"], "2")
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
                            ssl_verify=True, cert=None, max_results=100)

        self.assertEqual(client.base_url, 'http://example.com')
        self.assertEqual(client.project, 'perceval')
        self.assertEqual(client.user, 'user')
        self.assertEqual(client.password, 'password')
        self.assertTrue(client.ssl_verify)
        self.assertIsNone(client.cert)
        self.assertEqual(client.max_results, 100)

        client = JiraClient(url='http://example.com', project='perceval',
                            user='user', password='password',
                            ssl_verify=False, cert="cert", max_results=100)

        self.assertEqual(client.base_url, 'http://example.com')
        self.assertEqual(client.project, 'perceval')
        self.assertEqual(client.user, 'user')
        self.assertEqual(client.password, 'password')
        self.assertFalse(client.ssl_verify)
        self.assertEqual(client.cert, "cert")
        self.assertEqual(client.max_results, 100)

        client = JiraClient(url='http://example.com', project='perceval',
                            user='user', password=None, api_token='token',
                            ssl_verify=False, cert="cert", max_results=100)

        self.assertEqual(client.base_url, 'http://example.com')
        self.assertEqual(client.project, 'perceval')
        self.assertEqual(client.user, 'user')
        self.assertEqual(client.password, None)
        self.assertEqual(client.api_token, 'token')

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
            return 200, headers, body

        httpretty.register_uri(httpretty.GET,
                               JIRA_SEARCH_URL,
                               responses=[httpretty.Response(body=request_callback)
                                          for _ in range(2)])

        client = JiraClient(url='http://example.com', project='perceval',
                            user='user', password='password',
                            ssl_verify=False, cert=None, max_results=2)

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
    def test_get_comments(self):
        """Test get comments API call"""

        bodies_json = [read_file('data/jira/jira_comments_issue_page_1.json'),
                       read_file('data/jira/jira_comments_issue_page_2.json')]

        bodies = bodies_json[:]
        bodies = list(bodies_json)

        def request_callback(method, uri, headers):
            body = bodies.pop(0)
            return 200, headers, body

        httpretty.register_uri(httpretty.GET,
                               JIRA_ISSUE_1_COMMENTS_URL,
                               responses=[httpretty.Response(body=request_callback)
                                          for _ in range(2)])

        client = JiraClient(url='http://example.com', project='perceval',
                            user='user', password='password',
                            ssl_verify=False, cert=None, max_results=2)

        pages = [page for page in client.get_comments("1")]

        expected_req = [
            {
                'jql': ['project = perceval AND updated > 0 order by updated asc'],
                'maxResults': ['2'],
                'startAt': ['0']
            },
            {
                'jql': ['project = perceval AND updated > 0 order by updated asc'],
                'maxResults': ['2'],
                'startAt': ['2']
            }
        ]

        self.assertEqual(len(pages), 2)

        requests = httpretty.HTTPretty.latest_requests
        request = requests[0]
        self.assertEqual(request.method, 'GET')
        self.assertRegex(request.path, '/rest/api/2/issue/1/comment')
        self.assertDictEqual(request.querystring, expected_req[0])

        request = requests[1]
        self.assertEqual(request.method, 'GET')
        self.assertRegex(request.path, '/rest/api/2/issue/1/comment')
        self.assertDictEqual(request.querystring, expected_req[1])

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
                            ssl_verify=False, cert=None, max_results=None)

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
                            ssl_verify=False, cert=None, max_results=1)

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
        self.assertEqual(parser._backend, Jira)

        args = ['--backend-user', 'jsmith',
                '--backend-password', '1234',
                '--project', 'Perceval Jira',
                '--cert', 'aaaa',
                '--max-results', '1',
                '--tag', 'test',
                '--no-archive',
                '--from-date', '1970-01-01',
                JIRA_SERVER_URL]

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.user, 'jsmith')
        self.assertEqual(parsed_args.password, '1234')
        self.assertEqual(parsed_args.project, 'Perceval Jira')
        self.assertTrue(parsed_args.ssl_verify)
        self.assertEqual(parsed_args.cert, 'aaaa')
        self.assertEqual(parsed_args.max_results, 1)
        self.assertEqual(parsed_args.tag, 'test')
        self.assertTrue(parsed_args.no_archive)
        self.assertEqual(parsed_args.from_date, DEFAULT_DATETIME)
        self.assertEqual(parsed_args.url, JIRA_SERVER_URL)

        args = ['--backend-user', 'jsmith',
                '--backend-password', '1234',
                '--project', 'Perceval Jira',
                '--no-ssl-verify',
                '--cert', 'aaaa',
                '--max-results', '1',
                '--tag', 'test',
                '--no-archive',
                '--from-date', '1970-01-01',
                JIRA_SERVER_URL]

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.user, 'jsmith')
        self.assertEqual(parsed_args.password, '1234')
        self.assertEqual(parsed_args.project, 'Perceval Jira')
        self.assertFalse(parsed_args.ssl_verify)
        self.assertEqual(parsed_args.cert, 'aaaa')
        self.assertEqual(parsed_args.max_results, 1)
        self.assertEqual(parsed_args.tag, 'test')
        self.assertTrue(parsed_args.no_archive)
        self.assertEqual(parsed_args.from_date, DEFAULT_DATETIME)
        self.assertEqual(parsed_args.url, JIRA_SERVER_URL)

        args = ['--backend-user', 'jsmith',
                '--api-token', 'token_xxx',
                JIRA_SERVER_URL]

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.user, 'jsmith')
        self.assertEqual(parsed_args.api_token, 'token_xxx')


if __name__ == '__main__':
    unittest.main(warnings='ignore')
