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

import json
import logging

from grimoirelab_toolkit.datetime import datetime_utcnow, str_to_datetime

from ...backend import (Backend,
                        BackendCommand,
                        BackendCommandArgumentParser,
                        DEFAULT_SEARCH_FIELD)
from ...client import HttpClient, RateLimitHandler
from ...errors import BackendError

CATEGORY_TWEET = "tweet"
MAX_SEARCH_QUERY = 500

TWITTER_URL = 'https://twitter.com/'
TWITTER_API_URL = 'https://api.twitter.com/1.1/search/tweets.json'
MAX_ITEMS = 100

# Range before sleeping until rate limit reset
MIN_RATE_LIMIT = 1

# Time to avoid too many request exception
SLEEP_TIME = 30

TWEET_TYPE_MIXED = "mixed"
TWEET_TYPE_RECENT = "recent"
TWEET_TYPE_POPULAR = "popular"

RATE_LIMIT_HEADER = "x-rate-limit-remaining"
RATE_LIMIT_RESET_HEADER = "x-rate-limit-reset"

logger = logging.getLogger(__name__)


class Twitter(Backend):
    """Twitter backend.

    This class allows to fetch samples of tweets containing specific
    keywords. Initialize this class passing API key needed
    for authentication with the parameter `api_key`.

    :param query: query to fetch tweets
    :param api_token: token or key needed to use the API
    :param max_items: maximum number of issues requested on the same query
    :param sleep_for_rate: sleep until rate limit is reset
    :param min_rate_to_sleep: minimun rate needed to sleep until
         it will be reset
    :param sleep_time: time (in seconds) to sleep in case
        of connection problems
    :param tag: label used to mark the data
    :param archive: archive to store/retrieve items
    :param ssl_verify: enable/disable SSL verification
    """
    version = '0.4.0'

    CATEGORIES = [CATEGORY_TWEET]

    def __init__(self, query, api_token, max_items=MAX_ITEMS,
                 sleep_for_rate=False, min_rate_to_sleep=MIN_RATE_LIMIT,
                 sleep_time=SLEEP_TIME,
                 tag=None, archive=None, ssl_verify=True):
        origin = TWITTER_URL

        if len(query) >= MAX_SEARCH_QUERY:
            msg = "Search query length exceeded %s, max is %s" % (len(query), MAX_SEARCH_QUERY)
            raise BackendError(cause=msg)

        super().__init__(origin, tag=tag, archive=archive, ssl_verify=ssl_verify)
        self.query = query
        self.api_token = api_token
        self.max_items = max_items
        self.sleep_for_rate = sleep_for_rate
        self.min_rate_to_sleep = min_rate_to_sleep
        self.sleep_time = sleep_time

        self.client = None

    def search_fields(self, item):
        """Add search fields to an item.

        It adds the values of `metadata_id` plus the hashtags of a tweet.

        :param item: the item to extract the search fields values

        :returns: a dict of search fields
        """
        search_fields = {
            DEFAULT_SEARCH_FIELD: self.metadata_id(item)
        }

        entities = item['entities']
        if 'hashtags' in entities:
            search_fields['hashtags'] = [h['text'] for h in entities['hashtags']]

        return search_fields

    def fetch(self, category=CATEGORY_TWEET, since_id=None, max_id=None,
              geocode=None, lang=None,
              include_entities=True, tweets_type=TWEET_TYPE_MIXED):
        """Fetch the tweets from the server.

        This method fetches tweets from the TwitterSearch API published in the last seven days.

        :param category: the category of items to fetch
        :param since_id: if not null, it returns results with an ID greater than the specified ID
        :param max_id: when it is set or if not None, it returns results with an ID less than the specified ID
        :param geocode: if enabled, returns tweets by users located at latitude,longitude,"mi"|"km"
        :param lang: if enabled, restricts tweets to the given language, given by an ISO 639-1 code
        :param include_entities: if disabled, it excludes entities node
        :param tweets_type: type of tweets returned. Default is “mixed”, others are "recent" and "popular"

        :returns: a generator of tweets
        """
        kwargs = {"since_id": since_id,
                  "max_id": max_id,
                  "geocode": geocode,
                  "lang": lang,
                  "include_entities": include_entities,
                  "result_type": tweets_type}
        items = super().fetch(category, **kwargs)

        return items

    def fetch_items(self, category, **kwargs):
        """Fetch the tweets

        :param category: the category of items to fetch
        :param kwargs: backend arguments

        :returns: a generator of items
        """
        since_id = kwargs['since_id']
        max_id = kwargs['max_id']
        geocode = kwargs['geocode']
        lang = kwargs['lang']
        entities = kwargs['include_entities']
        tweets_type = kwargs['result_type']

        logger.info("Fetching tweets %s from %s to %s",
                    self.query, str(since_id),
                    str(max_id) if max_id else '--')

        tweets_ids = []
        min_date = None
        max_date = None
        group_tweets = self.client.tweets(self.query, since_id=since_id, max_id=max_id, geocode=geocode,
                                          lang=lang, include_entities=entities, result_type=tweets_type)

        for tweets in group_tweets:
            for i in range(len(tweets)):
                tweet = tweets[i]
                tweets_ids.append(tweet['id'])

                if tweets[-1] == tweet:
                    min_date = str_to_datetime(tweets[-1]['created_at'])

                if tweets[0] == tweet and not max_date:
                    max_date = str_to_datetime(tweets[0]['created_at'])

                yield tweet

        logger.info("Fetch process completed: %s (unique %s) tweets fetched, from %s to %s",
                    len(tweets_ids), len(list(set(tweets_ids))), min_date, max_date)

    @classmethod
    def has_archiving(cls):
        """Returns whether it supports archiving items on the fetch process.

        :returns: this backend supports items archive
        """
        return True

    @classmethod
    def has_resuming(cls):
        """Returns whether it supports to resume the fetch process.

        :returns: this backend supports items resuming
        """
        return False

    @staticmethod
    def metadata_id(item):
        """Extracts the identifier from a Twitter item."""

        return str(item['id_str'])

    @staticmethod
    def metadata_updated_on(item):
        """Extracts and coverts the update time from a Twitter item.

        The timestamp is extracted from 'created_at' field and converted
        to a UNIX timestamp.

        :param item: item generated by the backend

        :returns: a UNIX timestamp
        """
        ts = item['created_at']
        ts = str_to_datetime(ts)

        return ts.timestamp()

    @staticmethod
    def metadata_category(item):
        """Extracts the category from a Twitter item.

        This backend only generates one type of item which is
        'tweet'.
        """
        return CATEGORY_TWEET

    def _init_client(self, from_archive=False):
        """Init client"""

        return TwitterClient(self.api_token, self.max_items,
                             self.sleep_for_rate, self.min_rate_to_sleep, self.sleep_time,
                             self.archive, from_archive, self.ssl_verify)


