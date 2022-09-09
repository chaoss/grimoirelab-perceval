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
#     Valerio Cosentino <valcos@bitergia.com>
#     Prabhat <prabhatsharma7298@gmail.com>
#     Santiago Dueñas <sduenas@bitergia.com>
#     Harshal Mittal <harshalmittal4@gmail.com>
#

import datetime
import os
import shutil
import unittest.mock

from perceval.backend import BackendCommandArgumentParser
from perceval.errors import BackendError
from perceval.utils import DEFAULT_DATETIME

from perceval.backends.core.gerrit import (CATEGORY_REVIEW, MAX_REVIEWS, PORT,
                                           Gerrit,
                                           GerritCommand,
                                           GerritClient)

from base import TestCaseBackendArchive


GERRIT_REPO = "example.org"
GERRIT_USER = "user"

VERSION_UNKNOWN = 'data/gerrit/gerrit_version_unknown'
VERSION_214 = 'data/gerrit/gerrit_version_214'
VERSION_313 = 'data/gerrit/gerrit_version_313'
REVIEWS_PAGE_1 = 'data/gerrit/gerrit_reviews_page_1'
REVIEWS_PAGE_2 = 'data/gerrit/gerrit_reviews_page_2'
REVIEWS_PAGE_3 = 'data/gerrit/gerrit_reviews_page_3'

CMD_VERSION = "ssh  -p 29418 user@example.org gerrit  version "
CMD_REVIEWS_1 = "ssh  -p 29418 user@example.org gerrit  query limit:2 " \
                "'(status:open OR status:closed)' --all-approvals --comments --format=JSON --start=0"
CMD_REVIEWS_2 = "ssh  -p 29418 user@example.org gerrit  query limit:2 " \
                "'(status:open OR status:closed)' --all-approvals --comments --format=JSON --start=2"
CMD_REVIEWS_3 = "ssh  -p 29418 user@example.org gerrit  query limit:2 " \
                "'(status:open OR status:closed)' --all-approvals --comments --format=JSON --start=4"

RESPONSES = {CMD_VERSION: VERSION_214,
             CMD_REVIEWS_1: REVIEWS_PAGE_1,
             CMD_REVIEWS_2: REVIEWS_PAGE_2,
             CMD_REVIEWS_3: REVIEWS_PAGE_3}


def read_file(filename, mode='r'):
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), filename), mode) as f:
        content = f.read()
    return content


def mock_check_ouput_gerrit_3(*args, **kwargs):
    """Mock subprocess.check_output"""

    responses = {CMD_VERSION: VERSION_313,
                 CMD_REVIEWS_1: REVIEWS_PAGE_1,
                 CMD_REVIEWS_2: REVIEWS_PAGE_2,
                 CMD_REVIEWS_3: REVIEWS_PAGE_3}

    cmd = args[0]
    try:
        data = read_file(responses[cmd], 'rb')
    except Exception:
        data = None

    return data


def mock_check_ouput(*args, **kwargs):
    """Mock subprocess.check_output"""

    responses = {CMD_VERSION: VERSION_214,
                 CMD_REVIEWS_1: REVIEWS_PAGE_1,
                 CMD_REVIEWS_2: REVIEWS_PAGE_2,
                 CMD_REVIEWS_3: REVIEWS_PAGE_3}

    cmd = args[0]
    try:
        data = read_file(responses[cmd], 'rb')
    except Exception:
        data = None

    return data


def mock_check_ouput_version_unknown(*args, **kwargs):
    """Mock subprocess.check_output"""

    data = read_file(VERSION_UNKNOWN, 'rb')

    return data


def mock_check_ouput_empty_review(*args, **kwargs):
    """Mock subprocess.check_output"""

    return None


