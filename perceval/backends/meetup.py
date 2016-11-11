# -*- coding: utf-8 -*-
#
# Copyright (C) 2015-2016 Bitergia
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
#     Santiago Dueñas <sduenas@bitergia.com>
#

import logging

import requests

from ..utils import DEFAULT_DATETIME, datetime_to_utc, urljoin


logger = logging.getLogger(__name__)


MAX_ITEMS = 200


class MeetupClient:
    """Meetup API client.

    Client for fetching information from the Meetup server
    using its REST API v3.

    :param api_key: key needed to use the API
    :param max_items: maximum number of items per request
    """
    MEETUP_API_URL = "https://api.meetup.com/"

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

        params = {
            self.PFIELDS : self.VEVENT_FIELDS,
            self.PSTATUS : self.VSTATUS,
            self.PORDER : self.VUPDATED,
            self.PSCROLL : date,
            self.PPAGE : self.max_items,
        }

        for page in self._fetch(resource, params):
            yield page

    def comments(self, group, event_id):
        """Fetch the comments of a given event."""

        resource = urljoin(group, self.REVENTS, event_id, self.RCOMMENTS)

        params = {
            self.PPAGE : self.max_items
        }

        for page in self._fetch(resource, params):
            yield page

    def rsvps(self, group, event_id):
        """Fetch the rsvps of a given event."""

        resource = urljoin(group, self.REVENTS, event_id, self.RRSVPS)

        params = {
            self.PFIELDS : self.VRSVP_FIELDS,
            self.PPAGE : self.max_items,
            self.PRESPONSE : self.VRESPONSE
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
        url = urljoin(self.MEETUP_API_URL, resource)

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
                    self.PKEY : self.api_key,
                    self.PSIGN : 'true'
                }
            else:
                do_fetch = False