class TwitterClient(HttpClient, RateLimitHandler):
    """Twitter API client.

    Client for fetching information from the Twitter server
    using its REST API v1.1.

    :param api_key: key needed to use the API
    :param max_items: maximum number of items per request
    :param sleep_for_rate: sleep until rate limit is reset
    :param min_rate_to_sleep: minimun rate needed to sleep until
         it will be reset
    :param sleep_time: time (in seconds) to sleep in case
        of connection problems
    :param archive: an archive to store/read fetched data
    :param from_archive: it tells whether to write/read the archive
    :param ssl_verify: enable/disable SSL verification
    """
    # API headers
    HAUTHORIZATION = 'Authorization'

    # Resource parameters
    PQUERY = 'q'
    PCOUNT = 'count'
    PSINCE_ID = 'since_id'
    PMAX_ID = 'max_id'
    PGEOCODE = 'geocode'
    PLANG = 'lang'
    PINCLUDE_ENTITIES = 'include_entities'
    PRESULT_TYPE = 'result_type'

    def __init__(self, api_key, max_items=MAX_ITEMS,
                 sleep_for_rate=False, min_rate_to_sleep=MIN_RATE_LIMIT, sleep_time=SLEEP_TIME,
                 archive=None, from_archive=False, ssl_verify=True):
        self.api_key = api_key
        self.max_items = max_items

        super().__init__(TWITTER_API_URL, sleep_time=sleep_time, extra_status_forcelist=[429],
                         archive=archive, from_archive=from_archive, ssl_verify=ssl_verify)
        super().setup_rate_limit_handler(sleep_for_rate=sleep_for_rate, min_rate_to_sleep=min_rate_to_sleep,
                                         rate_limit_header=RATE_LIMIT_HEADER,
                                         rate_limit_reset_header=RATE_LIMIT_RESET_HEADER)

    def calculate_time_to_reset(self):
        """Number of seconds to wait. They are contained in the rate limit reset header"""

        time_to_reset = self.rate_limit_reset_ts - (datetime_utcnow().replace(microsecond=0).timestamp() + 1)
        time_to_reset = 0 if time_to_reset < 0 else time_to_reset

        return time_to_reset

    @staticmethod
    def sanitize_for_archive(url, headers, payload):
        """Sanitize payload of a HTTP request by removing the token information
        before storing/retrieving archived items

        :param: url: HTTP url request
        :param: headers: HTTP headers request
        :param: payload: HTTP payload request

        :returns url, headers and the sanitized payload
        """
        if TwitterClient.HAUTHORIZATION in headers:
            headers.pop(TwitterClient.HAUTHORIZATION)

        return url, headers, payload

    def tweets(self, query, since_id=None, max_id=None, geocode=None, lang=None,
               include_entities=True, result_type=TWEET_TYPE_MIXED):
        """Fetch tweets for a given query between since_id and max_id.

        :param query: query to fetch tweets
        :param since_id: if not null, it returns results with an ID greater than the specified ID
        :param max_id: if not null, it returns results with an ID less than the specified ID
        :param geocode: if enabled, returns tweets by users located at latitude,longitude,"mi"|"km"
        :param lang: if enabled, restricts tweets to the given language, given by an ISO 639-1 code
        :param include_entities: if disabled, it excludes entities node
        :param result_type: type of tweets returned. Default is “mixed”, others are "recent" and "popular"

        :returns: a generator of tweets
        """
        resource = self.base_url
        params = {self.PQUERY: query,
                  self.PCOUNT: self.max_items}

        if since_id:
            params[self.PSINCE_ID] = since_id

        if max_id:
            params[self.PMAX_ID] = max_id

        if geocode:
            params[self.PGEOCODE] = geocode

        if lang:
            params[self.PLANG] = lang

        params[self.PINCLUDE_ENTITIES] = include_entities
        params[self.PRESULT_TYPE] = result_type

        while True:
            raw_tweets = self._fetch(resource, params=params)
            tweets = json.loads(raw_tweets)

            if not tweets['statuses']:
                break

            params[self.PMAX_ID] = tweets['statuses'][-1]['id'] - 1
            yield tweets['statuses']

    def _fetch(self, url, params):
        """Fetch a resource.

        Method to fetch and to iterate over the contents of a
        type of resource. The method returns a generator of
        pages for that resource and parameters.

        :param url: the endpoint of the API
        :param params: parameters to filter

        :returns: the text of the response
        """
        if not self.from_archive:
            self.sleep_for_rate_limit()

        headers = {self.HAUTHORIZATION: 'Bearer ' + self.api_key}
        r = self.fetch(url, payload=params, headers=headers)

        if not self.from_archive:
            self.update_rate_limit(r)

        return r.text


