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

import logging

import requests

from ...errors import BaseError
from ...utils import urljoin


logger = logging.getLogger(__name__)

SLACK_URL = 'https://slack.com/'
MAX_ITEMS = 1000


class SlackClientError(BaseError):
    """Raised when an error occurs using the Slack client"""

    message = "%(error)s"


class SlackClient:
    """Slack API client.

    Client for fetching information from the Slack server
    using its REST API.

    :param api_key: key needed to use the API
    :param max_items: maximum number of items per request
    """
    URL = urljoin(SLACK_URL, 'api', '%(resource)s')

    RCHANNEL_HISTORY = 'channels.history'
    RUSER_INFO = 'users.info'

    PCHANNEL = 'channel'
    PCOUNT = 'count'
    POLDEST = 'oldest'
    PLATEST = 'latest'
    PTOKEN = 'token'
    PUSER = 'user'

    def __init__(self, api_token, max_items=MAX_ITEMS):
        self.api_token = api_token
        self.max_items = max_items

    def history(self, channel, oldest=None, latest=None):
        """Fetch the history of a channel."""

        resource = self.RCHANNEL_HISTORY

        params = {
            self.PCHANNEL : channel,
            self.PCOUNT : self.max_items
        }

        if oldest:
            params[self.POLDEST] = oldest
        if latest:
            params[self.PLATEST] = latest

        response = self._fetch(resource, params)

        return response

    def user(self, user_id):
        """Fetch user info."""

        resource = self.RUSER_INFO

        params = {
            self.PUSER : user_id
        }

        response = self._fetch(resource, params)

        return response

    def _fetch(self, resource, params):
        """Fetch a resource.

        :param resource: resource to get
        :param params: dict with the HTTP parameters needed to get
            the given resource
        """
        url = self.URL % {'resource' : resource}
        params[self.PTOKEN] = self.api_token

        logger.debug("Slack client requests: %s params: %s",
                     resource, str(params))

        r = requests.get(url, params=params)
        r.raise_for_status()

        # Check for possible API errors
        result = r.json()

        if not result['ok']:
            raise SlackClientError(error=result['error'])

        return r.text
