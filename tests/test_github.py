#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2015-2018 Bitergia
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
#     Quan Zhou <quan@bitergia.com>
#

import datetime
import os
import time
import unittest

import httpretty
import pkg_resources
import requests

pkg_resources.declare_namespace('perceval.backends')

from grimoirelab.toolkit.datetime import datetime_utcnow
from perceval.backend import BackendCommandArgumentParser
from perceval.client import RateLimitHandler
from perceval.errors import RateLimitError
from perceval.utils import DEFAULT_DATETIME
from perceval.backends.core.github import (GitHub,
                                           GitHubCommand,
                                           GitHubClient,
                                           CATEGORY_ISSUE,
                                           CATEGORY_PULL_REQUEST)
from base import TestCaseBackendArchive


GITHUB_API_URL = "https://api.github.com"
GITHUB_RATE_LIMIT = GITHUB_API_URL + "/rate_limit"
GITHUB_ISSUES_URL = GITHUB_API_URL + "/repos/zhquan_example/repo/issues"
GITHUB_PULL_REQUEST_URL = GITHUB_API_URL + "/repos/zhquan_example/repo/pulls"
GITHUB_ISSUE_1_COMMENTS_URL = GITHUB_ISSUES_URL + "/1/comments"
GITHUB_ISSUE_COMMENT_1_REACTION_URL = GITHUB_ISSUES_URL + "/comments/1/reactions"
GITHUB_ISSUE_2_REACTION_URL = GITHUB_ISSUES_URL + "/2/reactions"
GITHUB_ISSUE_2_COMMENTS_URL = GITHUB_ISSUES_URL + "/2/comments"
GITHUB_ISSUE_COMMENT_2_REACTION_URL = GITHUB_ISSUES_URL + "/comments/2/reactions"
GITHUB_PULL_REQUEST_1_URL = GITHUB_PULL_REQUEST_URL + "/1"
GITHUB_PULL_REQUEST_1_COMMENTS = GITHUB_PULL_REQUEST_1_URL + "/comments"
GITHUB_PULL_REQUEST_1_COMMENTS_2_REACTIONS = GITHUB_PULL_REQUEST_URL + "/comments/2/reactions"
GITHUB_PULL_REQUEST_1_REQUESTED_REVIEWERS_URL = GITHUB_PULL_REQUEST_1_URL + "/requested_reviewers"
GITHUB_PULL_REQUEST_2_URL = GITHUB_PULL_REQUEST_URL + "/2"
GITHUB_PULL_REQUEST_2_COMMENTS = GITHUB_PULL_REQUEST_2_URL + "/comments"
GITHUB_PULL_REQUEST_2_REQUESTED_REVIEWERS_URL = GITHUB_PULL_REQUEST_2_URL + "/requested_reviewers"
GITHUB_USER_URL = GITHUB_API_URL + "/users/zhquan_example"
GITHUB_ORGS_URL = GITHUB_API_URL + "/users/zhquan_example/orgs"
GITHUB_COMMAND_URL = GITHUB_API_URL + "/command"

GITHUB_ENTERPRISE_URL = "https://example.com"
GITHUB_ENTERPRISE_API_URL = "https://example.com/api/v3"
GITHUB_ENTREPRISE_RATE_LIMIT = GITHUB_ENTERPRISE_API_URL + "/rate_limit"
GITHUB_ENTERPRISE_ISSUES_URL = GITHUB_ENTERPRISE_API_URL + "/repos/zhquan_example/repo/issues"
GITHUB_ENTERPRISE_PULL_REQUESTS_URL = GITHUB_ENTERPRISE_API_URL + "/repos/zhquan_example/repo/pulls"
GITHUB_ENTERPRISE_ISSUE_1_COMMENTS_URL = GITHUB_ENTERPRISE_ISSUES_URL + "/1/comments"
GITHUB_ENTERPRISE_ISSUE_COMMENT_1_REACTION_URL = GITHUB_ENTERPRISE_ISSUES_URL + "/comments/1/reactions"
GITHUB_ENTERPRISE_ISSUE_2_REACTION_URL = GITHUB_ENTERPRISE_ISSUES_URL + "/2/reactions"
GITHUB_ENTERPRISE_ISSUE_2_COMMENTS_URL = GITHUB_ENTERPRISE_ISSUES_URL + "/2/comments"
GITHUB_ENTERPRISE_ISSUE_COMMENT_2_REACTION_URL = GITHUB_ENTERPRISE_ISSUES_URL + "/comments/2/reactions"
GITHUB_ENTERPRISE_USER_URL = GITHUB_ENTERPRISE_API_URL + "/users/zhquan_example"
GITHUB_ENTERPRISE_ORGS_URL = GITHUB_ENTERPRISE_API_URL + "/users/zhquan_example/orgs"
GITHUB_ENTREPRISE_PULL_REQUEST_1_URL = GITHUB_ENTERPRISE_PULL_REQUESTS_URL + "/1"
GITHUB_ENTREPRISE_PULL_REQUEST_1_COMMENTS = GITHUB_ENTREPRISE_PULL_REQUEST_1_URL + "/comments"
GITHUB_ENTREPRISE_PULL_REQUEST_1_COMMENTS_2_REACTIONS = GITHUB_ENTERPRISE_PULL_REQUESTS_URL + "/comments/2/reactions"
GITHUB_ENTREPRISE_REQUEST_REQUESTED_REVIEWERS_URL = GITHUB_ENTREPRISE_PULL_REQUEST_1_URL + "/requested_reviewers"


