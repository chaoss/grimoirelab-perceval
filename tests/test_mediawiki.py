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
#     Alvaro del Castillo <acs@bitergia.com>
#     Stephan Barth <stephan.barth@gmail.com>
#     Valerio Cosentino <valcos@bitergia.com>
#     Miguel Ángel Fernández <mafesan@bitergia.com>
#     Jesus M. Gonzalez-Barahona <jgb@gsyc.es>
#     Harshal Mittal <harshalmittal4@gmail.com>
#

import datetime
import dateutil
import httpretty
import os
import unittest
import urllib
import unittest.mock

from grimoirelab_toolkit.datetime import (datetime_to_utc,
                                          str_to_datetime)

from perceval.backend import BackendCommandArgumentParser
from perceval.errors import BackendError
from perceval.utils import DEFAULT_DATETIME
from perceval.backends.core.mediawiki import (MediaWiki,
                                              MediaWikiCommand,
                                              MediaWikiClient,
                                              logger)
from base import TestCaseBackendArchive


MEDIAWIKI_SERVER_URL = 'http://example.com'
MEDIAWIKI_API = MEDIAWIKI_SERVER_URL + '/api.php'

TESTED_VERSIONS = ['1.23', '1.28']


def read_file(filename, mode='r'):
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), filename), mode) as f:
        content = f.read()
    return content


class HTTPServer():

    requests_http = []  # requests done to the server

    @classmethod
    def routes(cls, version="1.28", empty=False, response_num=200):
        """Configure in http the routes to be served"""

        assert version in TESTED_VERSIONS

        if version == "1.28":
            mediawiki_siteinfo = read_file('data/mediawiki/mediawiki_siteinfo_1.28.json')
        elif version == "1.23":
            mediawiki_siteinfo = read_file('data/mediawiki/mediawiki_siteinfo_1.23.json')
        mediawiki_namespaces = read_file('data/mediawiki/mediawiki_namespaces.json')
        # For >= 1.27 in full and incremental mode, the same file
        mediawiki_pages_allrevisions = read_file('data/mediawiki/mediawiki_pages_allrevisions.json')
        if empty:
            mediawiki_pages_allrevisions = read_file('data/mediawiki/mediawiki_pages_allrevisions_empty.json')

        # For < 1.27 in full download
        mediawiki_pages_all = read_file('data/mediawiki/mediawiki_pages_all.json')
        if empty:
            mediawiki_pages_all = read_file('data/mediawiki/mediawiki_pages_all_empty.json')

        # For < 1.27 in incremental download
        mediawiki_pages_recent_changes = read_file('data/mediawiki/mediawiki_pages_recent_changes.json')

        # Pages with revisions
        mediawiki_page_476583 = read_file('data/mediawiki/mediawiki_page_476583_revisions.json')
        mediawiki_page_592384 = read_file('data/mediawiki/mediawiki_page_592384_revisions.json')
        mediawiki_page_476589 = read_file('data/mediawiki/mediawiki_page_476589_revisions.json')
        mediawiki_page_476590 = read_file('data/mediawiki/mediawiki_page_476590_revisions.json')

        def request_callback(method, uri, headers):
            params = urllib.parse.parse_qs(urllib.parse.urlparse(uri).query)
            if 'meta' in params and 'siteinfo' in params['meta']:
                body = mediawiki_siteinfo
                if 'siprop' in params:
                    body = mediawiki_namespaces
            elif 'list' in params:
                if 'allpages' in params['list']:
                    body = mediawiki_pages_all
                elif 'recentchanges' in params['list']:
                    body = mediawiki_pages_recent_changes
                elif 'allrevisions' in params['list']:
                    body = mediawiki_pages_allrevisions
            elif 'pageids' in params:
                if params['pageids'][0] == '476583':
                    body = mediawiki_page_476583
                elif params['pageids'][0] == '592384':
                    body = mediawiki_page_592384
                elif params['pageids'][0] == '476589':
                    body = mediawiki_page_476589
                elif params['pageids'][0] == '476590':
                    body = mediawiki_page_476590
            else:
                raise

            HTTPServer.requests_http.append(httpretty.last_request())

            return (response_num, headers, body)

        httpretty.register_uri(httpretty.GET,
                               MEDIAWIKI_API,
                               responses=[
                                   httpretty.Response(body=request_callback)
                               ])

    @classmethod
    def check_pages_contents(cls, testObj, pages):
        testObj.assertEqual(pages[0]['data']['pageid'], 592384)
        testObj.assertEqual(len(pages[0]['data']['revisions']), 2)
        testObj.assertEqual(pages[0]['origin'], MEDIAWIKI_SERVER_URL)
        testObj.assertEqual(pages[0]['uuid'], '528aa927f40d8e46a1e9f456fa318bf9f8a38105')
        testObj.assertEqual(pages[0]['updated_on'], 1466557537.0)
        testObj.assertEqual(pages[0]['category'], 'page')
        testObj.assertEqual(pages[0]['tag'], MEDIAWIKI_SERVER_URL)

        if len(pages) > 1:
            testObj.assertEqual(pages[1]['data']['pageid'], 476583)
            testObj.assertEqual(len(pages[1]['data']['revisions']), 500)
            testObj.assertEqual(pages[1]['origin'], MEDIAWIKI_SERVER_URL)
            testObj.assertEqual(pages[1]['uuid'], 'c627c598b1eb2a0fe8d6aef9af9968ad54038c7b')
            testObj.assertEqual(pages[1]['updated_on'], 1466616473.0)
            testObj.assertEqual(pages[1]['category'], 'page')
            testObj.assertEqual(pages[1]['tag'], MEDIAWIKI_SERVER_URL)


