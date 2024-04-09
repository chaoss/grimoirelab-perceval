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
#     Santiago Dueñas <sduenas@bitergia.com>
#     Stephan Barth <stephan.barth@gmail.com>
#     Valerio Cosentino <valcos@bitergia.com>
#     Jesus M. Gonzalez-Barahona <jgb@gsyc.es>
#     Harshal Mittal <harshalmittal4@gmail.com>
#

import json
import logging
import re

from grimoirelab_toolkit.uris import urijoin

from ...backend import (Backend,
                        BackendCommand,
                        BackendCommandArgumentParser)
from ...client import HttpClient

CATEGORY_MESSAGE = "message"

TELEGRAM_URL = 'https://telegram.org'
DEFAULT_OFFSET = 1

logger = logging.getLogger(__name__)


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

    The origin of the data will be set to the `TELEGRAM_URL` plus the name
    of the bot; i.e 'http://telegram.org/mybot'.

    :param bot: name of the bot
    :param bot_token: authentication token used by the bot
    :param tag: label used to mark the data
    :param archive: archive to store/retrieve items
    :param ssl_verify: enable/disable SSL verification
    """
    version = '1.0.0'

    CATEGORIES = [CATEGORY_MESSAGE]
    EXTRA_SEARCH_FIELDS = {
        'chat_name': ['message', 'chat', 'title'],
        'chat_id': ['message', 'chat', 'id']
    }

    def __init__(self, bot, bot_token, tag=None, archive=None, ssl_verify=True):
        origin = urijoin(TELEGRAM_URL, bot)

        super().__init__(origin, tag=tag, archive=archive, ssl_verify=ssl_verify)
        self.bot = bot
        self.bot_token = bot_token

        self.client = None

    def fetch(self, category=CATEGORY_MESSAGE, offset=DEFAULT_OFFSET, chats=None):
        """Fetch the messages the bot can read from the server.

        The method retrieves, from the Telegram server, the messages
        sent with an offset equal or greater than the given.

        A list of chats, groups and channels identifiers can be set
        using the parameter `chats`. When it is set, only those
        messages sent to any of these will be returned. An empty list
        will return no messages.

        :param category: the category of items to fetch
        :param offset: obtain messages from this offset
        :param chats: list of chat names used to filter messages

        :returns: a generator of messages

        :raises ValueError: when `chats` is an empty list
        """
        if not offset:
            offset = DEFAULT_OFFSET

        kwargs = {"offset": offset, "chats": chats}
        items = super().fetch(category, **kwargs)

        return items

    def fetch_items(self, category, **kwargs):
        """Fetch the messages

        :param category: the category of items to fetch
        :param kwargs: backend arguments

        :returns: a generator of items
        """
        offset = kwargs['offset']
        chats = kwargs['chats']

        logger.info("Looking for messages of '%s' bot from offset '%s'",
                    self.bot, offset)

        if chats is not None:
            if len(chats) == 0:
                logger.warning("Chat list filter is empty. No messages will be returned")
            else:
                logger.info("Messages which belong to chats %s will be fetched",
                            '[' + ','.join(str(ch_id) for ch_id in chats) + ']')

        nmsgs = 0

        while True:
            raw_json = self.client.updates(offset=offset)
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

    def metadata(self, item, filter_classified=False):
        """Telegram metadata.

        The method takes an item and overrides the `metadata` information
        to add extra information related to Telegram.

        Currently, it adds the 'offset' keyword.

        :param item: an item fetched by a backend
        :param filter_classified: sets if classified fields were filtered
        """
        item = super().metadata(item, filter_classified=filter_classified)
        item['offset'] = item['data']['update_id']

        return item

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
        return True

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
    def metadata_category(item):
        """Extracts the category from a Telegram item.

        This backend only generates one type of item which is
        'message'.
        """
        return CATEGORY_MESSAGE

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

            if 'edited_message' in msg:
                edit_message = msg.pop('edited_message')
                edit_date = edit_message.pop('edit_date')
                msg['message'] = edit_message
                msg['message']['date'] = edit_date
                msg['message']['edited'] = True
                logger.debug("Message %s is edited", msg['message']['message_id'])

            yield msg

    def _init_client(self, from_archive=False):
        """Init client"""

        return TelegramBotClient(self.bot_token, self.archive, from_archive, self.ssl_verify)

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


class TelegramCommand(BackendCommand):
    """Class to run Telegram backend from the command line."""

    BACKEND = Telegram

    @classmethod
    def setup_cmd_parser(cls):
        """Returns the Telegram argument parser."""

        aliases = {
            'bot_token': 'api_token'
        }
        parser = BackendCommandArgumentParser(cls.BACKEND,
                                              offset=True,
                                              token_auth=True,
                                              archive=True,
                                              aliases=aliases,
                                              ssl_verify=True)

        # Backend token is required
        action = parser.parser._option_string_actions['--api-token']
        action.required = True

        # Telegram options
        group = parser.parser.add_argument_group('Telegram arguments')
        group.add_argument('--chats', dest='chats',
                           nargs='+', type=int, default=None,
                           help="Fetch only the messages of these chat identifiers")

        # Required arguments
        parser.parser.add_argument('bot',
                                   help="Name of the bot")

        return parser


class TelegramBotClient(HttpClient):
    """Telegram Bot API 2.0 client.

    This class implements a simple client to retrieve those messages
    sent to a Telegram bot. This includes personal messages or
    messages sent to a channel (when privacy settings are disabled).

    :param bot_token: token for the bot
    :param archive: an archive to store/read fetched data
    :param from_archive: it tells whether to write/read the archive
    :param ssl_verify: enable/disable SSL verification
    """
    API_URL = "https://api.telegram.org/bot%(token)s/%(method)s"

    UPDATES_METHOD = 'getUpdates'
    OFFSET = 'offset'

    def __init__(self, bot_token, archive=None, from_archive=False, ssl_verify=True):
        super().__init__(self.API_URL, archive=archive, from_archive=from_archive, ssl_verify=ssl_verify)
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

    @staticmethod
    def sanitize_for_archive(url, headers, payload):
        """Sanitize URL of a HTTP request by removing the token information
        before storing/retrieving archived items

        :param: url: HTTP url request
        :param: headers: HTTP headers request
        :param: payload: HTTP payload request

        :returns the sanitized url, plus the headers and payload
        """
        url = re.sub('bot.*/', 'botXXXXX/', url)

        return url, headers, payload

    def _call(self, method, params):
        """Retrive the given resource.

        :param method: resource to retrieve
        :param params: dict with the HTTP parameters needed to retrieve
            the given resource
        """
        url = self.base_url % {'token': self.bot_token, 'method': method}

        logger.debug("Telegram bot calls method: %s params: %s",
                     method, str(params))

        r = self.fetch(url, payload=params)

        return r.text