class TestGerritBackend(unittest.TestCase):
    """Gerrit backend tests """

    def test_initialization(self):
        """Test whether attributes are initializated"""

        gerrit = Gerrit(GERRIT_REPO, tag='test')
        self.assertEqual(gerrit.hostname, GERRIT_REPO)
        self.assertEqual(gerrit.port, PORT)
        self.assertEqual(gerrit.max_reviews, MAX_REVIEWS)
        self.assertIsNone(gerrit.user)
        self.assertEqual(gerrit.tag, 'test')
        self.assertIsNone(gerrit.client)
        self.assertIsNone(gerrit.blacklist_ids)

        gerrit = Gerrit(GERRIT_REPO, GERRIT_USER,
                        port=1000, max_reviews=100,
                        id_filepath='/tmp/.ssh-keys/id_rsa')
        self.assertEqual(gerrit.hostname, GERRIT_REPO)
        self.assertEqual(gerrit.port, 1000)
        self.assertEqual(gerrit.max_reviews, 100)
        self.assertEqual(gerrit.tag, GERRIT_REPO)
        self.assertEqual(gerrit.user, GERRIT_USER)
        self.assertIsNone(gerrit.client)
        self.assertIsNone(gerrit.blacklist_ids)
        self.assertEqual(gerrit.id_filepath, '/tmp/.ssh-keys/id_rsa')

        gerrit = Gerrit(GERRIT_REPO, tag='test', blacklist_ids=['willy'])
        self.assertEqual(gerrit.hostname, GERRIT_REPO)
        self.assertEqual(gerrit.port, PORT)
        self.assertEqual(gerrit.max_reviews, MAX_REVIEWS)
        self.assertIsNone(gerrit.user)
        self.assertEqual(gerrit.tag, 'test')
        self.assertListEqual(gerrit.blacklist_ids, ['willy'])

    def test_has_archiving(self):
        """Test if it returns True when has_archiving is called"""

        self.assertEqual(Gerrit.has_archiving(), True)

    def test_has_resuming(self):
        """Test if it returns False when has_resuming is called"""

        self.assertEqual(Gerrit.has_resuming(), False)

    @unittest.mock.patch('subprocess.check_output', mock_check_ouput)
    def test_fetch(self):
        """Test fetch method"""

        mock_check_ouput.side_effect = mock_check_ouput

        gerrit = Gerrit(GERRIT_REPO, user=GERRIT_USER, port=29418, max_reviews=2)
        reviews = [review for review in gerrit.fetch(from_date=None)]

        self.assertIsNotNone(gerrit.client)
        self.assertEqual(len(reviews), 5)

        review = reviews[0]
        self.assertEqual(review['category'], CATEGORY_REVIEW)
        self.assertEqual(len(review['data']['comments']), 5)
        self.assertEqual(review['data']['owner']['username'], 'gehel')
        self.assertEqual(len(review['data']['patchSets']), 2)

        review = reviews[1]
        self.assertEqual(review['category'], CATEGORY_REVIEW)
        self.assertEqual(len(review['data']['comments']), 26)
        self.assertEqual(review['data']['owner']['username'], "lucaswerkmeister-wmde")
        self.assertEqual(len(review['data']['patchSets']), 1)

        review = reviews[2]
        self.assertEqual(review['category'], CATEGORY_REVIEW)
        self.assertEqual(len(review['data']['comments']), 13)
        self.assertEqual(review['data']['owner']['username'], "jayprakash12345")
        self.assertEqual(len(review['data']['patchSets']), 3)

        review = reviews[3]
        self.assertEqual(review['category'], CATEGORY_REVIEW)
        self.assertEqual(len(review['data']['comments']), 8)
        self.assertEqual(review['data']['owner']['username'], "elukey")
        self.assertEqual(len(review['data']['patchSets']), 2)

        review = reviews[4]
        self.assertEqual(review['category'], CATEGORY_REVIEW)
        self.assertEqual(len(review['data']['comments']), 13)
        self.assertEqual(review['data']['owner']['username'], "jayprakash12345")
        self.assertEqual(len(review['data']['patchSets']), 3)

    @unittest.mock.patch('subprocess.check_output', mock_check_ouput)
    def test_serch_fields(self):
        """Test whether the search_fields is properly set"""

        mock_check_ouput.side_effect = mock_check_ouput

        gerrit = Gerrit(GERRIT_REPO, user=GERRIT_USER, port=29418, max_reviews=2)
        reviews = [review for review in gerrit.fetch(from_date=None)]

        self.assertIsNotNone(gerrit.client)
        self.assertEqual(len(reviews), 5)

        review = reviews[0]
        self.assertEqual(gerrit.metadata_id(review['data']), review['search_fields']['item_id'])
        self.assertEqual(review['data']['project'], 'operations/puppet')
        self.assertEqual(review['data']['project'], review['search_fields']['project_name'])
        self.assertEqual(review['data']['id'], 'I99a07b8e55560db3ddc00e0c8c30c62b65136556')
        self.assertEqual(review['data']['id'], review['search_fields']['review_hash'])

        review = reviews[1]
        self.assertEqual(gerrit.metadata_id(review['data']), review['search_fields']['item_id'])
        self.assertEqual(review['data']['project'], 'mediawiki/extensions/Wikibase')
        self.assertEqual(review['data']['project'], review['search_fields']['project_name'])
        self.assertEqual(review['data']['id'], 'I9ad743250f37c3be369888b1b9be80d8d332f62f')
        self.assertEqual(review['data']['id'], review['search_fields']['review_hash'])

        review = reviews[2]
        self.assertEqual(gerrit.metadata_id(review['data']), review['search_fields']['item_id'])
        self.assertEqual(review['data']['project'], 'operations/mediawiki-config')
        self.assertEqual(review['data']['project'], review['search_fields']['project_name'])
        self.assertEqual(review['data']['id'], 'I9992907ef53f122b54ef2c64146da513477db025')
        self.assertEqual(review['data']['id'], review['search_fields']['review_hash'])

        review = reviews[3]
        self.assertEqual(gerrit.metadata_id(review['data']), review['search_fields']['item_id'])
        self.assertEqual(review['data']['project'], 'operations/puppet')
        self.assertEqual(review['data']['project'], review['search_fields']['project_name'])
        self.assertEqual(review['data']['id'], 'I3d8e4685095da4b6a53e826c8a73ec13e4d562d2')
        self.assertEqual(review['data']['id'], review['search_fields']['review_hash'])

        review = reviews[4]
        self.assertEqual(gerrit.metadata_id(review['data']), review['search_fields']['item_id'])
        self.assertEqual(review['data']['project'], 'operations/mediawiki-config')
        self.assertEqual(review['data']['project'], review['search_fields']['project_name'])
        self.assertEqual(review['data']['id'], 'I9992907ef53f122b54ef2c64146da513477db025')
        self.assertEqual(review['data']['id'], review['search_fields']['review_hash'])

    @unittest.mock.patch('subprocess.check_output', mock_check_ouput)
    def test_fetch_from_date(self):
        """Test fetch method with from date"""

        mock_check_ouput.side_effect = mock_check_ouput

        gerrit = Gerrit(GERRIT_REPO, user=GERRIT_USER, port=29418, max_reviews=2)
        from_date = datetime.datetime(2018, 3, 5)
        reviews = [review for review in gerrit.fetch(from_date=from_date)]

        self.assertIsNotNone(gerrit.client)
        self.assertEqual(len(reviews), 4)

        review = reviews[0]
        self.assertEqual(review['category'], CATEGORY_REVIEW)
        self.assertEqual(len(review['data']['comments']), 5)
        self.assertEqual(review['data']['owner']['username'], 'gehel')
        self.assertEqual(len(review['data']['patchSets']), 2)

        review = reviews[1]
        self.assertEqual(review['category'], CATEGORY_REVIEW)
        self.assertEqual(len(review['data']['comments']), 26)
        self.assertEqual(review['data']['owner']['username'], "lucaswerkmeister-wmde")
        self.assertEqual(len(review['data']['patchSets']), 1)

        review = reviews[2]
        self.assertEqual(review['category'], CATEGORY_REVIEW)
        self.assertEqual(len(review['data']['comments']), 13)
        self.assertEqual(review['data']['owner']['username'], "jayprakash12345")
        self.assertEqual(len(review['data']['patchSets']), 3)

        review = reviews[3]
        self.assertEqual(review['category'], CATEGORY_REVIEW)
        self.assertEqual(len(review['data']['comments']), 8)
        self.assertEqual(review['data']['owner']['username'], "elukey")
        self.assertEqual(len(review['data']['patchSets']), 2)

    def test_parse_reviews(self):
        """Test parse reviews method"""

        raw_reviews = read_file('data/gerrit/gerrit_reviews_page_1')
        reviews = Gerrit.parse_reviews(raw_reviews)

        self.assertEqual(len(reviews), 2)

        review = reviews[0]
        self.assertEqual(len(review['comments']), 5)
        self.assertEqual(review['owner']['username'], 'gehel')
        self.assertEqual(len(review['patchSets']), 2)

        review = reviews[1]
        self.assertEqual(len(review['comments']), 26)
        self.assertEqual(review['owner']['username'], "lucaswerkmeister-wmde")
        self.assertEqual(len(review['patchSets']), 1)


