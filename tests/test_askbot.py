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
import bs4
import json

import httpretty

if not '..' in sys.path:
    sys.path.insert(0, '..')

from perceval.backends.askbot import AskbotClient, AskbotParser

ASKBOT_URL = 'http://example.com'
ASKBOT_QUESTIONS_API_URL = ASKBOT_URL + '/api/v1/questions'
ASKBOT_QUESTION_2481_URL = ASKBOT_URL + '/question/2481'
ASKBOT_QUESTION_2488_URL = ASKBOT_URL + '/question/2488'
ASKBOT_QUESTION_EMPTY_URL = ASKBOT_URL + '/question/0'


def read_file(filename, mode='r'):
    with open(filename, mode) as f:
        content = f.read()
    return content


class TestAskbotParser(unittest.TestCase):
    "Askbot parser tests"
    def test_parse_question(self):
        """Test question parser. This test covers the case when a question contains more than
        ten answers and pagination is needed."""
        abparser = AskbotParser()

        page_1 = read_file('data/askbot/html_24396_multipage_openstack.html')
        page_2 = read_file('data/askbot/html_24396_multipage_2_openstack.html')
        page_3 = read_file('data/askbot/html_24396_multipage_3_openstack.html')
        page_4 = read_file('data/askbot/html_24396_multipage_4_openstack.html')

        question_api = json.loads(read_file('data/askbot/api_24396_openstack.json'))

        html_question = [page_1, page_2, page_3, page_4]

        parsed_question = abparser.parse_question(question_api, html_question)

        self.assertEqual(len(parsed_question['answers']), len(parsed_question['answer_ids']))

        self.assertIsNotNone(parsed_question['added_at'])
        self.assertIsNotNone(parsed_question['answer_count'])
        self.assertIsNotNone(parsed_question['author'])
        self.assertIsNotNone(parsed_question['id'])
        self.assertIsNotNone(parsed_question['last_activity_at'])
        self.assertIsNotNone(parsed_question['last_activity_by'])
        self.assertIsNotNone(parsed_question['score'])
        self.assertIsNotNone(parsed_question['summary'])
        self.assertIsNotNone(parsed_question['tags'])
        self.assertIsNotNone(parsed_question['title'])
        self.assertIsNotNone(parsed_question['url'])
        self.assertIsNotNone(parsed_question['view_count'])

    def test_parse_question_container(self):
        """Test parse question container. This tests the full case when a question is, apart from
        created, edited by another user"""
        abparser = AskbotParser()

        page = read_file('data/askbot/html_26830_comments_question_openstack.html')

        html_question = [page]

        bs_question = bs4.BeautifulSoup(html_question[0], "html.parser")

        container_info = abparser.parse_question_container(bs_question)

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

    def test_parse_question_comments(self):
        """Test comments retrieved from questions contains all its elements"""
        abparser = AskbotParser()

        page = read_file('data/askbot/html_26830_comments_question_openstack.html')

        html_question = [page]

        bs_question = bs4.BeautifulSoup(html_question[0], "html.parser")
        parsed_comments = abparser.parse_question_comments(bs_question)
        self.assertEqual(len(parsed_comments), 3)
        for parsed_comment in parsed_comments:
            self.assertIsNotNone(parsed_comment['id'])
            self.assertIsNotNone(parsed_comment['score'])
            self.assertIsNotNone(parsed_comment['summary'])
            self.assertIsNotNone(parsed_comment['author'])
            self.assertIsNotNone(parsed_comment['added_at'])

    def test_parse_answers(self):
        """Given a question, parse all the answers available (pagination included)"""
        abparser = AskbotParser()

        page = read_file('data/askbot/html_24396_multipage_openstack.html')

        html_question = [page]

        bs_question = bs4.BeautifulSoup(html_question[0], "html.parser")
        parsed_answers = abparser.parse_answers(bs_question)
        self.assertEqual(len(parsed_answers), 10)
        for parsed_answer in parsed_answers:
            self.assertIsNotNone(parsed_answer['id'])
            self.assertIsNotNone(parsed_answer['score'])
            self.assertIsNotNone(parsed_answer['summary'])

    def test_parse_answer_comments(self):
        """Iterate over all the comments"""
        abparser = AskbotParser()
        page = read_file('data/askbot/html_148_comments_answer_2_openstack.html')

        html_question = [page]

        bs_question = bs4.BeautifulSoup(html_question[0], "html.parser")
        bs_answers = bs_question.select("div.answer")
        comments_to_test = abparser.parse_answer_comments(bs_answers[1])
        comments = bs_answers[1].select("div.comment")
        parsed_comments = abparser.parse_comments(comments)
        self.assertEqual(comments_to_test, parsed_comments)

    def test_parse_comments(self):
        """Given a list of comments, test all the elements about to be parsed"""
        page = read_file('data/askbot/html_148_comments_answer_2_openstack.html')

        html_question = [page]

        bs_question = bs4.BeautifulSoup(html_question[0], "html.parser")
        bs_answers = bs_question.select("div.answer")
        comments = bs_answers[1].select("div.comment")
        parsed_comments = AskbotParser.parse_comments(AskbotParser, comments)
        expected_comment_0 = {
                              'summary': "HI, are there any guide on debugging with eclipse and pydev with the latest branch. I have tried commented out eventlet.monkeypatch(os=False) and replaced it with eventlet.monkeypatch(all=False,socket=True,time=True,os=False) and added import sys;sys.path.append('path') but breakpoints are ignored",
                              'author': {
                                        'id': '451',
                                        'username': 'sak'
                                        },
                              'id': '814',
                              'added_at': '1367914127.0',
                              'score': ''
                              }
        expected_comment_1 = {
                              'summary': '@sakthanks for asking. I believe yours would be a very good new question, more than a comment here. Do you mind posting it as a new question?',
                              'author': {
                                        'id': '9',
                                        'username': 'smaffulli'
                                        },
                              'id': '872',
                              'added_at': '1367949923.0',
                              'score': ''
                              }
        expected_comment_2 = {
                              'summary': 'cool. I have posted this as a new question: https://ask.openstack.org/question/815/how-do-i-debug-nova-service-with-eclipse-and-pydev/',
                              'author': {
                                         'id': '451',
                                         'username': 'sak'
                                         },
                              'id': '886',
                              'added_at': '1368003922.0',
                              'score': ''
                              }
        self.assertEqual(parsed_comments[0], expected_comment_0)
        self.assertEqual(parsed_comments[1], expected_comment_1)
        self.assertEqual(parsed_comments[2], expected_comment_2)
        self.assertEqual(len(parsed_comments), 3)

    def test_parse_number_of_html_pages(self):
        """Get the number of html needed to retrieve all the answers of a given page"""
        page = read_file('data/askbot/html_24396_multipage_openstack.html')

        html_question = [page]

        bs_question = bs4.BeautifulSoup(html_question[0], "html.parser")

        pages = AskbotParser.parse_number_of_html_pages(bs_question)
        self.assertEqual(pages, 4)

    def test_parse_comment_author(self):
        """Get the user id and username of the author of the comment"""
        page = read_file('data/askbot/html_7893_answer_3_updated.html')

        html_question = [page]

        bs_question = bs4.BeautifulSoup(html_question[0], "html.parser")
        question = bs_question.select("div.js-question")
        comments = question[0].select("div.comment")
        author = AskbotParser.parse_comment_author(comments[0])
        self.assertEqual(author['id'], "625")
        self.assertEqual(author['username'], "todofixthis")

    def test_parse_answer_container(self):
        """Test answer container parsing. The answer container can be one or two elements,
        one containing the user (or wiki) info, and one optional one containing information
        regarding updates in the answer."""

        page = read_file('data/askbot/html_7893_answer_3_updated.html')

        html_question = [page]

        bs_question = bs4.BeautifulSoup(html_question[0], "html.parser")

        bs_answers = bs_question.select("div.answer")
        body = bs_answers[2].select("div.post-body")
        update_info = body[0].select("div.post-update-info")
        answer_container = AskbotParser.parse_answer_container(AskbotParser, update_info)
        expected_answered_by = {
                                'country': 'Germany',
                                'reputation': '283',
                                'id': '707',
                                'username': 'Jtrain',
                                'badges': 'Jtrain has 9 gold badges, 5 silver badges and 16 bronze badges'
                                }
        expected_updated_by = {
                               'country': 'Chile',
                               'reputation': '1242',
                               'id': '625',
                               'username': 'todofixthis',
                               'badges': 'todofixthis has 35 gold badges, 28 silver badges and 50 bronze badges'
                               }

        self.assertEqual(answer_container['answered_by'], expected_answered_by)
        self.assertEqual(answer_container['updated_by'], expected_updated_by)


    def test_parse_user_info(self):
        """Test user info parsing. User info can be a wiki post or a user. When a user, some
        additional information can be added like country or website when available"""

        page = read_file('data/askbot/askbot_question_multipage_1.html')

        html_question = [page]

        bs_question = bs4.BeautifulSoup(html_question[0], "html.parser")
        # Test the user_info from the question which is a wiki post and not updated
        question = bs_question.select("div.js-question")
        container = question[0].select("div.post-update-info")
        created = container[0]
        author = AskbotParser.parse_user_info(created)
        self.assertEqual(author, "This post is a wiki")

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
