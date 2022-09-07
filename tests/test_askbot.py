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
#     Alberto Martín <alberto.martin@bitergia.com>
#     Santiago Dueñas <sduenas@bitergia.com>
#     Stephan Barth <stephan.barth@gmail.com>
#     Valerio Cosentino <valcos@bitergia.com>
#     Miguel Ángel Fernández <mafesan@bitergia.com>
#     Harshal Mittal <harshalmittal4@gmail.com>
#

import datetime
import json
import os
import shutil
import unittest

import bs4
import httpretty
import requests

from perceval.backend import BackendCommandArgumentParser
from perceval.backends.core.askbot import (Askbot,
                                           AskbotClient,
                                           AskbotParser,
                                           AskbotCommand)

from perceval.utils import DEFAULT_DATETIME
from base import TestCaseBackendArchive

ASKBOT_URL = 'http://example.com'
ASKBOT_QUESTIONS_API_URL = ASKBOT_URL + '/api/v1/questions'
ASKBOT_QUESTION_2481_URL = ASKBOT_URL + '/question/2481'
ASKBOT_QUESTION_2488_URL = ASKBOT_URL + '/question/2488'
ASKBOT_QUESTION_24396_URL = ASKBOT_URL + '/question/24396'
ASKBOT_QUESTION_EMPTY_URL = ASKBOT_URL + '/question/0'
ASKBOT_COMMENTS_API_URL = ASKBOT_URL + '/s/post_comments'
ASKBOT_COMMENTS_API_URL_OLD = ASKBOT_URL + '/post_comments'


def read_file(filename, mode='r'):
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), filename), mode) as f:
        content = f.read()
    return content


class TestAskbotParser(unittest.TestCase):
    """Askbot parser tests"""

    def test_parse_question_container(self):
        """Test parse question container.

        This tests the full case when a question is, apart from
        created, edited by another user.
        """
        abparser = AskbotParser()

        page = read_file('data/askbot/html_26830_comments_question_openstack.html')

        html_question = [page]

        container_info = abparser.parse_question_container(html_question[0])

        expected_container = {
            'author': {
                'badges': 'Ignacio Mulas has 4 gold badges, 6 silver badges and 9 bronze badges',
                'reputation': '111',
                'username': 'Ignacio Mulas',
                'id': '5000'
            },
            'updated_by': {
                'website': 'http://maffulli.net/',
                'badges': 'smaffulli has 36 gold badges, 67 silver badges and 100 bronze badges',
                'reputation': '6898',
                'username': 'smaffulli',
                'id': '9'
            }
        }
        self.assertEqual(container_info, expected_container)

    def test_parse_answers(self):
        """Given a question, parse all the answers available (pagination included)."""

        abparser = AskbotParser()

        page = read_file('data/askbot/html_24396_multipage_openstack.html')

        html_question = [page]

        parsed_answers = abparser.parse_answers(html_question[0])
        self.assertEqual(len(parsed_answers), 10)

        self.assertEqual(parsed_answers[0]['id'], '24427')
        self.assertEqual(parsed_answers[0]['score'], '0')
        self.assertEqual(parsed_answers[0]['added_at'], '1372894082.0')

        self.assertEqual(parsed_answers[1]['id'], '24426')
        self.assertEqual(parsed_answers[1]['score'], '0')
        self.assertEqual(parsed_answers[1]['added_at'], '1372475606.0')

        self.assertEqual(parsed_answers[2]['id'], '24425')
        self.assertEqual(parsed_answers[2]['score'], '0')
        self.assertEqual(parsed_answers[2]['added_at'], '1365772426.0')

        self.assertEqual(parsed_answers[3]['id'], '24424')
        self.assertEqual(parsed_answers[3]['score'], '0')
        self.assertEqual(parsed_answers[3]['added_at'], '1365766666.0')

        self.assertEqual(parsed_answers[4]['id'], '24423')
        self.assertEqual(parsed_answers[4]['score'], '0')
        self.assertEqual(parsed_answers[4]['added_at'], '1365762818.0')

        self.assertEqual(parsed_answers[5]['id'], '24419')
        self.assertEqual(parsed_answers[5]['score'], '0')
        self.assertEqual(parsed_answers[5]['added_at'], '1365715423.0')

        self.assertEqual(parsed_answers[6]['id'], '24418')
        self.assertEqual(parsed_answers[6]['score'], '0')
        self.assertEqual(parsed_answers[6]['added_at'], '1365687337.0')

        self.assertEqual(parsed_answers[7]['id'], '24417')
        self.assertEqual(parsed_answers[7]['score'], '0')
        self.assertEqual(parsed_answers[7]['added_at'], '1364970027.0')

        self.assertEqual(parsed_answers[8]['id'], '24416')
        self.assertEqual(parsed_answers[8]['score'], '0')
        self.assertEqual(parsed_answers[8]['added_at'], '1364965468.0')

        self.assertEqual(parsed_answers[9]['id'], '24414')
        self.assertEqual(parsed_answers[9]['score'], '0')
        self.assertEqual(parsed_answers[9]['added_at'], '1364453025.0')

    def test_parse_number_of_html_pages(self):
        """Get the number of html needed to retrieve all the answers of a given page."""

        page = read_file('data/askbot/html_24396_multipage_openstack.html')

        html_question = [page]

        pages = AskbotParser.parse_number_of_html_pages(html_question[0])
        self.assertEqual(pages, 4)

    def test_parse_user_info(self):
        """Test user info parsing.

        User info can be a wiki post or a user. When a user, some additional information
        can be added like country or website when available.
        """

        page = read_file('data/askbot/askbot_question_multipage_1.html')

        html_question = [page]

        bs_question = bs4.BeautifulSoup(html_question[0], "html.parser")
        # Test the user_info from the question which is a wiki post and not updated
        question = bs_question.select("div.js-question")
        container = question[0].select("div.post-update-info")
        created = container[0]
        author = AskbotParser.parse_user_info(created)
        self.assertEqual(author, {})

        # Test the user_info from an item with country and website
        page = read_file('data/askbot/html_country_and_website.html')
        html_question = [page]
        bs_question = bs4.BeautifulSoup(html_question[0], "html.parser")
        bs_answers = bs_question.select("div.answer")
        body = bs_answers[0].select("div.post-body")
        update_info = body[0].select("div.post-update-info")
        author = AskbotParser.parse_user_info(update_info[0])
        self.assertEqual(author['id'], "1")
        self.assertEqual(author['badges'], "Evgeny has 56 gold badges, 98 silver badges and 212 bronze badges")
        self.assertEqual(author['reputation'], "14023")
        self.assertEqual(author['username'], "Evgeny")
        self.assertEqual(author['website'], "http://askbot.org/")
        self.assertEqual(author['country'], "Chile")


