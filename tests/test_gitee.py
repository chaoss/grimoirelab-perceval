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

import datetime
import os
import unittest
import httpretty

from perceval.backend import BackendCommandArgumentParser
from perceval.backends.core.gitee import (Gitee, GiteeClient,
                                          CATEGORY_PULL_REQUEST, GiteeCommand, GITEE_REFRESH_TOKEN_URL, CATEGORY_REPO)

from base import TestCaseBackendArchive
from perceval.utils import DEFAULT_DATETIME, DEFAULT_LAST_DATETIME

GITEE_API_URL = "https://gitee.com/api/v5"
GITEE_REPO_URL = GITEE_API_URL + "/repos/gitee_example/repo"
GITEE_ISSUES_URL = GITEE_REPO_URL + "/issues"
GITEE_ISSUE_COMMENTS_URL_1 = GITEE_ISSUES_URL + "/I1DACG/comments"
GITEE_ISSUE_COMMENTS_URL_2 = GITEE_ISSUES_URL + "/I1DAQF/comments"
GITEE_USER_URL = GITEE_API_URL + "/users/willemjiang"
GITEE_USER_ORGS_URL = GITEE_API_URL + "/users/willemjiang/orgs"
GITEE_PULL_REQUEST_URL = GITEE_REPO_URL + "/pulls"
GITEE_PULL_REQUEST_1_COMMENTS_URL = GITEE_PULL_REQUEST_URL + "/1/comments"
GITEE_PULL_REQUEST_1_COMMITS_URL = GITEE_PULL_REQUEST_URL + "/1/commits"
GITEE_PULL_REQUEST_1_OPERATE_LOGS_URL = GITEE_PULL_REQUEST_URL + "/1/operate_logs"
GITEE_PULL_REQUEST_2_COMMENTS_URL = GITEE_PULL_REQUEST_URL + "/2/comments"
GITEE_PULL_REQUEST_2_COMMITS_URL = GITEE_PULL_REQUEST_URL + "/2/commits"
GITEE_PULL_REQUEST_2_OPERATE_LOGS_URL = GITEE_PULL_REQUEST_URL + "/2/operate_logs"


def read_file(filename, mode='r'):
    with open(os.path.join(
            os.path.dirname(os.path.abspath(__file__)), filename), mode) as f:
        content = f.read()
    return content


def setup_gitee_issue_services():
    setup_gitee_basic_services()
    __setup_gitee_issue_services()


def setup_gitee_pull_request_services():
    setup_gitee_basic_services()
    __setup_gitee_pull_request_services()


def setup_gitee_basic_services():
    setup_refresh_access_token_service()
    orgs = read_file('data/gitee/gitee_user_orgs')
    httpretty.register_uri(httpretty.GET, GITEE_USER_ORGS_URL, body=orgs, status=200)

    user = read_file('data/gitee/gitee_login')
    httpretty.register_uri(httpretty.GET, GITEE_USER_URL, body=user, status=200)

    repo = read_file('data/gitee/gitee_repo')
    httpretty.register_uri(httpretty.GET, GITEE_REPO_URL, body=repo, status=200)


def __setup_gitee_issue_services():
    issues1 = read_file('data/gitee/gitee_issues1')
    issues2 = read_file('data/gitee/gitee_issues2')

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
                           body=issues1, status=200,
                           forcing_headers=pagination_issue_header_1)

    httpretty.register_uri(httpretty.GET, GITEE_ISSUES_URL + "/?&page=2",
                           body=issues2, status=200,
                           forcing_headers=pagination_issue_header_2)

    issue1_comments = read_file('data/gitee/gitee_issue1_comments')
    httpretty.register_uri(httpretty.GET, GITEE_ISSUE_COMMENTS_URL_1,
                           body=issue1_comments, status=200,
                           forcing_headers={
                               "total_count": "1",
                               "total_page": "1"
                           })
    issue2_comments = read_file('data/gitee/gitee_issue2_comments')
    httpretty.register_uri(httpretty.GET, GITEE_ISSUE_COMMENTS_URL_2,
                           body=issue2_comments, status=200,
                           forcing_headers={
                               "total_count": "1",
                               "total_page": "1"
                           })


