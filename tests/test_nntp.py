#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2015-2017 Bitergia
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
#     Santiago Dueñas <sduenas@bitergia.com>
#

import collections
import nntplib
import shutil
import sys
import tempfile
import unittest
import unittest.mock

import pkg_resources

# Hack to make sure that tests import the right packages
# due to setuptools behaviour
sys.path.insert(0, '..')
pkg_resources.declare_namespace('perceval.backends')

from perceval.backend import BackendCommandArgumentParser
from perceval.cache import Cache
from perceval.errors import CacheError, ParseError
from perceval.backends.core.nntp import (NNTP,
                                         NNTPCommand)


NNTP_SERVER = 'nntp.example.com'
NNTP_GROUP = 'example.dev.project-link'


def read_file(filename, mode='r'):
    with open(filename, mode) as f:
        content = f.read()
    return content


MockArticleInfo = collections.namedtuple('ArticleInfo',
                                         ['number', 'message_id', 'lines'])


class MockNNTPLib:
    """Class for mocking nntplib"""

    def __init__(self):
        self.__articles = {
            1: ('<mailman.350.1458060579.14303.dev-project-link@example.com>', 'data/nntp/nntp_1.txt'),
            2: ('<mailman.361.1458076505.14303.dev-project-link@example.com>', 'data/nntp/nntp_2.txt'),
            3: ('error', 'error'),
            4: ('<mailman.5377.1312994002.4544.community-arab-world@lists.example.com>', 'data/nntp/nntp_parsing_error.txt')
        }

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def group(self, name):
        return None, None, 1, 4, None

    def over(self, message_spec):
        first = min(message_spec[0], len(self.__articles))
        last = min(message_spec[1], len(self.__articles))
        response = [(x, {'message_id': self.__articles[x][0]})
                    for x in range(first, last + 1)]
        return None, response

    def article(self, article_id):
        a = self.__articles[article_id]
        message_id = a[0]

        if message_id == 'error':
            raise nntplib.NNTPTemporaryError('not found')

        with open(a[1], 'rb') as f:
            lines = [l.rstrip() for l in f]
        return None, MockArticleInfo(article_id, message_id, lines)


