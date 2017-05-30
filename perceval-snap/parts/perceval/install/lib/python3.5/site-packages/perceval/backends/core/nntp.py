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

import functools
import io
import logging
import nntplib

import email.parser

from grimoirelab.toolkit.datetime import str_to_datetime

from ...backend import (Backend,
                        BackendCommand,
                        BackendCommandArgumentParser,
                        metadata)
from ...errors import CacheError, ParseError
from ...utils import message_to_dict


# Hack to avoid "line too long" errors
nntplib._MAXLINE = 4096

logger = logging.getLogger(__name__)

DEFAULT_OFFSET = 1


def nntp_metadata(func):
    """NNTP metadata decorator.

    This decorator takes items, overriding `metadata` decorator,
    to add extra information related to NNTP.
    """
    @functools.wraps(func)
    def decorator(self, *args, **kwargs):
        for item in func(self, *args, **kwargs):
            item['offset'] = item['data']['offset']
            yield item
    return decorator


class NNTP(Backend):
    """NNTP backend.

    This class allows to fetch the articles published on a news group
    using NNTP. It is initialized giving the host and the name of the
    news group.

    :param host: host
    :param group: name of the group
    :param tag: label used to mark the data
    :param cache: cache object to store raw data
    """
    version = '0.2.5'

    def __init__(self, host, group, tag=None, cache=None):
        origin = host + '-' + group

        super().__init__(origin, tag=tag, cache=cache)
        self.host = host
        self.group = group

    @nntp_metadata
    @metadata
    def fetch(self, offset=DEFAULT_OFFSET):
        """Fetch articles posted on a news group.

        This method fetches those messages or articles published
        on a news group starting on the given offset.

        :param offset: obtain messages from this offset

        :returns: a generator of articles
        """
        logger.info("Fetching articles of '%s' group on '%s' offset %s",
                    self.group, self.host, str(offset))

        self._purge_cache_queue()

        narts, iarts, tarts = (0, 0, 0)

        # Connect with the server and select the given group
        with nntplib.NNTP(self.host) as client:
            _, _, first, last, _ = client.group(self.group)

            if offset <= last:
                first = max(first, offset)
                _, overview = client.over((first, last))
            else:
                overview = []

            tarts = len(overview)

            logger.debug("Total number of articles to fetch: %s", tarts)

            for article_id, _ in overview:
                try:
                    article = self.__fetch_and_parse_article(client, article_id)
                except ParseError:
                    logger.warning("Error parsing %s article; skipping",
                                   article_id)
                    iarts += 1
                    continue
                except nntplib.NNTPTemporaryError as e:
                    logger.warning("Error '%s' fetching article %s; skipping",
                                   e.response, article_id)
                    iarts += 1
                    continue

                yield article
                narts += 1

                self._flush_cache_queue()

        logger.info("Fetch process completed: %s/%s articles fetched; %s ignored",
                    narts, tarts, iarts)

    @nntp_metadata
    @metadata
    def fetch_from_cache(self):
        """Fetch the articles from the cache.

        It returns the articles stored in the cache object, provided during
        the initialization of the object. If this method is called but
        no cache object was provided, the method will raise a `CacheError`
        exception.

        :returns: a generator of articles

        :raises CacheError: raised when an error occurs accessing the
            cache
        """
        if not self.cache:
            raise CacheError(cause="cache instance was not provided")

        logger.info("Retrieving cached articles of '%s' group on '%s'",
                    self.group, self.host)

        cache_items = self.cache.retrieve()

        narts = 0

        for raw_item in cache_items:
            reader = io.BytesIO(b'\n'.join(raw_item['lines']))
            raw_article = reader.read().decode('utf-8', errors='surrogateescape')
            data = self.parse_article(raw_article)

            article = self.__build_article(data,
                                           raw_item['message_id'],
                                           raw_item['number'])

            yield article
            narts += 1

        logger.info("Retrieval process completed: %s articles retrieved from cache",
                    narts)

    def __fetch_and_parse_article(self, client, article_id):
        _, info = client.article(article_id)

        # Store data on the cache
        cache_data = {
            'number': info.number,
            'message_id': info.message_id,
            'lines': info.lines
        }
        self._push_cache_queue(cache_data)

        # Parse article data
        reader = io.BytesIO(b'\n'.join(info.lines))
        raw_article = reader.read().decode('utf-8', errors='surrogateescape')
        data = self.parse_article(raw_article)

        article = self.__build_article(data,
                                       info.message_id,
                                       info.number)

        logger.debug("Article %s (offset: %s) parsed",
                     article['message_id'], article['offset'])

        return article

    def __build_article(self, article, message_id, offset):
        a = {k: v for k, v in article.items()}
        a['message_id'] = message_id
        a['offset'] = offset
        return a

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
        """Extracts the identifier from a NNTP item."""

        return item['message_id']

    @staticmethod
    def metadata_updated_on(item):
        """Extracts the update time from a NNTP item.

        The timestamp is extracted from 'Date' field and
        converted to a UNIX timestamp.

        :param item: item generated by the backend

        :returns: a UNIX timestamp
        """
        ts = item['Date']
        ts = str_to_datetime(ts)

        return ts.timestamp()

    @staticmethod
    def metadata_category(item):
        """Extracts the category from a NNTP item.

        This backend only generates one type of item which is
        'article'.
        """
        return 'article'

    @staticmethod
    def parse_article(raw_article):
        """Parse a NNTP article.

        This method parses a NNTP article stored in a string object
        and returns an dictionary.

        :param raw_article: NNTP article string

        :returns: a dictionary of type `requests.structures.CaseInsensitiveDict`

        :raises ParseError: when an error is found parsing the article
        """
        try:
            message = email.message_from_string(raw_article)
            article = message_to_dict(message)
        except UnicodeEncodeError as e:
            raise ParseError(cause=str(e))
        return article


class NNTPCommand(BackendCommand):
    """Class to run NNTP backend from the command line."""

    BACKEND = NNTP

    @staticmethod
    def setup_cmd_parser():
        """Returns the NNTP argument parser."""

        parser = BackendCommandArgumentParser(offset=True,
                                              cache=True)

        # Required arguments
        parser.parser.add_argument('host',
                                   help="NNTP server host")
        parser.parser.add_argument('group',
                                   help="Name of the NNTP group")

        return parser
