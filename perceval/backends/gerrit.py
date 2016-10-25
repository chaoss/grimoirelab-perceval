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
#     Alvaro del Castillo San Felix <acs@bitergia.com>
#     Santiago Dueñas <sduenas@bitergia.com>
#

import json
import logging
import os.path
import re
import subprocess
import time

from ..backend import Backend, BackendCommand, metadata
from ..cache import Cache
from ..errors import BackendError, CacheError
from ..utils import DEFAULT_DATETIME, str_to_datetime, datetime_to_utc


MAX_REVIEWS = 500 # Maximum number of reviews per query

logger = logging.getLogger(__name__)


class Gerrit(Backend):
    """Gerrit backend.

    Class to fetch the reviews from a Gerrit server. To initialize
    this class the URL of the server must be provided. The `url`
    will be set as the origin of the data.

    :param url: Gerrit server URL
    :param user: SSH user used to connect to the Gerrit server
    :param max_reviews: maximum number of reviews requested on the same query
    :param blacklist_reviews: exclude the reviews of this list while fetching
    :param tag: label used to mark the data
    :param cache: cache object to store raw data
    """
    version = '0.6.0'

    def __init__(self, url,
                 user=None, max_reviews=MAX_REVIEWS,
                 blacklist_reviews=None,
                 tag=None, cache=None):
        origin = url

        super().__init__(origin, tag=tag, cache=cache)
        self.url = url
        self.max_reviews = max(1, max_reviews)
        self.blacklist_reviews = blacklist_reviews
        self.client = GerritClient(self.url, user, max_reviews,
                                   blacklist_reviews)

    @metadata
    def fetch(self, from_date=DEFAULT_DATETIME):
        """Fetch the reviews from the repository.

        The method retrieves, from a Gerrit repository, the reviews
        updated since the given date.

        :param from_date: obtain reviews updated since this date

        :returns: a generator of reviews
        """
        self._purge_cache_queue()

        if self.client.version[0] == 2 and self.client.version[1] == 8:
            fetcher = self._fetch_gerrit28(from_date)
        else:
            fetcher = self._fetch_gerrit(from_date)

        for review in fetcher:
            yield review

    @metadata
    def fetch_from_cache(self):
        """Fetch reviews from the cache.

        It returns the reviews stored in the cache object provided during
        the initialization of the object. If this method is called but
        no cache object was provided, the method will raise a `CacheError`
        exception.

        :returns: a generator of items

        :raises CacheError: raised when an error occurs accesing the
            cache
        """
        if not self.cache:
            raise CacheError(cause="cache instance was not provided")

        cache_items = self.cache.retrieve()

        for raw_items in cache_items:
            reviews = self.parse_reviews(raw_items)
            for review in reviews:
                yield review

    def _fetch_gerrit28(self, from_date=DEFAULT_DATETIME):
        """ Specific fetch for gerrit 2.8 version.

        Get open and closed reviews in different queries.
        Take the newer review from both lists and iterate.
        """

        # Convert date to Unix time
        from_ut = datetime_to_utc(from_date)
        from_ut = from_ut.timestamp()

        filter_open = "status:open"
        filter_closed = "status:closed"

        last_item_open = self.client.next_retrieve_group_item()
        last_item_closed = self.client.next_retrieve_group_item()
        reviews_open = self._get_reviews(last_item_open, filter_open)
        reviews_closed = self._get_reviews(last_item_closed, filter_closed)
        last_nreviews_open = len(reviews_open)
        last_nreviews_closed = len(reviews_closed)

        while reviews_open or reviews_closed:
            if reviews_open and reviews_closed:
                if reviews_open[0]['lastUpdated'] >= reviews_closed[0]['lastUpdated']:
                    review_open = reviews_open.pop(0)
                    review = review_open
                else:
                    review_closed = reviews_closed.pop(0)
                    review = review_closed
            elif reviews_closed:
                review_closed = reviews_closed.pop(0)
                review = review_closed
            else:
                review_open = reviews_open.pop(0)
                review = review_open

            updated = review['lastUpdated']
            if updated <= from_ut:
                logger.debug("No more updates for %s" % (self.url))
                break
            else:
                yield review

            if not reviews_open and last_nreviews_open >= self.max_reviews:
                last_item_open = self.client.next_retrieve_group_item(last_item_open, review_open)
                reviews_open = self._get_reviews(last_item_open, filter_open)
                last_nreviews_open = len(reviews_open)
            if not reviews_closed and last_nreviews_closed >= self.max_reviews:
                last_item_closed = self.client.next_retrieve_group_item(last_item_closed, review_closed)
                reviews_closed = self._get_reviews(last_item_closed, filter_closed)
                last_nreviews_closed = len(reviews_closed)

    def _fetch_gerrit(self, from_date=DEFAULT_DATETIME):
        last_item = self.client.next_retrieve_group_item()
        reviews = self._get_reviews(last_item)
        last_nreviews = len(reviews)

        # Convert date to Unix time
        from_ut = datetime_to_utc(from_date)
        from_ut = from_ut.timestamp()

        while reviews:
            review = reviews.pop(0)
            try:
                last_item += 1
            except:
                pass  # last_item is a string in old gerrits
            updated = review['lastUpdated']
            if updated <= from_ut:
                logger.debug("No more updates for %s" % (self.url))
                break
            else:
                yield review

            if not reviews and last_nreviews >= self.max_reviews:
                logger.debug("GETTING MORE REVIEWS %i >= %i " % (last_nreviews, self.max_reviews))
                last_item = self.client.next_retrieve_group_item(last_item, review)
                reviews = self._get_reviews(last_item)
                last_nreviews = len(reviews)

    def _get_reviews(self, last_item, filter_=None):
        task_init = time.time()
        raw_data = self.client.reviews(last_item, filter_)
        self._push_cache_queue(raw_data)
        self._flush_cache_queue()
        reviews = self.parse_reviews(raw_data)
        logger.info("Received %i reviews in %.2fs" % (len(reviews),
                                                       time.time()-task_init))
        return reviews

    @classmethod
    def has_caching(cls):
        """Returns whether it supports caching items on the fetch process.

        :returns: this backend supports items cache
        """
        return True

    @classmethod
    def has_resuming(cls):
        """Returns whether it supports to resume the fetch process.

        :returns: this backend does not support items resuming
        """
        return False

    @staticmethod
    def metadata_id(item):
        """Extracts the identifier from a Gerrit item."""

        return item['id']

    @staticmethod
    def metadata_updated_on(item):
        """Extracts and converts the update time from a Gerrit item.

        The timestamp is extracted from 'lastUpdated' field. This date is
        a UNIX timestamp but needs to be converted to a float value.

        :param item: item generated by the backend

        :returns: a UNIX timestamp
        """
        return float(item['lastUpdated'])

    @staticmethod
    def metadata_category(item):
        """Extracts the category from a Gerrit item.

        This backend only generates one type of item which is
        'review'.
        """
        return 'review'

    @staticmethod
    def parse_reviews(raw_data):
        """Parse a Gerrit reviews list."""

        # Join isolated reviews in JSON in array for parsing
        items_raw = "[" + raw_data.replace("\n", ",") + "]"
        items_raw = items_raw.replace(",]", "]")
        items = json.loads(items_raw)
        reviews = []

        for item in items:
            if 'project' in item.keys():
                reviews.append(item)

        return reviews


