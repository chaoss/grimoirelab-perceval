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
#     Santiago Dueñas <sduenas@bitergia.com>
#     Stephan Barth <stephan.barth@gmail.com>
#     Valerio Cosentino <valcos@bitergia.com>
#     Miguel Ángel Fernández <mafesan@bitergia.com>
#     Harshal Mittal <harshalmittal4@gmail.com>
#

import copy
import datetime
import httpretty
import json
import os
import pkg_resources
import time
import unittest
import urllib

pkg_resources.declare_namespace('perceval.backends')

from perceval.backend import BackendCommandArgumentParser
from perceval.utils import DEFAULT_DATETIME
from perceval.backends.core.stackexchange import (StackExchange,
                                                  StackExchangeCommand,
                                                  StackExchangeClient,
                                                  MAX_QUESTIONS)
from base import TestCaseBackendArchive


VERSION_API = '/2.2'
STACKEXCHANGE_API_URL = 'https://api.stackexchange.com'
STACKEXCHANGE_VERSION_URL = STACKEXCHANGE_API_URL + VERSION_API
STACKEXCHANGE_QUESTIONS_URL = STACKEXCHANGE_VERSION_URL + '/questions'
QUESTIONS_FILTER = 'Bf*y*ByQD_upZqozgU6lXL_62USGOoV3)MFNgiHqHpmO_Y-jHR'


def read_file(filename, mode='r'):
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), filename), mode) as f:
        content = f.read()
    return content


class TestStackExchangeBackend(unittest.TestCase):
    """StackExchange backend tests"""

    def test_initialization(self):
        """Test whether attributes are initializated"""

        stack = StackExchange(site='stackoverflow', tagged='python',
                              max_questions=1, tag='test')

        self.assertEqual(stack.site, 'stackoverflow')
        self.assertEqual(stack.tagged, 'python')
        self.assertEqual(stack.max_questions, 1)
        self.assertEqual(stack.origin, 'stackoverflow')
        self.assertEqual(stack.tag, 'test')
        self.assertIsNone(stack.client)
        self.assertTrue(stack.ssl_verify)

        # When tag is empty or None it will be set to
        # the value in site
        stack = StackExchange(site='stackoverflow', ssl_verify=False)
        self.assertEqual(stack.site, 'stackoverflow')
        self.assertEqual(stack.origin, 'stackoverflow')
        self.assertEqual(stack.tag, 'stackoverflow')
        self.assertFalse(stack.ssl_verify)

        stack = StackExchange(site='stackoverflow', tag='')
        self.assertEqual(stack.site, 'stackoverflow')
        self.assertEqual(stack.origin, 'stackoverflow')
        self.assertEqual(stack.tag, 'stackoverflow')

    def test_has_archiving(self):
        """Test if it returns True when has_archiving is called"""

        self.assertEqual(StackExchange.has_archiving(), True)

    def test_has_resuming(self):
        """Test if it returns True when has_resuming is called"""

        self.assertEqual(StackExchange.has_resuming(), True)

    @httpretty.activate
    def test_fetch(self):
        """Test whether a list of questions is returned"""

        question = read_file('data/stackexchange/stackexchange_question')

        httpretty.register_uri(httpretty.GET,
                               STACKEXCHANGE_QUESTIONS_URL,
                               body=question, status=200)

        stack = StackExchange(site="stackoverflow", tagged="python",
                              api_token="aaa", max_questions=1)
        questions = [question for question in stack.fetch(from_date=None)]

        self.assertEqual(questions[0]['origin'], 'stackoverflow')
        self.assertEqual(questions[0]['uuid'], '43953bd75d1d4dbedb457059acb4b79fcf6712a8')
        self.assertEqual(questions[0]['updated_on'], 1459975066.0)
        self.assertEqual(questions[0]['category'], 'question')
        self.assertEqual(questions[0]['tag'], 'stackoverflow')

        data = json.loads(question)
        self.assertDictEqual(questions[0]['data'], data['items'][0])

    @httpretty.activate
    def test_search_fields(self):
        """Test whether the search_fields is properly set"""

        question = read_file('data/stackexchange/stackexchange_question')

        httpretty.register_uri(httpretty.GET,
                               STACKEXCHANGE_QUESTIONS_URL,
                               body=question, status=200)

        stack = StackExchange(site="stackoverflow", tagged="python",
                              api_token="aaa", max_questions=1)
        questions = [question for question in stack.fetch(from_date=None)]

        question = questions[0]
        self.assertEqual(stack.metadata_id(question['data']), question['search_fields']['item_id'])
        self.assertListEqual(question['data']['tags'], ['python', 'pandas'])
        self.assertEqual(question['data']['tags'], question['search_fields']['tags'])

    @httpretty.activate
    def test_fetch_empty(self):
        """Test whether a list of questions is returned"""

        # Required fields
        question = '{"total": 0, "page_size": 0, "quota_remaining": 0, "quota_max": 0, "has_more": false, "items": []}'
        httpretty.register_uri(httpretty.GET,
                               STACKEXCHANGE_QUESTIONS_URL,
                               body=question, status=200)

        stack = StackExchange(site="stackoverflow", tagged="python",
                              api_token="aaa", max_questions=1)
        questions = [question for question in stack.fetch(from_date=None)]

        self.assertEqual(len(questions), 0)

    @httpretty.activate
    def test_fetch_from_date(self):
        """Test whether a list of questions is returned"""

        question = read_file('data/stackexchange/stackexchange_question')

        httpretty.register_uri(httpretty.GET,
                               STACKEXCHANGE_QUESTIONS_URL,
                               body=question, status=200)

        from_date = datetime.datetime(2016, 4, 5)
        stack = StackExchange(site="stackoverflow", tagged="python",
                              api_token="aaa", max_questions=1)
        questions = [question for question in stack.fetch(from_date=from_date)]

        self.assertEqual(questions[0]['origin'], 'stackoverflow')
        self.assertEqual(questions[0]['uuid'], '43953bd75d1d4dbedb457059acb4b79fcf6712a8')
        self.assertEqual(questions[0]['updated_on'], 1459975066.0)
        self.assertEqual(questions[0]['category'], 'question')
        self.assertEqual(questions[0]['tag'], 'stackoverflow')

        # The date on the questions must be greater than from_date
        self.assertGreater(questions[0]['updated_on'], 1459900800)

        data = json.loads(question)
        self.assertDictEqual(questions[0]['data'], data['items'][0])


