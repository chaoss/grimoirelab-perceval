# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 Bitergia
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
#   Alvaro del Castillo San Felix <acs@bitergia.com>
#


from datetime import datetime
import json
import logging
import os.path
import re
import subprocess
from time import time

from ..backend import Backend, BackendCommand
from ..cache import Cache
from ..errors import BackendError, CacheError
from ..utils import DEFAULT_DATETIME, str_to_datetime


class Gerrit(Backend):
    """Gerrit backend."""

    def __init__(self, user=None, url=None, nreviews=None, cache=None):
        super().__init__(cache=cache)
        self.repository = url
        self.nreviews = nreviews
        self.number_results = None  # last number of results
        self.client = GerritClient(self.repository, user, nreviews)

    def fetch_from_cache(self):
        """Fetch the bugs from the cache.

        It returns the issues stored in the cache object provided during
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
            reviews = Gerrit.parse_reviews(raw_items)
            for review in reviews:
                yield review


    def fetch(self, from_date=DEFAULT_DATETIME):
        self._purge_cache_queue()

        last_item = self.client.next_retrieve_group_item()
        reviews = self._get_reviews(last_item)
        last_nreviews = len(reviews)

        while reviews:
            review = reviews.pop(0)
            last_item += 1
            updated = datetime.fromtimestamp(review['lastUpdated'])
            if updated <= from_date:
                logging.debug("No more updates for %s" % (self.repository))
                break

            yield review

            if not reviews and last_nreviews >= self.nreviews:
                last_item = self.client.next_retrieve_group_item(last_item, review)
                reviews = self._get_reviews(last_item)

    def _get_reviews(self, last_item):
        task_init = time()
        raw_data = self.client.reviews(last_item)
        self._push_cache_queue(raw_data)
        self._flush_cache_queue()
        reviews = Gerrit.parse_reviews(raw_data)
        logging.info("Received %i reviews in %.2fs" % (len(reviews),
                                                       time()-task_init))
        return reviews

    @classmethod
    def parse_reviews(cls, raw_data):
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

    # Regular expression to check the Gerrit version
    VERSION_REGEX = re.compile(r'gerrit version (\d+)\.(\d+).*')
    CMD_GERRIT = 'gerrit'
    CMD_VERSION = 'version'
    PORT = '29418'

    def __init__(self, repository, user, nreviews):
        self.gerrit_user = user
        self.nreviews = nreviews
        self.repository = repository
        self.project = None
        self._version = None
        self.gerrit_cmd = "ssh -p %s %s@%s" % (GerritClient.PORT, self.gerrit_user,
                                               self.repository)
        self.gerrit_cmd += " %s " % (GerritClient.CMD_GERRIT)

    @property
    def version(self):
        if self._version:
            return self._version

        cmd = self.gerrit_cmd + " %s " % (GerritClient.CMD_VERSION)

        logging.debug("Getting version: %s" % (cmd))
        raw_data = subprocess.check_output(cmd, shell=True)
        raw_data = str(raw_data, "UTF-8")
        logging.debug("Gerrit version: %s" % (raw_data))

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

    def _get_gerrit_cmd(self, last_item):

        cmd = self.gerrit_cmd + " query "
        if self.project:
            cmd += "project:"+self.project+" "
        cmd += "limit:" + str(self.nreviews)

        # This does not work for Wikimedia 2.8.1 version
        cmd += " '(status:open OR status:closed)' "

        cmd += " --all-approvals --comments --format=JSON"

        gerrit_version = self.version

        if last_item is not None:
            if gerrit_version[0] == 2 and gerrit_version[1] >= 9:
                cmd += " --start=" + str(last_item)
            else:
                cmd += " resume_sortkey:" + last_item

        return cmd

    def reviews(self, last_item):
        cmd = self._get_gerrit_cmd(last_item)

        logging.debug(cmd)
        raw_data = subprocess.check_output(cmd, shell=True)
        raw_data = str(raw_data, "UTF-8")

        return raw_data

    def next_retrieve_group_item(self, last_item = None, entry = None):
        """ Return the item to start from in next reviews group """

        next_item = None

        gerrit_version = self.version

        if gerrit_version[0] == 2 and gerrit_version[1] >= 9:
            if last_item is None:
                next_item = 0
            else:
                next_item = last_item
        else:
            if entry is not None:
                next_item = entry['sortKey']

        return next_item


class GerritCommand(BackendCommand):
    """Class to run Gerrit backend from the command line."""

    def __init__(self, *args):
        super().__init__(*args)

        self.user = self.parsed_args.user
        self.url = self.parsed_args.url
        self.nreviews = self.parsed_args.nreviews
        self.from_date = str_to_datetime(self.parsed_args.from_date)
        self.outfile = self.parsed_args.outfile

        if not self.parsed_args.no_cache:
            if not self.parsed_args.cache_path:
                base_path = os.path.expanduser('~/.perceval/cache/')
            else:
                base_path = self.parsed_args.cache_path
            # TODO: add get_id for backend to return the unique id
            cache_path = os.path.join(base_path, self.url)

            cache = Cache(cache_path)

            if self.parsed_args.clean_cache:
                cache.clean()
            else:
                cache.backup()
        else:
            cache = None

        self.backend = Gerrit(self.user, self.url,
                              self.nreviews, cache=cache)

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
            logging.info("Total reviews: %i", total)
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
        group.add_argument("--url", required=True,
                           help="Gerrit url")
        group.add_argument("--nreviews",  default=500, type=int,
                           help="Number of reviews per ssh query")

        return parser