class TestGerritBackendArchive(TestCaseBackendArchive):
    """Gerrit backend tests using an archive"""

    def setUp(self):
        super().setUp()
        self.backend_write_archive = Gerrit(GERRIT_REPO, user=GERRIT_USER, port=29418, max_reviews=2,
                                            archive=self.archive)
        self.backend_read_archive = Gerrit(GERRIT_REPO, user="another-user", port=29418, max_reviews=2,
                                           archive=self.archive)

    def tearDown(self):
        shutil.rmtree(self.test_path)

    @unittest.mock.patch('subprocess.check_output', mock_check_ouput)
    def test_fetch_from_archive(self):
        """Test whether a list of reviews is returned from the archive"""

        mock_check_ouput.side_effect = mock_check_ouput
        self.backend = Gerrit(GERRIT_REPO, user=GERRIT_USER, port=29418, max_reviews=2,
                              archive=self.archive)
        self._test_fetch_from_archive(from_date=None)

    @unittest.mock.patch('subprocess.check_output', mock_check_ouput)
    def test_fetch_from_date_from_archive(self):
        """Test whether a list of reviews is returned from archive after a given date"""

        mock_check_ouput.side_effect = mock_check_ouput
        self.backend = Gerrit(GERRIT_REPO, user=GERRIT_USER, max_reviews=2,
                              archive=self.archive)
        from_date = datetime.datetime(2018, 3, 5)
        self._test_fetch_from_archive(from_date=from_date)

    @unittest.mock.patch('subprocess.check_output', mock_check_ouput)
    def test_fetch_from_empty_archive(self):
        """Test whether no reviews are returned when the archive is empty"""

        mock_check_ouput.side_effect = mock_check_ouput
        self.backend = Gerrit(GERRIT_REPO, user=GERRIT_USER, max_reviews=2,
                              archive=self.archive)
        from_date = datetime.datetime(2100, 3, 5)
        self._test_fetch_from_archive(from_date=from_date)