def __setup_gitee_pull_request_services():
    pagination_pull_header_1 = {'Link': '<' + GITEE_PULL_REQUEST_URL +
                                        '/?&page=2>; rel="next", <' + GITEE_PULL_REQUEST_URL +
                                        '/?&page=2>; rel="last"',
                                'total_count': '2',
                                'total_page': '2'
                                }

    pagination_pull_header_2 = {'Link': '<' + GITEE_PULL_REQUEST_URL +
                                        '/?&page=1>;  rel="prev", <' + GITEE_PULL_REQUEST_URL +
                                        '/?&page=1>; rel="first"',
                                'total_count': '2',
                                'total_page': '2'
                                }

    pull_request_1 = read_file('data/gitee/gitee_pull_request1')
    httpretty.register_uri(httpretty.GET, GITEE_PULL_REQUEST_URL,
                           body=pull_request_1, status=200,
                           forcing_headers=pagination_pull_header_1)

    pull_request_2 = read_file('data/gitee/gitee_pull_request2')
    httpretty.register_uri(httpretty.GET, GITEE_PULL_REQUEST_URL + "/?&page=2",
                           body=pull_request_2, status=200,
                           forcing_headers=pagination_pull_header_2)

    pull_request_1_comments = read_file('data/gitee/gitee_pull_request1_comments')
    httpretty.register_uri(httpretty.GET, GITEE_PULL_REQUEST_1_COMMENTS_URL,
                           body=pull_request_1_comments, status=200,
                           forcing_headers={
                               "total_count": "1",
                               "total_page": "1"
                           })
    pull_request_1_commits = read_file('data/gitee/gitee_pull_request1_commits')
    httpretty.register_uri(httpretty.GET, GITEE_PULL_REQUEST_1_COMMITS_URL,
                           body=pull_request_1_commits, status=200,
                           forcing_headers={
                               "total_count": "1",
                               "total_page": "1"
                           })
    pull_request_2_comments = read_file('data/gitee/gitee_pull_request2_comments')
    httpretty.register_uri(httpretty.GET, GITEE_PULL_REQUEST_2_COMMENTS_URL,
                           body=pull_request_2_comments, status=200,
                           forcing_headers={
                               "total_count": "1",
                               "total_page": "1"
                           })
    pull_request_2_commits = read_file('data/gitee/gitee_pull_request2_commits')
    httpretty.register_uri(httpretty.GET, GITEE_PULL_REQUEST_2_COMMITS_URL,
                           body=pull_request_2_commits, status=200,
                           forcing_headers={
                               "total_count": "1",
                               "total_page": "1"
                           })
    pull_request_1_action_logs = read_file('data/gitee/gitee_pull_request1_action_logs')
    httpretty.register_uri(httpretty.GET, GITEE_PULL_REQUEST_1_OPERATE_LOGS_URL,
                           body=pull_request_1_action_logs, status=200)
    pull_request_2_action_logs = read_file('data/gitee/gitee_pull_request2_action_logs')
    httpretty.register_uri(httpretty.GET, GITEE_PULL_REQUEST_2_OPERATE_LOGS_URL,
                           body=pull_request_2_action_logs, status=200)


