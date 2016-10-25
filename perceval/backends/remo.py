# -*- coding: utf-8 -*-
#
# Copyright (C) 2016 Bitergia
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
#     Alvaro del Castillo <acs@bitergia.com>
#

import json
import logging
import os.path

import requests

from dateutil import parser

from ..backend import Backend, BackendCommand, metadata
from ..cache import Cache
from ..errors import BackendError, CacheError, ParseError

from ..utils import (DEFAULT_DATETIME,
                     datetime_to_utc,
                     str_to_datetime,
                     urljoin)


logger = logging.getLogger(__name__)

MOZILLA_REPS_URL = "https://reps.mozilla.org"

class ReMo(Backend):
    """ReMo backend for Perceval.

    This class retrieves the events from a ReMo URL. To initialize
    this class an URL may be provided. If not, https://reps.mozilla.org
    will be used. The origin of the data will be set to this URL.

    :param url: ReMo URL
    :param tag: label used to mark the data
    :param cache: cache object to store raw data
    """
    version = '0.4.0'

    def __init__(self, url=None, tag=None, cache=None):
        if not url:
            url = MOZILLA_REPS_URL
        origin = url

        super().__init__(origin, tag=tag, cache=cache)
        self.url = url
        self.client = ReMoClient(url)
        self.__users = {}  # internal users cache

    @metadata
    def fetch(self):
        """Fetch events from the ReMo url.

        The method retrieves, from a ReMo url, the
        events.

        :returns: a generator of events
        """

        logger.info("Looking for events at url '%s'", self.url)

        nevents = 0  # number of events processed
        tevents = 0  # number of events from API data
        nunknown_users = 0 # number os users not found with reps API

        self._purge_cache_queue()

        self.__users = self.__get_all_users()

        for raw_events in self.client.get_events():
            self._push_cache_queue(raw_events)
            events_data = json.loads(raw_events)
            tevents = events_data['meta']['total_count']

            events = events_data['objects']
            for event in events:
                if event["owner_name"] in self.__users:
                    event["owner_data"] = self.__users[event['owner_name']]
                else:
                    nunknown_users += 1
                yield event
                nevents += 1

            self._flush_cache_queue()

        logger.info("Total number of events: %i (%i expected)", nevents, tevents)
        logger.info("Unknown users: %i", nunknown_users)

    @metadata
    def fetch_from_cache(self):
        """Fetch the events from the cache.

        :returns: a generator of events

        :raises CacheError: raised when an error occurs accessing the
            cache
        """

        logger.info("Retrieving cached events: '%s'", self.url)

        if not self.cache:
            raise CacheError(cause="cache instance was not provided")

        cache_items = self.cache.retrieve()

        nevents = 0
        nunknown_users = 0

        users_json = json.loads(next(cache_items))

        for user in users_json['objects']:
            self.__users[user['fullname']] = user

        for items in cache_items:
            events = json.loads(items)['objects']
            for event in events:
                if event["owner_name"] in self.__users:
                    event["owner_data"] = self.__users[event['owner_name']]
                else:
                    nunknown_users += 1
                yield event
                nevents += 1

        logger.info("Retrieval process completed: %s events retrieved from cache",
                    nevents)
        logger.info("Unknown users: %i", nunknown_users)

    @classmethod
    def has_caching(cls):
        """Returns whether it supports caching items on the fetch process.

        :returns: this backend supports items cache
        """
        return True

    @classmethod
    def has_resuming(cls):
        """Returns whether it supports to resume the fetch process.

        :returns: this backend supports items resuming
        """
        return True

    @staticmethod
    def metadata_id(item):
        """Extracts the identifier from a ReMo item."""
        return str(item['event_url'])

    @staticmethod
    def metadata_updated_on(item):
        """Extracts the update time from a ReMo item.

        The timestamp is extracted from 'end' field.
        This date is a UNIX timestamp but needs to be converted to
        a float value.

        :param item: item generated by the backend

        :returns: a UNIX timestamp
        """
        return float(str_to_datetime(item['end']).timestamp())

    @staticmethod
    def metadata_category(item):
        """Extracts the category from a ReMo item.

        This backend only generates one type of item which is
        'event'.
        """
        return 'event'

    def __get_all_users(self):
        """Retrieve all users data"""
        # Get all users and return a dict with them

        if self.__users:
            return self.__users

        # In mozilla reps we have < 400 users
        max_mozilla_reps = 400

        all_users = {}
        raw_users = self.client.get_all_users(max_mozilla_reps)
        self._push_cache_queue(raw_users)

        users_json = json.loads(raw_users)
        nusers = users_json['meta']['total_count']
        self._flush_cache_queue()

        if  nusers > max_mozilla_reps:
            logging.error("Not getting all identities %i (%i retrieved)",
                          nusers, max_mozilla_reps)

        for user in users_json['objects']:
            all_users[user['fullname']] = user

        return(all_users)


