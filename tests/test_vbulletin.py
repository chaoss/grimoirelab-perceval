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
#     Alvaro del Castillo <acs@bitergia.com>
#

import datetime
import sys
import unittest

import httpretty
import pkg_resources

# Hack to make sure that tests import the right packages
# due to setuptools behaviour
sys.path.insert(0, '..')
pkg_resources.declare_namespace('perceval.backends')

from perceval.backend import BackendCommandArgumentParser
from perceval.utils import DEFAULT_DATETIME
from perceval.backends.core.vbulletin import (vBulletin,
                                              vBulletinCommand,
                                              vBulletinClient)


VBULLETIN_SERVER_URL = 'http://example.com'
VBULLETIN_API_URL = 'http://example.com/api.php'


def read_file(filename, mode='r'):
    with open(filename, mode) as f:
        content = f.read()
    return content


class TestvBulletinClient(unittest.TestCase):
    """vBulletin API client tests.

    Tests that we parse incoming data effectively and return it,
    and sign things correctly.
    """

    def test_init(self):
        """Test whether attributes are initializated"""

        client = vBulletinClient(VBULLETIN_SERVER_URL,
                                 api_key='aaaa', version="0.1")

        self.assertEqual(client.url, VBULLETIN_SERVER_URL)
        self.assertEqual(client.api_key, 'aaaa')

    def test_signing(self):
        """Test that we calculate signatures correctly"""
        client = vBulletinClient(VBULLETIN_SERVER_URL,
                                 api_key='aaaa', version="0.1")
        client.apiaccesstoken = "access"
        client.apiclientid = "clicli"
        client.secret = "secret"
        result = client._get_request_signature({"one": "two", "three": "four"})
        expected = {'api_c': 'clicli',
                    'api_s': 'access',
                    'api_sig': 'c17c27db7c4bd21b18802766685f4d6c',
                    'api_v': 1}

        self.assertDictEqual(result, expected)

    @httpretty.activate
    def test_forums_page(self):
        """Test forums_page API call"""

        # Set up a mock HTTP server
        api_init = read_file('data/vbulletin_api_init.json')
        forum = read_file('data/vbulletin_forum.json')
        forumdisplay = read_file('data/vbulletin_forumdisplay.json')

        def request_callback(method, uri, headers):
            if "api_init" in uri:
                body = api_init
            elif "forumdisplay" in uri:
                body = forumdisplay
            elif "forum" in uri:
                body = forum
            else:
                raise
            return (200, headers, body)

        httpretty.register_uri(httpretty.GET,
                               VBULLETIN_API_URL,
                               responses=[httpretty.Response(body=request_callback, status=200)])
        # Call API without args
        client = vBulletin(VBULLETIN_SERVER_URL, api_token='aaaa')
        from_date = datetime.datetime(2000, 5, 25, 2, 0, 0)
        response = client.fetch(from_date=from_date)

        threads = list(response)

        self.assertEqual(len(threads), 12)

        # Check request params
        expected = {
            'api_c': ['clicli'],
            'api_m': ['forumdisplay'],
            'api_s': ['accessaccess'],
            'api_sig': ['81fe1f3fc5d8897cd76ae0ac9ccde804'],
            'api_v': ['1'],
            'forumid': ['6']
        }

        req = httpretty.last_request()

        self.assertEqual(req.method, 'GET')
        self.assertRegex(req.path, '/api.php')
        self.assertDictEqual(req.querystring, expected)


class TestvBulletinCommand(unittest.TestCase):
    """Tests for vBulletinCommand class"""

    def test_backend_class(self):
        """Test if the backend class is vBulletin"""

        self.assertIs(vBulletinCommand.BACKEND, vBulletin)

    def test_setup_cmd_parser(self):
        """Test if it parser object is correctly initialized"""

        parser = vBulletinCommand.setup_cmd_parser()
        self.assertIsInstance(parser, BackendCommandArgumentParser)

        args = ['--from-date', '1970-01-01',
                VBULLETIN_SERVER_URL]

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.url, VBULLETIN_SERVER_URL)
        self.assertEqual(parsed_args.from_date, DEFAULT_DATETIME)


if __name__ == "__main__":
    unittest.main(warnings='ignore')
