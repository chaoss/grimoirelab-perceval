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
#     Quan Zhou <quan@bitergia.com>
#     Valerio Cosentino <valcos@bitergia.com>
#     Miguel Ángel Fernández <mafesan@bitergia.com>
#     Santiago Dueñas <sduenas@bitergia.com>
#     Jesus M. Gonzalez-Barahona <jgb@gsyc.es>
#     Lukasz Gryglicki <lukaszgryglicki@o2.pl>
#     David Pose Fernández <dpose@bitergia.com>
#     Alvaro del Castillo <acs@bitergia.com>
#     Harshal Mittal <harshalmittal4@gmail.com>
#     Aniruddha Karajgi <akarajgi0@gmail.com>
#     Cedric Williams <cewilliams@paypal.com>
#     JJMerchante <jj.merchante@gmail.com>
#

import datetime
import dateutil
import json
import os
import time
import unittest
import unittest.mock
import copy

import httpretty
import pkg_resources
import requests

pkg_resources.declare_namespace('perceval.backends')

from grimoirelab_toolkit.datetime import datetime_utcnow
from perceval.backend import BackendCommandArgumentParser
from perceval.client import RateLimitHandler
from perceval.errors import RateLimitError
from perceval.utils import (DEFAULT_DATETIME, DEFAULT_LAST_DATETIME)
from perceval.backends.core.github import (logger, GitHub,
                                           GitHubCommand,
                                           GitHubClient,
                                           CATEGORY_ISSUE,
                                           CATEGORY_PULL_REQUEST,
                                           CATEGORY_REPO,
                                           MAX_CATEGORY_ITEMS_PER_PAGE)
from base import TestCaseBackendArchive


GITHUB_API_URL = "https://api.github.com"
GITHUB_RATE_LIMIT = GITHUB_API_URL + "/rate_limit"
GITHUB_REPO_URL = GITHUB_API_URL + "/repos/zhquan_example/repo"
GITHUB_ISSUES_URL = GITHUB_REPO_URL + "/issues"
GITHUB_PULL_REQUEST_URL = GITHUB_REPO_URL + "/pulls"
GITHUB_ISSUE_1_COMMENTS_URL = GITHUB_ISSUES_URL + "/1/comments"
GITHUB_ISSUE_COMMENT_1_REACTION_URL = GITHUB_ISSUES_URL + "/comments/1/reactions"
GITHUB_ISSUE_2_REACTION_URL = GITHUB_ISSUES_URL + "/2/reactions"
GITHUB_ISSUE_2_COMMENTS_URL = GITHUB_ISSUES_URL + "/2/comments"
GITHUB_ISSUE_COMMENT_2_REACTION_URL = GITHUB_ISSUES_URL + "/comments/2/reactions"
GITHUB_PULL_REQUEST_1_URL = GITHUB_PULL_REQUEST_URL + "/1"
GITHUB_PULL_REQUEST_1_COMMENTS = GITHUB_PULL_REQUEST_1_URL + "/comments"
GITHUB_PULL_REQUEST_1_COMMITS = GITHUB_PULL_REQUEST_1_URL + "/commits"
GITHUB_PULL_REQUEST_1_REVIEWS = GITHUB_PULL_REQUEST_1_URL + "/reviews"
GITHUB_PULL_REQUEST_1_COMMENTS_2_REACTIONS = GITHUB_PULL_REQUEST_URL + "/comments/2/reactions"
GITHUB_PULL_REQUEST_1_REQUESTED_REVIEWERS_URL = GITHUB_PULL_REQUEST_1_URL + "/requested_reviewers"
GITHUB_PULL_REQUEST_2_URL = GITHUB_PULL_REQUEST_URL + "/2"
GITHUB_PULL_REQUEST_2_COMMENTS = GITHUB_PULL_REQUEST_2_URL + "/comments"
GITHUB_PULL_REQUEST_2_COMMITS = GITHUB_PULL_REQUEST_2_URL + "/commits"
GITHUB_PULL_REQUEST_2_REVIEWS = GITHUB_PULL_REQUEST_2_URL + "/reviews"
GITHUB_PULL_REQUEST_2_REQUESTED_REVIEWERS_URL = GITHUB_PULL_REQUEST_2_URL + "/requested_reviewers"
GITHUB_USER_URL = GITHUB_API_URL + "/users/zhquan_example"
GITHUB_ORGS_URL = GITHUB_API_URL + "/users/zhquan_example/orgs"
GITHUB_COMMAND_URL = GITHUB_API_URL + "/command"

GITHUB_ENTERPRISE_URL = "https://example.com"
GITHUB_ENTERPRISE_API_URL = "https://example.com/api/v3"
GITHUB_ENTREPRISE_RATE_LIMIT = GITHUB_ENTERPRISE_API_URL + "/rate_limit"
GITHUB_ENTREPRISE_REPO_URL = GITHUB_ENTERPRISE_API_URL + "/repos/zhquan_example/repo"
GITHUB_ENTERPRISE_ISSUES_URL = GITHUB_ENTREPRISE_REPO_URL + "/issues"
GITHUB_ENTERPRISE_PULL_REQUESTS_URL = GITHUB_ENTREPRISE_REPO_URL + "/pulls"
GITHUB_ENTERPRISE_ISSUE_1_COMMENTS_URL = GITHUB_ENTERPRISE_ISSUES_URL + "/1/comments"
GITHUB_ENTERPRISE_ISSUE_COMMENT_1_REACTION_URL = GITHUB_ENTERPRISE_ISSUES_URL + "/comments/1/reactions"
GITHUB_ENTERPRISE_ISSUE_2_REACTION_URL = GITHUB_ENTERPRISE_ISSUES_URL + "/2/reactions"
GITHUB_ENTERPRISE_ISSUE_2_COMMENTS_URL = GITHUB_ENTERPRISE_ISSUES_URL + "/2/comments"
GITHUB_ENTERPRISE_ISSUE_COMMENT_2_REACTION_URL = GITHUB_ENTERPRISE_ISSUES_URL + "/comments/2/reactions"
GITHUB_ENTERPRISE_USER_URL = GITHUB_ENTERPRISE_API_URL + "/users/zhquan_example"
GITHUB_ENTERPRISE_ORGS_URL = GITHUB_ENTERPRISE_API_URL + "/users/zhquan_example/orgs"
GITHUB_ENTREPRISE_PULL_REQUEST_1_URL = GITHUB_ENTERPRISE_PULL_REQUESTS_URL + "/1"
GITHUB_ENTREPRISE_PULL_REQUEST_1_COMMENTS = GITHUB_ENTREPRISE_PULL_REQUEST_1_URL + "/comments"
GITHUB_ENTREPRISE_PULL_REQUEST_1_COMMITS = GITHUB_ENTREPRISE_PULL_REQUEST_1_URL + "/commits"
GITHUB_ENTREPRISE_PULL_REQUEST_1_REVIEWS = GITHUB_ENTREPRISE_PULL_REQUEST_1_URL + "/reviews"
GITHUB_ENTREPRISE_PULL_REQUEST_1_COMMENTS_2_REACTIONS = GITHUB_ENTERPRISE_PULL_REQUESTS_URL + "/comments/2/reactions"
GITHUB_ENTREPRISE_REQUEST_REQUESTED_REVIEWERS_URL = GITHUB_ENTREPRISE_PULL_REQUEST_1_URL + "/requested_reviewers"
GITHUB_APP_INSTALLATION_URL = GITHUB_API_URL + '/app/installations'
GITHUB_APP_ACCESS_TOKEN_URL = GITHUB_APP_INSTALLATION_URL + '/1/access_tokens'
GITHUB_APP_AUTH_URL = GITHUB_API_URL + '/installation/repositories'


def read_file(filename, mode='r'):
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), filename), mode) as f:
        content = f.read()
    return content


