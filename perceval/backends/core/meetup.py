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

import json
import logging

import requests

from ...backend import (Backend,
                        BackendCommand,
                        BackendCommandArgumentParser,
                        metadata)
from ...errors import CacheError
from ...utils import (DEFAULT_DATETIME,
                      datetime_to_utc,
                      urljoin)


logger = logging.getLogger(__name__)


MEETUP_URL = 'https://meetup.com/'
MEETUP_API_URL = 'https://api.meetup.com/'
MAX_ITEMS = 200


class Meetup(Backend):
    """Meetup backend.

    This class allows to fetch the events of a group from the
    Meetup server. Initialize this class passing API key needed
    for authentication with the parameter `api_key`.

    :param group: name of the group where data will be fetched
    :param api_token: token or key needed to use the API
    :param max_items:  maximum number of issues requested on the same query
    :param tag: label used to mark the data
    :param cache: cache object to store raw data
    """
    version = '0.4.0'

    def __init__(self, group, api_token, max_items=MAX_ITEMS,
                 tag=None, cache=None):
        origin = MEETUP_URL

        super().__init__(origin, tag=tag, cache=cache)
        self.group = group
        self.max_items = max_items
        self.client = MeetupClient(api_token, max_items=max_items)

    @metadata
    def fetch(self, from_date=DEFAULT_DATETIME, to_date=None):
        """Fetch the events from the server.

        This method fetches those events of a group stored on the server
        that were updated since the given date. Data comments and rsvps
        are included within each event.

        :param from_date: obtain events updated since this date
        :param to_date: obtain events updated before this date

        :returns: a generator of events
        """
        logger.info("Fetching events of '%s' group from %s to %s",
                    self.group, str(from_date),
                    str(to_date) if to_date else '--')

        self._purge_cache_queue()

        from_date = datetime_to_utc(from_date)
        to_date_ts = datetime_to_utc(to_date).timestamp() if to_date else None

        nevents = 0
        stop_fetching = False

        ev_pages = self.client.events(self.group, from_date=from_date)

        for evp in ev_pages:
            self._push_cache_queue(evp)

            events = [event for event in self.parse_json(evp)]

            for event in events:
                event_id = event['id']

                event['comments'] = self.__fetch_and_parse_comments(event_id)
                event['rsvps'] = self.__fetch_and_parse_rsvps(event_id)

                # Check events updated before 'to_date'
                event_ts = self.metadata_updated_on(event)

                if to_date_ts and event_ts >= to_date_ts:
                    # Comments and RSVPS of items from the current
                    # page be fetched to avoid problems with the cache
                    stop_fetching = True
                    continue

                yield event
                nevents += 1

            self._flush_cache_queue()

            if stop_fetching:
                break

        logger.info("Fetch process completed: %s events fetched", nevents)

    @metadata
    def fetch_from_cache(self):
        """Fetch the events from the cache.

        It returns the events stored in the cache object, provided during
        the initialization of the object. If this method is called but
        no cache object was provided, the method will raise a `CacheError`
        exception.

        :returns: a generator of events

        :raises CacheError: raised when an error occurs accesing the
            cache
        """
        if not self.cache:
            raise CacheError(cause="cache instance was not provided")

        logger.info("Retrieving cached events: %s", self.origin)

        nevents = 0

        for event in self.__fetch_from_cache():
            yield event
            nevents += 1

        logger.info("Retrieval process completed: %s events retrieved from cache",
                    nevents)

    def __fetch_from_cache(self):
        def fetch_items_from_cache(cache_items, checkpoint):
            items = []

            while True:
                raw_page = next(cache_items)
                if raw_page == checkpoint:
                    break
                items += [item for item in self.parse_json(raw_page)]
            return items

        # Fetch from cache starts here
        cache_items = self.cache.retrieve()

        while True:
            try:
                raw_events = next(cache_items)
            except StopIteration:
                break

            events = [event for event in self.parse_json(raw_events)]

            for event in events:
                comments = fetch_items_from_cache(cache_items, '{ENDCOMMENTS}')
                rsvps = fetch_items_from_cache(cache_items, '{ENDRSVPS}')

                event['comments'] = comments
                event['rsvps'] = rsvps

                yield event

    def __fetch_and_parse_comments(self, event_id):
        logger.debug("Fetching and parsing comments from group '%s' event '%s'",
                     self.group, str(event_id))

        comments = []
        raw_pages = self.client.comments(self.group, event_id)

        for raw_page in raw_pages:
            self._push_cache_queue(raw_page)

            for comment in self.parse_json(raw_page):
                comments.append(comment)

        self._push_cache_queue('{ENDCOMMENTS}')

        return comments

    def __fetch_and_parse_rsvps(self, event_id):
        logger.debug("Fetching and parsing rsvps from group '%s' event '%s'",
                     self.group, str(event_id))

        rsvps = []
        raw_pages = self.client.rsvps(self.group, event_id)

        for raw_page in raw_pages:
            self._push_cache_queue(raw_page)

            for rsvp in self.parse_json(raw_page):
                rsvps.append(rsvp)

        self._push_cache_queue('{ENDRSVPS}')

        return rsvps

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
        """Extracts the identifier from a Meetup item."""

        return str(item['id'])

    @staticmethod
    def metadata_updated_on(item):
        """Extracts and coverts the update time from a Meetup item.

        The timestamp is extracted from 'updated' field and converted
        to a UNIX timestamp.

        :param item: item generated by the backend

        :returns: a UNIX timestamp
        """
        # Time is in milliseconds, convert it to seconds
        ts = item['updated']
        ts = ts / 1000.0

        return ts

    @staticmethod
    def metadata_category(item):
        """Extracts the category from a Meetup item.

        This backend only generates one type of item which is
        'event'.
        """
        return 'event'

    @staticmethod
    def parse_json(raw_json):
        """Parse a Meetup JSON stream.

        The method parses a JSON stream and returns a list
        with the parsed data.

        :param raw_json: JSON string to parse

        :returns: a list with the parsed data
        """
        result = json.loads(raw_json)
        return result