def setup_refresh_access_token_service():
    httpretty.register_uri(httpretty.POST, GITEE_REFRESH_TOKEN_URL, body="", status=200)


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
        setup_gitee_issue_services()
        empty_issue = '[]'
        httpretty.register_uri(httpretty.GET, GITEE_ISSUES_URL,
                               body=empty_issue, status=200,
                               forcing_headers={
                                   "total_count": "0",
                                   "total_page": "0"
                               })

        from_date = datetime.datetime(2019, 1, 1)
        gitee = Gitee("gitee_example", "repo", ["aaa"])

        issues = [issues for issues in gitee.fetch(from_date=from_date, to_date=None)]

        self.assertEqual(len(issues), 0)

    @httpretty.activate
    def test_fetch_issues(self):
        setup_gitee_issue_services()
        from_date = datetime.datetime(2019, 1, 1)
        gitee = Gitee("gitee_example", "repo", ["aaa"])
        issues = [issues for issues in gitee.fetch(from_date=from_date)]

        self.assertEqual(len(issues), 2)
        issue1 = issues[0]
        self.assertEqual(issue1['origin'], 'https://gitee.com/gitee_example/repo')
        self.assertEqual(issue1['uuid'], 'e954a17216b20e5b11c7eef99df06aefa8b8b974')
        self.assertEqual(issue1['updated_on'], 1577842375.0)
        self.assertEqual(issue1['tag'], 'https://gitee.com/gitee_example/repo')
        self.assertEqual(issue1['data']['assignee_data']['login'], 'willemjiang')
        self.assertEqual(issue1['data']['title'], 'First example issue')
        # TODO to add collaborators information
        # self.assertEqual(issue['data']['collaborators_data'][0]['login'], 'willemjiang')
        self.assertEqual(len(issue1['data']['comments_data']), 1)
        self.assertEqual(issue1['data']['comments_data'][0]['user_data']['login'], 'willemjiang')

        issue2 = issues[1]
        self.assertEqual(issue2['origin'], 'https://gitee.com/gitee_example/repo')
        self.assertEqual(issue2['uuid'], '3e5e90b1f0862c1b8a1adb52bc961e8a77ec2431')
        self.assertEqual(issue2['updated_on'], 1585710411.0)
        self.assertEqual(issue2['tag'], 'https://gitee.com/gitee_example/repo')
        self.assertEqual(issue2['data']['assignee_data']['login'], 'willemjiang')
        self.assertEqual(issue2['data']['title'], 'Second example issue')
        # TODO to add collaborators information
        # self.assertEqual(issue['data']['collaborators_data'][0]['login'], 'willemjiang')
        self.assertEqual(len(issue2['data']['comments_data']), 1)
        self.assertEqual(issue2['data']['comments_data'][0]['user_data']['login'], 'willemjiang')
        self.assertEqual(issue2['data']['comments_data'][0]['target']['issue']['number'], 'I1DAQF')

    @httpretty.activate
    def test_fetch_issues_with_to_data(self):
        setup_gitee_issue_services()
        to_date = datetime.datetime(2020, 2, 1)
        gitee = Gitee("gitee_example", "repo", ["aaa"])
        issues = [issues for issues in gitee.fetch(to_date=to_date)]

        self.assertEqual(len(issues), 1)
        issue = issues[0]
        self.assertEqual(issue['origin'], 'https://gitee.com/gitee_example/repo')
        self.assertEqual(issue['uuid'], 'e954a17216b20e5b11c7eef99df06aefa8b8b974')
        self.assertEqual(issue['updated_on'], 1577842375.0)
        self.assertEqual(issue['tag'], 'https://gitee.com/gitee_example/repo')
        self.assertEqual(issue['data']['assignee_data']['login'], 'willemjiang')
        self.assertEqual(issue['data']['title'], 'First example issue')
        # TODO to add collaborators information
        # self.assertEqual(issue['data']['collaborators_data'][0]['login'], 'willemjiang')
        self.assertEqual(len(issue['data']['comments_data']), 1)
        self.assertEqual(issue['data']['comments_data'][0]['user_data']['login'], 'willemjiang')

    @httpretty.activate
    def test_fetch_repo(self):
        setup_gitee_basic_services()
        gitee = Gitee("gitee_example", "repo", "[aaa]")
        repos = [repo for repo in gitee.fetch(category=CATEGORY_REPO)]

        self.assertEqual(len(repos), 1)
        repo = repos[0]
        self.assertEqual(repo['category'], 'repository')
        self.assertEqual(repo['data']['name'], "camel-on-cloud")
        self.assertEqual(repo['data']['forks_count'], 1)
        self.assertEqual(repo['data']['stargazers_count'], 2)
        self.assertEqual(repo['data']['watchers_count'], 3)
        self.assertEqual(repo['data']['open_issues_count'], 4)

    @httpretty.activate
    def test_fetch_pulls(self):
        setup_gitee_pull_request_services()
        from_date = datetime.datetime(2019, 1, 1)
        gitee = Gitee("gitee_example", "repo", "[aaa]")
        pulls = [pr for pr in gitee.fetch(category=CATEGORY_PULL_REQUEST, from_date=from_date)]

        self.assertEqual(len(pulls), 2)
        pull = pulls[0]
        self.assertEqual(pull['updated_on'], 1586078981.0)
        self.assertEqual(pull['uuid'], '497fa28f2109f702a7a88b1a4fbfbfb279a2266e')
        self.assertEqual(pull['data']['head']['repo']['path'], "camel-on-cloud")
        self.assertEqual(pull['data']['base']['repo']['path'], "camel-on-cloud")
        self.assertEqual(pull['data']['number'], 1)
        self.assertEqual(len(pull['data']['review_comments_data']), 1)
        self.assertEqual(pull['data']['review_comments_data'][0]['body'], "Add some comments here.")
        self.assertEqual(len(pull['data']['assignees_data']), 1)
        self.assertEqual(pull['data']['assignees_data'][0]['login'], "willemjiang")
        # check if the  testers_data there
        self.assertTrue( 'tester_data' not in pull['data'])
        self.assertEqual(pull['data']['commits_data'], ['8cd1bca4f2989ac2e2753a152c8c4c8e065b22f5'])
        self.assertEqual(pull['data']['merged_by'], "willemjiang")
        self.assertEqual(pull['data']['merged_by_data']['login'], "willemjiang")

        pull = pulls[1]
        self.assertEqual(pull['updated_on'], 1585976439.0)
        self.assertEqual(pull['uuid'], '46df79e68e92005db5c1897844e3a0c3acf1aa4f')
        self.assertEqual(pull['data']['head']['repo']['path'], "camel-on-cloud")
        self.assertEqual(pull['data']['base']['repo']['path'], "camel-on-cloud")
        self.assertEqual(pull['data']['number'], 2)
        self.assertEqual(len(pull['data']['review_comments_data']), 1)
        self.assertEqual(pull['data']['review_comments_data'][0]['body'], "Added comment here.")
        self.assertEqual(len(pull['data']['assignees_data']), 1)
        self.assertEqual(pull['data']['assignees_data'][0]['login'], "willemjiang")
        # check if the  testers_data there
        self.assertTrue('tester_data' not in pull['data'])
        self.assertEqual(pull['data']['commits_data'], ['586cc8e511097f5c5b7a4ce803a5efcaed99b9c2'])
        self.assertEqual(pull['data']['merged_by'], None)
        self.assertEqual(pull['data']['merged_by_data'], [])


    def test_has_resuming(self):
        """Test if it returns True when has_resuming is called"""

        self.assertEqual(Gitee.has_resuming(), True)

    def test_has_archiving(self):
        """Test if it returns True when has_archiving is called"""

        self.assertEqual(Gitee.has_archiving(), True)


