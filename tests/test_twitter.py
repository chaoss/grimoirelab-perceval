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
#     Jesus M. Gonzalez-Barahona <jgb@gsyc.es>
#     Harshal Mittal <harshalmittal4@gmail.com>
#

import datetime
import os
import requests
import time
import unittest
import unittest.mock

import dateutil
import httpretty
import pkg_resources

pkg_resources.declare_namespace('perceval.backends')

from grimoirelab_toolkit.datetime import str_to_datetime
from perceval.backend import BackendCommandArgumentParser
from perceval.errors import BackendError, RateLimitError
from perceval.backends.core.twitter import (Twitter,
                                            TwitterCommand,
                                            TwitterClient,
                                            MIN_RATE_LIMIT,
                                            TWEET_TYPE_POPULAR)
from base import TestCaseBackendArchive


TWITTER_API_URL = 'https://api.twitter.com/1.1/search/tweets.json'


def setup_http_server(no_tweets=False, rate_limit=None, reset_rate_limit=None, status=200):
    """Setup a mock HTTP server"""

    headers = {}
    headers['x-rate-limit-remaining'] = '20' if not rate_limit else rate_limit
    headers['x-rate-limit-reset'] = '15' if not reset_rate_limit else reset_rate_limit

    if no_tweets:
        tweets_page_empty = read_file('data/twitter/tweets_page_3.json')

        httpretty.register_uri(httpretty.GET,
                               TWITTER_API_URL +
                               "?q=query",
                               body=tweets_page_empty,
                               status=200,
                               forcing_headers=headers)
        return

    tweets_page_1 = read_file('data/twitter/tweets_page_1.json')
    tweets_page_2 = read_file('data/twitter/tweets_page_2.json')
    tweets_page_3 = read_file('data/twitter/tweets_page_3.json')

    httpretty.register_uri(httpretty.GET,
                           TWITTER_API_URL +
                           "?q=query&max_id=1005163131042193407",
                           body=tweets_page_3,
                           status=status,
                           forcing_headers=headers)

    httpretty.register_uri(httpretty.GET,
                           TWITTER_API_URL +
                           "?q=query",
                           body=tweets_page_1,
                           status=status,
                           forcing_headers=headers)

    httpretty.register_uri(httpretty.GET,
                           TWITTER_API_URL +
                           "?q=query&max_id=1005148958111555583",
                           body=tweets_page_2,
                           status=status,
                           forcing_headers=headers)


def read_file(filename, mode='r'):
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), filename), mode) as f:
        content = f.read()
    return content


class MockedTwitterClient(TwitterClient):

    def calculate_time_to_reset(self):

        return 1