class TwitterCommand(BackendCommand):
    """Class to run Twitter backend from the command line."""

    BACKEND = Twitter

    @classmethod
    def setup_cmd_parser(cls):
        """Returns the Twitter argument parser."""

        parser = BackendCommandArgumentParser(cls.BACKEND,
                                              token_auth=True,
                                              archive=True,
                                              ssl_verify=True)

        # Backend token is required
        action = parser.parser._option_string_actions['--api-token']
        action.required = True

        # Meetup options
        group = parser.parser.add_argument_group('Twitter arguments')
        group.add_argument('--max-items', dest='max_items',
                           type=int, default=MAX_ITEMS,
                           help="Maximum number of items requested on the same query")
        group.add_argument('--no-entities', dest='include_entities',
                           action='store_false',
                           help=" Exclude entities node")
        group.add_argument('--geo-code', dest='geocode',
                           help="Select tweets by users located at latitude,longitude,radius")
        group.add_argument('--lang', dest='lang',
                           help="Select tweets to the given language in ISO 639-1 code")
        group.add_argument('--tweets-type', dest='tweets_type', default=TWEET_TYPE_MIXED,
                           help="Type of tweets returned. Default is 'mixed', others are 'recent' and 'popular'")
        group.add_argument('--sleep-for-rate', dest='sleep_for_rate',
                           action='store_true',
                           help="sleep for getting more rate")
        group.add_argument('--min-rate-to-sleep', dest='min_rate_to_sleep',
                           default=MIN_RATE_LIMIT, type=int,
                           help="sleep until reset when the rate limit reaches this value")
        group.add_argument('--sleep-time', dest='sleep_time',
                           default=SLEEP_TIME, type=int,
                           help="minimun sleeping time to avoid too many request exception")

        # Required arguments
        parser.parser.add_argument('query',
                                   help="Search query including operators, max 500 chars")

        return parser
