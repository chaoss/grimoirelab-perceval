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
#     Alberto Martín <alberto.martin@bitergia.com>
#

import sys
import unittest
import requests

import httpretty

if not '..' in sys.path:
    sys.path.insert(0, '..')

from perceval.backends.askbot import AskbotClient

ASKBOT_URL = 'http://example.com'
ASKBOT_QUESTIONS_API_URL = ASKBOT_URL + '/api/v1/questions'
ASKBOT_QUESTION_2481_URL = ASKBOT_URL + '/question/2481'
ASKBOT_QUESTION_2488_URL = ASKBOT_URL + '/question/2488'
ASKBOT_QUESTION_EMPTY_URL = ASKBOT_URL + '/question/0'


def read_file(filename, mode='r'):
    with open(filename, mode) as f:
        content = f.read()
    return content


class TestAskbotClient(unittest.TestCase):
    """Askbot client unit tests.

    These tests do not check the body of the response, only if the call
    was well formed and if a response was obtained.
    """
    def test_init(self):
        """Test initialization parameters"""

        client = AskbotClient(ASKBOT_URL)
        self.assertEqual(client.base_url, ASKBOT_URL)

    @httpretty.activate
    def test_get_api_questions(self):
        """Test if API Questions call works"""

        body = read_file('data/askbot/askbot_api_questions.json')

        httpretty.register_uri(httpretty.GET,
                               ASKBOT_QUESTIONS_API_URL,
                               body=body, status=200)

        client = AskbotClient(ASKBOT_URL)

        result = client.get_api_questions(1)

        self.assertEqual(result, body)

        expected = {
                    'page': ['1'],
                    'sort': ['activity-asc']
                   }

        req = httpretty.last_request()

        self.assertEqual(req.method, 'GET')
        self.assertRegex(req.path, '/api/v1/questions')
        self.assertDictEqual(req.querystring, expected)

    @httpretty.activate
    def test_get_html_question(self):
        """Test if HTML Questions call works"""

        body = read_file('data/askbot/askbot_question.html')

        httpretty.register_uri(httpretty.GET,
                               ASKBOT_QUESTION_2481_URL,
                               body=body, status=200)

        client = AskbotClient(ASKBOT_URL)

        result = client.get_html_question(2481)

        self.assertEqual(result, body)

        req = httpretty.last_request()

        self.assertEqual(req.method, 'GET')
        self.assertRegex(req.path, '/question/2481')

    @httpretty.activate
    def test_get_html_question_multipage(self):
        """Test if HTML Questions multipage call works"""

        body = read_file('data/askbot/askbot_question_multipage_2.html')

        httpretty.register_uri(httpretty.GET,
                               ASKBOT_QUESTION_2488_URL,
                               body=body, status=200)

        client = AskbotClient(ASKBOT_URL)

        result = client.get_html_question(2488, 2)

        self.assertEqual(result, body)

        expected = {
                    'page': ['2'],
                    'sort': ['votes']
                   }

        req = httpretty.last_request()

        self.assertEqual(req.method, 'GET')
        self.assertRegex(req.path, '/question/2488')
        self.assertDictEqual(req.querystring, expected)

    @httpretty.activate
    def test_get_html_question_empty(self):
        """Test if HTML Questions call (non-existing question) works"""

        body = read_file('data/askbot/askbot_question_empty.html')

        httpretty.register_uri(httpretty.GET,
                               ASKBOT_QUESTION_EMPTY_URL,
                               body=body, status=404)

        client = AskbotClient(ASKBOT_URL)

        self.assertRaises(requests.exceptions.HTTPError, client.get_html_question, 0)

        req = httpretty.last_request()

        self.assertEqual(req.method, 'GET')
        self.assertRegex(req.path, '/question/0')

if __name__ == "__main__":
    unittest.main(warnings='ignore')
