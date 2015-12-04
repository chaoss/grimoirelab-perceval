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

'''Gerrit backend for Perseval'''


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

    name = "gerrit"

    def __init__(self, user=None, url=None, nreviews=None,
                 cache=None, **nouse):
        super().__init__(cache=cache)
        self.repository = url
        self.nreviews = nreviews
        self.last_item = None  # Start item for next iteration
        self.more_updates = True  # To check if reviews are updates
        self.number_results = self.nreviews  # Check for more items
        self.client = GerritClient(self.repository, user, nreviews)

    def get_id(self):
        ''' Return gerrit unique identifier '''

        return self.repository

    def get_field_unique_id(self):
        return "id"

    def fetch(self, from_date=DEFAULT_DATETIME):

        self._purge_cache_queue()

        reviews = self.get_reviews(from_date)
        self._push_cache_queue(reviews)

        while reviews:
            issue = reviews.pop(0)
            yield issue

            if not reviews:
                reviews = self.get_reviews(from_date)
                self._push_cache_queue(reviews)
                self._flush_cache_queue()

    def fetch_from_cache(self):
        """Fetch the bugs from the cache.

        It returns the bugs stored in the cache object provided during
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

        while True:
            try:
                raw_items = next(cache_items)
                if raw_items is None:
                    break
            except StopIteration:
                break

            for item in raw_items:
                yield item

    def get_reviews(self, from_date=None):
        """ Get all reviews from repository """

        reviews = []

        if self.number_results < self.nreviews or not self.more_updates:
            # No more reviews after last iteration
            return reviews

        task_init = time()
        raw_data = self.client.get_items(self.last_item)
        raw_data = str(raw_data, "UTF-8")
        tickets_raw = "[" + raw_data.replace("\n", ",") + "]"
        tickets_raw = tickets_raw.replace(",]", "]")

        tickets = json.loads(tickets_raw)

        for entry in tickets:
            if 'project' in entry.keys():
                entry_lastUpdated = \
                    datetime.fromtimestamp(entry['lastUpdated'])
                entry['lastUpdated_date'] = entry_lastUpdated.isoformat()

                if from_date:  # Incremental mode
                    if entry_lastUpdated <= from_date:
                        logging.debug("No more updates for %s"
                                      % (self.repository))
                        self.more_updates = False
                        break

                reviews.append(entry)

                self.last_item = self.client.get_next_item(self.last_item,
                                                           entry)
            elif 'rowCount' in entry.keys():
                # logging.info("CONTINUE FROM: " + str(last_item))
                self.number_results = entry['rowCount']

        logging.info("Received %i reviews in %.2fs" % (len(reviews),
                                                       time()-task_init))
        return reviews


class GerritClient():

    def __init__(self, repository, user, nreviews):
        self.gerrit_user = user
        self.nreviews = nreviews
        self.repository = repository
        self.project = None
        self.version = None
        self.gerrit_cmd = "ssh -p 29418 %s@%s" % (self.gerrit_user,
                                                  self.repository)
        self.gerrit_cmd += " gerrit "

    def _get_version(self):

        if self.version:
            return self.version

        cmd = self.gerrit_cmd + " version "

        logging.debug("Getting version: %s" % (cmd))
        raw_data = subprocess.check_output(cmd, shell=True)
        raw_data = str(raw_data, "UTF-8")
        logging.debug("Gerrit version: %s" % (raw_data))

        # output: gerrit version 2.10-rc1-988-g333a9dd
        m = re.match("gerrit version (\d+)\.(\d+).*", raw_data)

        if not m:
            cause = "Invalid gerrit version %s" % raw_data
            raise BackendError(cause=cause)

        try:
            mayor = int(m.group(1))
            minor = int(m.group(2))
        except:
            cause = "Gerrit client could not determine the server version."
            raise BackendError(cause=cause)

        self.version = [mayor, minor]
        return self.version

    def _get_gerrit_cmd(self, last_item):

        cmd = self.gerrit_cmd + " query "
        if self.project:
            cmd += "project:"+self.project+" "
        cmd += "limit:" + str(self.nreviews)

        # This does not work for Wikimedia 2.8.1 version
        cmd += " '(status:open OR status:closed)' "

        cmd += " --all-approvals --comments --format=JSON"

        gerrit_version = self._get_version()

        if last_item is not None:
            if gerrit_version[0] == 2 and gerrit_version[1] >= 9:
                cmd += " --start=" + str(last_item)
            else:
                cmd += " resume_sortkey:" + last_item

        return cmd

    def get_items(self, last_item):
        cmd = self._get_gerrit_cmd(last_item)

        logging.debug(cmd)
        raw_data = subprocess.check_output(cmd, shell=True)

        return raw_data

    def get_next_item(self, last_item, entry):
        next_item = None

        gerrit_version = self._get_version()

        if gerrit_version[0] == 2 and gerrit_version[1] >= 9:
            if last_item is None:
                next_item = 0
            self.last_item += 1
        else:
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
        """Fetch and print the bugs.

        This method runs the backend to fetch the bugs from the given
        repository. Bugs are converted to JSON objects and printed to the
        defined output.
        """
        if self.parsed_args.fetch_cache:
            bugs = self.backend.fetch_from_cache()
        else:
            bugs = self.backend.fetch(from_date=self.from_date)

        try:
            for bug in bugs:
                obj = json.dumps(bug, indent=4, sort_keys=True)
                self.outfile.write(obj)
                self.outfile.write('\n')
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