class TestGerritClient(unittest.TestCase):
    """ Gerrit API client tests """

    def test_init(self):
        """Test init method"""

        client = GerritClient(GERRIT_REPO)
        self.assertEqual(client.repository, GERRIT_REPO)
        self.assertIsNone(client.gerrit_user)
        self.assertEqual(client.max_reviews, MAX_REVIEWS)
        self.assertEqual(client.blacklist_reviews, [])
        self.assertEqual(client.port, PORT)
        self.assertFalse(client.from_archive)
        self.assertIsNone(client.archive)

        client = GerritClient(
            GERRIT_REPO, GERRIT_USER, port=1000, max_reviews=2,
            blacklist_reviews=["willy"],
            id_filepath='/tmp/.ssh-keys/id_rsa'
        )
        self.assertEqual(client.repository, GERRIT_REPO)
        self.assertEqual(client.gerrit_user, GERRIT_USER)
        self.assertEqual(client.max_reviews, 2)
        self.assertEqual(client.blacklist_reviews, ["willy"])
        self.assertEqual(client.port, 1000)
        self.assertEqual(client.id_filepath, '/tmp/.ssh-keys/id_rsa')
        self.assertFalse(client.from_archive)
        self.assertIsNone(client.archive)

    @unittest.mock.patch('subprocess.check_output', mock_check_ouput)
    def test_version(self):
        """Test version method"""

        mock_check_ouput.side_effect = mock_check_ouput
        client = GerritClient(GERRIT_REPO, GERRIT_USER)

        result = client.version
        self.assertEqual(result[0], 2)
        self.assertEqual(result[1], 14)

    @unittest.mock.patch('subprocess.check_output', mock_check_ouput_version_unknown)
    def test_unknown_version(self):
        """Test whether an exception is thrown when the gerrit version is unknown"""

        mock_check_ouput_version_unknown.side_effect = mock_check_ouput_version_unknown
        client = GerritClient(GERRIT_REPO, GERRIT_USER)

        with self.assertRaises(BackendError):
            _ = client.version

    @unittest.mock.patch('subprocess.check_output', mock_check_ouput)
    def test_reviews(self):
        """Test reviews method"""

        mock_check_ouput.side_effect = mock_check_ouput

        expected_raw = read_file('data/gerrit/gerrit_reviews_page_1')
        client = GerritClient(GERRIT_REPO, GERRIT_USER, max_reviews=2)
        result_raw = client.reviews(0)

        self.assertEqual(result_raw, expected_raw)

    @unittest.mock.patch('subprocess.check_output', mock_check_ouput_gerrit_3)
    def test_reviews_gerrit_3(self):
        """Test reviews method"""

        mock_check_ouput_gerrit_3.side_effect = mock_check_ouput_gerrit_3

        expected_raw = read_file('data/gerrit/gerrit_reviews_page_1')
        client = GerritClient(GERRIT_REPO, GERRIT_USER, max_reviews=2)
        result_raw = client.reviews(0)

        self.assertEqual(result_raw, expected_raw)

    @unittest.mock.patch('subprocess.check_output', mock_check_ouput_empty_review)
    def test_empty_review(self):
        """Test whether an excepti on is thrown when no data is returned"""

        mock_check_ouput_empty_review.side_effect = mock_check_ouput_empty_review

        client = GerritClient(GERRIT_REPO, GERRIT_USER, max_reviews=2)
        with self.assertRaises(RuntimeError):
            _ = client.reviews(0)

    @unittest.mock.patch('subprocess.check_output', mock_check_ouput)
    def test_next_retrieve_group_item(self):
        """Test next_retrieve_group_item method"""

        mock_check_ouput.side_effect = mock_check_ouput

        client = GerritClient(GERRIT_REPO, GERRIT_USER)
        client.version
        # version 3.1
        client._version[0] = 3
        client._version[1] = 1

        result = client.next_retrieve_group_item()
        self.assertEqual(result, 0)

        result = client.next_retrieve_group_item(last_item="last")
        self.assertEqual(result, "last")

        # version 2.10
        client._version[0] = 2
        client._version[1] = 10

        result = client.next_retrieve_group_item()
        self.assertEqual(result, 0)

        result = client.next_retrieve_group_item(last_item="last")
        self.assertEqual(result, "last")

        # version 2.9
        client._version[0] = 2
        client._version[1] = 9

        with self.assertRaises(BackendError):
            _ = client.next_retrieve_group_item()

        # version 1.x
        client._version[0] = 1
        result = client.next_retrieve_group_item(entry={'sortKey': 'asc'})
        self.assertEqual(result, 'asc')

    def test_sanitize_for_archive(self):
        """Test whether the sanitize method works properly"""

        cmd = "ssh -p 29418 user@example.org gerrit version"
        sanitized_cmd = GerritClient.sanitize_for_archive(cmd)

        self.assertEqual("ssh -p 29418 xxxxx@example.org gerrit version", sanitized_cmd)


