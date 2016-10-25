#!/usr/bin/env python3
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
#     Alvaro del Castillo <acs@bitergia.com>
#

import argparse
import json
import shutil
import sys
import tempfile
import unittest

import requests
import httpretty


if not '..' in sys.path:
    sys.path.insert(0, '..')

from perceval.cache import Cache
from perceval.errors import CacheError
from perceval.backends.kitsune import Kitsune, KitsuneCommand, KitsuneClient
from perceval.utils import str_to_datetime


KITSUNE_SERVER_URL = 'http://example.com'
KITSUNE_API = KITSUNE_SERVER_URL + '/api/2/'
KITSUNE_API_QUESTION = KITSUNE_SERVER_URL + '/api/2/question/'
KITSUNE_API_ANSWER = KITSUNE_SERVER_URL + '/api/2/answer/'

KITSUNE_SERVER_FAIL_PAGE = 69
KITSUNE_ITEMS_PER_PAGE = 20

def read_file(filename, mode='r'):
    with open(filename, mode) as f:
        content = f.read()
    return content


class HTTPServer():

    requests_http = []  # requests done to the server

    @classmethod
    def routes(cls, empty=False):
        """Configure in http the routes to be served"""
        mozilla_questions_1 = read_file('data/kitsune_questions_1_2.json')
        mozilla_questions_2 = read_file('data/kitsune_questions_2_2.json')
        mozilla_questions_empty = read_file('data/kitsune_questions_empty.json')
        mozilla_question_answers_1 = read_file('data/kitsune_question_answers.json')
        mozilla_question_answers_empty = read_file('data/kitsune_question_answers_empy.json')

        if empty:
            mozilla_questions_1 = mozilla_questions_empty

        def request_callback(method, uri, headers):
            page = uri.split("page=")[1].split("&")[0]
            if page == "1":
                if 'question/' in uri:
                    body = mozilla_questions_1
                else:
                    question = uri.split("question=")[1].split("&")[0]
                    body = mozilla_question_answers_1
                    body_json = json.loads(body)['results']
                    if body_json[0]['question'] != int(question):
                        # The answers are not for this question
                        body = mozilla_question_answers_empty
            elif page == "2":
                if 'question/' in uri:
                    body = mozilla_questions_2
                else:
                    body = mozilla_question_answers_1
            elif page == str(KITSUNE_SERVER_FAIL_PAGE):
                # To tests for Internal Server Error
                return (500, headers, '')
            elif page == str(KITSUNE_SERVER_FAIL_PAGE + 1):
                # Next page to the server fail returns questions
                return (200, headers, mozilla_questions_2)
            else:
                return (404, headers, '')

            HTTPServer.requests_http.append(httpretty.last_request())

            return (200, headers, body)

        httpretty.register_uri(httpretty.GET,
                               KITSUNE_API_QUESTION,
                               responses=[
                                    httpretty.Response(body=request_callback)
                               ])
        httpretty.register_uri(httpretty.GET,
                               KITSUNE_API_ANSWER,
                               responses=[
                                    httpretty.Response(body=request_callback)
                               ])


