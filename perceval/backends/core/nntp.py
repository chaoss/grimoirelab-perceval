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
#     Valerio Cosentino <valcos@bitergia.com>
#     Jesus M. Gonzalez-Barahona <jgb@gsyc.es>
#     Harshal Mittal <harshalmittal4@gmail.com>
#

import io
import logging
import email


try:
    import nntplib

    # Hack to avoid "line too long" errors
    nntplib._MAXLINE = 65536
except ImportError:
    # nntplib has been removed in Python 3.13
    nntplib = None


from grimoirelab_toolkit.datetime import str_to_datetime, InvalidDateError

from ...backend import (Backend,
                        BackendCommand,
                        BackendCommandArgumentParser)
from ...errors import ArchiveError, ParseError
from ...utils import message_to_dict

CATEGORY_ARTICLE = "article"
DEFAULT_OFFSET = 1
FALLBACK_DATE = '1970-01-01'

logger = logging.getLogger(__name__)


class NNTP(Backend):
    """NNTP backend.

    This class allows to fetch the articles published on a news group
    using NNTP. It is initialized giving the host and the name of the
    news group.

    :param host: host
    :param group: name of the group
    :param tag: label used to mark the data
    :param archive: archive to store/retrieve items
    """
    version = '1.0.0'

    CATEGORIES = [CATEGORY_ARTICLE]
    EXTRA_SEARCH_FIELDS = {
        'newsgroups': ['Newsgroups']
    }

    def __init__(self, host, group, tag=None, archive=None):

        if not nntplib:
            raise ImportError("nntp is no longer supported in Python >= 3.13 due"
                              "to nntplib has been removed from the standard library")

        origin = host + '-' + group

        super().__init__(origin, tag=tag, archive=archive)
        self.host = host
        self.group = group
        self.client = None

    def fetch(self, category=CATEGORY_ARTICLE, offset=DEFAULT_OFFSET):
        """Fetch articles posted on a news group.

        This method fetches those messages or articles published
        on a news group starting on the given offset.

        :param category: the category of items to fetch
        :param offset: obtain messages from this offset

        :returns: a generator of articles
        """
        if not offset:
            offset = DEFAULT_OFFSET

        kwargs = {'offset': offset}
        items = super().fetch(category, **kwargs)

        return items

    def fetch_items(self, category, **kwargs):
        """Fetch the articles

        :param category: the category of items to fetch
        :param kwargs: backend arguments

        :returns: a generator of items
        """
        offset = kwargs['offset']

        logger.info("Fetching articles of '%s' group on '%s' offset %s",
                    self.group, self.host, str(offset))

        narts, iarts, tarts = (0, 0, 0)

        _, _, first, last, _ = self.client.group(self.group)

        if offset <= last:
            first = max(first, offset)
            _, overview = self.client.over((first, last))
        else:
            overview = []

        tarts = len(overview)

        logger.debug("Total number of articles to fetch: %s", tarts)

        for article_id, _ in overview:
            try:
                article_raw = self.client.article(article_id)
                article = self.__parse_article(article_raw)
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

    def metadata(self, item, filter_classified=False):
        """NNTP metadata.

        This method takes items, overriding `metadata` decorator,
        to add extra information related to NNTP.

        :param item: an item fetched by a backend
        :param filter_classified: sets if classified fields were filtered
        """
        item = super().metadata(item, filter_classified=filter_classified)
        item['offset'] = item['data']['offset']

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
        if 'Date' in item:
            ts = item['Date']
        elif 'DATE' in item:
            ts = item['DATE']

        try:
            ts = str_to_datetime(ts)
        except InvalidDateError as e:
            # Set to the FALLBACK_DATE when it is not a valid date
            logger.warning("%s from Message-ID: %s. Set the fallback date: %s" %
                           (e, item['Message-ID'], FALLBACK_DATE))
            ts = str_to_datetime(FALLBACK_DATE)

        return ts.timestamp()

    @staticmethod
    def metadata_category(item):
        """Extracts the category from a NNTP item.

        This backend only generates one type of item which is
        'article'.
        """
        return CATEGORY_ARTICLE

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

    def _init_client(self, from_archive=False):
        """Init client"""

        return NNTTPClient(self.host, self.archive, from_archive)

    def __parse_article(self, info):
        reader = io.BytesIO(b'\n'.join(info['lines']))
        raw_article = reader.read().decode('utf-8', errors='surrogateescape')
        data = self.parse_article(raw_article)

        article = self.__build_article(data,
                                       info['message_id'],
                                       info['number'])

        logger.debug("Article %s (offset: %s) parsed",
                     article['message_id'], article['offset'])

        return article

    def __build_article(self, article, message_id, offset):
        a = {k: v for k, v in article.items()}
        a['message_id'] = message_id
        a['offset'] = offset
        return a


