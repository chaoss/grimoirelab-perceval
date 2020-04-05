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
#     Willem Jiang <willem.jiang@gmail.com>

# from base import TestCaseBackendArchive
import datetime
import os
import unittest
import httpretty
import pkg_resources

pkg_resources.declare_namespace('perceval.backends')

from perceval.backends.core.gitee import (Gitee, GiteeClient)

GITEE_API_URL = "https://gitee.com/api/v5"
GITEE_REPO_URL = GITEE_API_URL + "/repos/gitee_example/repo"
GITEE_ISSUES_URL = GITEE_REPO_URL + "/issues"
GITEE_ISSUE_COMMENTS_URL_1 = GITEE_ISSUES_URL + "/I1DACG/comments"
GITEE_USER_URL = GITEE_API_URL + "/users/willemjiang"
GITEE_USER_ORGS_URL = GITEE_API_URL + "/users/willemjiang/orgs"
GITEE_PULL_REQUEST_URL = GITEE_REPO_URL + "/pulls"


def read_file(filename, mode='r'):
    with open(os.path.join(
            os.path.dirname(os.path.abspath(__file__)), filename), mode) as f:
        content = f.read()
    return content


def setup_gitee_issue_service():
    issues = read_file('data/gitee/gitee_issues1')
    httpretty.register_uri(httpretty.GET, GITEE_ISSUES_URL,
                           body=issues, status=200,
                           forcing_headers={
                               "total_count": "1",
                               "total_page": "1"
                           })

    user = read_file('data/gitee/gitee_login')
    httpretty.register_uri(httpretty.GET, GITEE_USER_URL, body=user, status=200)

    issue_comments = read_file('data/gitee/gitee_issue1_comments')

    orgs = read_file('data/gitee/gitee_user_orgs')
    httpretty.register_uri(httpretty.GET, GITEE_USER_ORGS_URL, body=orgs, status=200)

    httpretty.register_uri(httpretty.GET, GITEE_ISSUE_COMMENTS_URL_1,
                           body=issue_comments, status=200,
                           forcing_headers={
                               "total_count": "1",
                               "total_page": "1"
                           })


class TestGiteeBackend(unittest.TestCase):
    """Gitee Backend tests"""

    def test_init(self):
        """ Test for the initialization of Gitee"""
        gitee = Gitee('gitee_example', 'repo', ['aaa'], tag='')
        self.assertEqual(gitee.owner, 'gitee_example')
        self.assertEqual(gitee.repository, 'repo')
        self.assertEqual(gitee.origin, 'https://gitee.com/gitee_example/repo')
        self.assertEqual(gitee.tag, 'https://gitee.com/gitee_example/repo')

    @httpretty.activate
    def test_fetch_empty(self):
        """ Test when get a empty issues API call """
        empty_issue = '[]'
        httpretty.register_uri(httpretty.GET, GITEE_ISSUES_URL,
                               body=empty_issue, status=200,
                               forcing_headers={
                                   "total_count": "0",
                                   "total_page": "0"
                               })

        from_date = datetime.datetime(2019, 1, 1)
        gitee = Gitee("gitee_example", "repo", ["aaa"])

        issues = [issues for issues in gitee.fetch(from_date=from_date)]

        self.assertEqual(len(issues), 0)

    @httpretty.activate
    def test_fetch_issues(self):
        setup_gitee_issue_service()
        from_date = datetime.datetime(2019, 1, 1)
        gitee = Gitee("gitee_example", "repo", ["aaa"])
        issues = [issues for issues in gitee.fetch(from_date=from_date)]

        self.assertEqual(len(issues), 1)
        issue = issues[0]
        self.assertEqual(issue['origin'], 'https://gitee.com/gitee_example/repo')
        self.assertEqual(issue['uuid'], 'e954a17216b20e5b11c7eef99df06aefa8b8b974')
        self.assertEqual(issue['updated_on'], 1585704775.0)
        self.assertEqual(issue['tag'], 'https://gitee.com/gitee_example/repo')
        self.assertEqual(issue['data']['assignee_data']['login'], 'willemjiang')
        # TODO to add collaborators information
        # self.assertEqual(issue['data']['collaborators_data'][0]['login'], 'willemjiang')
        self.assertEqual(len(issue['data']['comments_data']), 1)
        self.assertEqual(issue['data']['comments_data'][0]['user_data']['login'], 'willemjiang')

    # @httpretty.activate
    # def test_fetch_pulls(self):