class TestKitsuneBackend(unittest.TestCase):
    """Kitsune backend tests"""

    def test_initialization(self):
        """Test whether attributes are initializated"""

        kitsune = Kitsune(KITSUNE_SERVER_URL, tag='test')

        self.assertEqual(kitsune.url, KITSUNE_SERVER_URL)
        self.assertEqual(kitsune.origin, KITSUNE_SERVER_URL)
        self.assertEqual(kitsune.tag, 'test')
        self.assertIsInstance(kitsune.client, KitsuneClient)

        # When tag is empty or None it will be set to
        # the value in url
        kitsune = Kitsune(KITSUNE_SERVER_URL)
        self.assertEqual(kitsune.url, KITSUNE_SERVER_URL)
        self.assertEqual(kitsune.origin, KITSUNE_SERVER_URL)
        self.assertEqual(kitsune.tag, KITSUNE_SERVER_URL)

        kitsune = Kitsune(KITSUNE_SERVER_URL, tag='')
        self.assertEqual(kitsune.url, KITSUNE_SERVER_URL)
        self.assertEqual(kitsune.origin, KITSUNE_SERVER_URL)
        self.assertEqual(kitsune.tag, KITSUNE_SERVER_URL)

    def test_has_caching(self):
        """Test if it returns True when has_caching is called"""

        self.assertEqual(Kitsune.has_caching(), True)

    def test_has_resuming(self):
        """Test if it returns True when has_resuming is called"""

        self.assertEqual(Kitsune.has_resuming(), True)

    def __check_questions_contents(self, questions):
        self.assertEqual(questions[0]['data']['num_votes'], 2)
        self.assertEqual(questions[0]['data']['num_answers'], 0)
        self.assertEqual(questions[0]['data']['locale'], 'en-US')
        self.assertEqual(questions[0]['origin'], KITSUNE_SERVER_URL)
        self.assertEqual(questions[0]['uuid'], '8fa01e2aadf37c6f2fa300ce529fd1a23feac333')
        self.assertEqual(questions[0]['updated_on'], 1467798846.0)
        self.assertEqual(questions[0]['offset'], 0)
        self.assertEqual(questions[0]['category'], 'question')
        self.assertEqual(questions[0]['tag'], KITSUNE_SERVER_URL)

        if len(questions) > 1:
            self.assertEqual(questions[1]['data']['num_votes'], 1)
            self.assertEqual(questions[1]['data']['num_answers'], 0)
            self.assertEqual(questions[1]['data']['locale'], 'es')
            self.assertEqual(questions[1]['origin'], KITSUNE_SERVER_URL)
            self.assertEqual(questions[1]['uuid'], '7a3fbfb33cfaaa32b2f121994faf019a054a9a06')
            self.assertEqual(questions[1]['updated_on'], 1467798439.0)
            self.assertEqual(questions[1]['offset'], 1)
            self.assertEqual(questions[1]['category'], 'question')
            self.assertEqual(questions[1]['tag'], KITSUNE_SERVER_URL)

    @httpretty.activate
    def test_fetch(self):
        """Test whether the questions are returned"""

        HTTPServer.routes()

        # Test fetch questions with their reviews
        kitsune = Kitsune(KITSUNE_SERVER_URL)

        questions = [question for question in kitsune.fetch()]

        self.assertEqual(len(questions), 4)

        self.__check_questions_contents(questions)

    @httpretty.activate
    def test_fetch_offset(self):
        """Test whether the questions are returned offset"""

        HTTPServer.routes()

        # Test fetch questions with their reviews
        kitsune = Kitsune(KITSUNE_SERVER_URL)

        # Get all questions
        offset = 0
        questions = [question for question in kitsune.fetch(offset=offset)]
        self.assertEqual(len(questions), 4)
        self.__check_questions_contents(questions)

        # 4 total questions minus 2, 2 questions returned
        offset = 2
        questions = [question for question in kitsune.fetch(offset=offset)]
        self.assertEqual(len(questions), 2)
        self.assertEqual(questions[0]['offset'], 2)
        self.assertEqual(questions[1]['offset'], 3)

        offset = 4
        questions = [question for question in kitsune.fetch(offset=offset)]
        self.assertEqual(len(questions), 0)

        # Get no questions: we have two pages
        offset = KitsuneClient.ITEMS_PER_PAGE*2
        with self.assertRaises(requests.exceptions.HTTPError):
            questions = [question for question in kitsune.fetch(offset=offset)]
            self.assertEqual(len(questions), 0)

    @httpretty.activate
    def test_fetch_empty(self):
        """Test whether it works when no jobs are fetched"""

        HTTPServer.routes(empty=True)

        kitsune = Kitsune(KITSUNE_SERVER_URL)
        questions = [event for event in kitsune.fetch()]

        self.assertEqual(len(questions), 0)

    @httpretty.activate
    def test_fetch_server_error(self):
        """Test whether it works when the server fails"""

        HTTPServer.routes(empty=True)

        kitsune = Kitsune(KITSUNE_SERVER_URL)
        offset = (KITSUNE_SERVER_FAIL_PAGE - 1) * KITSUNE_ITEMS_PER_PAGE
        questions = [event for event in kitsune.fetch(offset=offset)]
        # After the failing page there are a page with 2 questions
        self.assertEqual(len(questions), 2)


