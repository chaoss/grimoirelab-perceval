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

import json
import logging

import requests

from ..backend import Backend, metadata
from ..errors import CacheError
from ..utils import urljoin


logger = logging.getLogger(__name__)


TELEGRAM_URL = 'https://telegram.org'
DEFAULT_OFFSET = 1


class Telegram(Backend):
    """Telegram backend.

    The Telegram backend fetches the messages that a Telegram bot can
    receive. Usually, these messages are direct or private messages but
    a bot can be configured to receive every message sent to a channel/group
    where it is subscribed. Take into account that messages are removed
    from the Telegram server 24 hours after they are sent. Moreover, once
    they are fetched using an offset, these messages are also removed. This
    means every time this backend is called, messages will be deleted.

    Initialize this class passing the name of the bot and the authentication
    token used by this bot. The authentication token is provided by Telegram
    once the bot is created.

    :param bot: name of the bot
    :param bot_token: authentication token used by the bot
    :param cache: cache object to store raw data
    :param origin: identifier of the repository; when `None` or an
        empty string are given, it will be set to the `TELEGRAM_URL`
        plus the name of the bot; i.e 'http://telegram.org/mybot'.
    """
    version = '0.1.0'

    def __init__(self, bot, bot_token, cache=None, origin=None):
        origin = origin if origin else urljoin(TELEGRAM_URL, bot)

        super().__init__(origin, cache=cache)
        self.bot = bot
        self.client = TelegramBotClient(bot_token)

    @metadata
    def fetch(self, offset=DEFAULT_OFFSET, chats=None):
        """Fetch the messages the bot can read from the server.

        The method retrieves, from the Telegram server, the messages
        sent with an offset equal or greater than the given.

        A list of chats, groups and channels identifiers can be set
        using the parameter `chats`. When it is set, only those
        messages sent to any of these will be returned. An empty list
        will return no messages.

        :param offset: obtain messages from this offset
        :param chats: list of chat names used to filter messages

        :returns: a generator of messages

        :raises ValueError: when `chats` is an empty list
        """
        logger.info("Looking for messages of '%s' bot from offset '%s'",
                    self.bot, offset)

        if chats is not None:
            if len(chats) == 0:
                logger.warning("Chat list filter is empty. No messages will be returned")
            else:
                logger.info("Messages which belong to chats %s will be fetched",
                            '[' + ','.join(str(ch_id) for ch_id in chats) + ']')

        self._purge_cache_queue()

        nmsgs = 0

        while True:
            raw_json = self.client.updates(offset=offset)

            # Due to Telegram deletes the messages from the server
            # when they are fetched, the backend stores these messages
            # in the cache before doing anything.
            self._push_cache_queue(raw_json)
            self._flush_cache_queue()

            messages = [msg for msg in self.parse_messages(raw_json)]

            if len(messages) == 0:
                break

            for msg in messages:
                offset = max(msg['update_id'], offset)

                if not self._filter_message_by_chats(msg, chats):
                    logger.debug("Message %s does not belong to any chat; filtered",
                                 msg['message']['message_id'])
                    continue

                yield msg
                nmsgs += 1

            offset += 1

        logger.info("Fetch process completed: %s messages fetched",
                    nmsgs)

    @metadata
    def fetch_from_cache(self):
        """Fetch the messages from the cache.

        It returns the messages stored in the cache object provided during
        the initialization of the object. If this method is called but
        no cache object was provided, the method will raise a `CacheError`
        exception.

        :returns: a generator of messages

        :raises CacheError: raised when an error occurs accesing the
            cache
        """
        if not self.cache:
            raise CacheError(cause="cache instance was not provided")

        logger.info("Retrieving cached messages: '%s'", self.bot)

        cache_items = self.cache.retrieve()

        nmsgs = 0

        for raw_json in cache_items:
            messages = [msg for msg in self.parse_messages(raw_json)]

            for msg in messages:
                yield msg
                nmsgs += 1

        logger.info("Retrieval process completed: %s messages retrieved from cache",
                    nmsgs)

    def _filter_message_by_chats(self, message, chats):
        """Check if a message can be filtered based in a list of chats.

        This method returns `True` when the message was sent to a chat
        of the given list. It also returns `True` when chats is `None`.

        :param message: Telegram message
        :param chats: list of chat, groups and channels identifiers

        :returns: `True` when the message can be filtered; otherwise,
            it returns `False`
        """
        if chats is None:
            return True

        chat_id = message['message']['chat']['id']

        return chat_id in chats

    @staticmethod
    def metadata_id(item):
        """Extracts the identifier from a Telegram item."""

        return str(item['message']['message_id'])

    @staticmethod
    def metadata_updated_on(item):
        """Extracts and coverts the update time from a Telegram item.

        The timestamp is extracted from 'date' field that is inside
        of 'message' dict. This date is converted to UNIX timestamp
        format.

        :param item: item generated by the backend

        :returns: a UNIX timestamp
        """
        ts = item['message']['date']
        ts = float(ts)

        return ts

    @staticmethod
    def parse_messages(raw_json):
        """Parse a Telegram JSON messages list.

        The method parses the JSON stream and returns an iterator of
        dictionaries. Each one of this, contains a Telegram message.

        :param raw_json: JSON string to parse

        :returns: a generator of parsed messages
        """
        result = json.loads(raw_json)

        messages = result['result']
        for msg in messages:
            yield msg


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
