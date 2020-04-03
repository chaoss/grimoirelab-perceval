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

#from base import TestCaseBackendArchive
import os
import unittest
import httpretty
import pkg_resources

pkg_resources.declare_namespace('perceval.backends')

from perceval.backends.core.gitee import (GiteeClient,GITEE_API_URL)

GITEE_API_URL = "https://gitee.com/api/v5"
GITEE_REPO_URL = GITEE_API_URL + "/repos/gitee_example/repo"
GITEE_ISSUES_URL = GITEE_REPO_URL + "/issues"
GITEE_ISSUE_COMMENTS_URL_1 = GITEE_ISSUES_URL + "/I1DI54/comments"
GITEE_PULL_REQUEST_URL = GITEE_REPO_URL + "/pulls"


def read_file(filename, mode='r'):
    with open(os.path.join(
            os.path.dirname(os.path.abspath(__file__)), filename), mode) as f:
        content = f.read()
    return content

class TestGiteeClient(unittest.TestCase):
    """Gitee API client tests"""

    def test_init(self):
        client = GiteeClient('gitee_example', 'repo', 'aaa')
        self.assertEqual(client.owner, 'gitee_example')
        self.assertEqual(client.repository, 'repo')
        self.assertEqual(client.max_retries, GiteeClient.MAX_RETRIES)
        self.assertEqual(client.sleep_time, GiteeClient.DEFAULT_SLEEP_TIME)
        self.assertEqual(client.max_retries, GiteeClient.MAX_RETRIES)
        self.assertEqual(client.base_url, 'https://gitee.com/api/v5/')
        self.assertTrue(client.ssl_verify)

    @httpretty.activate
    def test_get_empty_issues(self):
        """ Test when issue is empty API call """

        empty_issue='[]'
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
    def test_get_issues(self) :
        """Test Gitee issues API """

        issues = read_file('data/gitee/gitee_issues_page1')
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
    def test_issue_comments(self) :
        """Test Gitee issue comments API """

        issue_comments = read_file('data/gitee/gitee_issue_comments_1')
        httpretty.register_uri(httpretty.GET, GITEE_ISSUE_COMMENTS_URL_1, 
                                body=issue_comments, status=200,
                                forcing_headers={
                                    "total_count": "1",
                                    "total_page": "1"
                               })

        client = GiteeClient("gitee_example", "repo", 'aaa', None)
        raw_issue_comments = [comments for comments in client.issue_comments("I1DI54")]
        self.assertEqual(raw_issue_comments[0], issue_comments)
        
         # Check requests parameter
        expected = {
            'per_page': ['100'],
            'access_token': ['aaa']
        }
        self.assertDictEqual(httpretty.last_request().querystring, expected)

    @httpretty.activate
    def test_pulls(self):
        pull_request = read_file('data/gitee/gitee_pull_request_page_1')
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

                     