class TestMediaWikiBackend(unittest.TestCase):
    """MediaWiki backend tests"""

    def test_initialization(self):
        """Test whether attributes are initializated"""

        mediawiki = MediaWiki(MEDIAWIKI_SERVER_URL, tag='test')

        self.assertEqual(mediawiki.url, MEDIAWIKI_SERVER_URL)
        self.assertEqual(mediawiki.origin, MEDIAWIKI_SERVER_URL)
        self.assertEqual(mediawiki.tag, 'test')
        self.assertIsNone(mediawiki.client)
        self.assertTrue(mediawiki.ssl_verify)

        # When tag is empty or None it will be set to
        # the value in url
        mediawiki = MediaWiki(MEDIAWIKI_SERVER_URL, ssl_verify=False)
        self.assertEqual(mediawiki.url, MEDIAWIKI_SERVER_URL)
        self.assertEqual(mediawiki.origin, MEDIAWIKI_SERVER_URL)
        self.assertEqual(mediawiki.tag, MEDIAWIKI_SERVER_URL)
        self.assertFalse(mediawiki.ssl_verify)

        mediawiki = MediaWiki(MEDIAWIKI_SERVER_URL, tag='')
        self.assertEqual(mediawiki.url, MEDIAWIKI_SERVER_URL)
        self.assertEqual(mediawiki.origin, MEDIAWIKI_SERVER_URL)
        self.assertEqual(mediawiki.tag, MEDIAWIKI_SERVER_URL)

    def test_has_archiving(self):
        """Test if it returns True when has_archiving is called"""

        self.assertEqual(MediaWiki.has_archiving(), True)

    def test_has_resuming(self):
        """Test if it returns False when has_resuming is called"""

        self.assertEqual(MediaWiki.has_resuming(), False)

    @httpretty.activate
    @unittest.mock.patch('perceval.backends.core.mediawiki.datetime_utcnow')
    def test_fetch_max_recent_days(self, mock_utcnow):
        """Test whether the pages with their reviews are returned"""

        HTTPServer.routes("1.23")
        mock_utcnow.return_value = datetime.datetime(2100, 6, 10,
                                                     tzinfo=dateutil.tz.tzutc())

        from_date = dateutil.parser.parse("2016-06-23 15:35")
        mediawiki = MediaWiki(MEDIAWIKI_SERVER_URL)

        mediawiki._test_mode = True

        with self.assertRaises(BackendError):
            _ = [page for page in mediawiki.fetch(from_date=from_date)]

    @httpretty.activate
    def _test_search_fields(self, version):
        """Test whether the pages with their reviews are returned"""

        HTTPServer.routes(version)

        # Test fetch pages with their reviews
        mediawiki = MediaWiki(MEDIAWIKI_SERVER_URL)

        pages = [page for page in mediawiki.fetch()]

        page = pages[0]
        self.assertEqual(mediawiki.metadata_id(page['data']), page['search_fields']['item_id'])

        page = pages[1]
        self.assertEqual(mediawiki.metadata_id(page['data']), page['search_fields']['item_id'])

    @httpretty.activate
    @unittest.mock.patch('perceval.backends.core.mediawiki.datetime_utcnow')
    def _test_fetch_version(self, version, mock_utcnow, from_date=None, reviews_api=False):
        """Test whether the pages with their reviews are returned"""

        HTTPServer.routes(version)

        mock_utcnow.return_value = datetime.datetime(2016, 6, 10,
                                                     tzinfo=dateutil.tz.tzutc())

        # Test fetch pages with their reviews
        mediawiki = MediaWiki(MEDIAWIKI_SERVER_URL)

        if from_date:
            # Set flag to ignore MAX_RECENT_DAYS exception
            mediawiki._test_mode = True
            pages = [page for page in mediawiki.fetch(from_date=from_date, reviews_api=reviews_api)]
        else:
            pages = [page for page in mediawiki.fetch(reviews_api=reviews_api)]

        if version == "1.28" and reviews_api:
            # 2 pages in all name spaces
            self.assertEqual(len(pages), 2)
        elif version == "1.23" or not reviews_api:
            if not from_date:
                # 2 pages per each of the 5 name spaces
                self.assertEqual(len(pages), 2)
            else:
                # 1 page in recent changes
                self.assertEqual(len(pages), 2)

        HTTPServer.check_pages_contents(self, pages)