class TestStackExchangeBackendArchive(TestCaseBackendArchive):
    """StackExchange backend tests using an archive"""

    def setUp(self):
        super().setUp()
        self.backend_write_archive = StackExchange(site="stackoverflow.com", tagged="python",
                                                   api_token="aaa", max_questions=1,
                                                   archive=self.archive)
        self.backend_read_archive = StackExchange(site="stackoverflow.com", tagged="python",
                                                  api_token="bbb", max_questions=1,
                                                  archive=self.archive)

    @httpretty.activate
    def test_fetch_from_archive(self):
        """Test whether a list of questions is returned from archive"""

        question = read_file('data/stackexchange/stackexchange_question')

        httpretty.register_uri(httpretty.GET,
                               STACKEXCHANGE_QUESTIONS_URL,
                               body=question, status=200)

        self._test_fetch_from_archive()

    @httpretty.activate
    def test_fetch_from_date_from_archive(self):
        """Test whether a list of questions from a given date is returned from the archive"""

        question = read_file('data/stackexchange/stackexchange_question')

        httpretty.register_uri(httpretty.GET,
                               STACKEXCHANGE_QUESTIONS_URL,
                               body=question, status=200)

        from_date = datetime.datetime(2016, 4, 5)
        self._test_fetch_from_archive(from_date=from_date)

    @httpretty.activate
    def test_fetch_empty_from_archive(self):
        """Test whether a list of questions is returned from archive"""

        # Required fields
        question = '{"total": 0, "page_size": 0, "quota_remaining": 0, "quota_max": 0, "has_more": false, "items": []}'
        httpretty.register_uri(httpretty.GET,
                               STACKEXCHANGE_QUESTIONS_URL,
                               body=question, status=200)

        self._test_fetch_from_archive(from_date=None)


class TestStackExchangeBackendParsers(unittest.TestCase):
    """StackExchange backend parsers tests"""

    def test_parse_questions(self):
        """Test question parsing"""

        raw_parse = read_file('data/stackexchange/stackexchange_question_page')
        parse = read_file('data/stackexchange/stackexchange_question_parse')
        parse = json.loads(parse)

        questions = StackExchange.parse_questions(raw_parse)

        result = [question for question in questions]

        self.assertDictEqual(result[0], parse[0])
        self.assertDictEqual(result[1], parse[1])


