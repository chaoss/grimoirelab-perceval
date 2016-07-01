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


logger = logging.getLogger(__name__)


class TelegramBotClient:
    """Telegram Bot API 2.0 client.

    This class implements a simple client to retrieve those messages
    sent to a Telegram bot. This includes personal messages or
    messages sent to a channel (when privacy settings are disabled).

    :param bot_token: token for the bot
    """
    API_URL = "https://api.telegram.org/bot%(token)s/%(method)s"

    UPDATES_METHOD = 'getUpdates'
    OFFSET = 'offset'


    def __init__(self, bot_token):
        self.bot_token = bot_token

    def updates(self, offset=None):
        """Fetch the messages that a bot can read.

        When the `offset` is given it will retrieve all the messages
        that are greater or equal to that offset. Take into account
        that, due to how the API works, all previous messages will
        be removed from the server.

        :param offset: fetch the messages starting on this offset
        """
        params = {}

        if offset:
            params[self.OFFSET] = offset

        response = self._call(self.UPDATES_METHOD, params)

        return response

    def _call(self, method, params):
        """Retrive the given resource.

        :param resource: resource to retrieve
        :param params: dict with the HTTP parameters needed to retrieve
            the given resource
        """
        url = self.API_URL % {'token' : self.bot_token, 'method' : method}

        logger.debug("Telegram bot calls method: %s params: %s",
                     method, str(params))

        r = requests.get(url, params=params)
        r.raise_for_status()

        return r.text