class TestGitHubBackend(unittest.TestCase):
    """ GitHub backend tests """

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

        github = GitHub('zhquan_example', 'repo', ['aaa'], tag='test')

        self.assertEqual(github.owner, 'zhquan_example')
        self.assertEqual(github.repository, 'repo')
        self.assertEqual(github.origin, 'https://github.com/zhquan_example/repo')
        self.assertEqual(github.tag, 'test')
        self.assertEqual(github.max_items, MAX_CATEGORY_ITEMS_PER_PAGE)
        self.assertFalse(github.exclude_user_data)
        self.assertEqual(github.categories, [CATEGORY_ISSUE, CATEGORY_PULL_REQUEST, CATEGORY_REPO])
        self.assertTrue(github.ssl_verify)

        # When tag is empty or None it will be set to the value in origin
        github = GitHub('zhquan_example', 'repo', ['aaa'], ssl_verify=False)
        self.assertEqual(github.owner, 'zhquan_example')
        self.assertEqual(github.repository, 'repo')
        self.assertEqual(github.origin, 'https://github.com/zhquan_example/repo')
        self.assertEqual(github.tag, 'https://github.com/zhquan_example/repo')
        self.assertFalse(github.ssl_verify)

        github = GitHub('zhquan_example', 'repo', ['aaa'], tag='')
        self.assertEqual(github.owner, 'zhquan_example')
        self.assertEqual(github.repository, 'repo')
        self.assertEqual(github.origin, 'https://github.com/zhquan_example/repo')
        self.assertEqual(github.tag, 'https://github.com/zhquan_example/repo')

    def test_pool_of_tokens_initialization(self):
        """Test whether tokens parameter is initialized"""

        rate_limit = read_file('data/github/rate_limit')
        httpretty.register_uri(httpretty.GET,
                               GITHUB_RATE_LIMIT,
                               body=rate_limit,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        # Empty values generate an empty list of tokens
        github = GitHub('zhquan_example', 'repo', tag='test')
        self.assertListEqual(github.api_token, [])

        github = GitHub('zhquan_example', 'repo', api_token=[], tag='test')
        self.assertListEqual(github.api_token, [])

        # Initialize the tokens with a list
        github = GitHub('zhquan_example', 'repo', api_token=['aaa'], tag='test')
        self.assertListEqual(github.api_token, ['aaa'])

        github = GitHub('zhquan_example', 'repo', api_token=['aaa', 'bbb'], tag='')
        self.assertListEqual(github.api_token, ['aaa', 'bbb'])

    def test_has_resuming(self):
        """Test if it returns True when has_resuming is called"""

        self.assertEqual(GitHub.has_resuming(), True)

    def test_has_archiving(self):
        """Test if it returns True when has_archiving is called"""

        self.assertEqual(GitHub.has_archiving(), True)

    @httpretty.activate
    def test_fetch_issues(self):
        """Test whether a list of issues is returned"""

        body = read_file('data/github/github_request')
        login = read_file('data/github/github_login')
        orgs = read_file('data/github/github_orgs')
        comments = read_file('data/github/github_issue_comments_1')
        reactions = read_file('data/github/github_issue_comment_1_reactions')
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
                               body=body,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUE_1_COMMENTS_URL,
                               body=comments, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUE_COMMENT_1_REACTION_URL,
                               body=reactions, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_USER_URL,
                               body=login, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ORGS_URL,
                               body=orgs, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        github = GitHub("zhquan_example", "repo", ["aaa"])
        issues = [issues for issues in github.fetch(from_date=None, to_date=None)]

        self.assertEqual(len(issues), 1)

        issue = issues[0]
        self.assertEqual(issue['origin'], 'https://github.com/zhquan_example/repo')
        self.assertEqual(issue['uuid'], '58c073fd2a388c44043b9cc197c73c5c540270ac')
        self.assertEqual(issue['updated_on'], 1454328801.0)
        self.assertEqual(issue['category'], CATEGORY_ISSUE)
        self.assertEqual(issue['tag'], 'https://github.com/zhquan_example/repo')
        self.assertEqual(issue['data']['assignee_data']['login'], 'zhquan_example')
        self.assertEqual(len(issue['data']['assignees_data']), 1)
        self.assertEqual(issue['data']['assignees_data'][0]['login'], 'zhquan_example')
        self.assertEqual(len(issue['data']['comments_data']), 1)
        self.assertEqual(issue['data']['comments_data'][0]['user_data']['login'], 'zhquan_example')
        self.assertEqual(len(issue['data']['comments_data'][0]['reactions_data']),
                         issue['data']['comments_data'][0]['reactions']['total_count'])
        self.assertEqual(issue['data']['comments_data'][0]['reactions_data'][0]['user_data']['login'], 'zhquan_example')

    @httpretty.activate
    def test_fetch_issues_no_user_data(self):
        """Test whether a list of issues is returned without user data"""

        body = read_file('data/github/github_request')
        login = read_file('data/github/github_login')
        orgs = read_file('data/github/github_orgs')
        comments = read_file('data/github/github_issue_comments_1')
        reactions = read_file('data/github/github_issue_comment_1_reactions')
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
                               body=body,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUE_1_COMMENTS_URL,
                               body=comments, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUE_COMMENT_1_REACTION_URL,
                               body=reactions, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_USER_URL,
                               body=login, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ORGS_URL,
                               body=orgs, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        github = GitHub("zhquan_example", "repo", ["aaa"])
        issues = [issues for issues in github.fetch(from_date=None, to_date=None, filter_classified=True)]

        self.assertEqual(len(issues), 1)

        issue = issues[0]
        self.assertEqual(issue['origin'], 'https://github.com/zhquan_example/repo')
        self.assertEqual(issue['uuid'], '58c073fd2a388c44043b9cc197c73c5c540270ac')
        self.assertEqual(issue['updated_on'], 1454328801.0)
        self.assertEqual(issue['category'], CATEGORY_ISSUE)
        self.assertEqual(issue['tag'], 'https://github.com/zhquan_example/repo')
        self.assertNotIn('assignee_data', issue['data'])
        self.assertEqual(len(issue['data']['comments_data']), 1)
        self.assertNotIn('user_data', issue['data']['comments_data'][0])
        self.assertEqual(len(issue['data']['comments_data'][0]['reactions_data']),
                         issue['data']['comments_data'][0]['reactions']['total_count'])
        self.assertNotIn('user_data', issue['data']['comments_data'][0]['reactions_data'][0])

    @httpretty.activate
    def test_fetch_filtering_classified_fields(self):
        """Test if it removes classified fields from a set of fetched items"""

        body = read_file('data/github/github_request')
        login = read_file('data/github/github_login')
        orgs = read_file('data/github/github_orgs')
        rate_limit = read_file('data/github/rate_limit')
        # Issue
        comments = read_file('data/github/github_issue_comments_1')
        reactions = read_file('data/github/github_issue_comment_1_reactions')
        # Pull request
        pull = read_file('data/github/github_request_pull_request_1')
        pull_comments = read_file('data/github/github_request_pull_request_1_comments')
        pull_reviews_1 = read_file('data/github/github_request_pull_request_1_reviews')
        pull_commits = read_file('data/github/github_request_pull_request_1_commits')
        pull_comment_2_reactions = read_file('data/github/github_request_pull_request_1_comment_2_reactions')
        pull_requested_reviewers = read_file('data/github/github_request_requested_reviewers')

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
                               body=body,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUE_1_COMMENTS_URL,
                               body=comments, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUE_COMMENT_1_REACTION_URL,
                               body=reactions, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_USER_URL,
                               body=login, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ORGS_URL,
                               body=orgs, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_1_URL,
                               body=pull,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_1_COMMENTS,
                               body=pull_comments,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_1_REVIEWS,
                               body=pull_reviews_1,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_1_COMMITS,
                               body=pull_commits,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_1_COMMENTS_2_REACTIONS,
                               body=pull_comment_2_reactions,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_1_REQUESTED_REVIEWERS_URL,
                               body=pull_requested_reviewers, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        github = GitHub("zhquan_example", "repo", ["aaa"])

        # Issues
        issues = [issues for issues in github.fetch(from_date=None, to_date=None, filter_classified=True)]
        for issue in issues:
            self.assertEqual(issue['classified_fields_filtered'], ['user_data',
                                                                   'merged_by_data',
                                                                   'assignee_data',
                                                                   'assignees_data',
                                                                   'requested_reviewers_data',
                                                                   'comments_data.user_data',
                                                                   'comments_data.reactions_data.user_data',
                                                                   'reviews_data.user_data',
                                                                   'review_comments_data.user_data',
                                                                   'review_comments_data.reactions_data.user_data'])
            self.assertNotIn('user_data', issue['data'])
            self.assertNotIn('assignee_data', issue['data'])
            self.assertNotIn('assignees_data', issue['data'])
            self.assertNotIn('user_data', issue['data']['comments_data'][0])
            self.assertNotIn('user_data', issue['data']['comments_data'][0]['reactions_data'][0])

        # Pulls
        pulls = [pulls for pulls in github.fetch(category=CATEGORY_PULL_REQUEST,
                                                 from_date=None,
                                                 to_date=None,
                                                 filter_classified=True)]
        for pull in pulls:
            self.assertEqual(pull['classified_fields_filtered'], ['user_data',
                                                                  'merged_by_data',
                                                                  'assignee_data',
                                                                  'assignees_data',
                                                                  'requested_reviewers_data',
                                                                  'comments_data.user_data',
                                                                  'comments_data.reactions_data.user_data',
                                                                  'reviews_data.user_data',
                                                                  'review_comments_data.user_data',
                                                                  'review_comments_data.reactions_data.user_data'])

            self.assertNotIn('merged_by_data', pull['data'])
            self.assertNotIn('requested_reviewers_data', pull['data'])
            self.assertNotIn('user_data', pull['data']['review_comments_data'][1]['reactions_data'][0])
            self.assertNotIn('user_data', pull['data']['review_comments_data'][1])
            self.assertNotIn('user_data', pull['data']['reviews_data'][0])

    @httpretty.activate
    def test_search_fields_issues(self):
        """Test whether the search_fields is properly set"""

        body = read_file('data/github/github_request')
        login = read_file('data/github/github_login')
        orgs = read_file('data/github/github_orgs')
        comments = read_file('data/github/github_issue_comments_1')
        reactions = read_file('data/github/github_issue_comment_1_reactions')
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
                               body=body,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUE_1_COMMENTS_URL,
                               body=comments, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUE_COMMENT_1_REACTION_URL,
                               body=reactions, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_USER_URL,
                               body=login, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ORGS_URL,
                               body=orgs, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        github = GitHub("zhquan_example", "repo", ["aaa"])
        issues = [issues for issues in github.fetch(from_date=None, to_date=None)]

        issue = issues[0]
        self.assertEqual(github.metadata_id(issue['data']), issue['search_fields']['item_id'])
        self.assertEqual(issue['search_fields']['owner'], 'zhquan_example')
        self.assertEqual(issue['search_fields']['repo'], 'repo')

    @httpretty.activate
    def test_fetch_pulls(self):
        """Test whether a list of pull requests is returned"""

        body = read_file('data/github/github_request')
        login = read_file('data/github/github_login')
        orgs = read_file('data/github/github_orgs')
        pull = read_file('data/github/github_request_pull_request_1')
        pull_comments = read_file('data/github/github_request_pull_request_1_comments')
        pull_reviews_1 = read_file('data/github/github_request_pull_request_1_reviews')
        pull_commits = read_file('data/github/github_request_pull_request_1_commits')
        pull_comment_2_reactions = read_file('data/github/github_request_pull_request_1_comment_2_reactions')
        pull_requested_reviewers = read_file('data/github/github_request_requested_reviewers')
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
                               body=body,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_1_URL,
                               body=pull,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_1_COMMENTS,
                               body=pull_comments,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_1_REVIEWS,
                               body=pull_reviews_1,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_1_COMMITS,
                               body=pull_commits,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_1_COMMENTS_2_REACTIONS,
                               body=pull_comment_2_reactions,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_1_REQUESTED_REVIEWERS_URL,
                               body=pull_requested_reviewers, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        httpretty.register_uri(httpretty.GET,
                               GITHUB_USER_URL,
                               body=login, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ORGS_URL,
                               body=orgs, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        github = GitHub("zhquan_example", "repo", ["aaa"])
        pulls = [pulls for pulls in github.fetch(category=CATEGORY_PULL_REQUEST, from_date=None, to_date=None)]

        self.assertEqual(len(pulls), 1)

        pull = pulls[0]
        self.assertEqual(pull['origin'], 'https://github.com/zhquan_example/repo')
        self.assertEqual(pull['uuid'], '58c073fd2a388c44043b9cc197c73c5c540270ac')
        self.assertEqual(pull['updated_on'], 1451929343.0)
        self.assertEqual(pull['category'], CATEGORY_PULL_REQUEST)
        self.assertEqual(pull['tag'], 'https://github.com/zhquan_example/repo')
        self.assertEqual(pull['data']['merged_by_data']['login'], 'zhquan_example')
        self.assertEqual(len(pull['data']['requested_reviewers_data']), 1)
        self.assertEqual(pull['data']['requested_reviewers_data'][0]['login'], 'zhquan_example')
        self.assertEqual(len(pull['data']['review_comments_data']), 2)
        self.assertEqual(len(pull['data']['review_comments_data'][0]['reactions_data']), 0)
        self.assertEqual(len(pull['data']['review_comments_data'][1]['reactions_data']), 5)
        self.assertEqual(pull['data']['review_comments_data'][1]['reactions_data'][0]['content'], 'heart')
        self.assertEqual(len(pull['data']['commits_data']), 1)
        self.assertEqual(len(pull['data']['reviews_data']), 2)
        self.assertEqual(pull['data']['reviews_data'][0]['user_data']['login'], 'zhquan_example')

    @httpretty.activate
    def test_fetch_pulls_ghost_reviewer(self):
        """Test whether a warning is thrown when request reviewer info cannot be retrieved"""

        body = read_file('data/github/github_request')
        login = read_file('data/github/github_login')
        orgs = read_file('data/github/github_orgs')
        pull = read_file('data/github/github_request_pull_request_1')
        pull_comments = read_file('data/github/github_request_pull_request_1_comments')
        pull_reviews_1 = read_file('data/github/github_request_pull_request_1_reviews')
        pull_commits = read_file('data/github/github_request_pull_request_1_commits')
        pull_comment_2_reactions = read_file('data/github/github_request_pull_request_1_comment_2_reactions')
        pull_requested_reviewers = read_file('data/github/github_request_requested_reviewers_ghost')
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
                               body=body,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_1_URL,
                               body=pull,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_1_COMMENTS,
                               body=pull_comments,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_1_REVIEWS,
                               body=pull_reviews_1,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_1_COMMITS,
                               body=pull_commits,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_1_COMMENTS_2_REACTIONS,
                               body=pull_comment_2_reactions,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_1_REQUESTED_REVIEWERS_URL,
                               body=pull_requested_reviewers, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        httpretty.register_uri(httpretty.GET,
                               GITHUB_USER_URL,
                               body=login, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ORGS_URL,
                               body=orgs, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        github = GitHub("zhquan_example", "repo", ["aaa"])

        with self.assertLogs(logger, level='WARNING') as cm:
            pulls = [pulls for pulls in github.fetch(category=CATEGORY_PULL_REQUEST, from_date=None, to_date=None)]

            self.assertEqual(cm.output[-1],
                             'WARNING:perceval.backends.core.github:Impossible to identify '
                             'requested reviewer for pull request 1')

        self.assertEqual(len(pulls), 1)

        pull = pulls[0]
        self.assertEqual(pull['origin'], 'https://github.com/zhquan_example/repo')
        self.assertEqual(pull['uuid'], '58c073fd2a388c44043b9cc197c73c5c540270ac')
        self.assertEqual(pull['updated_on'], 1451929343.0)
        self.assertEqual(pull['category'], CATEGORY_PULL_REQUEST)
        self.assertEqual(pull['tag'], 'https://github.com/zhquan_example/repo')
        self.assertEqual(pull['data']['merged_by_data']['login'], 'zhquan_example')
        self.assertEqual(len(pull['data']['requested_reviewers_data']), 1)
        self.assertEqual(pull['data']['requested_reviewers_data'][0]['login'], 'zhquan_example')
        self.assertEqual(len(pull['data']['review_comments_data']), 2)
        self.assertEqual(len(pull['data']['review_comments_data'][0]['reactions_data']), 0)
        self.assertEqual(len(pull['data']['review_comments_data'][1]['reactions_data']), 5)
        self.assertEqual(pull['data']['review_comments_data'][1]['reactions_data'][0]['content'], 'heart')
        self.assertEqual(len(pull['data']['commits_data']), 1)
        self.assertEqual(len(pull['data']['reviews_data']), 2)
        self.assertEqual(pull['data']['reviews_data'][0]['user_data']['login'], 'zhquan_example')

    @httpretty.activate
    def test_fetch_pulls_no_user_data(self):
        """Test whether a list of pull requests is returned without user data"""

        body = read_file('data/github/github_request')
        login = read_file('data/github/github_login')
        orgs = read_file('data/github/github_orgs')
        pull = read_file('data/github/github_request_pull_request_1')
        pull_comments = read_file('data/github/github_request_pull_request_1_comments')
        pull_reviews_1 = read_file('data/github/github_request_pull_request_1_reviews')
        pull_commits = read_file('data/github/github_request_pull_request_1_commits')
        pull_comment_2_reactions = read_file('data/github/github_request_pull_request_1_comment_2_reactions')
        pull_requested_reviewers = read_file('data/github/github_request_requested_reviewers')
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
                               body=body,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_1_URL,
                               body=pull,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_1_COMMENTS,
                               body=pull_comments,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_1_REVIEWS,
                               body=pull_reviews_1,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_1_COMMITS,
                               body=pull_commits,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_1_COMMENTS_2_REACTIONS,
                               body=pull_comment_2_reactions,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_1_REQUESTED_REVIEWERS_URL,
                               body=pull_requested_reviewers, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        httpretty.register_uri(httpretty.GET,
                               GITHUB_USER_URL,
                               body=login, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ORGS_URL,
                               body=orgs, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        github = GitHub("zhquan_example", "repo", ["aaa"])
        pulls = [pulls for pulls in github.fetch(category=CATEGORY_PULL_REQUEST,
                                                 from_date=None,
                                                 to_date=None,
                                                 filter_classified=True)]

        self.assertEqual(len(pulls), 1)

        pull = pulls[0]
        self.assertEqual(pull['origin'], 'https://github.com/zhquan_example/repo')
        self.assertEqual(pull['uuid'], '58c073fd2a388c44043b9cc197c73c5c540270ac')
        self.assertEqual(pull['updated_on'], 1451929343.0)
        self.assertEqual(pull['category'], CATEGORY_PULL_REQUEST)
        self.assertEqual(pull['tag'], 'https://github.com/zhquan_example/repo')
        self.assertNotIn('merged_by_data', pull['data'])
        self.assertNotIn('requested_reviewers_data', pull['data'])
        self.assertEqual(len(pull['data']['review_comments_data']), 2)
        self.assertEqual(len(pull['data']['review_comments_data'][0]['reactions_data']), 0)
        self.assertEqual(len(pull['data']['review_comments_data'][1]['reactions_data']), 5)
        self.assertEqual(pull['data']['review_comments_data'][1]['reactions_data'][0]['content'], 'heart')
        self.assertNotIn('user_data', pull['data']['review_comments_data'][1]['reactions_data'][0])
        self.assertEqual(len(pull['data']['commits_data']), 1)
        self.assertEqual(len(pull['data']['reviews_data']), 2)
        self.assertNotIn('user_data', pull['data']['reviews_data'][0])

    @httpretty.activate
    def test_search_fields_pulls(self):
        """Test whether the search_fields is properly set"""

        body = read_file('data/github/github_request')
        login = read_file('data/github/github_login')
        orgs = read_file('data/github/github_orgs')
        pull = read_file('data/github/github_request_pull_request_1')
        pull_comments = read_file('data/github/github_request_pull_request_1_comments')
        pull_reviews_1 = read_file('data/github/github_request_pull_request_1_reviews')
        pull_commits = read_file('data/github/github_request_pull_request_1_commits')
        pull_comment_2_reactions = read_file('data/github/github_request_pull_request_1_comment_2_reactions')
        pull_requested_reviewers = read_file('data/github/github_request_requested_reviewers')
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
                               body=body,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_1_URL,
                               body=pull,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_1_COMMENTS,
                               body=pull_comments,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_1_REVIEWS,
                               body=pull_reviews_1,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_1_COMMITS,
                               body=pull_commits,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_1_COMMENTS_2_REACTIONS,
                               body=pull_comment_2_reactions,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_1_REQUESTED_REVIEWERS_URL,
                               body=pull_requested_reviewers, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        httpretty.register_uri(httpretty.GET,
                               GITHUB_USER_URL,
                               body=login, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ORGS_URL,
                               body=orgs, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        github = GitHub("zhquan_example", "repo", ["aaa"])
        pulls = [pulls for pulls in github.fetch(category=CATEGORY_PULL_REQUEST, from_date=None, to_date=None)]

        pull = pulls[0]
        self.assertEqual(github.metadata_id(pull['data']), pull['search_fields']['item_id'])
        self.assertEqual(pull['search_fields']['owner'], 'zhquan_example')
        self.assertEqual(pull['search_fields']['repo'], 'repo')

    @httpretty.activate
    @unittest.mock.patch('perceval.backends.core.github.datetime_utcnow')
    def test_fetch_repo(self, mock_utcnow):
        """Test whether repo information is returned"""

        mock_utcnow.return_value = datetime.datetime(2017, 1, 1,
                                                     tzinfo=dateutil.tz.tzutc())

        body = read_file('data/github/github_repo')
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
                               GITHUB_REPO_URL,
                               body=body,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        github = GitHub("zhquan_example", "repo", "aaa")
        repo = [repo for repo in github.fetch(category=CATEGORY_REPO)]

        self.assertEqual(len(repo), 1)

        repo_info = repo[0]

        self.assertEqual(repo_info['origin'], 'https://github.com/zhquan_example/repo')
        self.assertEqual(repo_info['uuid'], '7b352ce00a800d755d34be63b09cf2840d45a8b8')
        self.assertEqual(repo_info['updated_on'], 1483228800.0)
        self.assertEqual(repo_info['category'], CATEGORY_REPO)
        self.assertEqual(repo_info['tag'], 'https://github.com/zhquan_example/repo')
        self.assertEqual(repo_info['data']['forks'], 16687)
        self.assertEqual(repo_info['data']['stargazers_count'], 48188)
        self.assertEqual(repo_info['data']['subscribers_count'], 2904)
        self.assertEqual(repo_info['data']['updated_at'], "2019-02-14T16:21:58Z")
        self.assertEqual(repo_info['data']['fetched_on'], 1483228800.0)

    @httpretty.activate
    @unittest.mock.patch('perceval.backends.core.github.datetime_utcnow')
    def test_search_fields_repo(self, mock_utcnow):
        """Test whether the search_fields is properly set"""

        mock_utcnow.return_value = datetime.datetime(2017, 1, 1,
                                                     tzinfo=dateutil.tz.tzutc())

        body = read_file('data/github/github_repo')
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
                               GITHUB_REPO_URL,
                               body=body,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        github = GitHub("zhquan_example", "repo", "aaa")
        repo = [repo for repo in github.fetch(category=CATEGORY_REPO)]

        repo_info = repo[0]
        self.assertEqual(github.metadata_id(repo_info['data']), repo_info['search_fields']['item_id'])
        self.assertEqual(repo_info['search_fields']['owner'], 'zhquan_example')
        self.assertEqual(repo_info['search_fields']['repo'], 'repo')

    @httpretty.activate
    def test_fetch_more_issues(self):
        """Test when return two issues"""

        login = read_file('data/github/github_login')
        orgs = read_file('data/github/github_orgs')
        issue_1 = read_file('data/github/github_issue_1')
        issue_2 = read_file('data/github/github_issue_2')
        issue_2_reactions = read_file('data/github/github_issue_2_reactions')
        issue_1_comments = read_file('data/github/github_issue_comments_1')
        issue_2_comments = read_file('data/github/github_issue_comments_2')
        issue_comment_1_reactions = read_file('data/github/github_issue_comment_1_reactions')
        issue_comment_2_reactions = read_file('data/github/github_empty_request')
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
                               body=issue_1,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '5',
                                   'Link': '<' + GITHUB_ISSUES_URL + '/?&page=2>; rel="next", <' +
                                           GITHUB_ISSUES_URL + '/?&page=3>; rel="last"'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUE_1_COMMENTS_URL,
                               body=issue_1_comments, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUE_COMMENT_1_REACTION_URL,
                               body=issue_comment_1_reactions, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUES_URL + '/?&page=2',
                               body=issue_2,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '5'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUE_2_REACTION_URL,
                               body=issue_2_reactions, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUE_2_COMMENTS_URL,
                               body=issue_2_comments, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUE_COMMENT_2_REACTION_URL,
                               body=issue_comment_2_reactions, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_USER_URL,
                               body=login, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '5'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ORGS_URL,
                               body=orgs, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '5'
                               })

        github = GitHub("zhquan_example", "repo", ["aaa"])
        issues = [issues for issues in github.fetch()]

        self.assertEqual(len(issues), 2)

        issue = issues[0]
        self.assertEqual(issue['origin'], 'https://github.com/zhquan_example/repo')
        self.assertEqual(issue['uuid'], '58c073fd2a388c44043b9cc197c73c5c540270ac')
        self.assertEqual(issue['updated_on'], 1458035782.0)
        self.assertEqual(issue['category'], CATEGORY_ISSUE)
        self.assertEqual(issue['tag'], 'https://github.com/zhquan_example/repo')
        self.assertEqual(issue['data']['assignee_data']['login'], 'zhquan_example')
        self.assertEqual(len(issue['data']['assignees_data']), 1)
        self.assertEqual(len(issue['data']['comments_data']), 1)
        self.assertEqual(issue['data']['reactions']['total_count'], len(issue['data']['reactions_data']))
        self.assertEqual(issue['data']['comments_data'][0]['user_data']['login'], 'zhquan_example')
        self.assertEqual(issue['data']['comments_data'][0]['reactions']['total_count'],
                         len(issue['data']['comments_data'][0]['reactions_data']))

        issue = issues[1]
        self.assertEqual(issue['origin'], 'https://github.com/zhquan_example/repo')
        self.assertEqual(issue['uuid'], '4236619ac2073491640f1698b5c4e169895aaf69')
        self.assertEqual(issue['updated_on'], 1463324969.0)
        self.assertEqual(issue['category'], CATEGORY_ISSUE)
        self.assertEqual(issue['tag'], 'https://github.com/zhquan_example/repo')
        self.assertEqual(issue['data']['assignees_data'], [])
        self.assertEqual(len(issue['data']['comments_data']), 1)
        self.assertEqual(issue['data']['reactions']['total_count'], len(issue['data']['reactions_data']))
        self.assertEqual(issue['data']['comments_data'][0]['user_data']['login'], 'zhquan_example')
        self.assertEqual(issue['data']['comments_data'][0]['reactions']['total_count'],
                         len(issue['data']['comments_data'][0]['reactions_data']))

    @httpretty.activate
    def test_fetch_more_pulls(self):
        """Test when return two pulls"""

        login = read_file('data/github/github_login')
        orgs = read_file('data/github/github_orgs')
        issue_1 = read_file('data/github/github_issue_1')
        issue_2 = read_file('data/github/github_issue_2_with_pr')
        pull_1 = read_file('data/github/github_request_pull_request_1')
        pull_1_comments = read_file('data/github/github_request_pull_request_1_comments')
        pull_1_reviews = read_file('data/github/github_request_pull_request_1_reviews')
        pull_1_commits = read_file('data/github/github_request_pull_request_1_commits')
        pull_1_comment_2_reactions = read_file('data/github/github_request_pull_request_1_comment_2_reactions')
        pull_requested_reviewers = read_file('data/github/github_request_requested_reviewers')
        pull_2 = read_file('data/github/github_request_pull_request_2')
        pull_2_comments = read_file('data/github/github_request_pull_request_2_comments')
        pull_2_reviews = read_file('data/github/github_request_pull_request_2_reviews')
        pull_2_commits = read_file('data/github/github_request_pull_request_2_commits')
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
                               body=issue_1,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '5',
                                   'Link': '<' + GITHUB_ISSUES_URL + '/?&page=2>; rel="next", <' +
                                           GITHUB_ISSUES_URL + '/?&page=3>; rel="last"'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUES_URL + '/?&page=2',
                               body=issue_2,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '5'
                               })

        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_1_URL,
                               body=pull_1,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_1_COMMENTS,
                               body=pull_1_comments,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_1_COMMITS,
                               body=pull_1_commits,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_1_COMMENTS_2_REACTIONS,
                               body=pull_1_comment_2_reactions,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_1_REVIEWS,
                               body=pull_1_reviews, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_1_REQUESTED_REVIEWERS_URL,
                               body=pull_requested_reviewers, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_2_URL,
                               body=pull_2,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_2_COMMENTS,
                               body=pull_2_comments,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_2_COMMITS,
                               body=pull_2_commits,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_2_REVIEWS,
                               body=pull_2_reviews,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_2_REQUESTED_REVIEWERS_URL,
                               body=[],
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        httpretty.register_uri(httpretty.GET,
                               GITHUB_USER_URL,
                               body=login, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '5'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ORGS_URL,
                               body=orgs, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '5'
                               })

        github = GitHub("zhquan_example", "repo", ["aaa"])

        with self.assertLogs(logger) as cm:
            pulls = [pulls for pulls in github.fetch(category=CATEGORY_PULL_REQUEST, from_date=None)]

            self.assertEqual(len(pulls), 2)

            pull = pulls[0]
            self.assertEqual(pull['origin'], 'https://github.com/zhquan_example/repo')
            self.assertEqual(pull['uuid'], '58c073fd2a388c44043b9cc197c73c5c540270ac')
            self.assertEqual(pull['updated_on'], 1451929343.0)
            self.assertEqual(pull['category'], CATEGORY_PULL_REQUEST)
            self.assertEqual(pull['tag'], 'https://github.com/zhquan_example/repo')
            self.assertEqual(pull['data']['merged_by_data']['login'], 'zhquan_example')
            self.assertEqual(len(pull['data']['requested_reviewers_data']), 1)
            self.assertEqual(pull['data']['requested_reviewers_data'][0]['login'], 'zhquan_example')
            self.assertEqual(len(pull['data']['review_comments_data']), 2)
            self.assertEqual(len(pull['data']['review_comments_data'][0]['reactions_data']), 0)
            self.assertEqual(len(pull['data']['review_comments_data'][1]['reactions_data']), 5)
            self.assertEqual(pull['data']['review_comments_data'][1]['reactions_data'][0]['content'], 'heart')
            self.assertEqual(len(pull['data']['reviews_data']), 2)
            self.assertEqual(pull['data']['reviews_data'][0]['user_data']['login'], 'zhquan_example')
            self.assertEqual(len(pull['data']['commits_data']), 1)

            pull = pulls[1]
            self.assertEqual(pull['origin'], 'https://github.com/zhquan_example/repo')
            self.assertEqual(pull['uuid'], '58c073fd2a388c44043b9cc197c73c5c540270ac')
            self.assertEqual(pull['updated_on'], 1457113343.0)
            self.assertEqual(pull['category'], CATEGORY_PULL_REQUEST)
            self.assertEqual(pull['tag'], 'https://github.com/zhquan_example/repo')
            self.assertEqual(pull['data']['merged_by_data']['login'], 'zhquan_example')
            self.assertEqual(pull['data']['requested_reviewers_data'], [])
            self.assertEqual(len(pull['data']['review_comments_data']), 4)
            self.assertEqual(len(pull['data']['review_comments_data'][0]['reactions_data']), 0)
            self.assertEqual(len(pull['data']['review_comments_data'][1]['reactions_data']), 0)
            self.assertEqual(len(pull['data']['commits_data']), 1)
            self.assertEqual(len(pull['data']['reviews_data']), 1)
            self.assertEqual(pull['data']['reviews_data'][0]['user_data']['login'], 'zhquan_example')
            self.assertEqual(pull['data']['review_comments_data'][0]['user_data']['login'], "zhquan_example")
            self.assertIsNone(pull['data']['review_comments_data'][2]['user_data'])

            self.assertEqual(cm.output[0],
                             'WARNING:perceval.backends.core.github:'
                             'Missing user info for https://github.com/zhquan_example/repo/pull/88#pullrequestreview-205729183')

            self.assertEqual(cm.output[1],
                             'WARNING:perceval.backends.core.github:'
                             'Missing user info for https://api.github.com/repos/zhquan_example/repo/pulls/comments/2')

            self.assertEqual(cm.output[2],
                             'WARNING:perceval.backends.core.github:'
                             'Missing user info for https://api.github.com/repos/zhquan_example/repo/pulls/comments/2')

    @httpretty.activate
    def test_fetch_more_issues_no_user_data(self):
        """Test whether a list of issues is returned without user data"""

        login = read_file('data/github/github_login')
        orgs = read_file('data/github/github_orgs')
        issue_1 = read_file('data/github/github_issue_1')
        issue_2 = read_file('data/github/github_issue_2')
        issue_2_reactions = read_file('data/github/github_issue_2_reactions')
        issue_1_comments = read_file('data/github/github_issue_comments_1')
        issue_2_comments = read_file('data/github/github_issue_comments_2')
        issue_comment_1_reactions = read_file('data/github/github_issue_comment_1_reactions')
        issue_comment_2_reactions = read_file('data/github/github_empty_request')
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
                               body=issue_1,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '5',
                                   'Link': '<' + GITHUB_ISSUES_URL + '/?&page=2>; rel="next", <' +
                                           GITHUB_ISSUES_URL + '/?&page=3>; rel="last"'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUE_1_COMMENTS_URL,
                               body=issue_1_comments, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUE_COMMENT_1_REACTION_URL,
                               body=issue_comment_1_reactions, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUES_URL + '/?&page=2',
                               body=issue_2,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '5'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUE_2_REACTION_URL,
                               body=issue_2_reactions, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUE_2_COMMENTS_URL,
                               body=issue_2_comments, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUE_COMMENT_2_REACTION_URL,
                               body=issue_comment_2_reactions, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_USER_URL,
                               body=login, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '5'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ORGS_URL,
                               body=orgs, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '5'
                               })

        github = GitHub("zhquan_example", "repo", ["aaa"])
        issues = [issues for issues in github.fetch(filter_classified=True)]

        self.assertEqual(len(issues), 2)

        issue = issues[0]
        self.assertEqual(issue['origin'], 'https://github.com/zhquan_example/repo')
        self.assertEqual(issue['uuid'], '58c073fd2a388c44043b9cc197c73c5c540270ac')
        self.assertEqual(issue['updated_on'], 1458035782.0)
        self.assertEqual(issue['category'], CATEGORY_ISSUE)
        self.assertEqual(issue['tag'], 'https://github.com/zhquan_example/repo')
        self.assertNotIn('assignee_data', issue['data'])
        self.assertEqual(len(issue['data']['comments_data']), 1)
        self.assertEqual(issue['data']['reactions']['total_count'], len(issue['data']['reactions_data']))
        self.assertNotIn('user_data', issue['data']['comments_data'][0])
        self.assertEqual(issue['data']['comments_data'][0]['reactions']['total_count'],
                         len(issue['data']['comments_data'][0]['reactions_data']))

        issue = issues[1]
        self.assertEqual(issue['origin'], 'https://github.com/zhquan_example/repo')
        self.assertEqual(issue['uuid'], '4236619ac2073491640f1698b5c4e169895aaf69')
        self.assertEqual(issue['updated_on'], 1463324969.0)
        self.assertEqual(issue['category'], CATEGORY_ISSUE)
        self.assertEqual(issue['tag'], 'https://github.com/zhquan_example/repo')
        self.assertNotIn('assignees_data', issue['data'])
        self.assertEqual(len(issue['data']['comments_data']), 1)
        self.assertEqual(issue['data']['reactions']['total_count'], len(issue['data']['reactions_data']))
        self.assertNotIn('user_data', issue['data']['comments_data'][0])
        self.assertEqual(issue['data']['comments_data'][0]['reactions']['total_count'],
                         len(issue['data']['comments_data'][0]['reactions_data']))

    @httpretty.activate
    def test_fetch_more_pulls_no_user_data(self):
        """Test whether a list of pull requests is returned without user data"""

        login = read_file('data/github/github_login')
        orgs = read_file('data/github/github_orgs')
        issue_1 = read_file('data/github/github_issue_1')
        issue_2 = read_file('data/github/github_issue_2_with_pr')
        pull_1 = read_file('data/github/github_request_pull_request_1')
        pull_1_comments = read_file('data/github/github_request_pull_request_1_comments')
        pull_1_reviews = read_file('data/github/github_request_pull_request_1_reviews')
        pull_1_commits = read_file('data/github/github_request_pull_request_1_commits')
        pull_1_comment_2_reactions = read_file('data/github/github_request_pull_request_1_comment_2_reactions')
        pull_requested_reviewers = read_file('data/github/github_request_requested_reviewers')
        pull_2 = read_file('data/github/github_request_pull_request_2')
        pull_2_comments = read_file('data/github/github_request_pull_request_2_comments')
        pull_2_reviews = read_file('data/github/github_request_pull_request_2_reviews')
        pull_2_commits = read_file('data/github/github_request_pull_request_2_commits')
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
                               body=issue_1,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '5',
                                   'Link': '<' + GITHUB_ISSUES_URL + '/?&page=2>; rel="next", <' +
                                           GITHUB_ISSUES_URL + '/?&page=3>; rel="last"'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUES_URL + '/?&page=2',
                               body=issue_2,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '5'
                               })

        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_1_URL,
                               body=pull_1,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_1_COMMENTS,
                               body=pull_1_comments,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_1_COMMITS,
                               body=pull_1_commits,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_1_COMMENTS_2_REACTIONS,
                               body=pull_1_comment_2_reactions,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_1_REVIEWS,
                               body=pull_1_reviews, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_1_REQUESTED_REVIEWERS_URL,
                               body=pull_requested_reviewers, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_2_URL,
                               body=pull_2,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_2_COMMENTS,
                               body=pull_2_comments,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_2_COMMITS,
                               body=pull_2_commits,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_2_REVIEWS,
                               body=pull_2_reviews,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_2_REQUESTED_REVIEWERS_URL,
                               body=[],
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        httpretty.register_uri(httpretty.GET,
                               GITHUB_USER_URL,
                               body=login, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '5'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ORGS_URL,
                               body=orgs, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '5'
                               })

        github = GitHub("zhquan_example", "repo", ["aaa"])

        with self.assertLogs(logger) as cm:
            pulls = [pulls for pulls in github.fetch(category=CATEGORY_PULL_REQUEST,
                                                     from_date=None,
                                                     filter_classified=True)]

            self.assertEqual(len(pulls), 2)

            pull = pulls[0]
            self.assertEqual(pull['origin'], 'https://github.com/zhquan_example/repo')
            self.assertEqual(pull['uuid'], '58c073fd2a388c44043b9cc197c73c5c540270ac')
            self.assertEqual(pull['updated_on'], 1451929343.0)
            self.assertEqual(pull['category'], CATEGORY_PULL_REQUEST)
            self.assertEqual(pull['tag'], 'https://github.com/zhquan_example/repo')
            self.assertNotIn('merged_by_data', pull['data'])
            self.assertNotIn('requested_reviewers_data', pull['data'])
            self.assertEqual(len(pull['data']['review_comments_data']), 2)
            self.assertEqual(len(pull['data']['review_comments_data'][0]['reactions_data']), 0)
            self.assertEqual(len(pull['data']['review_comments_data'][1]['reactions_data']), 5)
            self.assertEqual(pull['data']['review_comments_data'][1]['reactions_data'][0]['content'], 'heart')
            self.assertEqual(len(pull['data']['reviews_data']), 2)
            self.assertNotIn('user_data', pull['data']['reviews_data'][0])
            self.assertEqual(len(pull['data']['commits_data']), 1)

            pull = pulls[1]
            self.assertEqual(pull['origin'], 'https://github.com/zhquan_example/repo')
            self.assertEqual(pull['uuid'], '58c073fd2a388c44043b9cc197c73c5c540270ac')
            self.assertEqual(pull['updated_on'], 1457113343.0)
            self.assertEqual(pull['category'], CATEGORY_PULL_REQUEST)
            self.assertEqual(pull['tag'], 'https://github.com/zhquan_example/repo')
            self.assertNotIn('merged_by_data', pull['data'])
            self.assertNotIn('requested_reviewers_data', pull['data'])
            self.assertEqual(len(pull['data']['review_comments_data']), 4)
            self.assertEqual(len(pull['data']['review_comments_data'][0]['reactions_data']), 0)
            self.assertEqual(len(pull['data']['review_comments_data'][1]['reactions_data']), 0)
            self.assertEqual(len(pull['data']['commits_data']), 1)
            self.assertEqual(len(pull['data']['reviews_data']), 1)
            self.assertNotIn('user_data', pull['data']['reviews_data'][0])
            self.assertNotIn('user_data', pull['data']['review_comments_data'][0])
            self.assertNotIn('user_data', pull['data']['review_comments_data'][2])

            self.assertEqual(cm.output[0],
                             "INFO:perceval.backends.core.github:"
                             "Excluding user data. Personal user information won't be collected from the API.")

            self.assertEqual(cm.output[1],
                             'WARNING:perceval.backends.core.github:'
                             'Missing user info for https://github.com/zhquan_example/repo/pull/88#pullrequestreview-205729183')

            self.assertEqual(cm.output[2],
                             'WARNING:perceval.backends.core.github:'
                             'Missing user info for https://api.github.com/repos/zhquan_example/repo/pulls/comments/2')

            self.assertEqual(cm.output[3],
                             'WARNING:perceval.backends.core.github:'
                             'Missing user info for https://api.github.com/repos/zhquan_example/repo/pulls/comments/2')

    @httpretty.activate
    def test_fetch_pulls_from_issues(self):
        """Test when return pull requests are fetched from only issues with pull request data """

        login = read_file('data/github/github_login')
        orgs = read_file('data/github/github_orgs')
        issue_1 = read_file('data/github/github_issue_1')
        issue_2 = read_file('data/github/github_issue_2')
        pull_request = read_file('data/github/github_request_pull_request_1')
        pull_request_comments = read_file('data/github/github_request_pull_request_1_comments')
        pull_request_reviews = read_file('data/github/github_request_pull_request_1_reviews')
        pull_request_commits = read_file('data/github/github_request_pull_request_1_commits')
        pull_request_comment_2_reactions = read_file('data/github/github_request_pull_request_1_comment_2_reactions')
        pull_requested_reviewers = read_file('data/github/github_request_requested_reviewers')
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
                               body=issue_1,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '5',
                                   'Link': '<' + GITHUB_ISSUES_URL + '/?&page=2>; rel="next", <' +
                                           GITHUB_ISSUES_URL + '/?&page=3>; rel="last"'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_1_URL,
                               body=pull_request,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_1_COMMENTS,
                               body=pull_request_comments,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_1_REVIEWS,
                               body=pull_request_reviews,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_1_COMMITS,
                               body=pull_request_commits,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_1_COMMENTS_2_REACTIONS,
                               body=pull_request_comment_2_reactions,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_1_REQUESTED_REVIEWERS_URL,
                               body=pull_requested_reviewers, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUES_URL + '/?&page=2',
                               body=issue_2,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '5'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_USER_URL,
                               body=login, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '5'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ORGS_URL,
                               body=orgs, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '5'
                               })

        github = GitHub("zhquan_example", "repo", ["aaa"])
        pulls = [pulls for pulls in github.fetch(category=CATEGORY_PULL_REQUEST)]

        self.assertEqual(len(pulls), 1)

        pull = pulls[0]
        self.assertEqual(pull['origin'], 'https://github.com/zhquan_example/repo')
        self.assertEqual(pull['uuid'], '58c073fd2a388c44043b9cc197c73c5c540270ac')
        self.assertEqual(pull['updated_on'], 1451929343.0)
        self.assertEqual(pull['category'], CATEGORY_PULL_REQUEST)
        self.assertEqual(pull['tag'], 'https://github.com/zhquan_example/repo')
        self.assertEqual(pull['data']['merged_by_data']['login'], 'zhquan_example')
        self.assertEqual(len(pull['data']['requested_reviewers_data']), 1)
        self.assertEqual(pull['data']['requested_reviewers_data'][0]['login'], 'zhquan_example')
        self.assertEqual(len(pull['data']['review_comments_data']), 2)
        self.assertEqual(len(pull['data']['review_comments_data'][0]['reactions_data']), 0)
        self.assertEqual(len(pull['data']['review_comments_data'][1]['reactions_data']), 5)
        self.assertEqual(pull['data']['review_comments_data'][1]['reactions_data'][0]['content'], 'heart')
        self.assertEqual(len(pull['data']['commits_data']), 1)
        self.assertEqual(len(pull['data']['reviews_data']), 2)
        self.assertEqual(pull['data']['reviews_data'][0]['user_data']['login'], 'zhquan_example')

    @httpretty.activate
    def test_fetch_issues_until_date(self):
        """Test when return one issue"""

        login = read_file('data/github/github_login')
        orgs = read_file('data/github/github_orgs')
        issue_1 = read_file('data/github/github_issue_1')
        issue_2 = read_file('data/github/github_issue_2')
        issue_2_reactions = read_file('data/github/github_issue_2_reactions')
        issue_1_comments = read_file('data/github/github_issue_comments_1')
        issue_2_comments = read_file('data/github/github_issue_comments_2')
        issue_comment_1_reactions = read_file('data/github/github_issue_comment_1_reactions')
        issue_comment_2_reactions = read_file('data/github/github_empty_request')
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
                               body=issue_1,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '5',
                                   'Link': '<' + GITHUB_ISSUES_URL + '/?&page=2>; rel="next", <' +
                                           GITHUB_ISSUES_URL + '/?&page=3>; rel="last"'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUE_1_COMMENTS_URL,
                               body=issue_1_comments, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUE_COMMENT_1_REACTION_URL,
                               body=issue_comment_1_reactions, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUES_URL + '/?&page=2',
                               body=issue_2,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '5'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUE_2_REACTION_URL,
                               body=issue_2_reactions, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUE_2_COMMENTS_URL,
                               body=issue_2_comments, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUE_COMMENT_2_REACTION_URL,
                               body=issue_comment_2_reactions, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_USER_URL,
                               body=login, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '5'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ORGS_URL,
                               body=orgs, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '5'
                               })

        to_date = datetime.datetime(2016, 3, 16)
        github = GitHub("zhquan_example", "repo", ["aaa"])
        issues = [issues for issues in github.fetch(to_date=to_date)]

        self.assertEqual(len(issues), 1)

        issue = issues[0]
        self.assertEqual(issue['origin'], 'https://github.com/zhquan_example/repo')
        self.assertEqual(issue['uuid'], '58c073fd2a388c44043b9cc197c73c5c540270ac')
        self.assertEqual(issue['updated_on'], 1458035782.0)
        self.assertEqual(issue['category'], CATEGORY_ISSUE)
        self.assertEqual(issue['tag'], 'https://github.com/zhquan_example/repo')
        self.assertEqual(issue['data']['assignee_data']['login'], 'zhquan_example')
        self.assertEqual(len(issue['data']['assignees_data']), 1)
        self.assertEqual(len(issue['data']['comments_data']), 1)
        self.assertEqual(issue['data']['reactions']['total_count'], len(issue['data']['reactions_data']))
        self.assertEqual(issue['data']['comments_data'][0]['user_data']['login'], 'zhquan_example')
        self.assertEqual(issue['data']['comments_data'][0]['reactions']['total_count'],
                         len(issue['data']['comments_data'][0]['reactions_data']))
        self.assertEqual(issue['data']['updated_at'], '2016-03-15T09:56:22Z')

    @httpretty.activate
    def test_fetch_pulls_until_date(self):
        """Test when return one pull"""

        login = read_file('data/github/github_login')
        orgs = read_file('data/github/github_orgs')
        issue_1 = read_file('data/github/github_issue_1')
        issue_2 = read_file('data/github/github_issue_2_with_pr')
        pull_1 = read_file('data/github/github_request_pull_request_1')
        pull_1_comments = read_file('data/github/github_request_pull_request_1_comments')
        pull_1_commits = read_file('data/github/github_request_pull_request_1_commits')
        pull_1_reviews = read_file('data/github/github_request_pull_request_1_reviews')
        pull_1_comment_2_reactions = read_file('data/github/github_request_pull_request_1_comment_2_reactions')
        pull_requested_reviewers = read_file('data/github/github_request_requested_reviewers')
        pull_2 = read_file('data/github/github_request_pull_request_2')
        pull_2_comments = read_file('data/github/github_request_pull_request_2_comments')
        pull_2_commits = read_file('data/github/github_request_pull_request_2_commits')
        pull_2_reviews = read_file('data/github/github_request_pull_request_2_reviews')
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
                               body=issue_1,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '5',
                                   'Link': '<' + GITHUB_ISSUES_URL + '/?&page=2>; rel="next", <' +
                                           GITHUB_ISSUES_URL + '/?&page=3>; rel="last"'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUES_URL + '/?&page=2',
                               body=issue_2,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '5'
                               })

        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_1_URL,
                               body=pull_1,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_1_COMMENTS,
                               body=pull_1_comments,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_1_COMMITS,
                               body=pull_1_commits,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_1_REVIEWS,
                               body=pull_1_reviews,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_1_COMMENTS_2_REACTIONS,
                               body=pull_1_comment_2_reactions,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_1_REQUESTED_REVIEWERS_URL,
                               body=pull_requested_reviewers, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_2_URL,
                               body=pull_2,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_2_COMMENTS,
                               body=pull_2_comments,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_2_REVIEWS,
                               body=pull_2_reviews,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_2_COMMITS,
                               body=pull_2_commits,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_2_REQUESTED_REVIEWERS_URL,
                               body=[],
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        httpretty.register_uri(httpretty.GET,
                               GITHUB_USER_URL,
                               body=login, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '5'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ORGS_URL,
                               body=orgs, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '5'
                               })

        github = GitHub("zhquan_example", "repo", ["aaa"])
        to_date = datetime.datetime(2016, 3, 1)
        pulls = [pulls for pulls in github.fetch(category=CATEGORY_PULL_REQUEST, to_date=to_date)]

        self.assertEqual(len(pulls), 1)

        pull = pulls[0]
        self.assertEqual(pull['origin'], 'https://github.com/zhquan_example/repo')
        self.assertEqual(pull['uuid'], '58c073fd2a388c44043b9cc197c73c5c540270ac')
        self.assertEqual(pull['updated_on'], 1451929343.0)
        self.assertEqual(pull['category'], CATEGORY_PULL_REQUEST)
        self.assertEqual(pull['tag'], 'https://github.com/zhquan_example/repo')
        self.assertEqual(pull['data']['merged_by_data']['login'], 'zhquan_example')
        self.assertEqual(len(pull['data']['requested_reviewers_data']), 1)
        self.assertEqual(pull['data']['requested_reviewers_data'][0]['login'], 'zhquan_example')
        self.assertEqual(len(pull['data']['reviews_data']), 2)
        self.assertEqual(pull['data']['reviews_data'][0]['user_data']['login'], 'zhquan_example')
        self.assertEqual(len(pull['data']['review_comments_data']), 2)
        self.assertEqual(len(pull['data']['review_comments_data'][0]['reactions_data']), 0)
        self.assertEqual(len(pull['data']['review_comments_data'][1]['reactions_data']), 5)
        self.assertEqual(pull['data']['review_comments_data'][1]['reactions_data'][0]['content'], 'heart')
        self.assertEqual(len(pull['data']['commits_data']), 1)
        self.assertEqual(pull['data']['updated_at'], '2016-01-04T17:42:23Z')

    @httpretty.activate
    def test_fetch_zero_reactions_on_issue(self):
        """Test zero reactions on a issue"""

        body = read_file('data/github/github_request')
        login = read_file('data/github/github_login')
        orgs = read_file('data/github/github_orgs')
        comments = read_file('data/github/github_empty_request')
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
                               body=body,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUE_1_COMMENTS_URL,
                               body=comments,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_USER_URL,
                               body=login, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ORGS_URL,
                               body=orgs, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        github = GitHub("zhquan_example", "repo", ["aaa"])
        issues = [issues for issues in github.fetch()]

        issue = issues[0]
        self.assertEqual(issue['data']['reactions']['total_count'], 0)
        self.assertEqual(issue['data']['reactions_data'], [])

    @httpretty.activate
    def test_fetch_issue_enterprise(self):
        """Test if it fetches issues from a GitHub Enterprise server"""

        login = read_file('data/github/github_login')
        orgs = read_file('data/github/github_orgs')
        issue_1 = read_file('data/github/github_issue_1')
        issue_2 = read_file('data/github/github_issue_2')
        issue_2_reactions = read_file('data/github/github_issue_2_reactions')
        issue_1_comments = read_file('data/github/github_issue_comments_1')
        issue_2_comments = read_file('data/github/github_issue_comments_2')
        issue_comment_1_reactions = read_file('data/github/github_issue_comment_1_reactions')
        issue_comment_2_reactions = read_file('data/github/github_empty_request')

        httpretty.register_uri(httpretty.GET,
                               GITHUB_ENTREPRISE_RATE_LIMIT,
                               body="",
                               status=404)

        httpretty.register_uri(httpretty.GET,
                               GITHUB_ENTERPRISE_ISSUES_URL,
                               body=issue_1, status=200,
                               forcing_headers={
                                   'Link': '<' + GITHUB_ENTERPRISE_ISSUES_URL + '/?&page=2>; rel="next", <' +
                                           GITHUB_ENTERPRISE_ISSUES_URL + '/?&page=2>; rel="last"'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ENTERPRISE_ISSUE_1_COMMENTS_URL,
                               body=issue_1_comments, status=200)
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ENTERPRISE_ISSUE_COMMENT_1_REACTION_URL,
                               body=issue_comment_1_reactions, status=200)
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ENTERPRISE_ISSUES_URL + '/?&page=2',
                               body=issue_2, status=200)
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ENTERPRISE_ISSUE_2_REACTION_URL,
                               body=issue_2_reactions, status=200)
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ENTERPRISE_ISSUE_2_COMMENTS_URL,
                               body=issue_2_comments, status=200)
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ENTERPRISE_ISSUE_COMMENT_2_REACTION_URL,
                               body=issue_comment_2_reactions, status=200)
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ENTERPRISE_USER_URL,
                               body=login, status=200)
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ENTERPRISE_ORGS_URL,
                               body=orgs, status=200)

        github = GitHub("zhquan_example", "repo", ["aaa"],
                        base_url=GITHUB_ENTERPRISE_URL)
        issues = [issues for issues in github.fetch()]

        self.assertEqual(len(issues), 2)

        issue = issues[0]
        self.assertEqual(issue['origin'], 'https://example.com/zhquan_example/repo')
        self.assertEqual(issue['uuid'], 'c03eca84a7518f629a75bc0d0e24180030688c3b')
        self.assertEqual(issue['updated_on'], 1458035782.0)
        self.assertEqual(issue['category'], CATEGORY_ISSUE)
        self.assertEqual(issue['tag'], 'https://example.com/zhquan_example/repo')
        self.assertEqual(issue['data']['assignee_data']['login'], 'zhquan_example')
        self.assertEqual(len(issue['data']['assignees_data']), 1)
        self.assertEqual(len(issue['data']['comments_data']), 1)
        self.assertEqual(issue['data']['reactions']['total_count'], len(issue['data']['reactions_data']))
        self.assertEqual(issue['data']['comments_data'][0]['user_data']['login'], 'zhquan_example')
        self.assertEqual(issue['data']['comments_data'][0]['reactions']['total_count'],
                         len(issue['data']['comments_data'][0]['reactions_data']))

        issue = issues[1]
        self.assertEqual(issues[1]['origin'], 'https://example.com/zhquan_example/repo')
        self.assertEqual(issues[1]['uuid'], 'c63bbfc15c0289abc8d9ade152ff1dbfcbb968fa')
        self.assertEqual(issue['updated_on'], 1463324969.0)
        self.assertEqual(issue['category'], CATEGORY_ISSUE)
        self.assertEqual(issue['tag'], 'https://example.com/zhquan_example/repo')
        self.assertEqual(issue['data']['assignees_data'], [])
        self.assertEqual(len(issue['data']['comments_data']), 1)
        self.assertEqual(issue['data']['reactions']['total_count'], len(issue['data']['reactions_data']))
        self.assertEqual(issue['data']['comments_data'][0]['user_data']['login'], 'zhquan_example')
        self.assertEqual(issue['data']['comments_data'][0]['reactions']['total_count'],
                         len(issue['data']['comments_data'][0]['reactions_data']))

    @httpretty.activate
    def test_fetch_pull_enterprise(self):
        """Test if it fetches pull requests from a GitHub Enterprise server"""

        login = read_file('data/github/github_login')
        orgs = read_file('data/github/github_orgs')
        issue_1 = read_file('data/github/github_issue_1')
        issue_2 = read_file('data/github/github_issue_2')
        pull_request = read_file('data/github/github_request_pull_request_1')
        pull_request_comments = read_file('data/github/github_request_pull_request_1_comments')
        pull_request_reviews = read_file('data/github/github_request_pull_request_1_reviews')
        pull_request_commits = read_file('data/github/github_request_pull_request_1_commits')
        pull_request_comment_2_reactions = read_file('data/github/github_request_pull_request_1_comment_2_reactions')
        pull_requested_reviewers = read_file('data/github/github_enterprise_request_requested_reviewers')

        httpretty.register_uri(httpretty.GET,
                               GITHUB_ENTREPRISE_RATE_LIMIT,
                               body="",
                               status=404)

        httpretty.register_uri(httpretty.GET,
                               GITHUB_ENTERPRISE_ISSUES_URL,
                               body=issue_1, status=200,
                               forcing_headers={
                                   'Link': '<' + GITHUB_ENTERPRISE_ISSUES_URL + '/?&page=2>; rel="next", <' +
                                           GITHUB_ENTERPRISE_ISSUES_URL + '/?&page=2>; rel="last"'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ENTREPRISE_REQUEST_REQUESTED_REVIEWERS_URL,
                               body=pull_requested_reviewers, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ENTERPRISE_ISSUES_URL + '/?&page=2',
                               body=issue_2, status=200)
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ENTERPRISE_USER_URL,
                               body=login, status=200)
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ENTERPRISE_ORGS_URL,
                               body=orgs, status=200)

        httpretty.register_uri(httpretty.GET,
                               GITHUB_ENTREPRISE_PULL_REQUEST_1_URL,
                               body=pull_request,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ENTREPRISE_PULL_REQUEST_1_COMMENTS,
                               body=pull_request_comments,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ENTREPRISE_PULL_REQUEST_1_REVIEWS,
                               body=pull_request_reviews,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ENTREPRISE_PULL_REQUEST_1_COMMITS,
                               body=pull_request_commits,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ENTREPRISE_PULL_REQUEST_1_COMMENTS_2_REACTIONS,
                               body=pull_request_comment_2_reactions,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        github = GitHub("zhquan_example", "repo", ["aaa"], base_url=GITHUB_ENTERPRISE_URL)

        pulls = [pulls for pulls in github.fetch(category=CATEGORY_PULL_REQUEST)]

        self.assertEqual(len(pulls), 1)

        pull = pulls[0]
        self.assertEqual(pull['origin'], 'https://example.com/zhquan_example/repo')
        self.assertEqual(pull['uuid'], 'c03eca84a7518f629a75bc0d0e24180030688c3b')
        self.assertEqual(pull['updated_on'], 1451929343.0)
        self.assertEqual(pull['category'], CATEGORY_PULL_REQUEST)
        self.assertEqual(pull['tag'], 'https://example.com/zhquan_example/repo')
        self.assertEqual(pull['data']['merged_by_data']['login'], 'zhquan_example')
        self.assertEqual(len(pull['data']['requested_reviewers_data']), 1)
        self.assertEqual(pull['data']['requested_reviewers_data'][0]['login'], 'zhquan_example')
        self.assertEqual(len(pull['data']['review_comments_data']), 2)
        self.assertEqual(len(pull['data']['review_comments_data'][0]['reactions_data']), 0)
        self.assertEqual(len(pull['data']['review_comments_data'][1]['reactions_data']), 5)
        self.assertEqual(pull['data']['review_comments_data'][1]['reactions_data'][0]['content'], 'heart')
        self.assertEqual(len(pull['data']['commits_data']), 1)
        self.assertEqual(len(pull['data']['reviews_data']), 2)
        self.assertEqual(pull['data']['reviews_data'][0]['user_data']['login'], 'zhquan_example')

    @httpretty.activate
    @unittest.mock.patch('perceval.backends.core.github.datetime_utcnow')
    def test_fetch_repo_enterprise(self, mock_utcnow):
        """Test whether repo information is returned"""

        mock_utcnow.return_value = datetime.datetime(2017, 1, 1,
                                                     tzinfo=dateutil.tz.tzutc())

        body = read_file('data/github/github_repo')
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
                               GITHUB_ENTREPRISE_REPO_URL,
                               body=body,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        github = GitHub("zhquan_example", "repo", "aaa", base_url=GITHUB_ENTERPRISE_URL)
        repo = [repo for repo in github.fetch(category=CATEGORY_REPO)]

        self.assertEqual(len(repo), 1)

        repo_info = repo[0]

        self.assertEqual(repo_info['origin'], 'https://example.com/zhquan_example/repo')
        self.assertEqual(repo_info['uuid'], 'b5dfd8cc4be38cdd123b7bd044197d6a13d8f29c')
        self.assertEqual(repo_info['updated_on'], 1483228800.0)
        self.assertEqual(repo_info['category'], CATEGORY_REPO)
        self.assertEqual(repo_info['tag'], 'https://example.com/zhquan_example/repo')
        self.assertEqual(repo_info['data']['forks'], 16687)
        self.assertEqual(repo_info['data']['stargazers_count'], 48188)
        self.assertEqual(repo_info['data']['subscribers_count'], 2904)
        self.assertEqual(repo_info['data']['updated_at'], "2019-02-14T16:21:58Z")
        self.assertEqual(repo_info['data']['fetched_on'], 1483228800.0)

    @httpretty.activate
    def test_fetch_from_date(self):
        """Test when return from date"""

        login = read_file('data/github/github_login')
        orgs = read_file('data/github/github_orgs')
        body = read_file('data/github/github_issue_2')
        comments = read_file('data/github/github_issue_comments_2')
        issue_reactions = read_file('data/github/github_issue_2_reactions')
        comment_reactions = read_file('data/github/github_empty_request')
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
                               body=body,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUE_2_COMMENTS_URL,
                               body=comments,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUE_2_REACTION_URL,
                               body=issue_reactions,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUE_COMMENT_2_REACTION_URL,
                               body=comment_reactions,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_USER_URL,
                               body=login, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ORGS_URL,
                               body=orgs, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        from_date = datetime.datetime(2016, 3, 1)
        github = GitHub("zhquan_example", "repo", ["aaa"])

        issues = [issues for issues in github.fetch(from_date=from_date)]

        issue = issues[0]
        self.assertEqual(issue['origin'], 'https://github.com/zhquan_example/repo')
        self.assertEqual(issue['uuid'], '4236619ac2073491640f1698b5c4e169895aaf69')
        self.assertEqual(issue['updated_on'], 1463324969.0)
        self.assertEqual(issue['category'], CATEGORY_ISSUE)
        self.assertEqual(issue['tag'], 'https://github.com/zhquan_example/repo')
        self.assertEqual(issue['data']['assignees_data'], [])
        self.assertEqual(len(issue['data']['comments_data']), 1)
        self.assertEqual(issue['data']['reactions']['total_count'], len(issue['data']['reactions_data']))
        self.assertEqual(issue['data']['comments_data'][0]['user_data']['login'], 'zhquan_example')
        self.assertEqual(issue['data']['comments_data'][0]['reactions']['total_count'],
                         len(issue['data']['comments_data'][0]['reactions_data']))

    @httpretty.activate
    def test_fetch_empty(self):
        """Test when return empty"""

        body = ""
        login = read_file('data/github/github_login')
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
                               body=body, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_USER_URL,
                               body=login, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ORGS_URL,
                               body="[]", status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        from_date = datetime.datetime(2016, 1, 1)
        github = GitHub("zhquan_example", "repo", ["aaa"])

        issues = [issues for issues in github.fetch(from_date=from_date)]

        self.assertEqual(len(issues), 0)

    @httpretty.activate
    def test_user_orgs_not_found(self):
        """Test whether 404 response when getting users orgs is managed"""

        body = read_file('data/github/github_request')
        login = read_file('data/github/github_login')
        orgs = read_file('data/github/github_orgs')
        comments = read_file('data/github/github_issue_comments_1')
        reactions = read_file('data/github/github_issue_comment_1_reactions')
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
                               body=body,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUE_1_COMMENTS_URL,
                               body=comments,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUE_COMMENT_1_REACTION_URL,
                               body=reactions,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_USER_URL,
                               body=login, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ORGS_URL,
                               body=orgs, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        # Check that 404 exception getting user orgs is managed
        GitHubClient._users_orgs.clear()  # clean cache to get orgs using the API
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ORGS_URL,
                               body=orgs, status=404,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        github = GitHub("zhquan_example", "repo", ["aaa"])
        _ = [issues for issues in github.fetch()]

        # Check that a no 402 exception getting user orgs is raised
        GitHubClient._users_orgs.clear()
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ORGS_URL,
                               body=orgs, status=402,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        github = GitHub("zhquan_example", "repo", ["aaa"])
        with self.assertRaises(requests.exceptions.HTTPError):
            _ = [issues for issues in github.fetch()]


class TestGitHubBackendArchive(TestCaseBackendArchive):
    """GitHub backend tests using an archive"""

    def setUp(self):
        super().setUp()
        self.backend_write_archive = GitHub("zhquan_example", "repo", ["aaa"], archive=self.archive)
        self.backend_read_archive = GitHub("zhquan_example", "repo", ["aaa"], archive=self.archive)

    @httpretty.activate
    def test_fetch_issues_from_archive(self):
        """Test whether a list of issues is returned from archive"""

        issue_1 = read_file('data/github/github_issue_1')
        issue_2 = read_file('data/github/github_issue_2')
        login = read_file('data/github/github_login')
        orgs = read_file('data/github/github_orgs')
        issue_1_comments = read_file('data/github/github_issue_comments_1')
        issue_2_comments = read_file('data/github/github_issue_comments_2')
        issue_2_reactions = read_file('data/github/github_issue_2_reactions')
        issue_comment_1_reactions = read_file('data/github/github_issue_comment_1_reactions')
        issue_comment_2_reactions = read_file('data/github/github_empty_request')
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
                               body=issue_1,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '5',
                                   'Link': '<' + GITHUB_ISSUES_URL + '/?&page=2>; rel="next", <' +
                                           GITHUB_ISSUES_URL + '/?&page=3>; rel="last"'
                               })

        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUES_URL + '/?&page=2',
                               body=issue_2,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '5'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUE_COMMENT_1_REACTION_URL,
                               body=issue_comment_1_reactions, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUE_COMMENT_2_REACTION_URL,
                               body=issue_comment_2_reactions, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUE_2_REACTION_URL,
                               body=issue_2_reactions, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUE_1_COMMENTS_URL,
                               body=issue_1_comments, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUE_2_COMMENTS_URL,
                               body=issue_2_comments, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_USER_URL,
                               body=login, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ORGS_URL,
                               body=orgs, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        self._test_fetch_from_archive(from_date=None)

    @httpretty.activate
    def test_fetch_pulls_from_archive(self):
        """Test whether a list of pull requests is returned from archive"""

        issue_1 = read_file('data/github/github_issue_1')
        issue_2 = read_file('data/github/github_issue_2')
        login = read_file('data/github/github_login')
        orgs = read_file('data/github/github_orgs')
        pull_request = read_file('data/github/github_request_pull_request_1')
        pull_request_reviews = read_file('data/github/github_request_pull_request_1_reviews')
        pull_request_comments = read_file('data/github/github_request_pull_request_1_comments')
        pull_request_commits = read_file('data/github/github_request_pull_request_1_commits')
        pull_request_comment_2_reactions = read_file('data/github/github_request_pull_request_1_comment_2_reactions')
        pull_requested_reviewers = read_file('data/github/github_request_requested_reviewers')
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
                               body=issue_1,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '5',
                                   'Link': '<' + GITHUB_ISSUES_URL + '/?&page=2>; rel="next", <' +
                                           GITHUB_ISSUES_URL + '/?&page=3>; rel="last"'
                               })

        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUES_URL + '/?&page=2',
                               body=issue_2,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '5'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_USER_URL,
                               body=login, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ORGS_URL,
                               body=orgs, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_1_URL,
                               body=pull_request,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_1_REVIEWS,
                               body=pull_request_reviews,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_1_COMMENTS,
                               body=pull_request_comments,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_1_COMMITS,
                               body=pull_request_commits,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_1_COMMENTS_2_REACTIONS,
                               body=pull_request_comment_2_reactions,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_1_REQUESTED_REVIEWERS_URL,
                               body=pull_requested_reviewers, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        self._test_fetch_from_archive(category=CATEGORY_PULL_REQUEST, from_date=None)

    @httpretty.activate
    def test_fetch_from_date_from_archive(self):
        """Test whether a list of issues is returned from archive after a given date"""

        login = read_file('data/github/github_login')
        orgs = read_file('data/github/github_orgs')
        body = read_file('data/github/github_issue_2')
        comments = read_file('data/github/github_issue_comments_2')
        issue_reactions = read_file('data/github/github_issue_2_reactions')
        comment_reactions = read_file('data/github/github_empty_request')
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
                               body=body,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUE_2_REACTION_URL,
                               body=issue_reactions,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUE_2_COMMENTS_URL,
                               body=comments, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUE_COMMENT_2_REACTION_URL,
                               body=comment_reactions,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_USER_URL,
                               body=login, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ORGS_URL,
                               body=orgs, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        from_date = datetime.datetime(2016, 3, 1)
        self._test_fetch_from_archive(from_date=from_date)

    @httpretty.activate
    def test_fetch_from_empty_archive(self):
        """Test whether no issues are returned when the archive is empty"""

        body = ""
        login = read_file('data/github/github_login')
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
                               body=body, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_USER_URL,
                               body=login, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ORGS_URL,
                               body="[]", status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        self._test_fetch_from_archive()