class TestMediaWikiBackend_1_23(TestMediaWikiBackend):
    """MediaWiki backend tests for MediaWiki 1.23 version"""

    def test_fetch(self):
        with self.assertLogs(logger, level='WARNING') as cm:
            self._test_fetch_version("1.23")
            self.assertEqual(cm.output[0],
                             'WARNING:perceval.backends.core.mediawiki:Revisions not found in NewEditor:Test '
                             '[page id: 476589], page skipped')

        with self.assertLogs(logger, level='WARNING') as cm:
            self._test_fetch_version("1.23", reviews_api=True)
            self.assertEqual(cm.output[2],
                             'WARNING:perceval.backends.core.mediawiki:Revisions not found in NewEditor:Test '
                             '[page id: 476589], page skipped')

        self._test_search_fields("1.23")

    @httpretty.activate
    def test_fetch_from_date(self):
        from_date = dateutil.parser.parse("2016-06-23 15:35")

        with self.assertLogs(logger, level='WARNING') as cm:
            self._test_fetch_version("1.23", from_date=from_date)
            self.assertEqual(cm.output[0],
                             'WARNING:perceval.backends.core.mediawiki:Revisions not found in OldEditor:Test '
                             '[page id: 476589], page skipped')
            self.assertIn('WARNING:perceval.backends.core.mediawiki:Missing pageid in page', cm.output[1])

    @httpretty.activate
    def test_fetch_empty(self):
        """Test whether it works when no pages are fetched"""

        HTTPServer.routes("1.23", empty=True)

        mediawiki = MediaWiki(MEDIAWIKI_SERVER_URL)
        pages = [page for page in mediawiki.fetch()]

        self.assertEqual(len(pages), 0)