class GerritClient():
    """Gerrit API client.

    This class implements a client to retrieve reviews from a Gerrit
    repository using the ssh API. Currently it supports <2.8 and >=2.9
    versions in incremental mode.

    Check the next link for more info:
    https://gerrit-documentation.storage.googleapis.com/Documentation/2.12/cmd-query.html

    :param repository: URL of the Gerrit server
    :param user: SSH user to be used to connect to gerrit server
    :param max_reviews: max number of reviews per query
    """
    VERSION_REGEX = re.compile(r'gerrit version (\d+)\.(\d+).*')
    CMD_GERRIT = 'gerrit'
    CMD_VERSION = 'version'
    PORT = '29418'

    def __init__(self, repository, user, max_reviews, blacklist_reviews=[]):
        self.gerrit_user = user
        self.max_reviews = max_reviews
        self.blacklist_reviews = blacklist_reviews
        self.repository = repository
        self.project = None
        self._version = None
        self.gerrit_cmd = "ssh -p %s %s@%s" % (GerritClient.PORT, self.gerrit_user,
                                               self.repository)
        self.gerrit_cmd += " %s " % (GerritClient.CMD_GERRIT)

    @property
    def version(self):
        """ Return the Gerrit server version."""

        if self._version:
            return self._version

        cmd = self.gerrit_cmd + " %s " % (GerritClient.CMD_VERSION)

        logger.debug("Getting version: %s" % (cmd))
        raw_data = subprocess.check_output(cmd, shell=True)
        raw_data = str(raw_data, "UTF-8")
        logger.debug("Gerrit version: %s" % (raw_data))

        # output: gerrit version 2.10-rc1-988-g333a9dd
        m = re.match(GerritClient.VERSION_REGEX, raw_data)

        if not m:
            cause = "Invalid gerrit version %s" % raw_data
            raise BackendError(cause=cause)

        try:
            mayor = int(m.group(1))
            minor = int(m.group(2))
        except:
            cause = "Gerrit client could not determine the server version."
            raise BackendError(cause=cause)

        self._version = [mayor, minor]
        return self._version

    def reviews(self, last_item, filter_=None):
        """Get the reviews starting from last_item."""

        cmd = self._get_gerrit_cmd(last_item, filter_)

        logger.debug(cmd)
        raw_data = subprocess.check_output(cmd, shell=True)
        raw_data = str(raw_data, "UTF-8")

        return raw_data

    def next_retrieve_group_item(self, last_item=None, entry=None):
        """Return the item to start from in next reviews group."""

        next_item = None

        gerrit_version = self.version

        if gerrit_version[0] == 2 and gerrit_version[1] >= 9:
            if last_item is None:
                next_item = 0
            else:
                next_item = last_item
        elif gerrit_version[0] == 2 and gerrit_version == 9:
            # https://groups.google.com/forum/#!topic/repo-discuss/yQgRR5hlS3E
            cause = "Gerrit 2.9.0 does not support pagination"
            raise BackendError(cause=cause)
        else:
            if entry is not None:
                next_item = entry['sortKey']

        return next_item

    def _get_gerrit_cmd(self, last_item, filter_=None):

        if filter_ and filter_ not in ['status:open','status:closed']:
            cause = "Filter not supported in gerrit %s" % (filter_)
            raise BackendError(cause=cause)

        cmd = self.gerrit_cmd + " query "
        if self.project:
            cmd += "project:"+self.project+" "
        cmd += "limit:" + str(self.max_reviews)

        if not filter_:
            cmd += " '(status:open OR status:closed)"
            if self.blacklist_reviews:
                blacklist_reviews = " AND NOT (%s)" % (' OR '.join(self.blacklist_reviews))
                cmd += blacklist_reviews
            cmd += "'"

        else:
            if self.blacklist_reviews:
                blacklist_reviews = " '%s AND NOT (%s)'" % (filter_, ','.join(self.blacklist_reviews))
                cmd += blacklist_reviews
            else:
                cmd += " %s " % (filter_)

        cmd += " --all-approvals --comments --format=JSON"

        gerrit_version = self.version

        if last_item is not None:
            if gerrit_version[0] == 2 and gerrit_version[1] >= 9:
                cmd += " --start=" + str(last_item)
            else:
                cmd += " resume_sortkey:" + last_item

        return cmd