class TestGitHubClient(unittest.TestCase):
    """GitHub API client tests"""

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

        client = GitHubClient('zhquan_example', 'repo', ['aaa'])

        self.assertEqual(client.owner, 'zhquan_example')
        self.assertEqual(client.repository, 'repo')
        self.assertEqual(client.max_retries, GitHubClient.MAX_RETRIES)
        self.assertEqual(client.sleep_time, GitHubClient.DEFAULT_SLEEP_TIME)
        self.assertEqual(client.max_retries, GitHubClient.MAX_RETRIES)
        self.assertEqual(client.base_url, 'https://api.github.com')
        self.assertTrue(client.ssl_verify)

        client = GitHubClient('zhquan_example', 'repo', ['aaa'], base_url=None,
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

        client = GitHubClient('zhquan_example', 'repo', ['aaa'], min_rate_to_sleep=RateLimitHandler.MAX_RATE_LIMIT + 1)
        self.assertEqual(client.min_rate_to_sleep, RateLimitHandler.MAX_RATE_LIMIT)

        client = GitHubClient('zhquan_example', 'repo', ['aaa'], min_rate_to_sleep=RateLimitHandler.MAX_RATE_LIMIT - 1)
        self.assertEqual(client.min_rate_to_sleep, RateLimitHandler.MAX_RATE_LIMIT - 1)

        client = GitHubClient('zhquan_example', 'repo', ['aaa'])
        self.assertEqual(client.tokens, ['aaa'])
        self.assertEqual(client.n_tokens, 1)
        self.assertEqual(client.current_token, 'aaa')

        client = GitHubClient('zhquan_example', 'repo', ['aaa', 'bbb'])
        self.assertEqual(client.tokens, ['aaa', 'bbb'])
        self.assertEqual(client.n_tokens, 2)

        client = GitHubClient('zhquan_example', 'repo', [])
        self.assertEqual(client.tokens, [])
        self.assertEqual(client.current_token, None)
        self.assertEqual(client.n_tokens, 0)

    @httpretty.activate
    def test_api_url_initialization(self):
        """Test API URL initialization for both basic and enterprise servers"""

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
                               GITHUB_ENTREPRISE_RATE_LIMIT,
                               body="",
                               status=404)

        client = GitHubClient("zhquan_example", "repo", ["aaa"])
        self.assertEqual(client.base_url, GITHUB_API_URL)

        client = GitHubClient("zhquan_example", "repo", ["aaa"],
                              base_url=GITHUB_ENTERPRISE_URL)
        self.assertEqual(client.base_url, GITHUB_ENTERPRISE_API_URL)

    @httpretty.activate
    def test_issues(self):
        """Test issues API call"""

        issues = read_file('data/github/github_request')
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
                               body=issues, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '5',
                                   'X-RateLimit-Reset': '5'
                               })

        client = GitHubClient("zhquan_example", "repo", ["aaa"], None)
        raw_issues = [issues for issues in client.issues()]
        self.assertEqual(raw_issues[0], issues)

        # Check requests
        expected = {
            'per_page': ['100'],
            'state': ['all'],
            'direction': ['asc'],
            'sort': ['updated']
        }

        self.assertDictEqual(httpretty.last_request().querystring, expected)
        self.assertEqual(httpretty.last_request().headers["Authorization"], "token aaa")

    @httpretty.activate
    def test_issues_github_app(self):
        """Test issues API call using GitHub APP"""

        issues = read_file('data/github/github_request')
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
                               body=issues, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '5',
                                   'X-RateLimit-Reset': '5'
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

        client = GitHubClient("zhquan_example", "repo", github_app_id='1', github_app_pk_filepath='data/github/private.pem')
        raw_issues = [issues for issues in client.issues()]
        self.assertEqual(raw_issues[0], issues)

        # Check requests
        expected = {
            'per_page': ['100'],
            'state': ['all'],
            'direction': ['asc'],
            'sort': ['updated']
        }

        self.assertDictEqual(httpretty.last_request().querystring, expected)
        self.assertEqual(httpretty.last_request().headers["Authorization"], "token v1.aaa")

    @httpretty.activate
    def test_issue_comments(self):
        """Test issue comments API call"""

        issue_comments = read_file('data/github/github_issue_comments_2')
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
                               GITHUB_ISSUE_2_COMMENTS_URL,
                               body=issue_comments,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        client = GitHubClient("zhquan_example", "repo", ["aaa"])

        issue_comments_raw = [rev for rev in client.issue_comments(2)]
        self.assertEqual(issue_comments_raw[0], issue_comments)

    @httpretty.activate
    def test_issue_reactions(self):
        """Test issue reactions API call"""

        issue_reactions = read_file('data/github/github_issue_2_reactions')
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
                               GITHUB_ISSUE_2_REACTION_URL,
                               body=issue_reactions, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        client = GitHubClient("zhquan_example", "repo", ["aaa"])

        issue_reactions_raw = [rev for rev in client.issue_reactions(2)]
        self.assertEqual(issue_reactions_raw[0], issue_reactions)

    @httpretty.activate
    def test_issue_comment_reactions(self):
        """Test issue comment reactions API call"""

        issue_comment_reactions = read_file('data/github/github_issue_comment_1_reactions')
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
                               GITHUB_ISSUE_COMMENT_1_REACTION_URL,
                               body=issue_comment_reactions,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        client = GitHubClient("zhquan_example", "repo", ["aaa"])

        issue_comment_reactions_raw = [rev for rev in client.issue_comment_reactions(1)]
        self.assertEqual(issue_comment_reactions_raw[0], issue_comment_reactions)

    @httpretty.activate
    def test_pulls(self):
        """Test pulls API call"""

        issue = read_file('data/github/github_request')
        pull_request = read_file('data/github/github_request_pull_request_1')
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
                               body=issue, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_PULL_REQUEST_1_URL,
                               body=pull_request,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        client = GitHubClient("zhquan_example", "repo", ["aaa"], None)
        raw_pulls = [pulls for pulls in client.pulls()]
        self.assertEqual(raw_pulls[0], pull_request)

        self.assertEqual(httpretty.last_request().headers["Authorization"], "token aaa")

    @httpretty.activate
    def test_repo(self):
        """Test repo API call"""

        repo = read_file('data/github/github_repo')
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
                               GITHUB_REPO_URL,
                               body=repo, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '5',
                                   'X-RateLimit-Reset': '5'
                               })

        client = GitHubClient("zhquan_example", "repo", ["aaa"])
        raw_repo = client.repo()
        self.assertEqual(raw_repo, repo)

        self.assertEqual(httpretty.last_request().headers["Authorization"], "token aaa")

    @httpretty.activate
    def test_enterprise_issues(self):
        """Test fetching issues from enterprise"""

        issue = read_file('data/github/github_request')

        httpretty.register_uri(httpretty.GET,
                               GITHUB_ENTREPRISE_RATE_LIMIT,
                               body="",
                               status=404)
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ENTERPRISE_ISSUES_URL,
                               body=issue, status=200)

        client = GitHubClient("zhquan_example", "repo", ["aaa"],
                              base_url=GITHUB_ENTERPRISE_URL)

        raw_issues = [issues for issues in client.issues()]
        self.assertEqual(raw_issues[0], issue)

        # Check requests
        expected = {
            'per_page': ['100'],
            'state': ['all'],
            'direction': ['asc'],
            'sort': ['updated']
        }

        self.assertDictEqual(httpretty.last_request().querystring, expected)
        self.assertEqual(httpretty.last_request().headers["Authorization"], "token aaa")

    @httpretty.activate
    def test_enterprise_pulls(self):
        """Test fetching pulls from enterprise"""

        issue = read_file('data/github/github_request')
        pull_request = read_file('data/github/github_request_pull_request_1')

        httpretty.register_uri(httpretty.GET,
                               GITHUB_ENTREPRISE_RATE_LIMIT,
                               body="",
                               status=404)
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ENTERPRISE_ISSUES_URL,
                               body=issue, status=200)
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ENTREPRISE_PULL_REQUEST_1_URL,
                               body=pull_request,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        client = GitHubClient("zhquan_example", "repo", ["aaa"], base_url=GITHUB_ENTERPRISE_URL)

        raw_pulls = [pulls for pulls in client.pulls()]
        self.assertEqual(raw_pulls[0], pull_request)

        self.assertEqual(httpretty.last_request().headers["Authorization"], "token aaa")

    @httpretty.activate
    def test_enterprise_repo(self):
        """Test repo API call from enterprise"""

        repo = read_file('data/github/github_repo')
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
                               GITHUB_ENTREPRISE_REPO_URL,
                               body=repo, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '5',
                                   'X-RateLimit-Reset': '5'
                               })

        client = GitHubClient("zhquan_example", "repo", ["aaa"], base_url=GITHUB_ENTERPRISE_URL)
        raw_repo = client.repo()
        self.assertEqual(raw_repo, repo)

        self.assertEqual(httpretty.last_request().headers["Authorization"], "token aaa")

    @httpretty.activate
    def test_get_from_date_issues(self):
        """Test issues from date API call"""

        issues = read_file('data/github/github_request_from_2016_03_01')
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
                               body=issues,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        from_date = datetime.datetime(2016, 3, 1)
        client = GitHubClient("zhquan_example", "repo", ["aaa"], None)

        raw_issues = [issues for issues in client.issues(from_date=from_date)]
        self.assertEqual(raw_issues[0], issues)

        # Check requests
        expected = {
            'per_page': ['100'],
            'state': ['all'],
            'direction': ['asc'],
            'since': ['2016-03-01T00:00:00'],
            'sort': ['updated']
        }
        self.assertDictEqual(httpretty.last_request().querystring, expected)
        self.assertEqual(httpretty.last_request().headers["Authorization"], "token aaa")

    @httpretty.activate
    def test_get_page_issues(self):
        """Test issues pagination API call"""

        issue_1 = read_file('data/github/github_issue_1')
        issue_2 = read_file('data/github/github_issue_2')
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
                               body=issue_1,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15',
                                   'Link': '<' + GITHUB_ISSUES_URL + '/?&page=2>; rel="next", <' +
                                           GITHUB_ISSUES_URL + '/?&page=3>; rel="last"'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUES_URL + '/?&page=2',
                               body=issue_2,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        client = GitHubClient("zhquan_example", "repo", ["aaa"])

        issues = [issues for issues in client.issues()]

        self.assertEqual(len(issues), 2)
        self.assertEqual(issues[0], issue_1)
        self.assertEqual(issues[1], issue_2)

        # Check requests
        expected = {
            'per_page': ['100'],
            'page': ['2'],
            'state': ['all'],
            'direction': ['asc'],
            'sort': ['updated']
        }

        self.assertDictEqual(httpretty.last_request().querystring, expected)
        self.assertEqual(httpretty.last_request().headers["Authorization"], "token aaa")

    @httpretty.activate
    def test_pull_requested_reviewers(self):
        """Test pull requested reviewers API call"""

        pull_requested_reviewers = read_file('data/github/github_request_requested_reviewers')
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
                               GITHUB_PULL_REQUEST_1_REQUESTED_REVIEWERS_URL,
                               body=pull_requested_reviewers, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        client = GitHubClient("zhquan_example", "repo", ["aaa"])

        pull_requested_reviewers_raw = [rev for rev in client.pull_requested_reviewers(1)]
        self.assertEqual(pull_requested_reviewers_raw[0], pull_requested_reviewers)

    @httpretty.activate
    def test_pull_review_comments(self):
        """Test pull review comments API call"""

        pull_request_comments = read_file('data/github/github_request_pull_request_1_comments')
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
                               GITHUB_PULL_REQUEST_1_COMMENTS,
                               body=pull_request_comments,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        client = GitHubClient("zhquan_example", "repo", ["aaa"])

        pull_review_comments_raw = [rev for rev in client.pull_review_comments(1)]
        self.assertEqual(pull_review_comments_raw[0], pull_request_comments)

    @httpretty.activate
    def test_pull_reviews(self):
        """Test pull reviews API call"""

        pull_request_reviews = read_file('data/github/github_request_pull_request_1_reviews')
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
                               GITHUB_PULL_REQUEST_1_REVIEWS,
                               body=pull_request_reviews,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        client = GitHubClient("zhquan_example", "repo", ["aaa"])

        pull_reviews_raw = [rev for rev in client.pull_reviews(1)]
        self.assertEqual(pull_reviews_raw[0], pull_request_reviews)

    @httpretty.activate
    def test_pull_commits(self):
        """Test pull commits API call"""

        pull_request_commits = read_file('data/github/github_request_pull_request_1_commits')
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
                               GITHUB_PULL_REQUEST_1_COMMITS,
                               body=pull_request_commits,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        client = GitHubClient("zhquan_example", "repo", ["aaa"])

        pull_commits_raw = [rev for rev in client.pull_commits(1)]
        self.assertEqual(pull_commits_raw[0], pull_request_commits)

    @httpretty.activate
    def test_pull_review_comment_reactions(self):
        """Test pull review comment reactions API call"""

        pull_comment_reactions = read_file('data/github/github_request_pull_request_1_comment_2_reactions')
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
                               GITHUB_PULL_REQUEST_1_COMMENTS_2_REACTIONS,
                               body=pull_comment_reactions,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        client = GitHubClient("zhquan_example", "repo", ["aaa"])

        pull_comment_reactions_raw = [rev for rev in client.pull_review_comment_reactions(2)]
        self.assertEqual(pull_comment_reactions_raw[0], pull_comment_reactions)

    @httpretty.activate
    def test_abuse_rate_limit(self):
        """Test when Abuse Rate Limit exception is thrown"""

        retry_after_value = 1

        abuse_rate_limit = read_file('data/github/abuse_rate_limit')
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
                               body=abuse_rate_limit, status=429,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '5',
                                   'X-RateLimit-Reset': '5',
                                   'Retry-After': str(retry_after_value)
                               })

        GitHubClient.MAX_RETRIES_ON_READ = 2
        client = GitHubClient("zhquan_example", "repo", ["aaa"], None)

        before = int(time.time())
        expected = before + (retry_after_value * client.max_retries_on_status)

        with self.assertRaises(requests.exceptions.HTTPError):
            _ = [issues for issues in client.issues()]

        after = int(time.time())
        self.assertTrue(expected <= after)

    @httpretty.activate
    def test_get_empty_issues(self):
        """ Test when issue is empty API call """

        issue = read_file('data/github/github_empty_request')
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
                               body=issue, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        client = GitHubClient("zhquan_example", "repo", ["aaa"], None)

        raw_issues = [issues for issues in client.issues()]
        self.assertEqual(raw_issues[0], issue)

        # Check requests
        expected = {
            'per_page': ['100'],
            'state': ['all'],
            'direction': ['asc'],
            'sort': ['updated']
        }

        self.assertDictEqual(httpretty.last_request().querystring, expected)
        self.assertEqual(httpretty.last_request().headers["Authorization"], "token aaa")

    @httpretty.activate
    def test_get_user(self):
        """Test get_user API call"""

        login = read_file('data/github/github_login')
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
                               GITHUB_USER_URL,
                               body=login, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        client = GitHubClient("zhquan_example", "repo", ["aaa"], None)
        response = client.user("zhquan_example")
        self.assertEqual(response, login)

    @httpretty.activate
    def test_get_user_orgs(self):
        """Test get_user_orgs API call"""

        orgs = read_file('data/github/github_orgs')
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
                               GITHUB_ORGS_URL,
                               body=orgs, status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        client = GitHubClient("zhquan_example", "repo", ["aaa"], None)
        response = client.user_orgs("zhquan_example")

        self.assertEqual(response, orgs)

    @httpretty.activate
    def test_http_wrong_status(self):
        """Test if a error is raised when the http status was not 200"""

        issue = ""
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
                               status=501,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        client = GitHubClient("zhquan_example", "repo", ["aaa"], sleep_time=1, max_retries=1)

        with self.assertRaises(requests.exceptions.HTTPError):
            _ = [issues for issues in client.issues()]

        # Check requests
        expected = {
            'per_page': ['100'],
            'state': ['all'],
            'direction': ['asc'],
            'sort': ['updated']
        }

        self.assertDictEqual(httpretty.last_request().querystring, expected)
        self.assertEqual(httpretty.last_request().headers["Authorization"], "token aaa")

    @httpretty.activate
    def test_http_retry_error(self):
        """Test if a retry error is raised when the http error is one of
        the extra_status_forcelist [403, 500, 502, 503]"""

        issue = ""
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
                               status=502,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        client = GitHubClient("zhquan_example", "repo", ["aaa"], sleep_time=1, max_retries=1)

        with self.assertRaises(requests.exceptions.RetryError):
            _ = [issues for issues in client.issues()]

    @httpretty.activate
    def test_choose_best_token_on_init(self):
        """Test if the client chooses the best token when there are several available"""

        # Token selection is based on the headers returned
        # by the server to each request made with different tokens
        forcing_headers_aaa = {
            'X-RateLimit-Remaining': '10',
            'X-RateLimit-Reset': '15'
        }
        forcing_headers_bbb = {
            'X-RateLimit-Remaining': '20',
            'X-RateLimit-Reset': '15'
        }
        forcing_headers_bbb_updated = {
            'X-RateLimit-Remaining': '19',
            'X-RateLimit-Reset': '15'
        }

        # Body of the response is ignored. Rate limit is got
        # from the headers
        rate_limit_body_aaa = read_file('data/github/rate_limit_aaa')
        rate_limit_body_bbb = read_file('data/github/rate_limit_bbb')

        # The client request the rate limit for tokens 'aaa' and 'bbb'.
        # Once it has selected the best token, it makes a new request
        # with that token to update the rate limit
        httpretty.register_uri(httpretty.GET,
                               GITHUB_RATE_LIMIT,
                               responses=[
                                   httpretty.Response(rate_limit_body_aaa, forcing_headers=forcing_headers_aaa),
                                   httpretty.Response(rate_limit_body_bbb, forcing_headers=forcing_headers_bbb),
                                   httpretty.Response(rate_limit_body_bbb, forcing_headers=forcing_headers_bbb_updated)
                               ])

        client = GitHubClient("zhquan_example", "repo", ["aaa", "bbb"],
                              sleep_for_rate=True)
        self.assertEqual(client.current_token, 'bbb')
        self.assertEqual(client.rate_limit, 19)

    @httpretty.activate
    def test_choose_best_token_when_approaching_limit(self):
        """Test if the client chooses the best token when the current one approaches the limit"""

        # The process will be as follows. The client request the rate limit
        # for tokens 'aaa', 'bbb' and 'ccc'. Once it has selected the best token,
        # in this case 'bbb', it makes a new request with that token to update
        # the rate limit.
        #
        # When it performs a query to get user data, first checks whether the
        # token is reaching to its limit. In this case it is, so it asks for
        # new tokens. Tokens 'aaa' and 'ccc' are refreshed so it gets the best
        # one, in this case 'aaa'.

        # Token selection is based on the headers returned
        # by the server to each request made with different tokens
        forcing_headers_aaa_init = {
            'X-RateLimit-Remaining': '10',
            'X-RateLimit-Reset': '15'
        }
        forcing_headers_bbb_init = {
            'X-RateLimit-Remaining': '20',
            'X-RateLimit-Reset': '15'
        }
        forcing_headers_ccc_init = {
            'X-RateLimit-Remaining': '0',
            'X-RateLimit-Reset': '15'
        }
        forcing_headers_bbb_updated = {
            'X-RateLimit-Remaining': '19',
            'X-RateLimit-Reset': '15'
        }
        forcing_headers_aaa_reset = {
            'X-RateLimit-Remaining': '200',
            'X-RateLimit-Reset': '15'
        }
        forcing_headers_ccc_reset = {
            'X-RateLimit-Remaining': '100',
            'X-RateLimit-Reset': '15'
        }
        forcing_headers_user = {
            'X-RateLimit-Remaining': '199',
            'X-RateLimit-Reset': '15'
        }

        # Body of the response is ignored. Rate limit is got
        # from the headers
        rate_limit_body_aaa = read_file('data/github/rate_limit_aaa')
        rate_limit_body_bbb = read_file('data/github/rate_limit_bbb')
        repo_body = read_file('data/github/github_repo')

        httpretty.register_uri(httpretty.GET,
                               GITHUB_RATE_LIMIT,
                               responses=[
                                   httpretty.Response(rate_limit_body_aaa, forcing_headers=forcing_headers_aaa_init),
                                   httpretty.Response(rate_limit_body_bbb, forcing_headers=forcing_headers_bbb_init),
                                   httpretty.Response(rate_limit_body_bbb, forcing_headers=forcing_headers_ccc_init),
                                   httpretty.Response(rate_limit_body_bbb, forcing_headers=forcing_headers_bbb_updated),
                                   httpretty.Response(rate_limit_body_aaa, forcing_headers=forcing_headers_aaa_reset),
                                   httpretty.Response(rate_limit_body_bbb, forcing_headers=forcing_headers_bbb_updated),
                                   httpretty.Response(rate_limit_body_aaa, forcing_headers=forcing_headers_ccc_reset),
                                   httpretty.Response(rate_limit_body_aaa, forcing_headers=forcing_headers_aaa_reset),
                               ])
        httpretty.register_uri(httpretty.GET,
                               GITHUB_REPO_URL,
                               body=repo_body, status=200,
                               forcing_headers=forcing_headers_user)

        client = GitHubClient("zhquan_example", "repo", ["aaa", "bbb", "ccc"],
                              sleep_for_rate=True, min_rate_to_sleep=18)

        self.assertEqual(client.current_token, 'bbb')
        self.assertEqual(client.rate_limit, 19)

        client.repo()

        self.assertEqual(client.current_token, 'aaa')
        self.assertEqual(client.rate_limit, 200)

    @httpretty.activate
    def test_calculate_time_to_reset(self):
        """Test whether the time to reset is zero if the sleep time is negative"""

        rate_limit = read_file('data/github/rate_limit')
        httpretty.register_uri(httpretty.GET,
                               GITHUB_RATE_LIMIT,
                               body=rate_limit,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': int(datetime_utcnow().replace(microsecond=0).timestamp())
                               })

        client = GitHubClient("zhquan_example", "repo", ["aaa"], sleep_for_rate=True)
        time_to_reset = client.calculate_time_to_reset()

        self.assertEqual(time_to_reset, 0)

    @httpretty.activate
    def test_sleep_for_rate(self):
        """Test get_page_issue API call"""

        issue_1 = read_file('data/github/github_empty_request')
        issue_2 = read_file('data/github/github_empty_request')
        rate_limit = read_file('data/github/rate_limit')

        wait = 2
        reset = int(time.time() + wait)

        httpretty.register_uri(httpretty.GET,
                               GITHUB_RATE_LIMIT,
                               body=rate_limit,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': reset
                               })

        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUES_URL,
                               body=issue_1,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '0',
                                   'X-RateLimit-Reset': reset,
                                   'Link': '<' + GITHUB_ISSUES_URL + '/?&page=2>; rel="next", <' +
                                           GITHUB_ISSUES_URL + '/?&page=3>; rel="last"'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUES_URL + '/?&page=2',
                               body=issue_2,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': reset
                               })

        client = GitHubClient("zhquan_example", "repo", ["aaa"], sleep_for_rate=True)

        issues = [issues for issues in client.issues()]
        after = int(time.time())

        self.assertTrue(reset >= after)
        self.assertEqual(len(issues), 2)
        self.assertEqual(issues[0], issue_1)
        self.assertEqual(issues[1], issue_2)

        # Check requests
        expected = {
            'per_page': ['100'],
            'page': ['2'],
            'state': ['all'],
            'direction': ['asc'],
            'sort': ['updated']
        }

        self.assertDictEqual(httpretty.last_request().querystring, expected)
        self.assertEqual(httpretty.last_request().headers["Authorization"], "token aaa")

    @httpretty.activate
    def test_rate_limit_error(self):
        """Test get_page_issue API call"""

        issue = read_file('data/github/github_empty_request')
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
                                   'X-RateLimit-Remaining': '0',
                                   'X-RateLimit-Reset': '0',
                                   'Link': '<' + GITHUB_ISSUES_URL + '/?&page=2>; rel="next", <' +
                                           GITHUB_ISSUES_URL + '/?&page=3>; rel="last"'
                               })

        client = GitHubClient("zhquan_example", "repo", ["aaa"], sleep_for_rate=False)

        with self.assertRaises(RateLimitError):
            _ = [issues for issues in client.issues()]

        # Check requests
        expected = {
            'per_page': ['100'],
            'state': ['all'],
            'direction': ['asc'],
            'sort': ['updated']
        }

        self.assertDictEqual(httpretty.last_request().querystring, expected)
        self.assertEqual(httpretty.last_request().headers["Authorization"], "token aaa")

    def test_sanitize_for_archive(self):
        """Test whether the sanitize method works properly"""

        url = "http://example.com"
        headers = {GitHubClient.HAUTHORIZATION: "token aaa"}
        c_headers = copy.deepcopy(headers)
        payload = {}

        san_u, san_h, san_p = GitHubClient.sanitize_for_archive(url, c_headers, payload)
        headers.pop(GitHubClient.HAUTHORIZATION)

        self.assertEqual(url, san_u)
        self.assertEqual(headers, san_h)
        self.assertEqual(payload, san_p)