class TestNNTPBackend(unittest.TestCase):
    """NNTP backend tests"""

    def test_initialization(self):
        """Test whether attributes are initializated"""

        expected_origin = NNTP_SERVER + '-' + NNTP_GROUP

        nntp = NNTP(NNTP_SERVER, NNTP_GROUP, tag='test')
        self.assertEqual(nntp.host, NNTP_SERVER)
        self.assertEqual(nntp.group, NNTP_GROUP)
        self.assertEqual(nntp.origin, expected_origin)
        self.assertEqual(nntp.tag, 'test')

        # When tag is empty or None it will be set to
        # the value in the origin
        nntp = NNTP(NNTP_SERVER, NNTP_GROUP)
        self.assertEqual(nntp.host, NNTP_SERVER)
        self.assertEqual(nntp.group, NNTP_GROUP)
        self.assertEqual(nntp.origin, expected_origin)
        self.assertEqual(nntp.tag, expected_origin)

        nntp = NNTP(NNTP_SERVER, NNTP_GROUP, tag='')
        self.assertEqual(nntp.host, NNTP_SERVER)
        self.assertEqual(nntp.group, NNTP_GROUP)
        self.assertEqual(nntp.origin, expected_origin)
        self.assertEqual(nntp.tag, expected_origin)

    def test_has_caching(self):
        """Test if it returns True when has_caching is called"""

        self.assertEqual(NNTP.has_caching(), True)

    def test_has_resuming(self):
        """Test if it returns True when has_resuming is called"""

        self.assertEqual(NNTP.has_resuming(), True)

    @unittest.mock.patch('nntplib.NNTP')
    def test_fetch(self, mock_nntp):
        """Test whether it fetches a set of articles"""

        mock_nntp.return_value = MockNNTPLib()

        nntp = NNTP(NNTP_SERVER, NNTP_GROUP)
        articles = [article for article in nntp.fetch()]

        expected = [
            ('<mailman.350.1458060579.14303.dev-project-link@example.com>', 1,
             'd088688545d7c2f3733993e215503b367193a26d', 1458039948.0),
            ('<mailman.361.1458076505.14303.dev-project-link@example.com>', 2,
             '8a20c77405349f442dad8e3ee8e60d392cc75ae7', 1458076496.0)
        ]
        expected_origin = NNTP_SERVER + '-' + NNTP_GROUP

        # Although there are 4 messages available on the server,
        # only two are valid
        self.assertEqual(len(articles), 2)

        for x in range(len(articles)):
            article = articles[x]
            expc = expected[x]
            self.assertEqual(article['data']['message_id'], expc[0])
            self.assertEqual(article['offset'], expc[1])
            self.assertEqual(article['uuid'], expc[2])
            self.assertEqual(article['origin'], expected_origin)
            self.assertEqual(article['updated_on'], expc[3])
            self.assertEqual(article['category'], 'article')
            self.assertEqual(article['tag'], expected_origin)

    @unittest.mock.patch('nntplib.NNTP')
    def test_fetch_from_offset(self, mock_nntp):
        """Test whether it fetches a set of articles from a given offset"""

        mock_nntp.return_value = MockNNTPLib()

        nntp = NNTP(NNTP_SERVER, NNTP_GROUP)
        articles = [article for article in nntp.fetch(offset=2)]

        expected = ('<mailman.361.1458076505.14303.dev-project-link@example.com>', 2,
                    '8a20c77405349f442dad8e3ee8e60d392cc75ae7', 1458076496.0)
        expected_origin = NNTP_SERVER + '-' + NNTP_GROUP

        self.assertEqual(len(articles), 1)

        article = articles[0]
        self.assertEqual(article['data']['message_id'], expected[0])
        self.assertEqual(article['offset'], expected[1])
        self.assertEqual(article['uuid'], expected[2])
        self.assertEqual(article['origin'], expected_origin)
        self.assertEqual(article['updated_on'], expected[3])
        self.assertEqual(article['category'], 'article')
        self.assertEqual(article['tag'], expected_origin)

    @unittest.mock.patch('nntplib.NNTP')
    def test_fetch_empty(self, mock_nntp):
        """Test if nothing is returned when there are no new articles"""

        mock_nntp.return_value = MockNNTPLib()

        nntp = NNTP(NNTP_SERVER, NNTP_GROUP)
        articles = [article for article in nntp.fetch(offset=3)]

        self.assertEqual(len(articles), 0)

    def test_parse_article(self):
        """Test if it parses an article stream"""

        raw_article = read_file('data/nntp/nntp_1.txt')

        article = NNTP.parse_article(raw_article)
        article = {k: v for k, v in article.items()}

        self.assertEqual(article['Message-ID'], '<mailman.350.1458060579.14303.dev-project-link@example.com>')
        self.assertEqual(article['NNTP-Posting-Date'], 'Tue, 15 Mar 2016 11:49:40 -0500')

        body = article.pop('body')
        self.assertEqual(body['plain'], "Hello folks,\n\n"
                                        "during yesterday's weekly meeting we talked about the need of starting to\n"
                                        "document the decisions that we are taking for Link. One of the questions\n"
                                        "was about whether we should use Github's or Mozilla's wiki for it. Both\n"
                                        "options looks good to me, but since there's already  some documentation at\n"
                                        "[1], I'll start adding more documentation there tomorrow unless someone\n"
                                        "disagrees and prefers Github's option.\n\n"
                                        "Cheers,\n\n"
                                        "/ Fernando\n\n"
                                        "[1] https://wiki.mozilla.org/Project_Link\n")
        self.assertEqual(len(body['html']), 663)

    @unittest.mock.patch('email.message_from_string')
    def test_parse_error_encoding(self, mock_parser):
        """Test if an exception is raised when an error is found with the enconding"""

        mock_parser.side_effect = UnicodeEncodeError("mockcodec", "astring",
                                                     1, 2, "fake reason")

        raw_article = read_file('data/nntp/nntp_1.txt')

        with self.assertRaises(ParseError):
            _ = NNTP.parse_article(raw_article)