def read_file(filename, mode='r'):
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), filename), mode) as f:
        content = f.read()
    return content


class TestGitHubBackend(unittest.TestCase):
    """ GitHub backend tests """

    @httpretty.activate
    def test_initialization(self):
        """Test whether attributes are initializated"""

        rate_limit = read_file('data/github/rate_limit')
        httpretty.register_uri(httpretty.GET,
                               GITHUB_RATE_LIMIT,
                               body=rate_limit,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        github = GitHub('zhquan_example', 'repo', 'aaa', tag='test')

        self.assertEqual(github.owner, 'zhquan_example')
        self.assertEqual(github.repository, 'repo')
        self.assertEqual(github.origin, 'https://github.com/zhquan_example/repo')
        self.assertEqual(github.tag, 'test')

        self.assertEqual(github.categories, [CATEGORY_ISSUE, CATEGORY_PULL_REQUEST])

        # When tag is empty or None it will be set to
        # the value in origin
        github = GitHub('zhquan_example', 'repo', 'aaa')
        self.assertEqual(github.owner, 'zhquan_example')
        self.assertEqual(github.repository, 'repo')
        self.assertEqual(github.origin, 'https://github.com/zhquan_example/repo')
        self.assertEqual(github.tag, 'https://github.com/zhquan_example/repo')

        github = GitHub('zhquan_example', 'repo', 'aaa', tag='')
        self.assertEqual(github.owner, 'zhquan_example')
        self.assertEqual(github.repository, 'repo')
        self.assertEqual(github.origin, 'https://github.com/zhquan_example/repo')
        self.assertEqual(github.tag, 'https://github.com/zhquan_example/repo')

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

        github = GitHub("zhquan_example", "repo", "aaa")
        issues = [issues for issues in github.fetch(from_date=None)]

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
    def test_fetch_pulls(self):
        """Test whether a list of pull requests is returned"""

        body = read_file('data/github/github_request')
        login = read_file('data/github/github_login')
        orgs = read_file('data/github/github_orgs')
        pull = read_file('data/github/github_request_pull_request_1')
        pull_comments = read_file('data/github/github_request_pull_request_1_comments')
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

        github = GitHub("zhquan_example", "repo", "aaa")
        pulls = [pulls for pulls in github.fetch(category=CATEGORY_PULL_REQUEST, from_date=None)]

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

        github = GitHub("zhquan_example", "repo", "aaa")
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
        self.assertEqual(issue['updated_on'], 1458054569.0)
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
        pull_1_comment_2_reactions = read_file('data/github/github_request_pull_request_1_comment_2_reactions')
        pull_requested_reviewers = read_file('data/github/github_request_requested_reviewers')
        pull_2 = read_file('data/github/github_request_pull_request_2')
        pull_2_comments = read_file('data/github/github_request_pull_request_2_comments')
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

        github = GitHub("zhquan_example", "repo", "aaa")
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

        pull = pulls[1]
        self.assertEqual(pull['origin'], 'https://github.com/zhquan_example/repo')
        self.assertEqual(pull['uuid'], '58c073fd2a388c44043b9cc197c73c5c540270ac')
        self.assertEqual(pull['updated_on'], 1451929343.0)
        self.assertEqual(pull['category'], CATEGORY_PULL_REQUEST)
        self.assertEqual(pull['tag'], 'https://github.com/zhquan_example/repo')
        self.assertEqual(pull['data']['merged_by_data']['login'], 'zhquan_example')
        self.assertEqual(pull['data']['requested_reviewers_data'], [])
        self.assertEqual(len(pull['data']['review_comments_data']), 2)
        self.assertEqual(len(pull['data']['review_comments_data'][0]['reactions_data']), 0)
        self.assertEqual(len(pull['data']['review_comments_data'][1]['reactions_data']), 0)

    @httpretty.activate
    def test_fetch_pulls_from_issues(self):
        """Test when return pull requests are fetched from only issues with pull request data """

        login = read_file('data/github/github_login')
        orgs = read_file('data/github/github_orgs')
        issue_1 = read_file('data/github/github_issue_1')
        issue_2 = read_file('data/github/github_issue_2')
        pull_request = read_file('data/github/github_request_pull_request_1')
        pull_request_comments = read_file('data/github/github_request_pull_request_1_comments')
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

        github = GitHub("zhquan_example", "repo", "aaa")
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

        github = GitHub("zhquan_example", "repo", "aaa")
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

        github = GitHub("zhquan_example", "repo", "aaa",
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
        self.assertEqual(issue['updated_on'], 1458054569.0)
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
        pull_request_comment_2_reactions = read_file('data/github/github_request_pull_request_1_comment_2_reactions')
        pull_requested_reviewers = read_file('data/github/github_request_requested_reviewers')

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
                               GITHUB_ENTREPRISE_PULL_REQUEST_1_COMMENTS_2_REACTIONS,
                               body=pull_request_comment_2_reactions,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })
        github = GitHub("zhquan_example", "repo", "aaa",
                        base_url=GITHUB_ENTERPRISE_URL)

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
        github = GitHub("zhquan_example", "repo", "aaa")

        issues = [issues for issues in github.fetch(from_date=from_date)]

        issue = issues[0]
        self.assertEqual(issue['origin'], 'https://github.com/zhquan_example/repo')
        self.assertEqual(issue['uuid'], '4236619ac2073491640f1698b5c4e169895aaf69')
        self.assertEqual(issue['updated_on'], 1458054569.0)
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
        github = GitHub("zhquan_example", "repo", "aaa")

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
        github = GitHub("zhquan_example", "repo", "aaa")
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

        github = GitHub("zhquan_example", "repo", "aaa")
        with self.assertRaises(requests.exceptions.HTTPError):
            _ = [issues for issues in github.fetch()]