class TestGitHubCommand(unittest.TestCase):
    """GitHubCommand unit tests"""

    def test_backend_class(self):
        """Test if the backend class is GitHub"""

        self.assertIs(GitHubCommand.BACKEND, GitHub)

    def test_setup_cmd_parser(self):
        """Test if it parser object is correctly initialized"""

        parser = GitHubCommand.setup_cmd_parser()
        self.assertIsInstance(parser, BackendCommandArgumentParser)
        self.assertEqual(parser._backend, GitHub)

        args = ['--sleep-for-rate',
                '--min-rate-to-sleep', '1',
                '--max-retries', '5',
                '--max-items', '10',
                '--sleep-time', '10',
                '--tag', 'test', '--no-archive',
                '--api-token', 'abcdefgh', 'ijklmnop',
                '--from-date', '1970-01-01',
                '--to-date', '2100-01-01',
                '--enterprise-url', 'https://example.com',
                'zhquan_example', 'repo']

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.owner, 'zhquan_example')
        self.assertEqual(parsed_args.repository, 'repo')
        self.assertEqual(parsed_args.base_url, 'https://example.com')
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
                '--github-app-id', '1',
                '--github-app-pk-filepath', 'data/github/private.pem',
                '--from-date', '1970-01-01',
                '--to-date', '2100-01-01',
                '--no-ssl-verify',
                '--enterprise-url', 'https://example.com',
                'zhquan_example', 'repo']

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.owner, 'zhquan_example')
        self.assertEqual(parsed_args.repository, 'repo')
        self.assertEqual(parsed_args.base_url, 'https://example.com')
        self.assertTrue(parsed_args.sleep_for_rate)
        self.assertEqual(parsed_args.max_retries, 5)
        self.assertEqual(parsed_args.max_items, 10)
        self.assertEqual(parsed_args.sleep_time, 10)
        self.assertEqual(parsed_args.tag, 'test')
        self.assertEqual(parsed_args.from_date, DEFAULT_DATETIME)
        self.assertEqual(parsed_args.to_date, DEFAULT_LAST_DATETIME)
        self.assertTrue(parsed_args.no_archive)
        self.assertFalse(parsed_args.ssl_verify)
        self.assertEqual(parsed_args.github_app_id, '1')
        self.assertEqual(parsed_args.github_app_pk_filepath, 'data/github/private.pem')


if __name__ == "__main__":
    unittest.main(warnings='ignore')