class TestTwitterBackend(unittest.TestCase):
    """Twitter backendtests"""

    @httpretty.activate
    def test_initialization(self):
        """Test whether attributes are initializated"""

        twitter = Twitter('query', 'my-token', max_items=5, tag='test',
                          sleep_for_rate=True, min_rate_to_sleep=10, sleep_time=60)

        self.assertEqual(twitter.origin, 'https://twitter.com/')
        self.assertEqual(twitter.tag, 'test')
        self.assertEqual(twitter.query, 'query')
        self.assertEqual(twitter.max_items, 5)
        self.assertTrue(twitter.sleep_for_rate)
        self.assertEqual(twitter.min_rate_to_sleep, 10)
        self.assertEqual(twitter.sleep_time, 60)
        self.assertIsNone(twitter.client)
        self.assertTrue(twitter.ssl_verify)

        # When tag is empty or None it will be set to the value in URL
        twitter = Twitter('query', 'my-token', ssl_verify=False)
        self.assertEqual(twitter.origin, 'https://twitter.com/')
        self.assertEqual(twitter.tag, 'https://twitter.com/')
        self.assertFalse(twitter.ssl_verify)

        twitter = Twitter('query', 'my-token', tag='')
        self.assertEqual(twitter.origin, 'https://twitter.com/')
        self.assertEqual(twitter.tag, 'https://twitter.com/')

    def test_initialization_long_query(self):
        """Test whether an exception is thrown when the search query is too long"""

        long_query = ''.join(['a' for i in range(0, 500)])
        with self.assertRaises(BackendError):
            _ = Twitter(long_query, 'my-token', max_items=5, tag='test',
                        sleep_for_rate=True, min_rate_to_sleep=10, sleep_time=60)

    def test_has_resuming(self):
        """Test if it returns False when has_resuming is called"""

        self.assertEqual(Twitter.has_resuming(), False)

    def test_has_archiving(self):
        """Test if it returns True when has_archiving is called"""

        self.assertEqual(Twitter.has_archiving(), True)

    @httpretty.activate
    def test_fetch_tweets(self):
        """Test whether a list of tweets is returned"""

        setup_http_server()
        twitter = Twitter('query', 'my-token', max_items=2)
        tweets = [tweets for tweets in twitter.fetch()]

        expected = ['1005149094560530432', '1005148958111555584', '1005277806383673344', '1005163131042193408']

        self.assertEqual(len(tweets), 4)
        for i in range(len(tweets)):
            tweet = tweets[i]
            self.assertEqual(tweet['data']['id_str'], expected[i])
            self.assertEqual(tweet['origin'], 'https://twitter.com/')
            self.assertEqual(tweet['updated_on'], str_to_datetime(tweet['data']['created_at']).timestamp())
            self.assertEqual(tweet['category'], 'tweet')
            self.assertEqual(tweet['tag'], 'https://twitter.com/')

    @httpretty.activate
    def test_search_fields(self):
        """Test whether the search_fields is properly set"""

        setup_http_server()
        twitter = Twitter('query', 'my-token', max_items=2)
        tweets = [tweets for tweets in twitter.fetch()]

        tweet = tweets[0]
        hashtags = [h['text'] for h in tweet['data']['entities'].get('hashtags', [])]
        self.assertEqual(twitter.metadata_id(tweet['data']), tweet['search_fields']['item_id'])
        self.assertListEqual(hashtags, ['openexpoeurope'])
        self.assertListEqual(tweet['search_fields']['hashtags'], ['openexpoeurope'])

        tweet = tweets[1]
        hashtags = [h['text'] for h in tweet['data']['entities'].get('hashtags', [])]
        self.assertEqual(twitter.metadata_id(tweet['data']), tweet['search_fields']['item_id'])
        self.assertListEqual(hashtags, ['OpenExpo18'])
        self.assertListEqual(tweet['search_fields']['hashtags'], ['OpenExpo18'])

        tweet = tweets[2]
        hashtags = [h['text'] for h in tweet['data']['entities'].get('hashtags', [])]
        self.assertEqual(twitter.metadata_id(tweet['data']), tweet['search_fields']['item_id'])
        self.assertListEqual(hashtags, ['structure', 'community'])
        self.assertListEqual(tweet['search_fields']['hashtags'], ['structure', 'community'])

    @httpretty.activate
    def test_fetch_no_tweets(self):
        """Test whether an empty list is returned if no tweets are available"""

        setup_http_server(no_tweets=True)

        twitter = Twitter('query', 'my-token', max_items=2)
        tweets = [tweets for tweets in twitter.fetch()]

        self.assertEqual(tweets, [])


class TestTwitterBackendArchive(TestCaseBackendArchive):
    """Twitter backend tests using an archive"""

    def setUp(self):
        super().setUp()
        self.backend_write_archive = Twitter('query', 'my-token', archive=self.archive)
        self.backend_read_archive = Twitter('query', 'my-token', archive=self.archive)

    @httpretty.activate
    def test_fetch_tweets_from_archive(self):
        """Test whether a list of tweets is returned from archive"""

        setup_http_server()
        self._test_fetch_from_archive()

    @httpretty.activate
    def test_fetch_from_empty_archive(self):
        """Test whether no issues are returned when the archive is empty"""

        setup_http_server(no_tweets=True)
        self._test_fetch_from_archive()


