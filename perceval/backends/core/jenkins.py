# -*- coding: utf-8 -*-
#
# Copyright (C) 2016-2017 Bitergia
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
#     Alvaro del Castillo <acs@bitergia.com>
#

import json
import logging
import time

import requests

from grimoirelab.toolkit.uris import urijoin

from ...backend import (Backend,
                        BackendCommand,
                        BackendCommandArgumentParser,
                        metadata)
from ...errors import CacheError


logger = logging.getLogger(__name__)


SLEEP_TIME = 10


class Jenkins(Backend):
    """Jenkins backend for Perceval.

    This class retrieves the builds from a Jenkins site.
    To initialize this class the URL must be provided.
    The `url` will be set as the origin of the data.

    :param url: Jenkins url
    :param tag: label used to mark the data
    :param cache: cache object to store raw data
    :param blacklist_jobs: exclude the jobs of this list while fetching
    :param sleep_time: minimun waiting time due to a timeout connection exception
    """
    version = '0.5.3'

    def __init__(self, url, tag=None, cache=None, blacklist_jobs=None, sleep_time=SLEEP_TIME):
        origin = url

        super().__init__(origin, tag=tag, cache=cache)
        self.url = url
        self.client = JenkinsClient(url, blacklist_jobs, sleep_time)
        self.blacklist_jobs = blacklist_jobs

    @metadata
    def fetch(self):
        """Fetch the builds from the url.

        The method retrieves, from a Jenkins url, the
        builds updated since the given date.

        :returns: a generator of builds
        """
        logger.info("Looking for projects at url '%s'", self.url)

        self._purge_cache_queue()

        nbuilds = 0  # number of builds processed
        njobs = 0  # number of jobs processed

        projects = json.loads(self.client.get_jobs())
        jobs = projects['jobs']

        for job in jobs:
            logger.debug("Adding builds from %s (%i/%i)",
                         job['url'], njobs, len(jobs))

            try:
                raw_builds = self.client.get_builds(job['name'])
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 500:
                    logger.warning(e)
                    logger.warning("Unable to fetch builds from job %s; skipping",
                                   job['url'])
                    continue
                else:
                    raise e

            if not raw_builds:
                continue

            try:
                builds = json.loads(raw_builds)
            except ValueError:
                logger.warning("Unable to parse builds from job %s; skipping",
                               job['url'])
                continue

            self._push_cache_queue(raw_builds)
            builds = builds['builds']
            for build in builds:
                yield build
                nbuilds += 1

            self._flush_cache_queue()
            njobs += 1

        logger.info("Total number of jobs: %i/%i", njobs, len(jobs))
        logger.info("Total number of builds: %i", nbuilds)

    @metadata
    def fetch_from_cache(self):
        """Fetch the builds from the cache.

        :returns: a generator of builds

        :raises CacheError: raised when an error occurs accessing the
            cache
        """
        if not self.cache:
            raise CacheError(cause="cache instance was not provided")

        cache_items = self.cache.retrieve()

        for items in cache_items:
            builds = json.loads(items)['builds']
            for build in builds:
                yield build

    @classmethod
    def has_caching(cls):
        """Returns whether it supports caching items on the fetch process.

        :returns: this backend supports items cache
        """
        return True

    @classmethod
    def has_resuming(cls):
        """Returns whether it supports to resume the fetch process.

        :returns: this backend does not supports items resuming
        """
        return False

    @staticmethod
    def metadata_id(item):
        """Extracts the identifier from a Build item."""
        return str(item['url'])

    @staticmethod
    def metadata_updated_on(item):
        """Extracts the update time from a Jenkins item.

        The timestamp is extracted from 'timestamp' field.
        This date is a UNIX timestamp but needs to be converted to
        a float value.

        :param item: item generated by the backend

        :returns: a UNIX timestamp
        """
        return float(item['timestamp'] / 1000)

    @staticmethod
    def metadata_category(item):
        """Extracts the category from a Jenkins item.

        This backend only generates one type of item which is
        'build'.
        """
        return 'build'


class JenkinsClient:
    """Jenkins API client.

    This class implements a simple client to retrieve builds from
    projects in a Jenkins node.

    :param url: URL of jenkins node: https://build.opnfv.org/ci

    :raises HTTPError: when an error occurs doing the request
    """
    MAX_RETRIES = 5

    def __init__(self, url, blacklist_jobs=None, sleep_time=SLEEP_TIME):
        self.url = url
        self.blacklist_jobs = blacklist_jobs
        self.sleep_time = sleep_time

    def get_jobs(self):
        """ Retrieve all jobs
        """
        url_jenkins = urijoin(self.url, "/api/json")

        return self.__send_request(url_jenkins)

    def get_builds(self, job_name):
        """ Retrieve all builds from a job
        """

        if self.blacklist_jobs and job_name in self.blacklist_jobs:
            logging.info("Not getting blacklisted job: %s", job_name)
            return

        # depth=2 to get builds details
        job_url = self.url + "/job/%s/" % (job_name)
        url_jenkins = job_url + "api/json?depth=2"

        return self.__send_request(url_jenkins)

    def __send_request(self, url):
        """send HTTP requests to the server"""

        retries = 0

        while retries < self.MAX_RETRIES:

            try:
                req = requests.get(url)
                req.raise_for_status()
                break
            except requests.exceptions.RequestException as e:
                if e.response.status_code in [408, 410, 502, 503, 504]:
                    retries += 1
                    time.sleep(self.sleep_time * retries)
                else:
                    raise e

        if retries == self.MAX_RETRIES:
            req.raise_for_status()

        return req.text


class JenkinsCommand(BackendCommand):
    """Class to run Jenkins backend from the command line."""

    BACKEND = Jenkins

    @staticmethod
    def setup_cmd_parser():
        """Returns the Jenkins argument parser."""

        parser = BackendCommandArgumentParser(cache=True)

        # Jenkins options
        group = parser.parser.add_argument_group('Jenkins arguments')
        group.add_argument('--blacklist-jobs', dest='blacklist_jobs',
                           nargs='*',
                           help="Wrong jobs that must not be retrieved.")

        group.add_argument('--sleep-time', dest='sleep_time',
                           type=int,
                           help="Minimun time to wait after a Timeout connection error.")

        # Required arguments
        parser.parser.add_argument('url',
                                   help="URL of the Jenkins server")

        return parser
