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
import sys
import unittest
import unittest.mock

import pkg_resources

# Hack to make sure that tests import the right packages
# due to setuptools behaviour
sys.path.insert(0, '..')
pkg_resources.declare_namespace('perceval.backends')

from perceval.backends.core.nntp import NNTP

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
            1 : ('<mailman.350.1458060579.14303.dev-project-link@example.com>', 'data/nntp/nntp_1.txt'),
            2 : ('<mailman.361.1458076505.14303.dev-project-link@example.com>', 'data/nntp/nntp_2.txt')
        }

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def group(self, name):
        return None, None, 1, 2, None

    def article(self, article_id):
        a = self.__articles[article_id]
        message_id = a[0]

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
        """Test if it returns False when has_caching is called"""

        self.assertEqual(NNTP.has_caching(), False)

    def test_has_resuming(self):
        """Test if it returns True when has_resuming is called"""

        self.assertEqual(NNTP.has_resuming(), True)

    @unittest.mock.patch('nntplib.NNTP')
    def test_fetch(self, mock_nntp):
        """Test whether it fetches a set of articles"""

        mock_nntp.return_value = MockNNTPLib()

        nntp = NNTP(NNTP_SERVER, NNTP_GROUP)
        articles = [article for article in nntp.fetch()]

        expected = [('<mailman.350.1458060579.14303.dev-project-link@example.com>', 1, 'd088688545d7c2f3733993e215503b367193a26d', 1458060580.0),
                    ('<mailman.361.1458076505.14303.dev-project-link@example.com>', 2, '8a20c77405349f442dad8e3ee8e60d392cc75ae7', 1458076506.0)]
        expected_origin = NNTP_SERVER + '-' + NNTP_GROUP

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

        expected = ('<mailman.361.1458076505.14303.dev-project-link@example.com>', 2, '8a20c77405349f442dad8e3ee8e60d392cc75ae7', 1458076506.0)
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
        article = {k: v for k,v in article.items()}

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


if __name__ == "__main__":
    unittest.main(warnings='ignore')
