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

import datetime
import sys
import unittest

import httpretty

if not '..' in sys.path:
    sys.path.insert(0, '..')

from perceval.backends.redmine import RedmineClient


REDMINE_URL = 'http://example.com'
REDMINE_ISSUES_URL = REDMINE_URL + '/issues.json'
REDMINE_ISSUE_7311_URL = REDMINE_URL + '/issues/7311.json'


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

    def request_callback(method, uri, headers):
        last_request = httpretty.last_request()
        params = last_request.querystring

        if uri == REDMINE_ISSUES_URL:
            if params['from_date'] == '1970-01-01T00:00:00Z' and \
                'offset' not in params:
                body = issues_body
            elif params['from_date'] == '2016-07-27T00:00:00Z' or \
                params['offset'] == 3:
                body = issues_next_body
            else:
                body = issues_empty_body
        else:
            raise

        http_requests.append(last_request)

        return (200, headers, body)

    httpretty.register_uri(httpretty.GET,
                           REDMINE_ISSUES_URL,
                           responses=[
                                httpretty.Response(body=request_callback)
                           ])

    return http_requests


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


if __name__ == "__main__":
    unittest.main(warnings='ignore')