class TestStackExchangeClient(unittest.TestCase):
    """StackExchange API client tests"""

    def test_initialization(self):
        """Test whether the parameters are initialized"""

        client = StackExchangeClient(site="stackoverflow", tagged="python", token="aaa")
        self.assertEqual(client.site, "stackoverflow")
        self.assertEqual(client.tagged, "python")
        self.assertEqual(client.token, "aaa")
        self.assertEqual(client.max_questions, MAX_QUESTIONS)
        self.assertTrue(client.ssl_verify)

        client = StackExchangeClient(site="stackoverflow", tagged="python", token="aaa",
                                     max_questions=5, ssl_verify=False)
        self.assertEqual(client.site, "stackoverflow")
        self.assertEqual(client.tagged, "python")
        self.assertEqual(client.token, "aaa")
        self.assertEqual(client.max_questions, 5)
        self.assertFalse(client.ssl_verify)

    @httpretty.activate
    def test_get_questions(self):
        """Test question API call"""

        question = read_file('data/stackexchange/stackexchange_question')

        httpretty.register_uri(httpretty.GET,
                               STACKEXCHANGE_QUESTIONS_URL,
                               body=question, status=200)

        payload = {
            'page': ['1'],
            'pagesize': ['1'],
            'order': ['desc'],
            'sort': ['activity'],
            'tagged': ['python'],
            'site': ['stackoverflow'],
            'key': ['aaa'],
            'filter': [QUESTIONS_FILTER]
        }

        client = StackExchangeClient(site="stackoverflow", tagged="python", token="aaa", max_questions=1)
        raw_questions = [questions for questions in client.get_questions(from_date=None)]

        self.assertEqual(len(raw_questions), 1)
        self.assertEqual(raw_questions[0], question)

        request = httpretty.last_request().querystring
        self.assertTrue(len(request), 1)
        self.assertDictEqual(request, payload)

    @httpretty.activate
    def test_get_question_empty(self):
        """ Test when question is empty API call """

        # Required fields
        question = '{"total": 0, "page_size": 0, "quota_remaining": 0, "quota_max": 0, "has_more": false}'

        httpretty.register_uri(httpretty.GET,
                               STACKEXCHANGE_QUESTIONS_URL,
                               body=question, status=200)

        payload = {
            'page': ['1'],
            'pagesize': ['1'],
            'order': ['desc'],
            'sort': ['activity'],
            'tagged': ['python'],
            'site': ['stackoverflow'],
            'key': ['aaa'],
            'filter': [QUESTIONS_FILTER]
        }

        client = StackExchangeClient(site="stackoverflow", tagged="python", token="aaa", max_questions=1)
        raw_questions = [questions for questions in client.get_questions(from_date=None)]

        self.assertEqual(len(raw_questions), 1)
        self.assertEqual(raw_questions[0], question)
        self.assertDictEqual(httpretty.last_request().querystring, payload)

    @httpretty.activate
    def test_get_questions_from_date(self):
        """Test question is returned from a given date"""

        question = read_file('data/stackexchange/stackexchange_question')

        httpretty.register_uri(httpretty.GET,
                               STACKEXCHANGE_QUESTIONS_URL,
                               body=question, status=200)

        from_date_unixtime = 1456876800 + time.timezone
        from_date = datetime.datetime(2016, 3, 2)

        payload = {
            'page': ['1'],
            'pagesize': ['1'],
            'order': ['desc'],
            'sort': ['activity'],
            'tagged': ['python'],
            'site': ['stackoverflow'],
            'key': ['aaa'],
            'filter': [QUESTIONS_FILTER],
            'min': [str(from_date_unixtime)]
        }

        client = StackExchangeClient(site="stackoverflow", tagged="python", token="aaa", max_questions=1)
        raw_questions = [questions for questions in client.get_questions(from_date=from_date)]

        self.assertEqual(len(raw_questions), 1)
        self.assertEqual(raw_questions[0], question)
        self.assertDictEqual(httpretty.last_request().querystring, payload)

    @httpretty.activate
    def test_get_questions_pagination(self):
        """Test question API call"""

        page_1 = read_file('data/stackexchange/stackexchange_question_page')
        page_2 = read_file('data/stackexchange/stackexchange_question_page_2')

        http_requests = []

        def request_callback(method, uri, headers):
            params = urllib.parse.parse_qs(urllib.parse.urlparse(uri).query)
            page = params.get('page')[0]
            body = page_1 if page == '1' else page_2

            http_requests.append(httpretty.last_request())

            return (200, headers, body)

        httpretty.register_uri(httpretty.GET,
                               STACKEXCHANGE_QUESTIONS_URL,
                               responses=[
                                   httpretty.Response(body=request_callback)
                               ])

        expected = [
            {
                'page': ['1'],
                'pagesize': ['1'],
                'order': ['desc'],
                'sort': ['activity'],
                'tagged': ['python'],
                'site': ['stackoverflow'],
                'key': ['aaa'],
                'filter': [QUESTIONS_FILTER]
            },
            {
                'page': ['2'],
                'pagesize': ['1'],
                'order': ['desc'],
                'sort': ['activity'],
                'tagged': ['python'],
                'site': ['stackoverflow'],
                'key': ['aaa'],
                'filter': [QUESTIONS_FILTER]
            }
        ]

        client = StackExchangeClient(site="stackoverflow",
                                     tagged="python",
                                     token="aaa", max_questions=1)
        raw_questions = [questions for questions in client.get_questions(from_date=None)]

        self.assertEqual(len(raw_questions), 2)
        self.assertEqual(raw_questions[0], page_1)
        self.assertEqual(raw_questions[1], page_2)

        self.assertEqual(len(http_requests), len(expected))

        for i in range(len(expected)):
            self.assertDictEqual(http_requests[i].querystring, expected[i])

    @httpretty.activate
    def test_backoff_waiting(self):
        """Test if the clients waits some seconds when backoff field is received"""

        backoff_page = read_file('data/stackexchange/stackexchange_question_backoff_page')
        question_page = read_file('data/stackexchange/stackexchange_question_page_2')

        def request_callback(method, uri, headers):
            params = urllib.parse.parse_qs(urllib.parse.urlparse(uri).query)
            page = params.get('page')[0]
            body = backoff_page if page == '1' else question_page
            return (200, headers, body)

        httpretty.register_uri(httpretty.GET,
                               STACKEXCHANGE_QUESTIONS_URL,
                               responses=[
                                   httpretty.Response(body=request_callback)
                               ])

        client = StackExchangeClient(site="stackoverflow",
                                     tagged="python",
                                     token="aaa", max_questions=1)

        before = time.time()
        raw_pages = [question for question in client.get_questions(from_date=None)]
        after = time.time()

        self.assertEqual(len(raw_pages), 2)

        # backoff value harcoded in the JSON
        diff = after - before
        self.assertGreaterEqual(diff, 0.2)

    def test_sanitize_for_archive(self):
        """Test whether the sanitize method works properly"""

        url = "http://example.com"
        headers = "headers-information"
        payload = {'order': 'desc',
                   'site': 'stackoverflow',
                   'sort': 'activity',
                   'pagesize': 1,
                   'key': 'aaa',
                   'filter': 'Bf*y*ByQD_upZqozgU6lXL_62USGOoV3)MFNgiHqHpmO_Y-jHR',
                   'page': 1,
                   'tagged': 'python'}

        s_url, s_headers, s_payload = StackExchangeClient.sanitize_for_archive(url, headers, copy.deepcopy(payload))
        payload.pop("key")

        self.assertEqual(url, s_url)
        self.assertEqual(headers, s_headers)
        self.assertEqual(payload, s_payload)


