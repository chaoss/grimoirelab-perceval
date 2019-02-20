#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2015-2019 Bitergia
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
#     Assad Montasser <assad.montasser@ow2.org>
#     Valerio Cosentino <valcos@bitergia.com>
#

import copy
import datetime
import json
import os
import time
import unittest

import httpretty
import pkg_resources
import requests

pkg_resources.declare_namespace('perceval.backends')

from grimoirelab_toolkit.datetime import datetime_utcnow
from perceval.backend import BackendCommandArgumentParser
from perceval.errors import RateLimitError
from perceval.utils import DEFAULT_DATETIME
from perceval.backends.core.gitlab import (logger,
                                           GitLab,
                                           GitLabCommand,
                                           GitLabClient,
                                           CATEGORY_ISSUE,
                                           CATEGORY_MERGE_REQUEST,
                                           MAX_RETRIES,
                                           DEFAULT_SLEEP_TIME)
from base import TestCaseBackendArchive

GITLAB_URL = "https://gitlab.com"
GITLAB_API_URL = GITLAB_URL + "/api/v4"
GITLAB_URL_PROJECT = GITLAB_API_URL + "/projects/fdroid%2Ffdroiddata"
GITLAB_ISSUES_URL = GITLAB_API_URL + "/projects/fdroid%2Ffdroiddata/issues"
GITLAB_MERGES_URL = GITLAB_API_URL + "/projects/fdroid%2Ffdroiddata/merge_requests"

GITLAB_ENTERPRISE_URL = "https://gitlab.ow2.org"
GITLAB_ENTERPRISE_API_URL = GITLAB_ENTERPRISE_URL + "/api/v4"
GITLAB_ENTERPRISE_URL_PROJECT = GITLAB_ENTERPRISE_API_URL + "/projects/am%2Ftest"
GITLAB_ENTERPRISE_ISSUES_URL = GITLAB_ENTERPRISE_API_URL + "/projects/am%2Ftest/issues"
GITLAB_ENTERPRISE_MERGES_URL = GITLAB_ENTERPRISE_API_URL + "/projects/am%2Ftest/merge_requests"


def setup_http_server(url_project, issues_url, merges_url, rate_limit_headers=None):
    project = read_file('data/gitlab/project')
    page_issues_1 = read_file('data/gitlab/issue_page_1')
    page_issues_2 = read_file('data/gitlab/issue_page_2')
    page_merges_1 = read_file('data/gitlab/merge_page_1')
    page_merges_2 = read_file('data/gitlab/merge_page_2')

    if not rate_limit_headers:
        rate_limit_headers = {}

    httpretty.register_uri(httpretty.GET,
                           url_project,
                           body=project,
                           status=200,
                           forcing_headers=rate_limit_headers)

    # issue pagination
    pagination_issue_header = {'Link': '<' + issues_url +
                               '/?&page=2>; rel="next", <' + issues_url +
                               '/?&page=3>; rel="last"'}

    pagination_merge_header = {'Link': '<' + merges_url +
                                       '/?&page=2>; rel="next", <' + merges_url +
                                       '/?&page=3>; rel="last"'}

    # merges paginatition
    pagination_issue_header.update(rate_limit_headers)
    httpretty.register_uri(httpretty.GET,
                           issues_url,
                           body=page_issues_1,
                           status=200,
                           forcing_headers=pagination_issue_header)

    httpretty.register_uri(httpretty.GET,
                           issues_url + '/?&page=2',
                           body=page_issues_2,
                           status=200,
                           forcing_headers=rate_limit_headers)

    pagination_merge_header.update(rate_limit_headers)
    httpretty.register_uri(httpretty.GET,
                           merges_url,
                           body=page_merges_1,
                           status=200,
                           forcing_headers=pagination_merge_header)

    httpretty.register_uri(httpretty.GET,
                           merges_url + '/?&page=2',
                           body=page_merges_2,
                           status=200,
                           forcing_headers=rate_limit_headers)

    notes_1 = read_file('data/gitlab/notes_1')
    notes_2 = read_file('data/gitlab/notes_2')
    notes_3 = read_file('data/gitlab/notes_3')
    notes_4 = read_file('data/gitlab/notes_4')

    # issue notes
    httpretty.register_uri(httpretty.GET,
                           issues_url + "/1/notes",
                           body=notes_1,
                           status=200,
                           forcing_headers=rate_limit_headers)

    httpretty.register_uri(httpretty.GET,
                           issues_url + "/2/notes",
                           body=notes_2,
                           status=200,
                           forcing_headers=rate_limit_headers)

    httpretty.register_uri(httpretty.GET,
                           issues_url + "/3/notes",
                           body=notes_3,
                           status=200,
                           forcing_headers=rate_limit_headers)

    httpretty.register_uri(httpretty.GET,
                           issues_url + "/4/notes",
                           body=notes_4,
                           status=200,
                           forcing_headers=rate_limit_headers)

    # merge notes
    httpretty.register_uri(httpretty.GET,
                           merges_url + "/1/notes",
                           body=notes_1,
                           status=200,
                           forcing_headers=rate_limit_headers)

    httpretty.register_uri(httpretty.GET,
                           merges_url + "/2/notes",
                           body=notes_2,
                           status=200,
                           forcing_headers=rate_limit_headers)

    httpretty.register_uri(httpretty.GET,
                           merges_url + "/3/notes",
                           body=notes_3,
                           status=200,
                           forcing_headers=rate_limit_headers)

    emoji = read_file('data/gitlab/emoji')
    empty_emoji = read_file('data/gitlab/empty_emoji')

    # merge details
    merge_1 = read_file('data/gitlab/merge_1')
    merge_2 = read_file('data/gitlab/merge_2')
    merge_3 = read_file('data/gitlab/merge_3')

    httpretty.register_uri(httpretty.GET,
                           merges_url + "/1",
                           body=merge_1,
                           status=200,
                           forcing_headers=rate_limit_headers)

    httpretty.register_uri(httpretty.GET,
                           merges_url + "/2",
                           body=merge_2,
                           status=200,
                           forcing_headers=rate_limit_headers)

    httpretty.register_uri(httpretty.GET,
                           merges_url + "/3",
                           body=merge_3,
                           status=200,
                           forcing_headers=rate_limit_headers)

    # merge versions
    merge_1_versions = read_file('data/gitlab/merge_1_versions')
    merge_2_versions = read_file('data/gitlab/merge_2_versions')
    merge_3_versions = read_file('data/gitlab/merge_3_versions')

    httpretty.register_uri(httpretty.GET,
                           merges_url + "/1/versions",
                           body=merge_1_versions,
                           status=200,
                           forcing_headers=rate_limit_headers)

    httpretty.register_uri(httpretty.GET,
                           merges_url + "/2/versions",
                           body=merge_2_versions,
                           status=200,
                           forcing_headers=rate_limit_headers)

    httpretty.register_uri(httpretty.GET,
                           merges_url + "/3/versions",
                           body=merge_3_versions,
                           status=200,
                           forcing_headers=rate_limit_headers)

    # merge version details
    merge_1_version_1 = read_file('data/gitlab/merge_1_version_1')
    merge_1_version_2 = read_file('data/gitlab/merge_1_version_2')
    merge_2_version_1 = read_file('data/gitlab/merge_2_version_1')
    merge_3_version_1 = read_file('data/gitlab/merge_3_version_1')

    httpretty.register_uri(httpretty.GET,
                           merges_url + "/1/versions/1",
                           body=merge_1_version_1,
                           status=200,
                           forcing_headers=rate_limit_headers)

    httpretty.register_uri(httpretty.GET,
                           merges_url + "/1/versions/2",
                           body=merge_1_version_2,
                           status=200,
                           forcing_headers=rate_limit_headers)

    httpretty.register_uri(httpretty.GET,
                           merges_url + "/2/versions/3",
                           body=merge_2_version_1,
                           status=200,
                           forcing_headers=rate_limit_headers)

    httpretty.register_uri(httpretty.GET,
                           merges_url + "/3/versions/4",
                           body=merge_3_version_1,
                           status=200,
                           forcing_headers=rate_limit_headers)

    # issue emojis
    httpretty.register_uri(httpretty.GET,
                           issues_url + "/1/award_emoji",
                           body=emoji,
                           status=200,
                           forcing_headers=rate_limit_headers)

    httpretty.register_uri(httpretty.GET,
                           issues_url + "/2/award_emoji",
                           body=empty_emoji,
                           status=200,
                           forcing_headers=rate_limit_headers)

    httpretty.register_uri(httpretty.GET,
                           issues_url + "/3/award_emoji",
                           body=emoji,
                           status=200,
                           forcing_headers=rate_limit_headers)

    httpretty.register_uri(httpretty.GET,
                           issues_url + "/4/award_emoji",
                           body=empty_emoji,
                           status=200,
                           forcing_headers=rate_limit_headers)

    httpretty.register_uri(httpretty.GET,
                           issues_url + "/1/notes/1/award_emoji",
                           body=emoji,
                           status=200,
                           forcing_headers=rate_limit_headers)

    httpretty.register_uri(httpretty.GET,
                           issues_url + "/1/notes/2/award_emoji",
                           body=empty_emoji,
                           status=200,
                           forcing_headers=rate_limit_headers)

    httpretty.register_uri(httpretty.GET,
                           issues_url + "/2/notes/1/award_emoji",
                           body=empty_emoji,
                           status=200,
                           forcing_headers=rate_limit_headers)

    httpretty.register_uri(httpretty.GET,
                           issues_url + "/3/notes/1/award_emoji",
                           body=empty_emoji,
                           status=200,
                           forcing_headers=rate_limit_headers)

    httpretty.register_uri(httpretty.GET,
                           issues_url + "/4/notes/1/award_emoji",
                           body=empty_emoji,
                           status=200,
                           forcing_headers=rate_limit_headers)

    # merge requests emojis
    httpretty.register_uri(httpretty.GET,
                           merges_url + "/1/award_emoji",
                           body=emoji,
                           status=200,
                           forcing_headers=rate_limit_headers)

    httpretty.register_uri(httpretty.GET,
                           merges_url + "/2/award_emoji",
                           body=empty_emoji,
                           status=200,
                           forcing_headers=rate_limit_headers)

    httpretty.register_uri(httpretty.GET,
                           merges_url + "/3/award_emoji",
                           body=emoji,
                           status=200,
                           forcing_headers=rate_limit_headers)

    httpretty.register_uri(httpretty.GET,
                           merges_url + "/1/notes/1/award_emoji",
                           body=emoji,
                           status=200,
                           forcing_headers=rate_limit_headers)

    httpretty.register_uri(httpretty.GET,
                           merges_url + "/1/notes/2/award_emoji",
                           body=empty_emoji,
                           status=200,
                           forcing_headers=rate_limit_headers)

    httpretty.register_uri(httpretty.GET,
                           merges_url + "/2/notes/1/award_emoji",
                           body=empty_emoji,
                           status=200,
                           forcing_headers=rate_limit_headers)

    httpretty.register_uri(httpretty.GET,
                           merges_url + "/3/notes/1/award_emoji",
                           body=empty_emoji,
                           status=200,
                           forcing_headers=rate_limit_headers)