class TestAskbotClient(unittest.TestCase):
    """Askbot client unit tests.

    These tests do not check the body of the response, only if the call
    was well formed and if a response was obtained.
    """
    def test_init(self):
        """Test initialization parameters"""

        ab = AskbotClient(ASKBOT_URL)

        self.assertEqual(ab.base_url, ASKBOT_URL)
        self.assertTrue(ab.ssl_verify)

        ab = AskbotClient(ASKBOT_URL, ssl_verify=False)

        self.assertEqual(ab.base_url, ASKBOT_URL)
        self.assertFalse(ab.ssl_verify)

    @httpretty.activate
    def test_get_api_questions(self):
        """Test if API Questions call works"""

        body = read_file('data/askbot/askbot_api_questions.json')

        httpretty.register_uri(httpretty.GET,
                               ASKBOT_QUESTIONS_API_URL,
                               body=body, status=200)

        client = AskbotClient(ASKBOT_URL)

        result = next(client.get_api_questions('api/v1/questions'))

        self.assertEqual(result, json.loads(body))

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
        """Test if HTML Questions call works."""

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
        """Test if HTML Questions multipage call works."""

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
        """Test if HTML Questions call (non-existing question) works."""

        body = read_file('data/askbot/askbot_question_empty.html')

        httpretty.register_uri(httpretty.GET,
                               ASKBOT_QUESTION_EMPTY_URL,
                               body=body, status=404)

        client = AskbotClient(ASKBOT_URL)

        self.assertRaises(requests.exceptions.HTTPError, client.get_html_question, 0)

        req = httpretty.last_request()

        self.assertEqual(req.method, 'GET')
        self.assertRegex(req.path, '/question/0')

    @httpretty.activate
    def test_403_status_get_comments(self):
        """Test whether, when fetching comments, an exception is thrown if HTTPError is not 403"""

        httpretty.register_uri(httpretty.GET,
                               ASKBOT_COMMENTS_API_URL,
                               body="", status=403)

        client = AskbotClient(ASKBOT_URL)

        with self.assertRaises(requests.exceptions.HTTPError):
            _ = client.get_comments(5)

    @httpretty.activate
    def test_500_status_get_comments(self):
        """Test whether, when fetching comments, an exception is thrown if HTTPError is not 503"""

        httpretty.register_uri(httpretty.GET,
                               ASKBOT_COMMENTS_API_URL,
                               body="", status=500)

        client = AskbotClient(ASKBOT_URL)
        self.assertEqual(client.get_comments(5), '[]')

    @httpretty.activate
    def test_get_comments(self):
        """Test if comments call works"""

        body = read_file('data/askbot/askbot_2481_multicomments.json')

        httpretty.register_uri(httpretty.GET,
                               ASKBOT_COMMENTS_API_URL,
                               body=body, status=200)

        client = AskbotClient(ASKBOT_URL)

        result = client.get_comments(17)

        self.assertEqual(result, body)

        expected = {
            'post_id': ['17'],
            'post_type': ['answer'],
            'avatar_size': ['0']
        }

        req = httpretty.last_request()

        self.assertEqual(req.method, 'GET')
        self.assertRegex(req.path, 's/post_comments')
        self.assertDictEqual(req.querystring, expected)

    @httpretty.activate
    def test_get_comments_old_url(self):
        """Test if commits call works with the old URL schema"""

        body = read_file('data/askbot/askbot_2481_multicomments.json')

        httpretty.register_uri(httpretty.GET,
                               ASKBOT_COMMENTS_API_URL,
                               body='', status=404)
        httpretty.register_uri(httpretty.GET,
                               ASKBOT_COMMENTS_API_URL_OLD,
                               body=body, status=200)

        client = AskbotClient(ASKBOT_URL)

        result = client.get_comments(17)

        self.assertEqual(result, body)

        expected = {
            'post_id': ['17'],
            'post_type': ['answer'],
            'avatar_size': ['0']
        }

        reqs = httpretty.httpretty.latest_requests

        self.assertEqual(len(reqs), 2)
        self.assertEqual(reqs[0].method, 'GET')
        self.assertRegex(reqs[0].path, '/s/post_comments')
        self.assertDictEqual(reqs[0].querystring, expected)
        self.assertEqual(reqs[1].method, 'GET')
        self.assertRegex(reqs[1].path, '/post_comments')
        self.assertDictEqual(reqs[1].querystring, expected)