class GerritCommand(BackendCommand):
    """Class to run Gerrit backend from the command line."""

    def __init__(self, *args):
        super().__init__(*args)

        self.url = self.parsed_args.url
        self.user = self.parsed_args.user
        self.max_reviews = self.parsed_args.max_reviews
        self.blacklist_reviews = self.parsed_args.blacklist_reviews
        self.from_date = str_to_datetime(self.parsed_args.from_date)
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

        self.backend = Gerrit(self.url,
                              user=self.user,
                              max_reviews=self.max_reviews,
                              blacklist_reviews=self.blacklist_reviews,
                              tag=self.tag,
                              cache=cache)

    def run(self):
        """Fetch and print the reviews.

        This method runs the backend to fetch the reviews from the given
        repository. Reviews are converted to JSON objects and printed to the
        defined output.
        """
        if self.parsed_args.fetch_cache:
            bugs = self.backend.fetch_from_cache()
        else:
            bugs = self.backend.fetch(from_date=self.from_date)

        try:
            total = 0
            for bug in bugs:
                obj = json.dumps(bug, indent=4, sort_keys=True)
                self.outfile.write(obj)
                self.outfile.write('\n')
                total += 1
            logger.info("Total reviews: %i", total)
        except IOError as e:
            raise RuntimeError(str(e))
        except Exception as e:
            if self.backend.cache:
                self.backend.cache.recover()
            raise RuntimeError(str(e))

    @classmethod
    def create_argument_parser(cls):
        """Returns the Gerrit argument parser."""

        parser = super().create_argument_parser()

        # Gerrit options
        group = parser.add_argument_group('Gerrit arguments')

        group.add_argument("--user",
                           help="Gerrit ssh user")
        group.add_argument("--max-reviews",  dest="max_reviews",
                           type=int, default=MAX_REVIEWS,
                           help="Max number of reviews per ssh query.")
        group.add_argument("--blacklist-reviews",  dest="blacklist_reviews",
                           nargs='*', help="Wrong reviews that must not be retrieved.")

        # Positional arguments
        group.add_argument("url",
                           help="URL of the Gerrit server")

        return parser