def read_file(filename, mode='r'):
    with open(os.path.join(
            os.path.dirname(os.path.abspath(__file__)), filename), mode) as f:
        content = f.read()
    return content


class TestGitLabBackend(unittest.TestCase):
    """ GitLab backend tests """

    @httpretty.activate
    def test_initialization(self):
        """Test whether attributes are initializated"""

        setup_http_server(GITLAB_URL_PROJECT, GITLAB_ISSUES_URL, GITLAB_MERGES_URL,
                          rate_limit_headers={'RateLimit-Remaining': '20'})

        gitlab = GitLab('fdroid', 'fdroiddata', api_token='aaa', tag='test')

        self.assertEqual(gitlab.owner, 'fdroid')
        self.assertEqual(gitlab.repository, 'fdroiddata')
        self.assertEqual(gitlab.origin, GITLAB_URL + '/fdroid/fdroiddata')
        self.assertEqual(gitlab.tag, 'test')
        self.assertIsNone(gitlab.client)
        self.assertIsNone(gitlab.blacklist_ids)
        self.assertEqual(gitlab.max_retries, MAX_RETRIES)
        self.assertEqual(gitlab.sleep_time, DEFAULT_SLEEP_TIME)

        # When tag is empty or None it will be set to
        # the value in origin
        gitlab = GitLab('fdroid', 'fdroiddata', api_token='aaa', max_retries=10,
                        sleep_time=100, blacklist_ids=[1, 2, 3])

        self.assertEqual(gitlab.owner, 'fdroid')
        self.assertEqual(gitlab.repository, 'fdroiddata')
        self.assertEqual(gitlab.origin, GITLAB_URL + '/fdroid/fdroiddata')
        self.assertEqual(gitlab.tag, GITLAB_URL + '/fdroid/fdroiddata')
        self.assertIsNone(gitlab.client)
        self.assertEqual(gitlab.max_retries, 10)
        self.assertEqual(gitlab.sleep_time, 100)
        self.assertEqual(gitlab.blacklist_ids, [1, 2, 3])

    @httpretty.activate
    def test_initialization_entreprise(self):
        """Test whether attributes are initialized for the entreprise version"""

        setup_http_server(GITLAB_ENTERPRISE_URL_PROJECT,
                          GITLAB_ENTERPRISE_ISSUES_URL,
                          GITLAB_ENTERPRISE_MERGES_URL)

        gitlab = GitLab('am', 'test', base_url=GITLAB_ENTERPRISE_URL, tag='')

        self.assertEqual(gitlab.owner, 'am')
        self.assertEqual(gitlab.repository, 'test')
        self.assertEqual(gitlab.origin, GITLAB_ENTERPRISE_URL + "/am/test")
        self.assertEqual(gitlab.tag, GITLAB_ENTERPRISE_URL + "/am/test")
        self.assertIsNone(gitlab.client)

    def test_has_archiving(self):
        """Test if it returns False when has_archiving is called"""

        self.assertEqual(GitLab.has_archiving(), True)

    def test_has_resuming(self):
        """Test if it returns False when has_resuming is called"""

        self.assertEqual(GitLab.has_resuming(), True)

    @httpretty.activate
    def test_fetch_issues(self):
        """Test whether issues are properly fetched from GitLab"""

        setup_http_server(GITLAB_URL_PROJECT, GITLAB_ISSUES_URL, GITLAB_MERGES_URL)

        gitlab = GitLab("fdroid", "fdroiddata", "your-token")

        issues = [issues for issues in gitlab.fetch()]

        self.assertEqual(len(issues), 4)

        issue = issues[0]
        self.assertEqual(issue['origin'], GITLAB_URL + '/fdroid/fdroiddata')
        self.assertEqual(issue['category'], CATEGORY_ISSUE)
        self.assertEqual(issue['tag'], GITLAB_URL + '/fdroid/fdroiddata')
        self.assertEqual(issue['data']['author']['id'], 1)
        self.assertEqual(issue['data']['author']['username'], 'redfish64')

        issue = issues[1]
        self.assertEqual(issue['origin'], GITLAB_URL + '/fdroid/fdroiddata')
        self.assertEqual(issue['category'], CATEGORY_ISSUE)
        self.assertEqual(issue['tag'], GITLAB_URL + '/fdroid/fdroiddata')
        self.assertEqual(issue['data']['author']['id'], 1)
        self.assertEqual(issue['data']['author']['username'], 'redfish64')

        issue = issues[2]
        self.assertEqual(issue['origin'], GITLAB_URL + '/fdroid/fdroiddata')
        self.assertEqual(issue['category'], CATEGORY_ISSUE)
        self.assertEqual(issue['tag'], GITLAB_URL + '/fdroid/fdroiddata')
        self.assertEqual(issue['data']['author']['id'], 2)
        self.assertEqual(issue['data']['author']['username'], 'YoeriNijs')

        issue = issues[3]
        self.assertEqual(issue['origin'], GITLAB_URL + '/fdroid/fdroiddata')
        self.assertEqual(issue['category'], CATEGORY_ISSUE)
        self.assertEqual(issue['tag'], GITLAB_URL + '/fdroid/fdroiddata')
        self.assertEqual(issue['data']['author']['id'], 2)
        self.assertEqual(issue['data']['author']['username'], 'YoeriNijs')

    @httpretty.activate
    def test_fetch_issues_blacklisted(self):
        """Test whether blacklist issues are not fetched from GitLab"""

        setup_http_server(GITLAB_URL_PROJECT, GITLAB_ISSUES_URL, GITLAB_MERGES_URL)

        gitlab = GitLab("fdroid", "fdroiddata", "your-token", blacklist_ids=[1, 2, 3])

        with self.assertLogs(level='WARNING') as cm:
            issues = [issues for issues in gitlab.fetch()]
            self.assertEqual(cm.output[0], 'WARNING:perceval.backends.core.gitlab:Skipping blacklisted issue 1')
            self.assertEqual(cm.output[1], 'WARNING:perceval.backends.core.gitlab:Skipping blacklisted issue 2')
            self.assertEqual(cm.output[2], 'WARNING:perceval.backends.core.gitlab:Skipping blacklisted issue 3')

        self.assertEqual(len(issues), 1)

        issue = issues[0]
        self.assertEqual(issue['origin'], GITLAB_URL + '/fdroid/fdroiddata')
        self.assertEqual(issue['category'], CATEGORY_ISSUE)
        self.assertEqual(issue['tag'], GITLAB_URL + '/fdroid/fdroiddata')
        self.assertEqual(issue['data']['author']['id'], 2)
        self.assertEqual(issue['data']['author']['username'], 'YoeriNijs')

    @httpretty.activate
    def test_fetch_merges(self):
        """Test whether merges are properly fetched from GitLab"""

        setup_http_server(GITLAB_URL_PROJECT, GITLAB_ISSUES_URL, GITLAB_MERGES_URL)

        gitlab = GitLab("fdroid", "fdroiddata", "your-token")

        merges = [merges for merges in gitlab.fetch(category=CATEGORY_MERGE_REQUEST)]

        self.assertEqual(len(merges), 3)

        merge = merges[0]
        self.assertEqual(merge['origin'], GITLAB_URL + '/fdroid/fdroiddata')
        self.assertEqual(merge['category'], CATEGORY_MERGE_REQUEST)
        self.assertEqual(merge['tag'], GITLAB_URL + '/fdroid/fdroiddata')
        self.assertEqual(merge['data']['author']['id'], 1)
        self.assertEqual(merge['data']['author']['username'], 'redfish64')
        self.assertEqual(len(merge['data']['versions_data']), 2)
        self.assertTrue('diffs' not in merge['data']['versions_data'][0])
        self.assertTrue('diffs' not in merge['data']['versions_data'][1])

        merge = merges[1]
        self.assertEqual(merge['origin'], GITLAB_URL + '/fdroid/fdroiddata')
        self.assertEqual(merge['category'], CATEGORY_MERGE_REQUEST)
        self.assertEqual(merge['tag'], GITLAB_URL + '/fdroid/fdroiddata')
        self.assertEqual(merge['data']['author']['id'], 1)
        self.assertEqual(merge['data']['author']['username'], 'redfish64')
        self.assertEqual(len(merge['data']['versions_data']), 1)
        self.assertTrue('diffs' not in merge['data']['versions_data'][0])

        merge = merges[2]
        self.assertEqual(merge['origin'], GITLAB_URL + '/fdroid/fdroiddata')
        self.assertEqual(merge['category'], CATEGORY_MERGE_REQUEST)
        self.assertEqual(merge['tag'], GITLAB_URL + '/fdroid/fdroiddata')
        self.assertEqual(merge['data']['author']['id'], 1)
        self.assertEqual(merge['data']['author']['username'], 'redfish64')
        self.assertEqual(len(merge['data']['versions_data']), 1)
        self.assertTrue('diffs' not in merge['data']['versions_data'][0])

    @httpretty.activate
    def test_fetch_merges_blacklisted(self):
        """Test whether blacklist merge requests are not fetched from GitLab"""

        setup_http_server(GITLAB_URL_PROJECT, GITLAB_ISSUES_URL, GITLAB_MERGES_URL)

        gitlab = GitLab("fdroid", "fdroiddata", "your-token", blacklist_ids=[1, 2])

        with self.assertLogs(level='WARNING') as cm:
            merges = [merges for merges in gitlab.fetch(category=CATEGORY_MERGE_REQUEST)]
            self.assertEqual(cm.output[0], 'WARNING:perceval.backends.core.gitlab:'
                                           'Skipping blacklisted merge request 1')
            self.assertEqual(cm.output[1], 'WARNING:perceval.backends.core.gitlab:'
                                           'Skipping blacklisted merge request 2')

        self.assertEqual(len(merges), 1)

        merge = merges[0]
        self.assertEqual(merge['origin'], GITLAB_URL + '/fdroid/fdroiddata')
        self.assertEqual(merge['category'], CATEGORY_MERGE_REQUEST)
        self.assertEqual(merge['tag'], GITLAB_URL + '/fdroid/fdroiddata')
        self.assertEqual(merge['data']['author']['id'], 1)
        self.assertEqual(merge['data']['author']['username'], 'redfish64')
        self.assertEqual(len(merge['data']['versions_data']), 1)
        self.assertTrue('diffs' not in merge['data']['versions_data'][0])

    @httpretty.activate
    def test_fetch_issues_from_date(self):
        """Test whether issues from a given date are properly fetched from GitLab"""

        setup_http_server(GITLAB_URL_PROJECT, GITLAB_ISSUES_URL, GITLAB_MERGES_URL)

        gitlab = GitLab("fdroid", "fdroiddata", "your-token")
        from_date = datetime.datetime(2017, 3, 18)
        issues = [issues for issues in gitlab.fetch(from_date=from_date)]

        self.assertEqual(len(issues), 4)

        issue = issues[0]
        self.assertEqual(issue['origin'], GITLAB_URL + '/fdroid/fdroiddata')
        self.assertEqual(issue['category'], CATEGORY_ISSUE)
        self.assertEqual(issue['tag'], GITLAB_URL + '/fdroid/fdroiddata')
        self.assertEqual(issue['data']['author']['id'], 1)
        self.assertEqual(issue['data']['author']['username'], 'redfish64')

        issue = issues[1]
        self.assertEqual(issue['origin'], GITLAB_URL + '/fdroid/fdroiddata')
        self.assertEqual(issue['category'], CATEGORY_ISSUE)
        self.assertEqual(issue['tag'], GITLAB_URL + '/fdroid/fdroiddata')
        self.assertEqual(issue['data']['author']['id'], 1)
        self.assertEqual(issue['data']['author']['username'], 'redfish64')

        issue = issues[2]
        self.assertEqual(issue['origin'], GITLAB_URL + '/fdroid/fdroiddata')
        self.assertEqual(issue['category'], CATEGORY_ISSUE)
        self.assertEqual(issue['tag'], GITLAB_URL + '/fdroid/fdroiddata')
        self.assertEqual(issue['data']['author']['id'], 2)
        self.assertEqual(issue['data']['author']['username'], 'YoeriNijs')

        issue = issues[3]
        self.assertEqual(issue['origin'], GITLAB_URL + '/fdroid/fdroiddata')
        self.assertEqual(issue['category'], CATEGORY_ISSUE)
        self.assertEqual(issue['tag'], GITLAB_URL + '/fdroid/fdroiddata')
        self.assertEqual(issue['data']['author']['id'], 2)
        self.assertEqual(issue['data']['author']['username'], 'YoeriNijs')

        # check that the from_date param is in the querystring
        expected = {
            'state': ['all'],
            'order_by': ['updated_at'],
            'sort': ['asc'],
            'per_page': ['100'],
            'updated_after': ['2017-03-18T00:00:00 00:00']
        }
        request = httpretty.HTTPretty.latest_requests[1]
        self.assertDictEqual(request.querystring, expected)

    @httpretty.activate
    def test_fetch_merges_from_date(self):
        """Test whether merge requests from a given date are properly fetched from GitLab"""

        setup_http_server(GITLAB_URL_PROJECT, GITLAB_ISSUES_URL, GITLAB_MERGES_URL)

        gitlab = GitLab("fdroid", "fdroiddata", "your-token")
        from_date = datetime.datetime(2017, 3, 18)
        merges = [merges for merges in gitlab.fetch(from_date=from_date, category=CATEGORY_MERGE_REQUEST)]

        self.assertEqual(len(merges), 3)

        merge = merges[0]
        self.assertEqual(merge['origin'], GITLAB_URL + '/fdroid/fdroiddata')
        self.assertEqual(merge['category'], CATEGORY_MERGE_REQUEST)
        self.assertEqual(merge['tag'], GITLAB_URL + '/fdroid/fdroiddata')
        self.assertEqual(merge['data']['author']['id'], 1)
        self.assertEqual(merge['data']['author']['username'], 'redfish64')
        self.assertEqual(len(merge['data']['versions_data']), 2)
        self.assertTrue('diffs' not in merge['data']['versions_data'][0])
        self.assertTrue('diffs' not in merge['data']['versions_data'][1])

        merge = merges[1]
        self.assertEqual(merge['origin'], GITLAB_URL + '/fdroid/fdroiddata')
        self.assertEqual(merge['category'], CATEGORY_MERGE_REQUEST)
        self.assertEqual(merge['tag'], GITLAB_URL + '/fdroid/fdroiddata')
        self.assertEqual(merge['data']['author']['id'], 1)
        self.assertEqual(merge['data']['author']['username'], 'redfish64')
        self.assertEqual(len(merge['data']['versions_data']), 1)
        self.assertTrue('diffs' not in merge['data']['versions_data'][0])

        merge = merges[2]
        self.assertEqual(merge['origin'], GITLAB_URL + '/fdroid/fdroiddata')
        self.assertEqual(merge['category'], CATEGORY_MERGE_REQUEST)
        self.assertEqual(merge['tag'], GITLAB_URL + '/fdroid/fdroiddata')
        self.assertEqual(merge['data']['author']['id'], 1)
        self.assertEqual(merge['data']['author']['username'], 'redfish64')
        self.assertEqual(len(merge['data']['versions_data']), 1)
        self.assertTrue('diffs' not in merge['data']['versions_data'][0])

        # check that the from_date param is in the querystring
        expected = {
            'state': ['all'],
            'order_by': ['updated_at'],
            'sort': ['asc'],
            'per_page': ['100'],
            'updated_after': ['2017-03-18T00:00:00 00:00'],
            'view': ['simple']
        }
        request = httpretty.HTTPretty.latest_requests[1]
        self.assertDictEqual(request.querystring, expected)

    @httpretty.activate
    def test_fetch_issues_enterprise(self):
        """Test whether issues are properly fetched from GitLab Enterprise server"""

        setup_http_server(GITLAB_ENTERPRISE_URL_PROJECT,
                          GITLAB_ENTERPRISE_ISSUES_URL,
                          GITLAB_ENTERPRISE_MERGES_URL)

        gitlab = GitLab('am', 'test', base_url=GITLAB_ENTERPRISE_URL)

        issues = [issues for issues in gitlab.fetch()]

        self.assertEqual(len(issues), 4)

        issue = issues[0]
        self.assertEqual(issue['origin'], GITLAB_ENTERPRISE_URL + '/am/test')
        self.assertEqual(issue['category'], CATEGORY_ISSUE)
        self.assertEqual(issue['tag'], GITLAB_ENTERPRISE_URL + '/am/test')
        self.assertEqual(issue['data']['author']['id'], 1)
        self.assertEqual(issue['data']['author']['username'], 'redfish64')

        issue = issues[1]
        self.assertEqual(issue['origin'], GITLAB_ENTERPRISE_URL + '/am/test')
        self.assertEqual(issue['category'], CATEGORY_ISSUE)
        self.assertEqual(issue['tag'], GITLAB_ENTERPRISE_URL + '/am/test')
        self.assertEqual(issue['data']['author']['id'], 1)
        self.assertEqual(issue['data']['author']['username'], 'redfish64')

        issue = issues[2]
        self.assertEqual(issue['origin'], GITLAB_ENTERPRISE_URL + '/am/test')
        self.assertEqual(issue['category'], CATEGORY_ISSUE)
        self.assertEqual(issue['tag'], GITLAB_ENTERPRISE_URL + '/am/test')
        self.assertEqual(issue['data']['author']['id'], 2)
        self.assertEqual(issue['data']['author']['username'], 'YoeriNijs')

        issue = issues[3]
        self.assertEqual(issue['origin'], GITLAB_ENTERPRISE_URL + '/am/test')
        self.assertEqual(issue['category'], CATEGORY_ISSUE)
        self.assertEqual(issue['tag'], GITLAB_ENTERPRISE_URL + '/am/test')
        self.assertEqual(issue['data']['author']['id'], 2)
        self.assertEqual(issue['data']['author']['username'], 'YoeriNijs')

    @httpretty.activate
    def test_fetch_merges_enterprise(self):
        """Test whether merges are properly fetched from GitLab Enterprise server"""

        setup_http_server(GITLAB_ENTERPRISE_URL_PROJECT,
                          GITLAB_ENTERPRISE_ISSUES_URL,
                          GITLAB_ENTERPRISE_MERGES_URL)

        gitlab = GitLab('am', 'test', base_url=GITLAB_ENTERPRISE_URL)

        merges = [merges for merges in gitlab.fetch(category=CATEGORY_MERGE_REQUEST)]

        self.assertEqual(len(merges), 3)

        merge = merges[0]
        self.assertEqual(merge['origin'], GITLAB_ENTERPRISE_URL + '/am/test')
        self.assertEqual(merge['category'], CATEGORY_MERGE_REQUEST)
        self.assertEqual(merge['tag'], GITLAB_ENTERPRISE_URL + '/am/test')
        self.assertEqual(merge['data']['author']['id'], 1)
        self.assertEqual(merge['data']['author']['username'], 'redfish64')
        self.assertEqual(len(merge['data']['versions_data']), 2)
        self.assertTrue('diffs' not in merge['data']['versions_data'][0])
        self.assertTrue('diffs' not in merge['data']['versions_data'][1])

        merge = merges[1]
        self.assertEqual(merge['origin'], GITLAB_ENTERPRISE_URL + '/am/test')
        self.assertEqual(merge['category'], CATEGORY_MERGE_REQUEST)
        self.assertEqual(merge['tag'], GITLAB_ENTERPRISE_URL + '/am/test')
        self.assertEqual(merge['data']['author']['id'], 1)
        self.assertEqual(merge['data']['author']['username'], 'redfish64')
        self.assertEqual(len(merge['data']['versions_data']), 1)
        self.assertTrue('diffs' not in merge['data']['versions_data'][0])

        merge = merges[2]
        self.assertEqual(merge['origin'], GITLAB_ENTERPRISE_URL + '/am/test')
        self.assertEqual(merge['category'], CATEGORY_MERGE_REQUEST)
        self.assertEqual(merge['tag'], GITLAB_ENTERPRISE_URL + '/am/test')
        self.assertEqual(merge['data']['author']['id'], 1)
        self.assertEqual(merge['data']['author']['username'], 'redfish64')
        self.assertEqual(len(merge['data']['versions_data']), 1)
        self.assertTrue('diffs' not in merge['data']['versions_data'][0])

    @httpretty.activate
    def test_fetch_issues_empty(self):
        """Test when return empty"""

        page_1 = ''

        httpretty.register_uri(httpretty.GET,
                               GITLAB_URL_PROJECT,
                               body='',
                               status=200)

        httpretty.register_uri(httpretty.GET,
                               GITLAB_ISSUES_URL,
                               body=page_1,
                               status=200)

        gitlab = GitLab("fdroid", "fdroiddata", api_token="your-token")

        issues = [issues for issues in gitlab.fetch()]

        self.assertEqual(len(issues), 0)

    @httpretty.activate
    def test_fetch_merges_empty(self):
        """Test when return empty"""

        page_1 = ''

        httpretty.register_uri(httpretty.GET,
                               GITLAB_URL_PROJECT,
                               body='',
                               status=200)

        httpretty.register_uri(httpretty.GET,
                               GITLAB_MERGES_URL,
                               body=page_1,
                               status=200)

        gitlab = GitLab("fdroid", "fdroiddata", api_token="your-token")

        merges = [merges for merges in gitlab.fetch(category=CATEGORY_MERGE_REQUEST)]

        self.assertEqual(len(merges), 0)