class TestGitHubBackendArchive(TestCaseBackendArchive):
    """GitHub backend tests using an archive"""

    def setUp(self):
        super().setUp()
        self.backend_write_archive = GitHub("zhquan_example", "repo", "aaa", archive=self.archive)
        self.backend_read_archive = GitHub("zhquan_example", "repo", "aaa", archive=self.archive)

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
        pull_request_comments = read_file('data/github/github_request_pull_request_1_comments')
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
                               GITHUB_PULL_REQUEST_1_COMMENTS,
                               body=pull_request_comments,
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

        client = GitHubClient('zhquan_example', 'repo', 'aaa')

        self.assertEqual(client.owner, 'zhquan_example')
        self.assertEqual(client.repository, 'repo')
        self.assertEqual(client.max_retries, GitHubClient.MAX_RETRIES)
        self.assertEqual(client.sleep_time, GitHubClient.DEFAULT_SLEEP_TIME)
        self.assertEqual(client.max_retries, GitHubClient.MAX_RETRIES)
        self.assertEqual(client.base_url, 'https://api.github.com')

        client = GitHubClient('zhquan_example', 'repo', 'aaa', min_rate_to_sleep=RateLimitHandler.MAX_RATE_LIMIT + 1)
        self.assertEqual(client.min_rate_to_sleep, RateLimitHandler.MAX_RATE_LIMIT)

        client = GitHubClient('zhquan_example', 'repo', 'aaa', min_rate_to_sleep=RateLimitHandler.MAX_RATE_LIMIT - 1)
        self.assertEqual(client.min_rate_to_sleep, RateLimitHandler.MAX_RATE_LIMIT - 1)

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

        client = GitHubClient("zhquan_example", "repo", "aaa")
        self.assertEqual(client.base_url, GITHUB_API_URL)

        client = GitHubClient("zhquan_example", "repo", "aaa",
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

        client = GitHubClient("zhquan_example", "repo", "aaa", None)
        raw_issues = [issues for issues in client.issues()]
        self.assertEqual(raw_issues[0], issues)

        # Check requests
        expected = {
            'per_page': ['30'],
            'state': ['all'],
            'direction': ['asc'],
            'sort': ['updated']
        }

        self.assertDictEqual(httpretty.last_request().querystring, expected)
        self.assertEqual(httpretty.last_request().headers["Authorization"], "token aaa")

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

        client = GitHubClient("zhquan_example", "repo", "aaa")

        pull_requested_reviewers_raw = [rev for rev in client.issue_comments(2)]
        self.assertEqual(pull_requested_reviewers_raw[0], issue_comments)

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

        client = GitHubClient("zhquan_example", "repo", "aaa")

        pull_requested_reviewers_raw = [rev for rev in client.issue_reactions(2)]
        self.assertEqual(pull_requested_reviewers_raw[0], issue_reactions)

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

        client = GitHubClient("zhquan_example", "repo", "aaa")

        pull_requested_reviewers_raw = [rev for rev in client.issue_comment_reactions(1)]
        self.assertEqual(pull_requested_reviewers_raw[0], issue_comment_reactions)

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

        client = GitHubClient("zhquan_example", "repo", "aaa", None)
        raw_pulls = [pulls for pulls in client.pulls()]
        self.assertEqual(raw_pulls[0], pull_request)

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

        client = GitHubClient("zhquan_example", "repo", "aaa",
                              base_url=GITHUB_ENTERPRISE_URL)

        raw_issues = [issues for issues in client.issues()]
        self.assertEqual(raw_issues[0], issue)

        # Check requests
        expected = {
            'per_page': ['30'],
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

        client = GitHubClient("zhquan_example", "repo", "aaa",
                              base_url=GITHUB_ENTERPRISE_URL)

        raw_pulls = [pulls for pulls in client.pulls()]
        self.assertEqual(raw_pulls[0], pull_request)

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
        client = GitHubClient("zhquan_example", "repo", "aaa", None)

        raw_issues = [issues for issues in client.issues(from_date=from_date)]
        self.assertEqual(raw_issues[0], issues)

        # Check requests
        expected = {
            'per_page': ['30'],
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

        client = GitHubClient("zhquan_example", "repo", "aaa")

        issues = [issues for issues in client.issues()]

        self.assertEqual(len(issues), 2)
        self.assertEqual(issues[0], issue_1)
        self.assertEqual(issues[1], issue_2)

        # Check requests
        expected = {
            'per_page': ['30'],
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

        client = GitHubClient("zhquan_example", "repo", "aaa")

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

        client = GitHubClient("zhquan_example", "repo", "aaa")

        pull_review_comments_raw = [rev for rev in client.pull_review_comments(1)]
        self.assertEqual(pull_review_comments_raw[0], pull_request_comments)

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

        client = GitHubClient("zhquan_example", "repo", "aaa")

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
        client = GitHubClient("zhquan_example", "repo", "aaa", None)

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

        client = GitHubClient("zhquan_example", "repo", "aaa", None)

        raw_issues = [issues for issues in client.issues()]
        self.assertEqual(raw_issues[0], issue)

        # Check requests
        expected = {
            'per_page': ['30'],
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

        client = GitHubClient("zhquan_example", "repo", "aaa", None)
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

        client = GitHubClient("zhquan_example", "repo", "aaa", None)
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
                               status=500,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        client = GitHubClient("zhquan_example", "repo", "aaa", sleep_time=1, max_retries=1)

        with self.assertRaises(requests.exceptions.HTTPError):
            _ = [issues for issues in client.issues()]

        # Check requests
        expected = {
            'per_page': ['30'],
            'state': ['all'],
            'direction': ['asc'],
            'sort': ['updated']
        }

        self.assertDictEqual(httpretty.last_request().querystring, expected)
        self.assertEqual(httpretty.last_request().headers["Authorization"], "token aaa")

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

        client = GitHubClient("zhquan_example", "repo", "aaa", sleep_for_rate=True)
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

        client = GitHubClient("zhquan_example", "repo", "aaa", sleep_for_rate=True)

        issues = [issues for issues in client.issues()]
        after = int(time.time())

        self.assertTrue(reset >= after)
        self.assertEqual(len(issues), 2)
        self.assertEqual(issues[0], issue_1)
        self.assertEqual(issues[1], issue_2)

        # Check requests
        expected = {
            'per_page': ['30'],
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

        client = GitHubClient("zhquan_example", "repo", "aaa", sleep_for_rate=False)

        with self.assertRaises(RateLimitError):
            _ = [issues for issues in client.issues()]

        # Check requests
        expected = {
            'per_page': ['30'],
            'state': ['all'],
            'direction': ['asc'],
            'sort': ['updated']
        }

        self.assertDictEqual(httpretty.last_request().querystring, expected)
        self.assertEqual(httpretty.last_request().headers["Authorization"], "token aaa")


class TestGitHubCommand(unittest.TestCase):
    """GitHubCommand unit tests"""

    def test_backend_class(self):
        """Test if the backend class is GitHub"""

        self.assertIs(GitHubCommand.BACKEND, GitHub)

    def test_setup_cmd_parser(self):
        """Test if it parser object is correctly initialized"""

        parser = GitHubCommand.setup_cmd_parser()
        self.assertIsInstance(parser, BackendCommandArgumentParser)

        args = ['--sleep-for-rate',
                '--min-rate-to-sleep', '1',
                '--max-retries', '5',
                '--sleep-time', '10',
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
        self.assertEqual(parsed_args.max_retries, 5)
        self.assertEqual(parsed_args.sleep_time, 10)
        self.assertEqual(parsed_args.tag, 'test')
        self.assertEqual(parsed_args.from_date, DEFAULT_DATETIME)
        self.assertEqual(parsed_args.no_archive, True)
        self.assertEqual(parsed_args.api_token, 'abcdefgh')


if __name__ == "__main__":
    unittest.main(warnings='ignore')