class NNTTPClient():
    """NNTP client

    :param host: host
    :param group: name of the group
    :param archive: an archive to store/read fetched data
    :param from_archive: it tells whether to write/read the archive
    """

    GROUP = "group"
    ARTICLE = "article"
    OVER = "over"

    def __init__(self, host, archive=None, from_archive=False):

        if not nntplib:
            raise ImportError("nntp is no longer supported in Python >= 3.13 due"
                              "to nntplib has been removed from the standard library")
        else:
            logging.warning("nntp will no longer be supported in Python >= 3.13 due"
                            "to nntplib has been removed from the standard library")

        self.host = host
        self.archive = archive
        self.from_archive = from_archive

        if not self.from_archive:
            self.handler = nntplib.NNTP(self.host)

    def __del__(self):
        if not self.from_archive:
            self.quit()

    def group(self, group_name):
        """Fetch group data

        :param group_name: name of the group
        """
        return self._fetch("group", group_name)

    def over(self, offset):
        """Fetch messages data

        :param offset: a tuple representing the offset to retrieve
        """
        return self._fetch("over", offset)

    def article(self, article_id):
        """Fetch article data

        :param article_id: id of the article to fetch
        """
        return self._fetch("article", article_id)

    def _fetch(self, method, args):
        """Fetch NNTP data from the server or from the archive

        :param method: the name of the command to execute
        :param args: the arguments required by the command
        """
        if self.from_archive:
            data = self._fetch_from_archive(method, args)
        else:
            data = self._fetch_from_remote(method, args)

        return data

    def _fetch_article(self, article_id):
        """Fetch article data

        :param article_id: id of the article to fetch
        """
        fetched_data = self.handler.article(article_id)
        data = {
            'number': fetched_data[1].number,
            'message_id': fetched_data[1].message_id,
            'lines': fetched_data[1].lines
        }

        return data

    def _fetch_from_remote(self, method, args):
        """Fetch data from NNTP

        :param method: the name of the command to execute
        :param args: the arguments required by the command
        """
        try:
            if method == NNTTPClient.GROUP:
                data = self.handler.group(args)
            elif method == NNTTPClient.OVER:
                data = self.handler.over(args)
            elif method == NNTTPClient.ARTICLE:
                data = self._fetch_article(args)
        except nntplib.NNTPTemporaryError as e:
            data = e
            raise e
        finally:
            if self.archive:
                self.archive.store(method, args, None, data)

        return data

    def _fetch_from_archive(self, method, args):
        """Fetch data from the archive

        :param method: the name of the command to execute
        :param args: the arguments required by the command
        """
        if not self.archive:
            raise ArchiveError(cause="Archive not provided")

        data = self.archive.retrieve(method, args, None)

        if isinstance(data, nntplib.NNTPTemporaryError):
            raise data

        return data

    def quit(self):
        self.handler.quit()


class NNTPCommand(BackendCommand):
    """Class to run NNTP backend from the command line."""

    BACKEND = NNTP

    @classmethod
    def setup_cmd_parser(cls):
        """Returns the NNTP argument parser."""

        parser = BackendCommandArgumentParser(cls.BACKEND,
                                              offset=True,
                                              archive=True)

        # Required arguments
        parser.parser.add_argument('host',
                                   help="NNTP server host")
        parser.parser.add_argument('group',
                                   help="Name of the NNTP group")

        return parser