class TestGitHUbBackendArchive(TestCaseBackendArchive):
    """GitHub backend tests using an archive"""

    def setUp(self):
        super().setUp()
        self.backend_write_archive = GitLab("fdroid", "fdroiddata", api_token="your-token", archive=self.archive)
        self.backend_read_archive = GitLab("fdroid", "fdroiddata", api_token="your-token", archive=self.archive)

    @httpretty.activate
    def test_fetch_issues_from_archive(self):
        """Test whether issues are properly fetched from the archive"""

        setup_http_server(GITLAB_URL_PROJECT, GITLAB_ISSUES_URL, GITLAB_MERGES_URL)
        self._test_fetch_from_archive(from_date=None)

    @httpretty.activate
    def test_fetch_merges_from_archive(self):
        """Test whether merges are properly fetched from the archive"""

        setup_http_server(GITLAB_URL_PROJECT, GITLAB_ISSUES_URL, GITLAB_MERGES_URL)
        self._test_fetch_from_archive(category=CATEGORY_MERGE_REQUEST, from_date=None)

    @httpretty.activate
    def test_fetch_issues_from_date(self):
        """Test whether issues from a given date are properly fetched from GitLab"""

        setup_http_server(GITLAB_URL_PROJECT, GITLAB_ISSUES_URL, GITLAB_MERGES_URL)

        from_date = datetime.datetime(2017, 3, 18)
        self._test_fetch_from_archive(from_date=from_date)

    @httpretty.activate
    def test_fetch_merges_from_date(self):
        """Test whether merges from a given date are properly fetched from GitLab"""

        setup_http_server(GITLAB_URL_PROJECT, GITLAB_ISSUES_URL, GITLAB_MERGES_URL)

        from_date = datetime.datetime(2017, 3, 18)
        self._test_fetch_from_archive(category=CATEGORY_MERGE_REQUEST, from_date=from_date)

    @httpretty.activate
    def test_fetch_issues_enterprise(self):
        """Test whether issues are properly fetched from GitLab Enterprise server"""

        setup_http_server(GITLAB_ENTERPRISE_URL_PROJECT,
                          GITLAB_ENTERPRISE_ISSUES_URL,
                          GITLAB_ENTERPRISE_MERGES_URL)

        self.backend_write_archive = GitLab('am', 'test', base_url=GITLAB_ENTERPRISE_URL, archive=self.archive)
        self.backend_read_archive = GitLab('am', 'test', base_url=GITLAB_ENTERPRISE_URL, archive=self.archive)
        self._test_fetch_from_archive()

    @httpretty.activate
    def test_fetch_merges_enterprise(self):
        """Test whether merges are properly fetched from GitLab Enterprise server"""

        setup_http_server(GITLAB_ENTERPRISE_URL_PROJECT,
                          GITLAB_ENTERPRISE_ISSUES_URL,
                          GITLAB_ENTERPRISE_MERGES_URL)

        self.backend_write_archive = GitLab('am', 'test', base_url=GITLAB_ENTERPRISE_URL, archive=self.archive)
        self.backend_read_archive = GitLab('am', 'test', base_url=GITLAB_ENTERPRISE_URL, archive=self.archive)
        self._test_fetch_from_archive(category=CATEGORY_MERGE_REQUEST)

    @httpretty.activate
    def test_fetch_issues_empty(self):
        """Test when return empty"""

        page_1 = ''

        httpretty.register_uri(httpretty.GET,
                               GITLAB_URL_PROJECT,
                               body='',
                               status=200)

        httpretty.register_uri(httpretty.GET,
                               GITLAB_ISSUES_URL,
                               body=page_1,
                               status=200)

        self._test_fetch_from_archive()

    @httpretty.activate
    def test_fetch_merges_empty(self):
        """Test when return empty"""

        page_1 = ''

        httpretty.register_uri(httpretty.GET,
                               GITLAB_URL_PROJECT,
                               body='',
                               status=200)

        httpretty.register_uri(httpretty.GET,
                               GITLAB_MERGES_URL,
                               body=page_1,
                               status=200)

        self._test_fetch_from_archive(category=CATEGORY_MERGE_REQUEST)