class TestGiteeClient(unittest.TestCase):
    """Gitee API client tests"""

    def test_init(self):
        """ Test for the initialization of GiteeClient """
        client = GiteeClient('gitee_example', 'repo', 'aaa')
        self.assertEqual(client.owner, 'gitee_example')
        self.assertEqual(client.repository, 'repo')
        self.assertEqual(client.max_retries, GiteeClient.MAX_RETRIES)
        self.assertEqual(client.sleep_time, GiteeClient.DEFAULT_SLEEP_TIME)
        self.assertEqual(client.max_retries, GiteeClient.MAX_RETRIES)
        self.assertEqual(client.base_url, GITEE_API_URL)
        self.assertTrue(client.ssl_verify)

    @httpretty.activate
    def test_get_empty_issues(self):
        """ Test when issue is empty API call """

        empty_issue = '[]'
        httpretty.register_uri(httpretty.GET, GITEE_ISSUES_URL,
                               body=empty_issue, status=200,
                               forcing_headers={
                                   "total_count": "0",
                                   "total_page": "0"
                               })

        client = GiteeClient('gitee_example', 'repo', 'aaa')
        raw_issues = [issues for issues in client.issues()]
        self.assertEqual(raw_issues[0], empty_issue)

        # Check requests parameter
        expected = {
            'per_page': ['100'],
            'state': ['all'],
            'direction': ['asc'],
            'sort': ['updated'],
            'access_token': ['aaa']
        }
        self.assertDictEqual(httpretty.last_request().querystring, expected)

    @httpretty.activate
    def test_get_issues(self):
        """Test Gitee issues API """

        issues = read_file('data/gitee/gitee_issues1')
        httpretty.register_uri(httpretty.GET, GITEE_ISSUES_URL,
                               body=issues, status=200,
                               forcing_headers={
                                   "total_count": "1",
                                   "total_page": "1"
                               })

        client = GiteeClient("gitee_example", "repo", 'aaa', None)
        raw_issues = [issues for issues in client.issues()]
        self.assertEqual(raw_issues[0], issues)

        # Check requests parameter
        expected = {
            'per_page': ['100'],
            'state': ['all'],
            'direction': ['asc'],
            'sort': ['updated'],
            'access_token': ['aaa']
        }
        self.assertDictEqual(httpretty.last_request().querystring, expected)

    @httpretty.activate
    def test_get_two_pages_issues(self):
        """Test Gitee issues API """

        issues_1 = read_file('data/gitee/gitee_issues1')
        issues_2 = read_file('data/gitee/gitee_issues2')
        pagination_issue_header_1 = {'Link': '<' + GITEE_ISSUES_URL +
                                     '/?&page=2>; rel="next", <' + GITEE_ISSUES_URL +
                                     '/?&page=2>; rel="last"',
                                     'total_count': '2',
                                     'total_page': '2'
                                     }

        pagination_issue_header_2 = {'Link': '<' + GITEE_ISSUES_URL +
                                     '/?&page=1>;  rel="prev", <' + GITEE_ISSUES_URL +
                                     '/?&page=1>; rel="first"',
                                     'total_count': '2',
                                     'total_page': '2'
                                     }

        httpretty.register_uri(httpretty.GET, GITEE_ISSUES_URL,
                               body=issues_1, status=200,
                               forcing_headers=pagination_issue_header_1)

        httpretty.register_uri(httpretty.GET, GITEE_ISSUES_URL + '/?&page=2',
                               body=issues_2, status=200,
                               forcing_headers=pagination_issue_header_2)

        client = GiteeClient("gitee_example", "repo", 'aaa', None)
        raw_issues = [issues for issues in client.issues()]
        self.assertEqual(raw_issues[0], issues_1)
        self.assertEqual(raw_issues[1], issues_2)

    @httpretty.activate
    def test_issue_comments(self):
        """Test Gitee issue comments API """

        issue_comments = read_file('data/gitee/gitee_issue1_comments')
        httpretty.register_uri(httpretty.GET, GITEE_ISSUE_COMMENTS_URL_1,
                               body=issue_comments, status=200,
                               forcing_headers={
                                   "total_count": "1",
                                   "total_page": "1"
                               })

        client = GiteeClient("gitee_example", "repo", 'aaa', None)
        raw_issue_comments = [comments for comments in client.issue_comments("I1DACG")]
        self.assertEqual(raw_issue_comments[0], issue_comments)

        # Check requests parameter
        expected = {
            'per_page': ['100'],
            'access_token': ['aaa']
        }
        self.assertDictEqual(httpretty.last_request().querystring, expected)

    @httpretty.activate
    def test_pulls(self):
        pull_request = read_file('data/gitee/gitee_pull_request1')
        httpretty.register_uri(httpretty.GET, GITEE_PULL_REQUEST_URL,
                               body=pull_request, status=200,
                               forcing_headers={
                                   "total_count": "1",
                                   "total_page": "1"
                               })
        client = GiteeClient("gitee_example", "repo", 'aaa', None)
        raw_pulls = [pulls for pulls in client.pulls()]
        self.assertEqual(raw_pulls[0], pull_request)

        # Check requests parameter
        expected = {
            'per_page': ['100'],
            'state': ['all'],
            'direction': ['asc'],
            'sort': ['updated'],
            'access_token': ['aaa']
        }
        self.assertDictEqual(httpretty.last_request().querystring, expected)

    @httpretty.activate
    def test_repo(self):
        repo = read_file('data/gitee/gitee_repo')
        httpretty.register_uri(httpretty.GET, GITEE_REPO_URL, body=repo, status=200)
        client = GiteeClient("gitee_example", "repo", 'aaa', None)
        raw_repo = client.repo()
        self.assertEqual(raw_repo, repo)

    @httpretty.activate
    def test_user_orgs(self):
        orgs = read_file('data/gitee/gitee_user_orgs')
        httpretty.register_uri(httpretty.GET, GITEE_USER_ORGS_URL, body=orgs, status=200)
        client = GiteeClient("gitee_example", "repo", 'aaa', None)
        raw_orgs = client.user_orgs("willemjiang")
        self.assertEqual(raw_orgs, orgs)

    @httpretty.activate
    def test_get_user(self):
        user = read_file('data/gitee/gitee_login')
        httpretty.register_uri(httpretty.GET, GITEE_USER_URL, body=user, status=200)
        client = GiteeClient("gitee_example", "repo", 'aaa', None)
        raw_user = client.user("willemjiang")
        self.assertEqual(raw_user, user)