class TestAskbotBackend(unittest.TestCase):
    """Askbot backend tests."""

    def test_initialization(self):
        """Test whether attributes are initializated."""

        ab = Askbot(ASKBOT_URL, tag='test')

        self.assertEqual(ab.url, ASKBOT_URL)
        self.assertEqual(ab.tag, 'test')
        self.assertIsNone(ab.client, None)
        self.assertTrue(ab.ssl_verify)

        # When tag is empty or None it will be set to
        # the value in url
        ab = Askbot(ASKBOT_URL)
        self.assertEqual(ab.url, ASKBOT_URL)
        self.assertEqual(ab.tag, ASKBOT_URL)

        ab = Askbot(ASKBOT_URL, tag='', ssl_verify=False)
        self.assertEqual(ab.url, ASKBOT_URL)
        self.assertEqual(ab.tag, ASKBOT_URL)
        self.assertFalse(ab.ssl_verify)

    @httpretty.activate
    def test_too_many_redirects(self):
        """Test whether a too many redirects error is properly handled"""

        question_api_1 = read_file('data/askbot/askbot_api_questions.json')
        question_api_2 = read_file('data/askbot/askbot_api_questions_2.json')
        question_html_2 = read_file('data/askbot/askbot_question_multipage_1.html')
        question_html_2_2 = read_file('data/askbot/askbot_question_multipage_2.html')
        comments = read_file('data/askbot/askbot_2481_multicomments.json')

        httpretty.register_uri(httpretty.GET,
                               ASKBOT_QUESTIONS_API_URL,
                               body=question_api_1, status=200)
        httpretty.register_uri(httpretty.GET,
                               ASKBOT_QUESTIONS_API_URL,
                               body=question_api_2, status=200)

        httpretty.register_uri(httpretty.GET,
                               ASKBOT_QUESTION_2481_URL,
                               location=ASKBOT_QUESTION_2481_URL, status=301)

        httpretty.register_uri(httpretty.GET,
                               ASKBOT_QUESTION_2488_URL,
                               body=question_html_2, status=200)

        httpretty.register_uri(httpretty.GET,
                               ASKBOT_QUESTION_2488_URL,
                               body=question_html_2_2, status=200)

        httpretty.register_uri(httpretty.GET,
                               ASKBOT_COMMENTS_API_URL,
                               body=comments, status=200)

        backend = Askbot(ASKBOT_URL)
        questions = [question for question in backend.fetch()]

        self.assertEqual(len(questions), 1)

    @httpretty.activate
    def test_fetch(self):
        """Test whether a list of questions is returned"""

        question_api_1 = read_file('data/askbot/askbot_api_questions.json')
        question_api_2 = read_file('data/askbot/askbot_api_questions_2.json')
        question_html_1 = read_file('data/askbot/askbot_question.html')
        question_html_2 = read_file('data/askbot/askbot_question_multipage_1.html')
        question_html_2_2 = read_file('data/askbot/askbot_question_multipage_2.html')
        comments = read_file('data/askbot/askbot_2481_multicomments.json')

        httpretty.register_uri(httpretty.GET,
                               ASKBOT_QUESTIONS_API_URL,
                               body=question_api_1, status=200)
        httpretty.register_uri(httpretty.GET,
                               ASKBOT_QUESTIONS_API_URL,
                               body=question_api_2, status=200)

        httpretty.register_uri(httpretty.GET,
                               ASKBOT_QUESTION_2481_URL,
                               body=question_html_1, status=200)

        httpretty.register_uri(httpretty.GET,
                               ASKBOT_QUESTION_2488_URL,
                               body=question_html_2, status=200)

        httpretty.register_uri(httpretty.GET,
                               ASKBOT_QUESTION_2488_URL,
                               body=question_html_2_2, status=200)

        httpretty.register_uri(httpretty.GET,
                               ASKBOT_COMMENTS_API_URL,
                               body=comments, status=200)

        backend = Askbot(ASKBOT_URL)

        questions = [question for question in backend.fetch()]

        json_comments = json.loads(comments)

        self.assertEqual(len(questions[0]['data']['answers']), len(questions[0]['data']['answer_ids']))
        self.assertTrue(questions[0]['data']['answers'][0]['accepted'])
        self.assertEqual(questions[0]['tag'], 'http://example.com')
        self.assertEqual(questions[0]['uuid'], '3fb5f945a0dd223c60218a98ad35bad6043f9f5f')
        self.assertEqual(questions[0]['updated_on'], 1408116902.0)
        self.assertEqual(questions[0]['data']['id'], 2488)
        self.assertEqual(questions[0]['category'], backend.metadata_category(questions[0]))
        self.assertEqual(questions[0]['data']['comments'][0], json_comments[0])
        self.assertEqual(len(questions[0]['data']['comments']), len(json_comments))
        self.assertEqual(len(questions[1]['data']['answers']), len(questions[1]['data']['answer_ids']))
        self.assertFalse(questions[1]['data']['answers'][0]['accepted'])
        self.assertEqual(questions[1]['tag'], 'http://example.com')
        self.assertEqual(questions[1]['uuid'], 'ecc1320265e400edb28700cc3d02efc6d76410be')
        self.assertEqual(questions[1]['updated_on'], 1349928216.0)
        self.assertEqual(questions[1]['data']['id'], 2481)
        self.assertEqual(questions[1]['category'], backend.metadata_category(questions[1]))

    @httpretty.activate
    def test_search_fields(self):
        """Test whether the search_fields is properly set"""

        question_api_1 = read_file('data/askbot/askbot_api_questions.json')
        question_api_2 = read_file('data/askbot/askbot_api_questions_2.json')
        question_html_1 = read_file('data/askbot/askbot_question.html')
        question_html_2 = read_file('data/askbot/askbot_question_multipage_1.html')
        question_html_2_2 = read_file('data/askbot/askbot_question_multipage_2.html')
        comments = read_file('data/askbot/askbot_2481_multicomments.json')

        httpretty.register_uri(httpretty.GET,
                               ASKBOT_QUESTIONS_API_URL,
                               body=question_api_1, status=200)
        httpretty.register_uri(httpretty.GET,
                               ASKBOT_QUESTIONS_API_URL,
                               body=question_api_2, status=200)

        httpretty.register_uri(httpretty.GET,
                               ASKBOT_QUESTION_2481_URL,
                               body=question_html_1, status=200)

        httpretty.register_uri(httpretty.GET,
                               ASKBOT_QUESTION_2488_URL,
                               body=question_html_2, status=200)

        httpretty.register_uri(httpretty.GET,
                               ASKBOT_QUESTION_2488_URL,
                               body=question_html_2_2, status=200)

        httpretty.register_uri(httpretty.GET,
                               ASKBOT_COMMENTS_API_URL,
                               body=comments, status=200)

        backend = Askbot(ASKBOT_URL)

        questions = [question for question in backend.fetch()]

        question = questions[0]
        self.assertEqual(backend.metadata_id(question['data']), question['search_fields']['item_id'])
        self.assertListEqual(question['data']['tags'], ['askbot-sites'])
        self.assertEqual(question['data']['tags'], question['search_fields']['tags'])

        question = questions[1]
        self.assertEqual(backend.metadata_id(question['data']), question['search_fields']['item_id'])
        self.assertListEqual(question['data']['tags'], ['feature-request', 'messaging'])
        self.assertEqual(question['data']['tags'], question['search_fields']['tags'])

    @httpretty.activate
    def test_fetch_from_date(self):
        """Test whether a list of questions is returned from a given date."""

        question_api_1 = read_file('data/askbot/askbot_api_questions.json')
        question_api_2 = read_file('data/askbot/askbot_api_questions_2.json')
        question_html_1 = read_file('data/askbot/askbot_question.html')
        question_html_2 = read_file('data/askbot/askbot_question_multipage_1.html')
        question_html_2_2 = read_file('data/askbot/askbot_question_multipage_2.html')
        comments = read_file('data/askbot/askbot_2481_multicomments.json')

        httpretty.register_uri(httpretty.GET,
                               ASKBOT_QUESTIONS_API_URL,
                               body=question_api_1, status=200)
        httpretty.register_uri(httpretty.GET,
                               ASKBOT_QUESTIONS_API_URL,
                               body=question_api_2, status=200)

        httpretty.register_uri(httpretty.GET,
                               ASKBOT_QUESTION_2481_URL,
                               body=question_html_1, status=200)

        httpretty.register_uri(httpretty.GET,
                               ASKBOT_QUESTION_2488_URL,
                               body=question_html_2, status=200)

        httpretty.register_uri(httpretty.GET,
                               ASKBOT_QUESTION_2488_URL,
                               body=question_html_2_2, status=200)

        httpretty.register_uri(httpretty.GET,
                               ASKBOT_COMMENTS_API_URL,
                               body=comments, status=200)

        backend = Askbot(ASKBOT_URL)

        from_date = datetime.datetime(2013, 1, 1)

        questions = [question for question in backend.fetch(from_date=from_date)]

        self.assertEqual(questions[0]['tag'], 'http://example.com')
        self.assertEqual(questions[0]['uuid'], '3fb5f945a0dd223c60218a98ad35bad6043f9f5f')
        self.assertEqual(questions[0]['updated_on'], 1408116902.0)
        self.assertEqual(questions[0]['data']['id'], 2488)
        self.assertEqual(len(questions), 1)

    def test_has_resuming(self):
        """Test if it returns True when has_resuming is called."""

        self.assertEqual(Askbot.has_resuming(), True)

    def test_has_archiving(self):
        """Test if it returns True when has_resuming is called"""

        self.assertEqual(Askbot.has_archiving(), True)