class TestGitLabClient(unittest.TestCase):
    """GitLab API client tests"""

    @httpretty.activate
    def test_initialization(self):
        """Test initialization for GitLab server"""

        setup_http_server(GITLAB_URL_PROJECT, GITLAB_ISSUES_URL, GITLAB_MERGES_URL,
                          rate_limit_headers={'RateLimit-Remaining': '20'})

        client = GitLabClient("fdroid", "fdroiddata", "your-token")
        self.assertEqual(client.owner, "fdroid")
        self.assertEqual(client.repository, "fdroiddata")
        self.assertEqual(client.token, "your-token")
        self.assertEqual(client.sleep_for_rate, False)
        self.assertEqual(client.base_url, GITLAB_API_URL)
        self.assertEqual(client.min_rate_to_sleep, GitLabClient.MIN_RATE_LIMIT)
        self.assertEqual(client.sleep_time, GitLabClient.DEFAULT_SLEEP_TIME)
        self.assertEqual(client.max_retries, GitLabClient.MAX_RETRIES)
        self.assertEqual(client.rate_limit, 20)
        self.assertEqual(client.rate_limit_reset_ts, None)

        client = GitLabClient("fdroid", "fdroiddata", "your-token", sleep_for_rate=True,
                              min_rate_to_sleep=100, max_retries=10, sleep_time=100)

        self.assertEqual(client.sleep_for_rate, True)
        self.assertEqual(client.base_url, GITLAB_API_URL)
        self.assertEqual(client.min_rate_to_sleep, 100)
        self.assertEqual(client.sleep_time, 100)
        self.assertEqual(client.max_retries, 10)

    @httpretty.activate
    def test_initialization_entreprise(self):
        """Test initialization for GitLab entreprise server"""

        setup_http_server(GITLAB_ENTERPRISE_URL_PROJECT,
                          GITLAB_ENTERPRISE_ISSUES_URL,
                          GITLAB_ENTERPRISE_MERGES_URL)

        client = GitLabClient("am", "test", None, base_url=GITLAB_ENTERPRISE_URL)

        self.assertEqual(client.owner, "am")
        self.assertEqual(client.repository, "test")
        self.assertEqual(client.token, None)
        self.assertEqual(client.sleep_for_rate, False)
        self.assertEqual(client.base_url, GITLAB_ENTERPRISE_API_URL)
        self.assertEqual(client.min_rate_to_sleep, GitLabClient.MIN_RATE_LIMIT)
        self.assertEqual(client.sleep_time, GitLabClient.DEFAULT_SLEEP_TIME)
        self.assertEqual(client.max_retries, GitLabClient.MAX_RETRIES)
        self.assertEqual(client.rate_limit, None)
        self.assertEqual(client.rate_limit_reset_ts, None)

    @httpretty.activate
    def test_initialization_http_error(self):
        """Test whether issues when initializing the rate limit are properly handled"""

        project = read_file('data/gitlab/project')
        httpretty.register_uri(httpretty.GET,
                               GITLAB_URL_PROJECT,
                               body=project,
                               status=401)

        with self.assertRaises(requests.exceptions.HTTPError):
            GitLabClient("fdroid", "fdroiddata", "your-token")

        project = read_file('data/gitlab/project')
        httpretty.register_uri(httpretty.GET,
                               GITLAB_URL_PROJECT,
                               body=project,
                               status=400)

        with self.assertLogs(logger, level='WARNING') as cm:
            GitLabClient("fdroid", "fdroiddata", "your-token")
            self.assertEqual(cm.output[0], 'WARNING:perceval.backends.core.gitlab:Rate limit not initialized: 400 '
                                           'Client Error: Bad Request for '
                                           'url: https://gitlab.com/api/v4/projects/fdroid%2Ffdroiddata')

    @httpretty.activate
    def test_issues(self):
        """Test issues API call"""

        setup_http_server(GITLAB_URL_PROJECT, GITLAB_ISSUES_URL, GITLAB_MERGES_URL,
                          rate_limit_headers={'RateLimit-Remaining': '20'})

        page_1 = read_file('data/gitlab/issue_page_1')
        page_2 = read_file('data/gitlab/issue_page_2')

        client = GitLabClient("fdroid", "fdroiddata", "your-token")

        raw_issues = [issues for issues in client.issues()]

        self.assertEqual(len(raw_issues), 2)
        self.assertEqual(raw_issues[0], page_1)
        self.assertEqual(raw_issues[1], page_2)

        # Check requests
        expected = {
            'state': ['all'],
            'sort': ['asc'],
            'order_by': ['updated_at'],
            'page': ['2'],
            'per_page': ['100']
        }

        self.assertDictEqual(httpretty.last_request().querystring, expected)
        self.assertEqual(httpretty.last_request().headers["PRIVATE-TOKEN"], "your-token")

    @httpretty.activate
    def test_merges(self):
        """Test merges API call"""

        setup_http_server(GITLAB_URL_PROJECT, GITLAB_ISSUES_URL, GITLAB_MERGES_URL,
                          rate_limit_headers={'RateLimit-Remaining': '20'})

        page_1 = read_file('data/gitlab/merge_page_1')
        page_2 = read_file('data/gitlab/merge_page_2')

        client = GitLabClient("fdroid", "fdroiddata", "your-token")

        raw_merges = [merges for merges in client.merges()]

        self.assertEqual(len(raw_merges), 2)
        self.assertEqual(raw_merges[0], page_1)
        self.assertEqual(raw_merges[1], page_2)

        # Check requests
        expected = {
            'state': ['all'],
            'sort': ['asc'],
            'order_by': ['updated_at'],
            'page': ['2'],
            'per_page': ['100'],
            'view': ['simple']
        }

        self.assertDictEqual(httpretty.last_request().querystring, expected)
        self.assertEqual(httpretty.last_request().headers["PRIVATE-TOKEN"], "your-token")

    @httpretty.activate
    def test_issues_from_date(self):
        """Test issues API call with from date parameter"""

        setup_http_server(GITLAB_URL_PROJECT, GITLAB_ISSUES_URL, GITLAB_MERGES_URL,
                          rate_limit_headers={'RateLimit-Remaining': '20'})

        page_1 = read_file('data/gitlab/issue_page_1')
        page_2 = read_file('data/gitlab/issue_page_2')

        from_date = datetime.datetime(2017, 1, 1)
        client = GitLabClient("fdroid", "fdroiddata", "your-token")

        raw_issues = [issues for issues in client.issues(from_date)]

        self.assertEqual(len(raw_issues), 2)
        self.assertEqual(raw_issues[0], page_1)
        self.assertEqual(raw_issues[1], page_2)

        # Check requests
        expected = {
            'state': ['all'],
            'sort': ['asc'],
            'order_by': ['updated_at'],
            'page': ['2'],
            'per_page': ['100'],
            'updated_after': ['2017-01-01T00:00:00']
        }

        self.assertDictEqual(httpretty.last_request().querystring, expected)
        self.assertEqual(httpretty.last_request().headers["PRIVATE-TOKEN"], "your-token")

    @httpretty.activate
    def test_merges_from_date(self):
        """Test merges API call with from date parameter"""

        setup_http_server(GITLAB_URL_PROJECT, GITLAB_ISSUES_URL, GITLAB_MERGES_URL,
                          rate_limit_headers={'RateLimit-Remaining': '20'})

        page_1 = read_file('data/gitlab/merge_page_1')
        page_2 = read_file('data/gitlab/merge_page_2')

        from_date = datetime.datetime(2017, 1, 1)
        client = GitLabClient("fdroid", "fdroiddata", "your-token")

        raw_merges = [merges for merges in client.merges(from_date)]

        self.assertEqual(len(raw_merges), 2)
        self.assertEqual(raw_merges[0], page_1)
        self.assertEqual(raw_merges[1], page_2)

        # Check requests
        expected = {
            'state': ['all'],
            'sort': ['asc'],
            'order_by': ['updated_at'],
            'page': ['2'],
            'per_page': ['100'],
            'updated_after': ['2017-01-01T00:00:00'],
            'view': ['simple']
        }

        self.assertDictEqual(httpretty.last_request().querystring, expected)
        self.assertEqual(httpretty.last_request().headers["PRIVATE-TOKEN"], "your-token")

    @httpretty.activate
    def test_issues_empty(self):
        """Test when issue is empty API call"""

        httpretty.register_uri(httpretty.GET,
                               GITLAB_URL_PROJECT,
                               body='',
                               status=200)

        httpretty.register_uri(httpretty.GET,
                               GITLAB_ISSUES_URL,
                               body="[]",
                               status=200
                               )

        client = GitLabClient("fdroid", "fdroiddata", "aaa")

        raw_issues = [issues for issues in client.issues()]

        self.assertEqual(raw_issues[0], "[]")

        self.assertEqual(
            httpretty.last_request().headers["PRIVATE-TOKEN"], "aaa")

    @httpretty.activate
    def test_merges_empty(self):
        """Test when merges is empty API call"""

        httpretty.register_uri(httpretty.GET,
                               GITLAB_URL_PROJECT,
                               body='',
                               status=200)

        httpretty.register_uri(httpretty.GET,
                               GITLAB_MERGES_URL,
                               body="[]",
                               status=200
                               )

        client = GitLabClient("fdroid", "fdroiddata", "aaa")

        raw_merges = [merges for merges in client.merges()]

        self.assertEqual(raw_merges[0], "[]")

        self.assertEqual(
            httpretty.last_request().headers["PRIVATE-TOKEN"], "aaa")

    @httpretty.activate
    def test_notes(self):
        """Test notes API call"""

        setup_http_server(GITLAB_URL_PROJECT, GITLAB_ISSUES_URL, GITLAB_MERGES_URL,
                          rate_limit_headers={'RateLimit-Remaining': '20'})

        client = GitLabClient("fdroid", "fdroiddata", "your-token")
        raw_notes = next(client.notes("issues", 1))
        notes = json.loads(raw_notes)

        self.assertEqual(len(notes), 2)

        raw_notes = next(client.notes("merge_requests", 2))
        notes = json.loads(raw_notes)

        self.assertEqual(len(notes), 1)

    @httpretty.activate
    def test_merge_versions(self):
        """Test merge versions API call"""

        setup_http_server(GITLAB_URL_PROJECT, GITLAB_ISSUES_URL, GITLAB_MERGES_URL,
                          rate_limit_headers={'RateLimit-Remaining': '20'})

        client = GitLabClient("fdroid", "fdroiddata", "your-token")
        raw_versions = next(client.merge_versions(1))
        versions = json.loads(raw_versions)

        self.assertEqual(len(versions), 2)

    @httpretty.activate
    def test_merge_version(self):
        """Test merge version API call"""

        setup_http_server(GITLAB_URL_PROJECT, GITLAB_ISSUES_URL, GITLAB_MERGES_URL,
                          rate_limit_headers={'RateLimit-Remaining': '20'})

        client = GitLabClient("fdroid", "fdroiddata", "your-token")
        raw_merge_version = client.merge_version(1, 1)
        merge_version = json.loads(raw_merge_version)

        self.assertEqual(len(merge_version['commits']), 1)
        self.assertEqual(len(merge_version['diffs']), 1)

    @httpretty.activate
    def test_merge(self):
        """Test merge API call"""

        setup_http_server(GITLAB_URL_PROJECT, GITLAB_ISSUES_URL, GITLAB_MERGES_URL,
                          rate_limit_headers={'RateLimit-Remaining': '20'})

        client = GitLabClient("fdroid", "fdroiddata", "your-token")
        raw_merge = client.merge(1)
        merge = json.loads(raw_merge)

        self.assertIsNone(merge['merged_by'])
        self.assertIsNone(merge['merged_at'])

    @httpretty.activate
    def test_emojis(self):
        """Test emojis API call"""

        setup_http_server(GITLAB_URL_PROJECT, GITLAB_ISSUES_URL, GITLAB_MERGES_URL,
                          rate_limit_headers={'RateLimit-Remaining': '20'})

        client = GitLabClient("fdroid", "fdroiddata", "your-token")
        raw_emojis = next(client.emojis("issues", 1))
        emojis = json.loads(raw_emojis)

        self.assertEqual(len(emojis), 2)

        raw_emojis = next(client.emojis("merge_requests", 1))
        emojis = json.loads(raw_emojis)

        self.assertEqual(len(emojis), 2)

    @httpretty.activate
    def test_note_emojis(self):
        """Test note_emojis API call"""

        setup_http_server(GITLAB_URL_PROJECT, GITLAB_ISSUES_URL, GITLAB_MERGES_URL,
                          rate_limit_headers={'RateLimit-Remaining': '20'})

        client = GitLabClient("fdroid", "fdroiddata", "your-token")
        raw_emojis = next(client.note_emojis("issues", 1, 2))
        emojis = json.loads(raw_emojis)

        self.assertEqual(len(emojis), 0)

        raw_emojis = next(client.note_emojis("merge_requests", 1, 1))
        emojis = json.loads(raw_emojis)

        self.assertEqual(len(emojis), 2)

    @httpretty.activate
    def test_http_wrong_status(self):
        """Test if a error is raised when the http status was not 200"""

        httpretty.register_uri(httpretty.GET,
                               GITLAB_URL_PROJECT,
                               body='',
                               status=200,
                               forcing_headers={
                                   'RateLimit-Remaining': '20',
                                   'RateLimit-Reset': '15'
                               })

        httpretty.register_uri(httpretty.GET,
                               GITLAB_ISSUES_URL,
                               body="",
                               status=500
                               )

        client = GitLabClient("fdroid", "fdroiddata", "your-token", sleep_time=1)

        with self.assertRaises(requests.exceptions.HTTPError):
            _ = [issues for issues in client.issues()]

    @httpretty.activate
    def test_calculate_time_to_reset(self):
        """Test whether the time to reset is zero if the sleep time is negative"""

        httpretty.register_uri(httpretty.GET,
                               GITLAB_URL_PROJECT,
                               body='',
                               status=200,
                               forcing_headers={
                                   'RateLimit-Remaining': '20',
                                   'RateLimit-Reset': int(datetime_utcnow().replace(microsecond=0).timestamp())
                               })

        client = GitLabClient("fdroid", "fdroiddata", "your-token")
        time_to_reset = client.calculate_time_to_reset()

        self.assertEqual(time_to_reset, 0)

    @httpretty.activate
    def test_sleep_for_rate(self):
        """Test whether a RateLimit error is thrown when the sleep for rate parameter is false"""

        wait = 2
        reset = int(time.time() + wait)

        httpretty.register_uri(httpretty.GET,
                               GITLAB_URL_PROJECT,
                               body='',
                               status=200,
                               forcing_headers={
                                   'RateLimit-Remaining': '20',
                                   'RateLimit-Reset': reset
                               })

        httpretty.register_uri(httpretty.GET,
                               GITLAB_ISSUES_URL,
                               body='[]',
                               status=200,
                               forcing_headers={
                                   'RateLimit-Remaining': '0',
                                   'RateLimit-Reset': reset,
                                   'Link': '<' + GITLAB_ISSUES_URL + '/?&page=2>; rel="next", <' +
                                    GITLAB_ISSUES_URL +
                                    '/?&page=3>; rel="last"'
                               })

        httpretty.register_uri(httpretty.GET,
                               GITLAB_ISSUES_URL + '/?&page=2',
                               body='[]',
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': reset
                               })

        client = GitLabClient("fdroid", "fdroiddata", "your-token", sleep_for_rate=True)

        issues = [issues for issues in client.issues()]
        after = int(time.time())

        self.assertTrue(reset >= after)
        self.assertEqual(len(issues), 2)

        client = GitLabClient("fdroid", "fdroiddata", "your-token")

        with self.assertRaises(RateLimitError):
            _ = [issues for issues in client.issues()]

    def test_sanitize_for_archive(self):
        """Test whether the sanitize method works properly"""

        url = "http://example.com"
        headers = {'PRIVATE-TOKEN': 'ABCDEF'}
        payload = {}

        s_url, s_headers, s_payload = GitLabClient.sanitize_for_archive(url, copy.deepcopy(headers), payload)
        headers.pop('PRIVATE-TOKEN')

        self.assertEqual(url, s_url)
        self.assertEqual(headers, s_headers)
        self.assertEqual(payload, s_payload)