class TestGiteeBackendArchive(TestCaseBackendArchive):
    """GitHub backend tests using an archive"""

    def setUp(self):
        super().setUp()
        self.backend_write_archive = Gitee("gitee_example", "repo", ["aaa"], archive=self.archive)
        self.backend_read_archive = Gitee("gitee_example", "repo", ["aaa"], archive=self.archive)

    @httpretty.activate
    def test_fetch_issues_from_archive(self):
        """Test whether a list of issues is returned from archive"""
        setup_gitee_issue_services()
        self._test_fetch_from_archive(from_date=None)

    @httpretty.activate
    def test_fetch_pulls_from_archive(self):
        """Test whether a list of pull requests is returned from archive"""
        setup_gitee_pull_request_services()
        self._test_fetch_from_archive(category=CATEGORY_PULL_REQUEST, from_date=None)

    @httpretty.activate
    def test_fetch_from_date_from_archive(self):
        """Test whether a list of issues is returned from archive after a given date"""
        setup_gitee_issue_services()
        from_date = datetime.datetime(2016, 3, 1)
        self._test_fetch_from_archive(from_date=from_date)

    @httpretty.activate
    def test_fetch_from_empty_archive(self):
        """Test whether no issues are returned when the archive is empty"""
        setup_gitee_basic_services()
        empty_issue = ''
        httpretty.register_uri(httpretty.GET, GITEE_ISSUES_URL,
                               body=empty_issue, status=200,
                               forcing_headers={
                                   "total_count": "0",
                                   "total_page": "0"
                               })
        self._test_fetch_from_archive()