class TestAskbotBackendArchive(TestCaseBackendArchive):
    """Askbot backend tests using an archive"""

    def setUp(self):
        super().setUp()
        self.backend_write_archive = Askbot(ASKBOT_URL, archive=self.archive)
        self.backend_read_archive = Askbot(ASKBOT_URL, archive=self.archive)

    def tearDown(self):
        shutil.rmtree(self.test_path)

    @httpretty.activate
    def test_fetch_from_archive(self):
        """Test whether a list of questions is returned from the archive"""

        question_api_1 = read_file('data/askbot/askbot_api_questions.json')
        question_api_2 = read_file('data/askbot/askbot_api_questions_2.json')
        question_html_1 = read_file('data/askbot/askbot_question.html')
        question_html_2 = read_file('data/askbot/askbot_question_multipage_1.html')
        question_html_2_2 = read_file('data/askbot/askbot_question_multipage_2.html')
        comments = read_file('data/askbot/askbot_2481_multicomments.json')

        httpretty.register_uri(httpretty.GET,
                               ASKBOT_QUESTIONS_API_URL,
                               body=question_api_1, status=200)
        httpretty.register_uri(httpretty.GET,
                               ASKBOT_QUESTIONS_API_URL,
                               body=question_api_2, status=200)

        httpretty.register_uri(httpretty.GET,
                               ASKBOT_QUESTION_2481_URL,
                               body=question_html_1, status=200)

        httpretty.register_uri(httpretty.GET,
                               ASKBOT_QUESTION_2488_URL,
                               body=question_html_2, status=200)

        httpretty.register_uri(httpretty.GET,
                               ASKBOT_QUESTION_2488_URL,
                               body=question_html_2_2, status=200)

        httpretty.register_uri(httpretty.GET,
                               ASKBOT_COMMENTS_API_URL,
                               body=comments, status=200)

        self._test_fetch_from_archive(from_date=None)

    @httpretty.activate
    def test_fetch_from_date_from_archive(self):
        """Test whether a list of questions is returned from a given date from the archive."""

        question_api_1 = read_file('data/askbot/askbot_api_questions.json')
        question_api_2 = read_file('data/askbot/askbot_api_questions_2.json')
        question_html_1 = read_file('data/askbot/askbot_question.html')
        question_html_2 = read_file('data/askbot/askbot_question_multipage_1.html')
        question_html_2_2 = read_file('data/askbot/askbot_question_multipage_2.html')
        comments = read_file('data/askbot/askbot_2481_multicomments.json')

        httpretty.register_uri(httpretty.GET,
                               ASKBOT_QUESTIONS_API_URL,
                               body=question_api_1, status=200)
        httpretty.register_uri(httpretty.GET,
                               ASKBOT_QUESTIONS_API_URL,
                               body=question_api_2, status=200)

        httpretty.register_uri(httpretty.GET,
                               ASKBOT_QUESTION_2481_URL,
                               body=question_html_1, status=200)

        httpretty.register_uri(httpretty.GET,
                               ASKBOT_QUESTION_2488_URL,
                               body=question_html_2, status=200)

        httpretty.register_uri(httpretty.GET,
                               ASKBOT_QUESTION_2488_URL,
                               body=question_html_2_2, status=200)

        httpretty.register_uri(httpretty.GET,
                               ASKBOT_COMMENTS_API_URL,
                               body=comments, status=200)

        from_date = datetime.datetime(2013, 1, 1)
        self._test_fetch_from_archive(from_date=from_date)