class TestMediaWikiBackend_1_28(TestMediaWikiBackend):
    """MediaWiki backend tests for MediaWiki 1.28 version"""

    def test_fetch(self):
        with self.assertLogs(logger, level='WARNING') as cm:
            self._test_fetch_version("1.28")
            self.assertEqual(cm.output[0],
                             'WARNING:perceval.backends.core.mediawiki:Revisions not found in NewEditor:Test '
                             '[page id: 476589], page skipped')

        with self.assertLogs(logger, level='WARNING') as cm:
            self._test_fetch_version("1.28", reviews_api=True)
            self.assertEqual(cm.output[0],
                             'WARNING:perceval.backends.core.mediawiki:Revisions not found in NewEditor:Test '
                             '[page id: 476589], page skipped')

        self._test_search_fields("1.28")

    @httpretty.activate
    def test_fetch_from_date(self):
        from_date = dateutil.parser.parse("2016-06-23 15:35")

        with self.assertLogs(logger, level='WARNING') as cm:
            self._test_fetch_version("1.28", from_date=from_date)
            self.assertEqual(cm.output[0],
                             'WARNING:perceval.backends.core.mediawiki:Revisions not found in OldEditor:Test '
                             '[page id: 476589], page skipped')
            self.assertIn('WARNING:perceval.backends.core.mediawiki:Missing pageid in page', cm.output[1])

        with self.assertLogs(logger, level='WARNING') as cm:
            self._test_fetch_version("1.28", from_date=from_date, reviews_api=True)
            self.assertEqual(cm.output[0],
                             'WARNING:perceval.backends.core.mediawiki:Revisions not found in NewEditor:Test '
                             '[page id: 476589], page skipped')

    @httpretty.activate
    def test_fetch_empty_1_28(self):
        """Test whether it works when no pages are fetched"""

        HTTPServer.routes("1.28", empty=True)

        mediawiki = MediaWiki(MEDIAWIKI_SERVER_URL)
        pages = [page for page in mediawiki.fetch()]

        self.assertEqual(len(pages), 0)


class TestMediaWikiBackendArchive(TestCaseBackendArchive):
    """MediaWiki backend tests using an archive"""

    def setUp(self):
        super().setUp()
        self.backend_write_archive = MediaWiki(MEDIAWIKI_SERVER_URL, archive=self.archive)
        self.backend_read_archive = MediaWiki(MEDIAWIKI_SERVER_URL, archive=self.archive)

    @httpretty.activate
    @unittest.mock.patch('perceval.backends.core.mediawiki.datetime_utcnow')
    def _test_version(self, version, mock_utcnow, reviews_api=False):
        """Test whether the archive works"""

        HTTPServer.routes(version)
        mock_utcnow.return_value = datetime.datetime(2016, 6, 10,
                                                     tzinfo=dateutil.tz.tzutc())

        from_date = dateutil.parser.parse("2016-06-23 15:35")

        self._test_fetch_from_archive(from_date=from_date, reviews_api=reviews_api)


class TestMediaWikiBackendArchive1_23(TestMediaWikiBackendArchive):
    """MediaWiki backend tests using an archive for MediaWiki 1.23 version"""

    @httpretty.activate
    def test_fetch_from_archive(self):
        """Test whether the archive works"""

        with self.assertLogs(logger, level='WARNING') as cm:
            self._test_version("1.23")
            self.assertEqual(cm.output[0],
                             'WARNING:perceval.backends.core.mediawiki:Revisions not found in OldEditor:Test '
                             '[page id: 476589], page skipped')
            self.assertIn('WARNING:perceval.backends.core.mediawiki:Missing pageid in page', cm.output[1])


class TestMediaWikiBackendArchive1_28(TestMediaWikiBackendArchive):
    """MediaWiki backend tests using an archive for MediaWiki 1.28 version"""

    @httpretty.activate
    def test_fetch_from_archive(self):
        """Test whether the archive works"""

        with self.assertLogs(logger, level='WARNING') as cm:
            self._test_version("1.28")
            self.assertEqual(cm.output[0],
                             'WARNING:perceval.backends.core.mediawiki:Revisions not found in OldEditor:Test '
                             '[page id: 476589], page skipped')
            self.assertIn('WARNING:perceval.backends.core.mediawiki:Missing pageid in page', cm.output[1])

    @httpretty.activate
    def test_fetch_from_archive_reviews(self):
        """Test whether the archive works"""

        with self.assertLogs(logger, level='WARNING') as cm:
            self._test_version("1.28", reviews_api=True)
            self.assertEqual(cm.output[0],
                             'WARNING:perceval.backends.core.mediawiki:Revisions not found in NewEditor:Test '
                             '[page id: 476589], page skipped')