class TestTwitterClient(unittest.TestCase):
    """Twitter API client tests"""

    def test_init(self):
        """Test initialization"""

        client = TwitterClient('aaaa', max_items=10)
        self.assertEqual(client.api_key, 'aaaa')
        self.assertEqual(client.max_items, 10)
        self.assertFalse(client.sleep_for_rate)
        self.assertEqual(client.min_rate_to_sleep, MIN_RATE_LIMIT)
        self.assertTrue(client.ssl_verify)

        client = TwitterClient('aaaa', max_items=10,
                               sleep_for_rate=True,
                               min_rate_to_sleep=4)
        self.assertEqual(client.api_key, 'aaaa')
        self.assertEqual(client.max_items, 10)
        self.assertTrue(client.sleep_for_rate)
        self.assertEqual(client.min_rate_to_sleep, 4)

        # Max rate limit is never overtaken
        client = TwitterClient('aaaa', max_items=10,
                               sleep_for_rate=True,
                               min_rate_to_sleep=100000000,
                               ssl_verify=False)
        self.assertEqual(client.min_rate_to_sleep, client.MAX_RATE_LIMIT)
        self.assertFalse(client.ssl_verify)

    @httpretty.activate
    def test_tweets_no_params(self):
        """Test tweets API call with no params"""

        setup_http_server()

        client = TwitterClient("aaa", max_items=2)
        group_tweets = client.tweets("query")
        group_tweets = [tweets for tweets in group_tweets]

        self.assertEqual(len(group_tweets), 2)

        # Check requests
        expected = {
            'q': ['query'],
            'count': ['2'],
            'max_id': ['1005163131042193407'],
            'include_entities': ['True'],
            'result_type': ['mixed']
        }

        self.assertDictEqual(httpretty.last_request().querystring, expected)
        self.assertEqual(httpretty.last_request().headers["Authorization"], "Bearer aaa")

    @httpretty.activate
    def test_tweets_params(self):
        """Test tweets API call with params"""

        setup_http_server()

        client = TwitterClient("aaa", max_items=2)
        group_tweets = client.tweets("query", since_id=1, max_id=1005163131042193407,
                                     geocode="37.781157 -122.398720 1km", lang="eu",
                                     include_entities=False, result_type=TWEET_TYPE_POPULAR)
        group_tweets = [tweets for tweets in group_tweets]

        self.assertEqual(len(group_tweets), 2)

        expected = {
            'q': ['query'],
            'since_id': ['1'],
            'max_id': ['1005163131042193407'],
            'count': ['2'],
            'include_entities': ['False'],
            'result_type': ['popular'],
            'geocode': ['37.781157 -122.398720 1km'],
            'lang': ['eu']
        }

        self.assertDictEqual(httpretty.last_request().querystring, expected)
        self.assertEqual(httpretty.last_request().headers["Authorization"], "Bearer aaa")

    @unittest.mock.patch('perceval.backends.core.twitter.datetime_utcnow')
    def test_calculate_time_to_reset(self, mock_utcnow):
        """Test whether the time to reset is zero if the sleep time is negative"""

        mock_utcnow.return_value = datetime.datetime(2017, 1, 1,
                                                     tzinfo=dateutil.tz.tzutc())

        client = TwitterClient("aaa", max_items=2)
        client.rate_limit_reset_ts = 0

        time_to_reset = client.calculate_time_to_reset()
        self.assertEqual(time_to_reset, 0)

    @httpretty.activate
    def test_sleep_for_rate(self):
        """Test if the clients sleeps when the rate limit is reached"""

        wait_to_reset = 1
        setup_http_server(rate_limit=1, reset_rate_limit=wait_to_reset)

        client = MockedTwitterClient('aaaa', max_items=2,
                                     min_rate_to_sleep=100,
                                     sleep_for_rate=True)
        before = float(time.time())
        _ = [tweets for tweets in client.tweets('query')]
        after = float(time.time())
        diff = after - before

        self.assertGreaterEqual(diff, wait_to_reset)

    @httpretty.activate
    def test_too_many_requests(self):
        """Test if a Retry error is raised"""

        setup_http_server(status=429)

        client = TwitterClient("aaa", max_items=2, sleep_time=0.1)
        start = float(time.time())
        expected = start + (sum([i * client.sleep_time for i in range(client.MAX_RETRIES)]))

        events = client.tweets('query')
        with self.assertRaises(requests.exceptions.RetryError):
            _ = [event for event in events]

        end = float(time.time())
        self.assertGreater(end, expected)

    @httpretty.activate
    def test_rate_limit_error(self):
        """Test if a rate limit error is raised when rate is exhausted"""

        wait_to_reset = 1
        setup_http_server(rate_limit=1, reset_rate_limit=wait_to_reset)

        client = MockedTwitterClient('aaaa', max_items=2,
                                     min_rate_to_sleep=100)
        with self.assertRaises(RateLimitError):
            [tweets for tweets in client.tweets('query')]

    def test_sanitize_for_archive(self):
        """Test whether the sanitize method works properly"""

        url = "http://example.com"
        headers = {'Authorization': 'Bearer my-token'}
        payload = {'q': 'query',
                   'count': 100,
                   'include_entities': True,
                   'result_type': 'mixed'}

        s_url, s_headers, s_payload = TwitterClient.sanitize_for_archive(url, headers, payload)

        self.assertEqual(url, s_url)
        self.assertEqual({}, s_headers)
        self.assertEqual(payload, s_payload)