class TestGerritCommand(unittest.TestCase):
    """GerritCommand unit tests"""

    def test_backend_class(self):
        """Test if the backend class is GitHub"""

        self.assertIs(GerritCommand.BACKEND, Gerrit)

    def test_setup_cmd_parser(self):
        """Test if it parser object is correctly initialized"""

        parser = GerritCommand.setup_cmd_parser()
        self.assertIsInstance(parser, BackendCommandArgumentParser)
        self.assertEqual(parser._backend, Gerrit)

        args = [GERRIT_REPO,
                '--user', GERRIT_USER,
                '--max-reviews', '5',
                '--blacklist-ids', '',
                '--disable-host-key-check',
                '--ssh-port', '1000',
                '--tag', 'test', '--no-archive']

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.hostname, GERRIT_REPO)
        self.assertEqual(parsed_args.user, GERRIT_USER)
        self.assertEqual(parsed_args.max_reviews, 5)
        self.assertEqual(parsed_args.tag, 'test')
        self.assertEqual(parsed_args.from_date, DEFAULT_DATETIME)
        self.assertEqual(parsed_args.no_archive, True)
        self.assertEqual(parsed_args.port, 1000)
        self.assertListEqual(parsed_args.blacklist_ids, [''])

        args = [GERRIT_REPO,
                '--user', GERRIT_USER,
                '--max-reviews', '5',
                '--blacklist-ids', 'willy', 'wolly', 'wally',
                '--disable-host-key-check',
                '--ssh-port', '1000',
                '--ssh-id-filepath', '/my/keys/id_rsa',
                '--tag', 'test', '--no-archive']

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.hostname, GERRIT_REPO)
        self.assertEqual(parsed_args.user, GERRIT_USER)
        self.assertEqual(parsed_args.max_reviews, 5)
        self.assertEqual(parsed_args.tag, 'test')
        self.assertEqual(parsed_args.from_date, DEFAULT_DATETIME)
        self.assertEqual(parsed_args.no_archive, True)
        self.assertEqual(parsed_args.port, 1000)
        self.assertEqual(parsed_args.id_filepath, '/my/keys/id_rsa')
        self.assertListEqual(parsed_args.blacklist_ids, ['willy', 'wolly', 'wally'])


if __name__ == "__main__":
    unittest.main(warnings='ignore')