class TestMediaWikiClient(unittest.TestCase):
    """MediaWiki API client tests."""

    @httpretty.activate
    def test_get_namespaces(self):
        HTTPServer.routes()
        body = read_file('data/mediawiki/mediawiki_namespaces.json')
        client = MediaWikiClient(MEDIAWIKI_SERVER_URL)
        response = client.get_namespaces()
        req = HTTPServer.requests_http[-1]
        self.assertEqual(response, body)
        self.assertEqual(req.method, 'GET')
        self.assertRegex(req.path, '/api.php')
        # Check request params
        expected = {
            'action': ['query'],
            'meta': ['siteinfo'],
            'siprop': ['namespaces'],
            'format': ['json']
        }
        self.assertDictEqual(req.querystring, expected)

    @httpretty.activate
    def __test_get_version(self, version, response_num=200):
        if response_num != 200:
            HTTPServer.routes('1.28', response_num=response_num)
        elif version == "1.23":
            HTTPServer.routes('1.23')
            body = read_file('data/mediawiki/mediawiki_siteinfo_1.23.json')
            response_ok = [1, 23]
        elif version == "1.28":
            HTTPServer.routes('1.28')
            body = read_file('data/mediawiki/mediawiki_siteinfo_1.28.json')
            response_ok = [1, 28]
        else:
            self.assertEqual(False)
        client = MediaWikiClient(MEDIAWIKI_SERVER_URL)
        response = client.get_version()
        req = HTTPServer.requests_http[-1]
        self.assertEqual(response, response_ok)
        self.assertEqual(req.method, 'GET')
        self.assertRegex(req.path, '/api.php')
        # Check request params
        expected = {
            'action': ['query'],
            'meta': ['siteinfo'],
            'format': ['json']
        }
        self.assertDictEqual(req.querystring, expected)

    @httpretty.activate
    def test_get_version_1_23(self):
        self.__test_get_version('1.23')

    @httpretty.activate
    def test_get_version_1_28(self):
        self.__test_get_version('1.28')

    @httpretty.activate
    def test_get_version_exception(self):
        with self.assertRaises(BackendError):
            self.__test_get_version('1.28', response_num=401)

    @httpretty.activate
    def test_get_pages(self):
        HTTPServer.routes()
        body = read_file('data/mediawiki/mediawiki_pages_all.json')
        client = MediaWikiClient(MEDIAWIKI_SERVER_URL)
        namespace = '0'
        response = client.get_pages(namespace)
        req = HTTPServer.requests_http[-1]
        self.assertEqual(response, body)
        self.assertEqual(req.method, 'GET')
        self.assertRegex(req.path, '/api.php')
        # Check request params
        expected = {
            'action': ['query'],
            'list': ['allpages'],
            'apnamespace': ['0'],
            'aplimit': ['max'],
            'format': ['json']
        }
        self.assertDictEqual(req.querystring, expected)

    @httpretty.activate
    def test_get_pages_apcontinue(self):
        HTTPServer.routes()
        body = read_file('data/mediawiki/mediawiki_pages_all.json')
        client = MediaWikiClient(MEDIAWIKI_SERVER_URL)
        namespace = '0'
        response = client.get_pages(namespace, apcontinue="xxx")
        req = HTTPServer.requests_http[-1]
        self.assertEqual(response, body)
        self.assertEqual(req.method, 'GET')
        self.assertRegex(req.path, '/api.php')
        # Check request params
        expected = {
            'action': ['query'],
            'list': ['allpages'],
            'apnamespace': ['0'],
            'aplimit': ['max'],
            'format': ['json'],
            'apcontinue': ['xxx']
        }
        self.assertDictEqual(req.querystring, expected)

    @httpretty.activate
    def test_get_recent_pages(self):
        HTTPServer.routes()
        body = read_file('data/mediawiki/mediawiki_pages_recent_changes.json')
        client = MediaWikiClient(MEDIAWIKI_SERVER_URL)
        namespaces = ['0']
        response = client.get_recent_pages(namespaces)
        req = HTTPServer.requests_http[-1]
        self.assertEqual(response, body)
        self.assertEqual(req.method, 'GET')
        self.assertRegex(req.path, '/api.php')
        # Check request params
        expected = {
            'action': ['query'],
            'list': ['recentchanges'],
            'format': ['json'],
            'rclimit': ['max'],
            'rcnamespace': ['0'],
            'rcprop': ['title|timestamp|ids']
        }
        self.assertDictEqual(req.querystring, expected)

    @httpretty.activate
    def test_get_recent_pages_rccontinue(self):
        HTTPServer.routes()
        body = read_file('data/mediawiki/mediawiki_pages_recent_changes.json')
        client = MediaWikiClient(MEDIAWIKI_SERVER_URL)
        namespaces = ['0']
        response = client.get_recent_pages(namespaces, rccontinue="xxx")
        req = HTTPServer.requests_http[-1]
        self.assertEqual(response, body)
        self.assertEqual(req.method, 'GET')
        self.assertRegex(req.path, '/api.php')
        # Check request params
        expected = {
            'action': ['query'],
            'list': ['recentchanges'],
            'format': ['json'],
            'rclimit': ['max'],
            'rcnamespace': ['0'],
            'rcprop': ['title|timestamp|ids'],
            'rccontinue': ['xxx']
        }
        self.assertDictEqual(req.querystring, expected)

    @httpretty.activate
    def test_get_revisions(self):
        HTTPServer.routes()
        body = read_file('data/mediawiki/mediawiki_page_476583_revisions.json')
        client = MediaWikiClient(MEDIAWIKI_SERVER_URL)
        response = client.get_revisions(476583)
        req = HTTPServer.requests_http[-1]
        self.assertEqual(response, body)
        self.assertEqual(req.method, 'GET')
        self.assertRegex(req.path, '/api.php')
        # Check request params
        expected = {
            'action': ['query'],
            'prop': ['revisions'],
            'pageids': ['476583'],
            'format': ['json'],
            'rvlimit': ['max'],
            'rvdir': ['newer']
        }
        self.assertDictEqual(req.querystring, expected)

    @httpretty.activate
    def test_get_revisions_last_date(self):
        HTTPServer.routes()
        body = read_file('data/mediawiki/mediawiki_page_476583_revisions.json')
        client = MediaWikiClient(MEDIAWIKI_SERVER_URL)

        str_date = '2016-01-01 00:00'
        dt = str_to_datetime(str_date)
        response = client.get_revisions(476583, last_date=dt)
        req = HTTPServer.requests_http[-1]
        self.assertEqual(response, body)
        self.assertEqual(req.method, 'GET')
        self.assertRegex(req.path, '/api.php')
        # Check request params
        expected = {
            'action': ['query'],
            'prop': ['revisions'],
            'pageids': ['476583'],
            'format': ['json'],
            'rvlimit': ['max'],
            'rvdir': ['newer'],
            'rvstart': ['2016-01-01T00:00:00 00:00']
        }
        self.assertDictEqual(req.querystring, expected)

    @httpretty.activate
    def test_get_pages_from_allrevisions(self):
        HTTPServer.routes()
        body = read_file('data/mediawiki/mediawiki_pages_allrevisions.json')
        client = MediaWikiClient(MEDIAWIKI_SERVER_URL)
        namespaces = ['0']
        response = client.get_pages_from_allrevisions(namespaces)
        req = HTTPServer.requests_http[-1]
        self.assertEqual(response, body)
        self.assertEqual(req.method, 'GET')
        self.assertRegex(req.path, '/api.php')
        # Check request params
        expected = {
            'action': ['query'],
            'list': ['allrevisions'],
            'arvnamespace': ['0'],
            'arvdir': ['newer'],
            'arvlimit': ['max'],
            'format': ['json'],
            'arvprop': ['ids']
        }
        self.assertDictEqual(req.querystring, expected)

    @httpretty.activate
    def test_get_pages_from_allrevisions_from_date(self):
        HTTPServer.routes()
        body = read_file('data/mediawiki/mediawiki_pages_allrevisions.json')
        client = MediaWikiClient(MEDIAWIKI_SERVER_URL)
        namespaces = ['0']
        str_date = '2016-01-01 00:00'
        dt = str_to_datetime(str_date)
        from_date = datetime_to_utc(dt)
        response = client.get_pages_from_allrevisions(namespaces, from_date)
        req = HTTPServer.requests_http[-1]
        self.assertEqual(response, body)
        self.assertEqual(req.method, 'GET')
        self.assertRegex(req.path, '/api.php')
        # Check request params
        expected = {
            'action': ['query'],
            'list': ['allrevisions'],
            'arvnamespace': ['0'],
            'arvdir': ['newer'],
            'arvlimit': ['max'],
            'format': ['json'],
            'arvprop': ['ids'],
            'arvstart': ['2016-01-01T00:00:00Z']
        }
        self.assertDictEqual(req.querystring, expected)

        from_date = datetime.datetime(2016, 1, 1, 0, 0, 0)

        with self.assertRaises(ValueError):
            _ = client.get_pages_from_allrevisions(namespaces, from_date)

    @httpretty.activate
    def test_get_pages_from_allrevisions_arvcontinue(self):
        HTTPServer.routes()
        body = read_file('data/mediawiki/mediawiki_pages_allrevisions.json')
        client = MediaWikiClient(MEDIAWIKI_SERVER_URL)
        namespaces = ['0']
        response = client.get_pages_from_allrevisions(namespaces, arvcontinue="xxx")
        req = HTTPServer.requests_http[-1]
        self.assertEqual(response, body)
        self.assertEqual(req.method, 'GET')
        self.assertRegex(req.path, '/api.php')
        # Check request params
        expected = {
            'action': ['query'],
            'list': ['allrevisions'],
            'arvnamespace': ['0'],
            'arvdir': ['newer'],
            'arvlimit': ['max'],
            'format': ['json'],
            'arvprop': ['ids'],
            'arvcontinue': ['xxx']
        }
        self.assertDictEqual(req.querystring, expected)