class TestGitLabCommand(unittest.TestCase):
    """GitLabCommand unit tests"""

    def test_backend_class(self):
        """Test if the backend class is GitLab"""

        self.assertIs(GitLabCommand.BACKEND, GitLab)

    def test_setup_cmd_parser(self):
        """Test if it parser object is correctly initialized"""

        parser = GitLabCommand.setup_cmd_parser()
        self.assertIsInstance(parser, BackendCommandArgumentParser)

        args = ['--sleep-for-rate',
                '--min-rate-to-sleep', '1',
                '--tag', 'test', '--no-archive',
                '--api-token', 'abcdefgh',
                '--from-date', '1970-01-01',
                '--enterprise-url', 'https://example.com',
                'zhquan_example', 'repo']

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.owner, 'zhquan_example')
        self.assertEqual(parsed_args.repository, 'repo')
        self.assertEqual(parsed_args.base_url, 'https://example.com')
        self.assertEqual(parsed_args.sleep_for_rate, True)
        self.assertEqual(parsed_args.min_rate_to_sleep, 1)
        self.assertEqual(parsed_args.tag, 'test')
        self.assertEqual(parsed_args.from_date, DEFAULT_DATETIME)
        self.assertEqual(parsed_args.no_archive, True)
        self.assertEqual(parsed_args.api_token, 'abcdefgh')
        self.assertEqual(parsed_args.max_retries, MAX_RETRIES)
        self.assertEqual(parsed_args.sleep_time, DEFAULT_SLEEP_TIME)

        args = ['--sleep-for-rate',
                '--min-rate-to-sleep', '1',
                '--tag', 'test', '--no-archive',
                '--max-retries', '5',
                '--sleep-time', '10',
                '--api-token', 'abcdefgh',
                '--from-date', '1970-01-01',
                '--blacklist-ids', '1', '2', '3',
                '--enterprise-url', 'https://example.com',
                '--category', CATEGORY_MERGE_REQUEST,
                'zhquan_example', 'repo']

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.owner, 'zhquan_example')
        self.assertEqual(parsed_args.repository, 'repo')
        self.assertEqual(parsed_args.base_url, 'https://example.com')
        self.assertEqual(parsed_args.sleep_for_rate, True)
        self.assertEqual(parsed_args.min_rate_to_sleep, 1)
        self.assertEqual(parsed_args.tag, 'test')
        self.assertEqual(parsed_args.from_date, DEFAULT_DATETIME)
        self.assertEqual(parsed_args.no_archive, True)
        self.assertEqual(parsed_args.api_token, 'abcdefgh')
        self.assertEqual(parsed_args.category, CATEGORY_MERGE_REQUEST)
        self.assertEqual(parsed_args.blacklist_ids, [1, 2, 3])
        self.assertEqual(parsed_args.max_retries, 5)
        self.assertEqual(parsed_args.sleep_time, 10)


if __name__ == "__main__":
    unittest.main(warnings='ignore')