class ReMoClient:
    """ReMo API client.

    This class implements a simple client to retrieve events from
    projects in a ReMo site.

    :param url: URL of ReMo (sample https://reps.mozilla.org)

    :raises HTTPError: when an error occurs doing the request
    """

    def __init__(self, url, limit=40):
        # 40 it the max limit for events.
        self.url = url
        self.limit = limit
        self.api_events_url = urljoin(self.url, '/api/v1/event/')
        self.api_events_url += '/'  # API needs a final /
        self.api_reps_url = urljoin(self.url, '/api/v1/rep/')
        self.api_reps_url += '/'  # API needs a final /

    def call(self, uri, params):
        """Run an API command.
        :param params: dict with the HTTP parameters needed to run
            the given command
        """
        logger.debug("ReMo client calls API: %s params: %s",
                     self.api_events_url, str(params))

        req = requests.get(uri, params=params)
        req.raise_for_status()

        return req.text

    def get_all_users(self, max_users=400):
        """Retrieve all users"""

        params = {
            "limit": max_users
        }

        logging.info("Retrieving all users data ...")
        raw_users = self.call(self.api_reps_url, params)

        return raw_users

    def get_events(self):
        """Retrieve all events or reps using pagination """

        more = True # There are more reps to be processed
        next_uri = None # URI for the next reps query
        offset = "0"

        api = self.api_events_url

        while more:
            params = {
                "offset":offset,
                "limit":self.limit
            }

            raw_items = self.call(api, params)
            yield raw_items

            items_data = json.loads(raw_items)
            next_uri = items_data['meta']['next']

            if not next_uri:
                more = False
            else:
                # /api/v1/event/?limit=40&offset=40
                offset = next_uri.split("offset=")[1]


class ReMoCommand(BackendCommand):
    """Class to run ReMo backend from the command line."""

    def __init__(self, *args):
        super().__init__(*args)
        self.url = self.parsed_args.url
        self.tag = self.parsed_args.tag
        self.outfile = self.parsed_args.outfile

        if not self.parsed_args.no_cache:
            if not self.parsed_args.cache_path:
                base_path = os.path.expanduser('~/.perceval/cache/')
            else:
                base_path = self.parsed_args.cache_path

            cache_path = os.path.join(base_path, self.url)

            cache = Cache(cache_path)

            if self.parsed_args.clean_cache:
                cache.clean()
            else:
                cache.backup()
        else:
            cache = None

        self.backend = ReMo(self.url, tag=self.tag, cache=cache)

    def run(self):
        """Fetch and print the Events.

        This method runs the backend to fetch the events of a given url.
        Events are converted to JSON objects and printed to the
        defined output.
        """
        if self.parsed_args.fetch_cache:
            events = self.backend.fetch_from_cache()
        else:
            events = self.backend.fetch()

        try:
            for event in events:
                obj = json.dumps(event, indent=4, sort_keys=True)
                self.outfile.write(obj)
                self.outfile.write('\n')
        except requests.exceptions.HTTPError as e:
            raise requests.exceptions.HTTPError(str(e.response.json()))
        except IOError as e:
            raise RuntimeError(str(e))
        except Exception as e:
            if self.backend.cache:
                self.backend.cache.recover()
            raise RuntimeError(str(e))

    @classmethod
    def create_argument_parser(cls):
        """Returns the ReMo argument parser."""

        parser = super().create_argument_parser()

        # Remove --from-date argument from parent parser
        # because it is not needed by this backend
        action = parser._option_string_actions['--from-date']
        parser._handle_conflict_resolve(None, [('--from-date', action)])


        # ReMo options
        group = parser.add_argument_group('ReMo arguments')

        group.add_argument("url", default="https://reps.mozilla.org", nargs='?',
                           help="ReMo URL (default: https://reps.mozilla.org)")

        return parser