class TestMediaWikiCommand(unittest.TestCase):
    """Tests for MediaWikiCommand class"""

    def test_backend_class(self):
        """Test if the backend class is MediaWiki"""

        self.assertIs(MediaWikiCommand.BACKEND, MediaWiki)

    def test_setup_cmd_parser(self):
        """Test if it parser object is correctly initialized"""

        parser = MediaWikiCommand.setup_cmd_parser()
        self.assertIsInstance(parser, BackendCommandArgumentParser)
        self.assertEqual(parser._backend, MediaWiki)

        args = ['--tag', 'test',
                '--no-archive', '--from-date', '1970-01-01',
                MEDIAWIKI_SERVER_URL]

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.url, MEDIAWIKI_SERVER_URL)
        self.assertEqual(parsed_args.tag, 'test')
        self.assertTrue(parsed_args.no_archive)
        self.assertTrue(parsed_args.ssl_verify)
        self.assertEqual(parsed_args.from_date, DEFAULT_DATETIME)

        args = ['--tag', 'test', '--no-ssl-verify',
                '--no-archive', '--from-date', '1970-01-01',
                MEDIAWIKI_SERVER_URL]

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.url, MEDIAWIKI_SERVER_URL)
        self.assertEqual(parsed_args.tag, 'test')
        self.assertTrue(parsed_args.no_archive)
        self.assertFalse(parsed_args.ssl_verify)
        self.assertEqual(parsed_args.from_date, DEFAULT_DATETIME)


if __name__ == "__main__":
    unittest.main(warnings='ignore')