class TestStackExchangeCommand(unittest.TestCase):
    """StackExchangeCommand unit tests"""

    def test_backend_class(self):
        """Test if the backend class is StackExchange"""

        self.assertIs(StackExchangeCommand.BACKEND, StackExchange)

    def test_setup_cmd_parser(self):
        """Test if it parser object is correctly initialized"""

        parser = StackExchangeCommand.setup_cmd_parser()
        self.assertIsInstance(parser, BackendCommandArgumentParser)
        self.assertEqual(parser._backend, StackExchange)

        args = ['--site', 'stackoverflow',
                '--tagged', 'python',
                '--api-token', 'aaa',
                '--max-questions', '1',
                '--tag', 'test',
                '--no-archive',
                '--from-date', '1970-01-01']

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.site, 'stackoverflow')
        self.assertEqual(parsed_args.tagged, 'python')
        self.assertEqual(parsed_args.api_token, 'aaa')
        self.assertEqual(parsed_args.max_questions, 1)
        self.assertEqual(parsed_args.tag, 'test')
        self.assertTrue(parsed_args.no_archive)
        self.assertTrue(parsed_args.ssl_verify)
        self.assertEqual(parsed_args.from_date, DEFAULT_DATETIME)

        args = ['--site', 'stackoverflow',
                '--tagged', 'python',
                '--api-token', 'aaa',
                '--max-questions', '1',
                '--tag', 'test',
                '--no-ssl-verify',
                '--from-date', '1970-01-01']

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.site, 'stackoverflow')
        self.assertEqual(parsed_args.tagged, 'python')
        self.assertEqual(parsed_args.api_token, 'aaa')
        self.assertEqual(parsed_args.max_questions, 1)
        self.assertEqual(parsed_args.tag, 'test')
        self.assertFalse(parsed_args.ssl_verify)
        self.assertEqual(parsed_args.from_date, DEFAULT_DATETIME)


if __name__ == "__main__":
    unittest.main(warnings='ignore')
