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
#     Valerio Cosentino <valcos@bitergia.com>
#

import os
import sys
import time
import unittest

import httpretty
import pkg_resources
import requests

# Hack to make sure that tests import the right packages
# due to setuptools behaviour
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
pkg_resources.declare_namespace('perceval.backends')

from perceval.client import HttpClient, RateLimitHandler


CLIENT_API_URL = "https://gateway.marvel.com/v1/"
CLIENT_SPIDERMAN_URL = "https://gateway.marvel.com/v1/public/characters/1"
CLIENT_SUPERMAN_URL = "https://gateway.marvel.com/v1/public/characters/2"
CLIENT_BATMAN_URL = "https://gateway.marvel.com/v1/public/characters/3"
CLIENT_IRONMAN_URL = "https://gateway.marvel.com/v1/public/characters/4"


class MockedClient(HttpClient, RateLimitHandler):

    def __init__(self, base_url, default_sleep_time=0.1, max_retries=1):

        super().__init__(base_url, default_sleep_time=default_sleep_time, max_retries=max_retries)
        super().setup_rate_limit_handler()


class TestHttpClient(unittest.TestCase):
    """Http client tests """

    def test_initialization(self):
        """Test whether attributes are initializated"""

        client = MockedClient(CLIENT_API_URL)

        self.assertEqual(client.base_url, CLIENT_API_URL)
        self.assertEqual(client.max_retries, 1)
        self.assertEqual(client.max_retries_on_connect, HttpClient.MAX_RETRIES_ON_CONNECT)
        self.assertEqual(client.max_retries_on_read, HttpClient.MAX_RETRIES_ON_READ)
        self.assertEqual(client.max_retries_on_redirect, HttpClient.MAX_RETRIES_ON_REDIRECT)
        self.assertEqual(client.max_retries_on_read, HttpClient.MAX_RETRIES_ON_READ)
        self.assertEqual(client.max_retries_on_status, HttpClient.MAX_RETRIES_ON_STATUS)
        self.assertEqual(client.status_forcelist, HttpClient.DEFAULT_STATUS_FORCE_LIST)
        self.assertEqual(client.method_whitelist, HttpClient.DEFAULT_METHOD_WHITELIST)
        self.assertEqual(client.raise_on_redirect, HttpClient.DEFAULT_RAISE_ON_REDIRECT)
        self.assertEqual(client.raise_on_status, HttpClient.DEFAULT_RAISE_ON_STATUS)
        self.assertEqual(client.respect_retry_after_header, HttpClient.DEFAULT_RESPECT_RETRY_AFTER_HEADER)
        self.assertEqual(client.default_sleep_time, 0.1)

        self.assertIsNotNone(client.session)

    @httpretty.activate
    def test_close_session(self):
        """Test wheter the session is properly closed"""

        output = "success"
        httpretty.register_uri(httpretty.GET,
                               CLIENT_SPIDERMAN_URL,
                               body=output,
                               status=200)

        client = MockedClient(CLIENT_API_URL)
        response = client.fetch(CLIENT_SPIDERMAN_URL)
        self.assertEqual(response.headers['connection'], 'close')

    @httpretty.activate
    def test_fetch(self):
        """Test fetch method"""

        output = "success"
        httpretty.register_uri(httpretty.GET,
                               CLIENT_SPIDERMAN_URL,
                               body=output,
                               status=200)

        httpretty.register_uri(httpretty.POST,
                               CLIENT_SPIDERMAN_URL,
                               body=output,
                               status=200)

        httpretty.register_uri(httpretty.GET,
                               CLIENT_SUPERMAN_URL,
                               body=output,
                               status=403)

        client = MockedClient(CLIENT_API_URL)
        response = client.fetch(CLIENT_SPIDERMAN_URL)

        self.assertEqual(response.request.method, HttpClient.GET)
        self.assertEqual(response.text, output)

        response = client.fetch(CLIENT_SPIDERMAN_URL, method=HttpClient.POST)
        self.assertEqual(response.request.method, HttpClient.POST)
        self.assertEqual(response.text, output)

        with self.assertRaises(requests.exceptions.HTTPError):
            _ = client.fetch(CLIENT_SUPERMAN_URL)

    @httpretty.activate
    def test_fetch_retry_after(self):
        """Test whether calls returning 503, 413, 429 status codes are retried"""

        retry_after_value = 1

        httpretty.register_uri(httpretty.GET,
                               CLIENT_SPIDERMAN_URL,
                               body="",
                               status=413,
                               forcing_headers={
                                   'Retry-After': str(retry_after_value)
                               })

        httpretty.register_uri(httpretty.GET,
                               CLIENT_SUPERMAN_URL,
                               body="",
                               status=429,
                               forcing_headers={
                                   'Retry-After': str(retry_after_value)
                               })

        httpretty.register_uri(httpretty.GET,
                               CLIENT_BATMAN_URL,
                               body="",
                               status=503,
                               forcing_headers={
                                   'Retry-After': str(retry_after_value)
                               })

        client = MockedClient(CLIENT_API_URL)

        urls = [CLIENT_SPIDERMAN_URL, CLIENT_SUPERMAN_URL, CLIENT_BATMAN_URL]

        for url in urls:
            before = int(time.time())
            expected = before + (retry_after_value * client.max_retries)

            with self.assertRaises(requests.exceptions.HTTPError):
                _ = client.fetch(url)

            after = int(time.time())
            self.assertTrue(expected <= after)

    @httpretty.activate
    def test_fetch_retry(self):
        """Test whether calls returning redirect status codes and 408, 423, 504 status codes are retried"""

        httpretty.register_uri(httpretty.GET,
                               CLIENT_IRONMAN_URL,
                               body="",
                               status=301)

        httpretty.register_uri(httpretty.GET,
                               CLIENT_SPIDERMAN_URL,
                               body="",
                               status=408)

        httpretty.register_uri(httpretty.GET,
                               CLIENT_SUPERMAN_URL,
                               body="",
                               status=423)

        httpretty.register_uri(httpretty.GET,
                               CLIENT_BATMAN_URL,
                               body="",
                               status=504)

        client = MockedClient(CLIENT_API_URL)

        urls = [CLIENT_SPIDERMAN_URL, CLIENT_SUPERMAN_URL, CLIENT_BATMAN_URL]

        for url in urls:
            with self.assertRaises(requests.exceptions.RetryError):
                _ = client.fetch(url)

    @httpretty.activate
    def test_init_rate_limit(self):
        """Test init rate limit"""

        httpretty.register_uri(httpretty.GET,
                               CLIENT_SPIDERMAN_URL,
                               body="",
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                               })

        httpretty.register_uri(httpretty.GET,
                               CLIENT_SUPERMAN_URL,
                               body="",
                               status=200)

        client = MockedClient(CLIENT_API_URL)
        response = client.fetch(CLIENT_SPIDERMAN_URL)
        client.init_rate_limit(response)

        self.assertEqual(client.rate_limit, 20)
        self.assertEqual(client.rate_limit_reset_ts, 15)

        client = MockedClient(CLIENT_API_URL)
        response = client.fetch(CLIENT_SUPERMAN_URL)
        client.init_rate_limit(response)

        self.assertEqual(client.rate_limit, None)
        self.assertEqual(client.rate_limit_reset_ts, None)


if __name__ == "__main__":
    unittest.main(warnings='ignore')