class TestGiteeClient(unittest.TestCase):
    """Gitee API client tests"""

    @httpretty.activate
    def test_init(self):
        """ Test for the initialization of GiteeClient """
        setup_refresh_access_token_service()
        client = GiteeClient('gitee_example', 'repo', ['aaa'])
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
        setup_refresh_access_token_service()
        empty_issue = '[]'
        httpretty.register_uri(httpretty.GET, GITEE_ISSUES_URL,
                               body=empty_issue, status=200,
                               forcing_headers={
                                   "total_count": "0",
                                   "total_page": "0"
                               })

        client = GiteeClient('gitee_example', 'repo', ['aaa'])
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
    def test_get_without_api_token(self):
        """ Test when issue is empty API call """
        empty_issue = '[]'
        httpretty.register_uri(httpretty.GET, GITEE_ISSUES_URL,
                               body=empty_issue, status=200,
                               forcing_headers={
                                   "total_count": "0",
                                   "total_page": "0"
                               })

        httpretty.register_uri(httpretty.POST, GITEE_REFRESH_TOKEN_URL, body=empty_issue, status=200)

        client = GiteeClient('gitee_example', 'repo', None)
        raw_issues = [issues for issues in client.issues()]
        self.assertEqual(raw_issues[0], empty_issue)

        # Check requests parameter
        expected = {
            'per_page': ['100'],
            'state': ['all'],
            'direction': ['asc'],
            'sort': ['updated']
        }
        self.assertDictEqual(httpretty.last_request().querystring, expected)

    @httpretty.activate
    def test_get_issues(self):
        """Test Gitee issues API """
        setup_refresh_access_token_service()
        issues = read_file('data/gitee/gitee_issues1')
        httpretty.register_uri(httpretty.GET, GITEE_ISSUES_URL,
                               body=issues, status=200,
                               forcing_headers={
                                   "total_count": "1",
                                   "total_page": "1"
                               })

        client = GiteeClient("gitee_example", "repo", ['aaa'], None)
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
        setup_refresh_access_token_service()
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

        client = GiteeClient("gitee_example", "repo", ['aaa'], None)
        raw_issues = [issues for issues in client.issues()]
        self.assertEqual(raw_issues[0], issues_1)
        self.assertEqual(raw_issues[1], issues_2)

    @httpretty.activate
    def test_issue_comments(self):
        """Test Gitee issue comments API """
        setup_refresh_access_token_service()
        issue_comments = read_file('data/gitee/gitee_issue1_comments')
        httpretty.register_uri(httpretty.GET, GITEE_ISSUE_COMMENTS_URL_1,
                               body=issue_comments, status=200,
                               forcing_headers={
                                   "total_count": "1",
                                   "total_page": "1"
                               })

        client = GiteeClient("gitee_example", "repo", ['aaa'], None)
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
        setup_refresh_access_token_service()
        pull_request = read_file('data/gitee/gitee_pull_request1')
        httpretty.register_uri(httpretty.GET, GITEE_PULL_REQUEST_URL,
                               body=pull_request, status=200,
                               forcing_headers={
                                   "total_count": "1",
                                   "total_page": "1"
                               })
        client = GiteeClient("gitee_example", "repo", ['aaa'], None)
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
    def test_pulls_action_logs(self):
        setup_refresh_access_token_service()
        pull_action_logs = read_file('data/gitee/gitee_pull_request1_action_logs')
        httpretty.register_uri(httpretty.GET, GITEE_PULL_REQUEST_1_OPERATE_LOGS_URL,
                               body=pull_action_logs, status=200)
        client = GiteeClient("gitee_example", "repo", ['aaa'], None)
        raw_logs = [logs for logs in client.pull_action_logs(1)]
        self.assertEqual(raw_logs[0], pull_action_logs)

    @httpretty.activate
    def test_repo(self):
        setup_refresh_access_token_service()
        repo = read_file('data/gitee/gitee_repo')
        httpretty.register_uri(httpretty.GET, GITEE_REPO_URL, body=repo, status=200)
        client = GiteeClient("gitee_example", "repo", ['aaa'], None)
        raw_repo = client.repo()
        self.assertEqual(raw_repo, repo)

    @httpretty.activate
    def test_user_orgs(self):
        setup_refresh_access_token_service()
        orgs = read_file('data/gitee/gitee_user_orgs')
        httpretty.register_uri(httpretty.GET, GITEE_USER_ORGS_URL, body=orgs, status=200)
        client = GiteeClient("gitee_example", "repo", ['aaa'], None)
        raw_orgs = client.user_orgs("willemjiang")
        self.assertEqual(raw_orgs, orgs)

    @httpretty.activate
    def test_get_user(self):
        setup_refresh_access_token_service()
        user = read_file('data/gitee/gitee_login')
        httpretty.register_uri(httpretty.GET, GITEE_USER_URL, body=user, status=200)
        client = GiteeClient("gitee_example", "repo", ['aaa'], None)
        raw_user = client.user("willemjiang")
        self.assertEqual(raw_user, user)