class MeetupCommand(BackendCommand):
    """Class to run Meetup backend from the command line."""

    BACKEND = Meetup

    @staticmethod
    def setup_cmd_parser():
        """Returns the Meetup argument parser."""

        parser = BackendCommandArgumentParser(from_date=True,
                                              to_date=True,
                                              token_auth=True,
                                              cache=True)

        # Meetup options
        group = parser.parser.add_argument_group('Meetup arguments')
        group.add_argument('--max-items', dest='max_items',
                           type=int, default=MAX_ITEMS,
                           help="Maximum number of items requested on the same query")

        # Required arguments
        parser.parser.add_argument('group',
                                   help="Meetup group name")

        return parser


class MeetupClient:
    """Meetup API client.

    Client for fetching information from the Meetup server
    using its REST API v3.

    :param api_key: key needed to use the API
    :param max_items: maximum number of items per request
    """
    RCOMMENTS = 'comments'
    REVENTS = 'events'
    RRSVPS = 'rsvps'

    PFIELDS = 'fields'
    PKEY = 'key'
    PORDER = 'order'
    PPAGE = 'page'
    PRESPONSE = 'response'
    PSCROLL = 'scroll'
    PSIGN = 'sign'
    PSTATUS = 'status'

    VEVENT_FIELDS = ['event_hosts', 'featured', 'group_topics',
                     'plain_text_description', 'rsvpable', 'series']
    VRSVP_FIELDS = ['attendance_status']
    VRESPONSE = ['yes', 'no']
    VSTATUS = ['cancelled', 'upcoming', 'past', 'proposed',
               'suggested', 'draft']
    VUPDATED = 'updated'

    def __init__(self, api_key, max_items=MAX_ITEMS):
        self.api_key = api_key
        self.max_items = max_items

    def events(self, group, from_date=DEFAULT_DATETIME):
        """Fetch the events pages of a given group."""

        date = datetime_to_utc(from_date)
        date = date.strftime("since:%Y-%m-%dT%H:%M:%S.000Z")

        resource = urljoin(group, self.REVENTS)

        # Hack required due to Metup API does not support list
        # values with the format `?param=value1&param=value2`.
        # It only works with `?param=value1,value2`.
        # Morever, urrlib3 encodes comma characters when values
        # are given using params dict, which it doesn't work
        # with Meetup, either.
        fixed_params = '?' + self.PFIELDS + '=' + ','.join(self.VEVENT_FIELDS)
        fixed_params += '&' + self.PSTATUS + '=' + ','.join(self.VSTATUS)
        resource += fixed_params

        params = {
            self.PORDER: self.VUPDATED,
            self.PSCROLL: date,
            self.PPAGE: self.max_items
        }

        for page in self._fetch(resource, params):
            yield page

    def comments(self, group, event_id):
        """Fetch the comments of a given event."""

        resource = urljoin(group, self.REVENTS, event_id, self.RCOMMENTS)

        params = {
            self.PPAGE: self.max_items
        }

        for page in self._fetch(resource, params):
            yield page

    def rsvps(self, group, event_id):
        """Fetch the rsvps of a given event."""

        resource = urljoin(group, self.REVENTS, event_id, self.RRSVPS)

        # Same hack that in 'events' method
        fixed_params = '?' + self.PFIELDS + '=' + ','.join(self.VRSVP_FIELDS)
        fixed_params += '&' + self.PRESPONSE + '=' + ','.join(self.VRESPONSE)
        resource += fixed_params

        params = {
            self.PPAGE: self.max_items
        }

        for page in self._fetch(resource, params):
            yield page

    def _fetch(self, resource, params):
        """Fetch a resource.

        Method to fetch and to iterate over the contents of a
        type of resource. The method returns a generator of
        pages for that resource and parameters.

        :param resource: type of the resource
        :param params: parameters to filter

        :returns: a generator of pages for the requeste resource
        """
        url = urljoin(MEETUP_API_URL, resource)

        params[self.PKEY] = self.api_key
        params[self.PSIGN] = 'true',

        do_fetch = True

        while do_fetch:
            logger.debug("Meetup client calls resource: %s params: %s",
                         resource, str(params))

            r = requests.get(url, params=params)
            r.raise_for_status()
            yield r.text

            if r.links and 'next' in r.links:
                url = r.links['next']['url']
                params = {
                    self.PKEY: self.api_key,
                    self.PSIGN: 'true'
                }
            else:
                do_fetch = False
