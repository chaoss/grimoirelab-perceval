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
#     Santiago Dueñas <sduenas@bitergia.com>
#     Valerio Cosentino <valcos@bitergia.com>
#     Miguel Ángel Fernández <mafesan@bitergia.com>
#     Harshal Mittal <harshalmittal4@gmail.com>
#

import collections
import nntplib
import os
import shutil
import tempfile
import unittest
import unittest.mock

from perceval.archive import Archive
from perceval.backend import BackendCommandArgumentParser
from perceval.errors import ArchiveError, ParseError
from perceval.backends.core.nntp import (NNTP,
                                         NNTTPClient,
                                         NNTPCommand)
from base import TestCaseBackendArchive


NNTP_SERVER = 'nntp.example.com'
NNTP_GROUP = 'example.dev.project-link'


def read_file(filename, mode='r'):
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), filename), mode) as f:
        content = f.read()
    return content


MockArticleInfo = collections.namedtuple('ArticleInfo',
                                         ['number', 'message_id', 'lines'])


class MockNNTPLib:
    """Class for mocking nntplib"""

    def __init__(self):
        self.__articles = {
            1: ('<mailman.350.1458060579.14303.dev-project-link@example.com>',
                os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data/nntp/nntp_1.txt')),
            2: ('<mailman.361.1458076505.14303.dev-project-link@example.com>',
                os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data/nntp/nntp_2.txt')),
            3: ('error', 'error'),
            4: ('<mailman.5377.1312994002.4544.community-arab-world@lists.example.com>',
                os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data/nntp/nntp_parsing_error.txt'))
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
            lines = [line.rstrip() for line in f]
        return None, MockArticleInfo(article_id, message_id, lines)

    def quit(self):
        pass


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
        self.assertIsNone(nntp.client)

        # When tag is empty or None it will be set to
        # the value in the origin
        nntp = NNTP(NNTP_SERVER, NNTP_GROUP)
        self.assertEqual(nntp.host, NNTP_SERVER)
        self.assertEqual(nntp.group, NNTP_GROUP)
        self.assertEqual(nntp.origin, expected_origin)
        self.assertEqual(nntp.tag, expected_origin)
        self.assertIsNone(nntp.client)

        nntp = NNTP(NNTP_SERVER, NNTP_GROUP, tag='')
        self.assertEqual(nntp.host, NNTP_SERVER)
        self.assertEqual(nntp.group, NNTP_GROUP)
        self.assertEqual(nntp.origin, expected_origin)
        self.assertEqual(nntp.tag, expected_origin)
        self.assertIsNone(nntp.client)

    def test_has_archiving(self):
        """Test if it returns True when has_archiving is called"""

        self.assertEqual(NNTP.has_archiving(), True)

    def test_has_resuming(self):
        """Test if it returns True when has_resuming is called"""

        self.assertEqual(NNTP.has_resuming(), True)

    @unittest.mock.patch('nntplib.NNTP')
    def test_fetch(self, mock_nntp):
        """Test whether it fetches a set of articles"""

        mock_nntp.return_value = MockNNTPLib()

        nntp = NNTP(NNTP_SERVER, NNTP_GROUP)
        articles = [article for article in nntp.fetch(offset=None)]

        expected = [
            ('<mailman.350.1458060579.14303.dev-project-link@example.com>', 1,
             'd088688545d7c2f3733993e215503b367193a26d', 0.0),
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
    def test_search_fields(self, mock_nntp):
        """Test whether the search_fields is properly set"""

        mock_nntp.return_value = MockNNTPLib()

        nntp = NNTP(NNTP_SERVER, NNTP_GROUP)
        articles = [article for article in nntp.fetch(offset=None)]

        article = articles[0]
        self.assertEqual(nntp.metadata_id(article['data']), article['search_fields']['item_id'])
        self.assertEqual(article['data']['Newsgroups'], 'example.dev.project-link')
        self.assertEqual(article['data']['Newsgroups'], article['search_fields']['newsgroups'])

        article = articles[1]
        self.assertEqual(nntp.metadata_id(article['data']), article['search_fields']['item_id'])
        self.assertEqual(article['data']['Newsgroups'], 'mozilla.dev.project-link')
        self.assertEqual(article['data']['Newsgroups'], article['search_fields']['newsgroups'])

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


class TestNNTPBackendArchive(TestCaseBackendArchive):
    """NNTP backend tests using an archive"""

    def setUp(self):
        super().setUp()
        self.backend_write_archive = NNTP(NNTP_SERVER, NNTP_GROUP, archive=self.archive)
        self.backend_read_archive = NNTP(NNTP_SERVER, NNTP_GROUP, archive=self.archive)

    @unittest.mock.patch('nntplib.NNTP')
    def test_fetch_from_archive(self, mock_nntp):
        """Test whether it fetches a set of articles from the archive"""

        mock_nntp.return_value = MockNNTPLib()
        self._test_fetch_from_archive()

    @unittest.mock.patch('nntplib.NNTP')
    def test_fetch_from_offset(self, mock_nntp):
        """Test whether it fetches a set of articles from a given offset in the archive"""

        mock_nntp.return_value = MockNNTPLib()
        self._test_fetch_from_archive(offset=2)

    @unittest.mock.patch('nntplib.NNTP')
    def test_fetch_empty(self, mock_nntp):
        """Test if nothing is returned when there are no new articles in the archive"""

        mock_nntp.return_value = MockNNTPLib()
        self._test_fetch_from_archive(offset=3)


class TestNNTPClient(unittest.TestCase):
    """Tests for NNTPCommand client"""

    def setUp(self):
        self.test_path = tempfile.mkdtemp(prefix='perceval_')
        archive_path = os.path.join(self.test_path, 'myarchive')
        self.archive = Archive.create(archive_path)

    def tearDown(self):
        shutil.rmtree(self.test_path)

    @unittest.mock.patch('nntplib.NNTP')
    def initalization(self, mock_nntp):
        """Test whether the client is correctly initialized"""

        mock_nntp.return_value = MockNNTPLib()
        client = NNTTPClient(NNTP_SERVER, archive=None, from_archive=False)

        self.assertEqual(client.host, NNTP_SERVER)
        self.assertIsNone(client.archive)
        self.assertFalse(client.from_archive)
        self.assertIsNone(client.handler)

        mock_nntp.return_value = MockNNTPLib()
        client = NNTTPClient(NNTP_SERVER, archive=self.archive, from_archive=False)

        self.assertEqual(client.host, NNTP_SERVER)
        self.assertEqual(client.archive, self.archive)
        self.assertFalse(client.from_archive)
        self.assertIsNotNone(client.handler)

        mock_nntp.return_value = MockNNTPLib()
        client = NNTTPClient(NNTP_SERVER, archive=self.archive, from_archive=True)

        self.assertEqual(client.host, NNTP_SERVER)
        self.assertEqual(client.archive, self.archive)
        self.assertTrue(client.from_archive)
        self.assertIsNotNone(client.handler)

    @unittest.mock.patch('nntplib.NNTP')
    def test_group(self, mock_nntp):
        """Test whether the group method works properly"""

        mock_nntp.return_value = MockNNTPLib()

        client = NNTTPClient(NNTP_SERVER, archive=self.archive, from_archive=False)
        data = client.group("example.dev.project-link")
        self.assertEqual((None, None, 1, 4, None), data)

        client = NNTTPClient(NNTP_SERVER, archive=self.archive, from_archive=True)
        archived_data = client.group("example.dev.project-link")
        self.assertEqual((None, None, 1, 4, None), data)

        self.assertEqual(data, archived_data)

    @unittest.mock.patch('nntplib.NNTP')
    def test_over(self, mock_nntp):
        """Test whether the over method works properly"""

        mock_nntp.return_value = MockNNTPLib()

        client = NNTTPClient(NNTP_SERVER, archive=self.archive, from_archive=False)
        data = client.over((1, 1))
        self.assertEqual(len(data), 2)
        self.assertDictEqual(data[1][0][1],
                             {'message_id': '<mailman.350.1458060579.14303.dev-project-link@example.com>'})

        client = NNTTPClient(NNTP_SERVER, archive=self.archive, from_archive=True)
        archived_data = client.over((1, 1))
        self.assertEqual(len(data), 2)
        self.assertDictEqual(data[1][0][1],
                             {'message_id': '<mailman.350.1458060579.14303.dev-project-link@example.com>'})

        self.assertEqual(data, archived_data)

    @unittest.mock.patch('nntplib.NNTP')
    def test_article(self, mock_nntp):
        """Test whether the article method works properly"""

        mock_nntp.return_value = MockNNTPLib()

        client = NNTTPClient(NNTP_SERVER, archive=self.archive, from_archive=False)
        data = client.article(2)
        self.assertEqual(len(data), 3)
        self.assertEqual(len(data['lines']), 220)
        self.assertEqual(data['lines'][-1], b'--lATx5p5hwwFl8QooX4JNWNU6e6LBSB7ES--')
        self.assertEqual(data['message_id'], '<mailman.361.1458076505.14303.dev-project-link@example.com>')
        self.assertEqual(data['number'], 2)

        client = NNTTPClient(NNTP_SERVER, archive=self.archive, from_archive=True)
        archived_data = client.article(2)
        self.assertEqual(len(data), 3)
        self.assertEqual(len(data['lines']), 220)
        self.assertEqual(data['lines'][-1], b'--lATx5p5hwwFl8QooX4JNWNU6e6LBSB7ES--')
        self.assertEqual(data['message_id'], '<mailman.361.1458076505.14303.dev-project-link@example.com>')
        self.assertEqual(data['number'], 2)

        self.assertEqual(data, archived_data)

    @unittest.mock.patch('nntplib.NNTP')
    def test_archive_not_provided(self, mock_nntp):
        """Test whether an exception is thrown if the archive is not provided"""

        mock_nntp.return_value = MockNNTPLib()

        client = NNTTPClient(NNTP_SERVER, archive=None, from_archive=True)
        with self.assertRaises(ArchiveError):
            client.group("example.dev.project-link")

    @unittest.mock.patch('nntplib.NNTP')
    def test_fetch_remote_nntp_temporary_error(self, mock_nntp):
        """Test whether an exception is thrown in case of temporary error"""

        mock_nntp.return_value = MockNNTPLib()
        client = NNTTPClient(NNTP_SERVER, archive=None, from_archive=False)

        with self.assertRaises(nntplib.NNTPTemporaryError):
            client._fetch_from_remote("article", 3)

    @unittest.mock.patch('nntplib.NNTP')
    def test_fetch_from_archive(self, mock_nntp):
        """Test whether the fetch from archive method works properly"""

        mock_nntp.return_value = MockNNTPLib()

        # first we upload data to the archive
        client = NNTTPClient(NNTP_SERVER, archive=self.archive, from_archive=False)
        group = client.group("example.dev.project-link")
        over = client.over((1, 1))
        article = client.article(2)

        # then we read the data within the archive
        client = NNTTPClient(NNTP_SERVER, archive=self.archive, from_archive=True)

        group_archived = client._fetch_from_archive("group", "example.dev.project-link")
        self.assertEqual(group, group_archived)

        over_archived = client._fetch_from_archive("over", (1, 1))
        self.assertEqual(over, over_archived)

        article_archived = client._fetch_from_archive("article", 2)
        self.assertEqual(article, article_archived)

    @unittest.mock.patch('nntplib.NNTP')
    def test_fetch_from_article(self, mock_nntp):
        """Test whether the fetch_from_article works properly"""

        mock_nntp.return_value = MockNNTPLib()

        client = NNTTPClient(NNTP_SERVER, archive=self.archive, from_archive=False)
        data = client._fetch_article(2)
        self.assertEqual(len(data), 3)
        self.assertIsNotNone(data['lines'])
        self.assertEqual(len(data['lines']), 220)

        self.assertIsNotNone(data['message_id'])
        self.assertEqual(data['message_id'], '<mailman.361.1458076505.14303.dev-project-link@example.com>')

        self.assertIsNotNone(data['number'])
        self.assertEqual(data['number'], 2)


class TestNNTPCommand(unittest.TestCase):
    """Tests for NNTPCommand class"""

    def test_backend_class(self):
        """Test if the backend class is Phabricator"""

        self.assertIs(NNTPCommand.BACKEND, NNTP)

    def test_setup_cmd_parser(self):
        """Test if it parser object is correctly initialized"""

        parser = NNTPCommand.setup_cmd_parser()
        self.assertIsInstance(parser, BackendCommandArgumentParser)
        self.assertEqual(parser._backend, NNTP)

        args = ['nntp.example.com',
                'example.dev.project-link',
                '--tag', 'test',
                '--no-archive',
                '--offset', '6']

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.host, 'nntp.example.com')
        self.assertEqual(parsed_args.group, 'example.dev.project-link')
        self.assertEqual(parsed_args.tag, 'test')
        self.assertEqual(parsed_args.no_archive, True)
        self.assertEqual(parsed_args.offset, 6)


if __name__ == "__main__":
    unittest.main(warnings='ignore')