class TestAskbotCommand(unittest.TestCase):
    """Tests for AskbotCommand class."""

    def test_backend_class(self):
        """Test if the backend class is Askbot"""

        self.assertIs(AskbotCommand.BACKEND, Askbot)

    def test_setup_cmd_parser(self):
        """Test if it parser object is correctly initialized"""

        parser = AskbotCommand.setup_cmd_parser()
        self.assertIsInstance(parser, BackendCommandArgumentParser)
        self.assertEqual(parser._backend, Askbot)

        args = ['--tag', 'test',
                '--from-date', '1970-01-01',
                '--no-archive',
                ASKBOT_URL]

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.url, ASKBOT_URL)
        self.assertEqual(parsed_args.tag, 'test')
        self.assertEqual(parsed_args.from_date, DEFAULT_DATETIME)
        self.assertTrue(parsed_args.no_archive)
        self.assertTrue(parsed_args.ssl_verify)

        args = ['--tag', 'test',
                '--from-date', '1970-01-01',
                '--no-ssl-verify',
                ASKBOT_URL]

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.url, ASKBOT_URL)
        self.assertEqual(parsed_args.tag, 'test')
        self.assertEqual(parsed_args.from_date, DEFAULT_DATETIME)
        self.assertFalse(parsed_args.ssl_verify)


if __name__ == "__main__":
    unittest.main(warnings='ignore')