class TestTwitterCommand(unittest.TestCase):
    """TwitterCommand unit tests"""

    def test_backend_class(self):
        """Test if the backend class is Twitter"""

        self.assertIs(TwitterCommand.BACKEND, Twitter)

    def test_setup_cmd_parser(self):
        """Test if it parser object is correctly initialized"""

        parser = TwitterCommand.setup_cmd_parser()
        self.assertIsInstance(parser, BackendCommandArgumentParser)
        self.assertEqual(parser._backend, Twitter)

        args = ['--sleep-for-rate',
                '--min-rate-to-sleep', '1',
                '--sleep-time', '10',
                '--tag', 'test',
                '--no-archive',
                '--api-token', 'abcdefgh',
                '--max-items', '10',
                '--no-entities',
                '--geo-code', '37.781157 -122.398720 1mi',
                '--lang', 'eu',
                '--tweets-type', TWEET_TYPE_POPULAR,
                'query']

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.query, 'query')
        self.assertEqual(parsed_args.tweets_type, TWEET_TYPE_POPULAR)
        self.assertEqual(parsed_args.lang, 'eu')
        self.assertEqual(parsed_args.geocode, '37.781157 -122.398720 1mi')
        self.assertFalse(parsed_args.include_entities)
        self.assertEqual(parsed_args.max_items, 10)
        self.assertEqual(parsed_args.api_token, 'abcdefgh')
        self.assertTrue(parsed_args.no_archive)
        self.assertEqual(parsed_args.tag, 'test')
        self.assertEqual(parsed_args.sleep_time, 10)
        self.assertTrue(parsed_args.sleep_for_rate)
        self.assertEqual(parsed_args.min_rate_to_sleep, 1)
        self.assertTrue(parsed_args.ssl_verify)

        args = ['--sleep-for-rate',
                '--min-rate-to-sleep', '1',
                '--sleep-time', '10',
                '--tag', 'test',
                '--no-ssl-verify',
                '--api-token', 'abcdefgh',
                'query']

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.query, 'query')
        self.assertEqual(parsed_args.tag, 'test')
        self.assertEqual(parsed_args.sleep_time, 10)
        self.assertTrue(parsed_args.sleep_for_rate)
        self.assertEqual(parsed_args.min_rate_to_sleep, 1)
        self.assertFalse(parsed_args.ssl_verify)
        self.assertEqual(parsed_args.api_token, 'abcdefgh')


if __name__ == "__main__":
    unittest.main(warnings='ignore')