class TestGiteeCommand(unittest.TestCase):
    """GitHubCommand unit tests"""

    def test_backend_class(self):
        """Test if the backend class is GitHub"""

        self.assertIs(GiteeCommand.BACKEND, Gitee)

    def test_setup_cmd_parser(self):
        """Test if it parser object is correctly initialized"""

        parser = GiteeCommand.setup_cmd_parser()
        self.assertIsInstance(parser, BackendCommandArgumentParser)
        self.assertEqual(parser._backend, Gitee)

        args = ['--sleep-for-rate',
                '--min-rate-to-sleep', '1',
                '--max-retries', '5',
                '--max-items', '10',
                '--sleep-time', '10',
                '--tag', 'test', '--no-archive',
                '--api-token', 'abcdefgh', 'ijklmnop',
                '--from-date', '1970-01-01',
                '--to-date', '2100-01-01',
                'gitee_example', 'repo']

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.owner, 'gitee_example')
        self.assertEqual(parsed_args.repository, 'repo')
        self.assertTrue(parsed_args.sleep_for_rate)
        self.assertEqual(parsed_args.max_retries, 5)
        self.assertEqual(parsed_args.max_items, 10)
        self.assertEqual(parsed_args.sleep_time, 10)
        self.assertEqual(parsed_args.tag, 'test')
        self.assertEqual(parsed_args.from_date, DEFAULT_DATETIME)
        self.assertEqual(parsed_args.to_date, DEFAULT_LAST_DATETIME)
        self.assertTrue(parsed_args.no_archive)
        self.assertTrue(parsed_args.ssl_verify)
        self.assertEqual(parsed_args.api_token, ['abcdefgh', 'ijklmnop'])

        args = ['--sleep-for-rate',
                '--min-rate-to-sleep', '1',
                '--max-retries', '5',
                '--max-items', '10',
                '--sleep-time', '10',
                '--tag', 'test', '--no-archive',
                '--api-token', 'abcdefgh', 'ijklmnop',
                '--from-date', '1970-01-01',
                '--to-date', '2100-01-01',
                '--no-ssl-verify',
                'gitee_example', 'repo']

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.owner, 'gitee_example')
        self.assertEqual(parsed_args.repository, 'repo')
        self.assertTrue(parsed_args.sleep_for_rate)
        self.assertEqual(parsed_args.max_retries, 5)
        self.assertEqual(parsed_args.max_items, 10)
        self.assertEqual(parsed_args.sleep_time, 10)
        self.assertEqual(parsed_args.tag, 'test')
        self.assertEqual(parsed_args.from_date, DEFAULT_DATETIME)
        self.assertEqual(parsed_args.to_date, DEFAULT_LAST_DATETIME)
        self.assertTrue(parsed_args.no_archive)
        self.assertFalse(parsed_args.ssl_verify)
        self.assertEqual(parsed_args.api_token, ['abcdefgh', 'ijklmnop'])


if __name__ == "__main__":
    unittest.main(warnings='ignore')