class TestNNTPBackendCache(unittest.TestCase):
    """NNTP backend tests using a cache"""

    def setUp(self):
        self.tmp_path = tempfile.mkdtemp(prefix='perceval_')

    def tearDown(self):
        shutil.rmtree(self.tmp_path)

    @unittest.mock.patch('nntplib.NNTP')
    def test_fetch_from_cache(self, mock_nntp):
        """Test whether the cache works"""

        mock_nntp.return_value = MockNNTPLib()

        # First, we fetch the tasks from the server,
        # storing them in a cache
        cache = Cache(self.tmp_path)
        nntp = NNTP(NNTP_SERVER, NNTP_GROUP, cache=cache)
        articles = [article for article in nntp.fetch()]

        self.assertEqual(len(articles), 2)

        # Now, we get the articles from the cache which
        # should be the same
        cached_articles = [article for article in nntp.fetch_from_cache()]
        self.assertEqual(len(cached_articles), len(articles))

        expected = [
            ('<mailman.350.1458060579.14303.dev-project-link@example.com>', 1,
             'd088688545d7c2f3733993e215503b367193a26d', 1458039948.0),
            ('<mailman.361.1458076505.14303.dev-project-link@example.com>', 2,
             '8a20c77405349f442dad8e3ee8e60d392cc75ae7', 1458076496.0)
        ]
        expected_origin = NNTP_SERVER + '-' + NNTP_GROUP

        self.assertEqual(len(cached_articles), len(expected))

        for x in range(len(cached_articles)):
            carticle = cached_articles[x]
            expc = expected[x]
            self.assertEqual(carticle['data']['message_id'], expc[0])
            self.assertEqual(carticle['offset'], expc[1])
            self.assertEqual(carticle['uuid'], expc[2])
            self.assertEqual(carticle['origin'], expected_origin)
            self.assertEqual(carticle['updated_on'], expc[3])
            self.assertEqual(carticle['category'], 'article')
            self.assertEqual(carticle['tag'], expected_origin)

            # Compare chached and fetched task
            self.assertDictEqual(carticle['data'], articles[x]['data'])

    def test_fetch_from_empty_cache(self):
        """Test if there are not any articles returned when the cache is empty"""

        cache = Cache(self.tmp_path)
        nntp = NNTP(NNTP_SERVER, NNTP_GROUP, cache=cache)
        cached_articles = [article for article in nntp.fetch_from_cache()]
        self.assertEqual(len(cached_articles), 0)

    def test_fetch_from_non_set_cache(self):
        """Test if a error is raised when the cache was not set"""

        nntp = NNTP(NNTP_SERVER, NNTP_GROUP)

        with self.assertRaises(CacheError):
            _ = [article for article in nntp.fetch_from_cache()]


class TestNNTPCommand(unittest.TestCase):
    """Tests for NNTPCommand class"""

    def test_backend_class(self):
        """Test if the backend class is Phabricator"""

        self.assertIs(NNTPCommand.BACKEND, NNTP)

    def test_setup_cmd_parser(self):
        """Test if it parser object is correctly initialized"""

        parser = NNTPCommand.setup_cmd_parser()
        self.assertIsInstance(parser, BackendCommandArgumentParser)

        args = ['nntp.example.com',
                'example.dev.project-link',
                '--tag', 'test',
                '--no-cache',
                '--offset', '6']

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.host, 'nntp.example.com')
        self.assertEqual(parsed_args.group, 'example.dev.project-link')
        self.assertEqual(parsed_args.tag, 'test')
        self.assertEqual(parsed_args.no_cache, True)
        self.assertEqual(parsed_args.offset, 6)


if __name__ == "__main__":
    unittest.main(warnings='ignore')