class TestKitsuneBackendCache(unittest.TestCase):
    """Kitsune backend tests using a cache"""

    def setUp(self):
        self.tmp_path = tempfile.mkdtemp(prefix='perceval_')

    def tearDown(self):
        shutil.rmtree(self.tmp_path)

    @httpretty.activate
    def test_fetch_from_cache(self):
        """Test whether the cache works"""

        HTTPServer.routes()

        # First, we fetch the questions from the server, storing them
        # in a cache
        cache = Cache(self.tmp_path)
        kitsune = Kitsune(KITSUNE_SERVER_URL, cache=cache)

        questions = [event for event in kitsune.fetch()]

        requests_done = len(HTTPServer.requests_http)

        # Now, we get the questions from the cache.
        # The contents should be the same and there won't be
        # any new request to the server
        cached_questions = [event for event in kitsune.fetch_from_cache()]
        # No new requests to the server
        self.assertEqual(len(HTTPServer.requests_http), requests_done)
        # The contents should be the same
        self.assertEqual(len(cached_questions), len(questions))
        for i in range(0,len(questions)):
            self.assertDictEqual(cached_questions[i]['data'], questions[i]['data'])

    def test_fetch_from_empty_cache(self):
        """Test if there are not any questions returned when the cache is empty"""

        cache = Cache(self.tmp_path)
        kitsune = Kitsune(KITSUNE_SERVER_URL, cache=cache)
        cached_questions = [event for event in kitsune.fetch_from_cache()]
        self.assertEqual(len(cached_questions), 0)

    def test_fetch_from_non_set_cache(self):
        """Test if a error is raised when the cache was not set"""

        kitsune = Kitsune(KITSUNE_SERVER_URL)

        with self.assertRaises(CacheError):
            _ = [event for event in kitsune.fetch_from_cache()]


class TestKitsuneCommand(unittest.TestCase):

    @httpretty.activate
    def test_parsing_on_init(self):
        """Test if the class is initialized"""

        args = ['--tag', 'test', KITSUNE_SERVER_URL]

        cmd = KitsuneCommand(*args)
        self.assertIsInstance(cmd.parsed_args, argparse.Namespace)
        self.assertEqual(cmd.parsed_args.url, KITSUNE_SERVER_URL)
        self.assertEqual(cmd.parsed_args.tag, 'test')
        self.assertIsInstance(cmd.backend, Kitsune)

    def test_argument_parser(self):
        """Test if it returns a argument parser object"""

        parser = KitsuneCommand.create_argument_parser()
        self.assertIsInstance(parser, argparse.ArgumentParser)


class TestKitsuneClient(unittest.TestCase):
    """Kitsune API client tests

    These tests not check the body of the response, only if the call
    was well formed and if a response was obtained. Due to this, take
    into account that the body returned on each request might not
    match with the parameters from the request.
    """
    @httpretty.activate
    def test_init(self):
        """Test initialization"""
        client = KitsuneClient(KITSUNE_SERVER_URL)

    @httpretty.activate
    def test_get_questions(self):
        """Test get_questions API call"""

        HTTPServer.routes()

        # Set up a mock HTTP server
        body = read_file('data/kitsune_questions_1_2.json')
        client = KitsuneClient(KITSUNE_SERVER_URL)
        response = next(client.get_questions()) # first group of questions
        req = HTTPServer.requests_http[-1]
        self.assertEqual(response, body)
        self.assertEqual(req.method, 'GET')
        self.assertRegex(req.path, '/api/2/question/')
        # Check request params
        expected = {
                    'page' : ['1'],
                    'ordering' : ['updated'],
                    }
        self.assertDictEqual(req.querystring, expected)

    @httpretty.activate
    def test_get_question_answers(self):
        """Test get_question_answers API call"""

        HTTPServer.routes()

        # Set up a mock HTTP server
        body = read_file('data/kitsune_question_answers.json')
        client = KitsuneClient(KITSUNE_SERVER_URL)
        question_id = 1129949
        response = next(client.get_question_answers(question_id))
        req = HTTPServer.requests_http[-1]
        self.assertEqual(response, body)
        self.assertEqual(req.method, 'GET')
        self.assertRegex(req.path, '/api/2/answer/')
        # Check request params
        expected = {
                    'question': ['1129949'],
                    'page' : ['1'],
                    'ordering' : ['updated']
                    }
        self.assertDictEqual(req.querystring, expected)

if __name__ == "__main__":
    unittest.main(warnings='ignore')
