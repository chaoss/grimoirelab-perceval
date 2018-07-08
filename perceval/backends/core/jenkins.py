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

import requests

from grimoirelab_toolkit.uris import urijoin

from ...backend import (Backend,
                        BackendCommand,
                        BackendCommandArgumentParser)
from ...client import HttpClient

CATEGORY_BUILD = "build"
SLEEP_TIME = 10
DETAIL_DEPTH = 1

logger = logging.getLogger(__name__)


class Jenkins(Backend):
    """Jenkins backend for Perceval.

    This class retrieves the builds from a Jenkins site.
    To initialize this class the URL must be provided.
    The `url` will be set as the origin of the data.

    :param url: Jenkins url
    :param tag: label used to mark the data
    :param archive: archive to store/retrieve items
    :param blacklist_jobs: exclude the jobs of this list while fetching
    :param detail_depth: control the detail level of the data returned by the API
    :param sleep_time: minimun waiting time due to a timeout connection exception
    :param archive: collect builds already retrieved from an archive
    """
    version = '0.11.0'

    CATEGORIES = [CATEGORY_BUILD]

    def __init__(self, url, tag=None, archive=None,
                 blacklist_jobs=None, detail_depth=DETAIL_DEPTH, sleep_time=SLEEP_TIME):
        origin = url

        super().__init__(origin, tag=tag, archive=archive)
        self.url = url
        self.sleep_time = sleep_time
        self.blacklist_jobs = blacklist_jobs
        self.detail_depth = detail_depth

        self.client = None

    def fetch(self, category=CATEGORY_BUILD):
        """Fetch the builds from the url.

        The method retrieves, from a Jenkins url, the
        builds updated since the given date.

        :param category: the category of items to fetch

        :returns: a generator of builds
        """

        kwargs = {}
        items = super().fetch(category, **kwargs)

        return items

    def fetch_items(self, category, **kwargs):
        """Fetch the contents

        :param category: the category of items to fetch
        :param kwargs: backend arguments

        :returns: a generator of items
        """
        logger.info("Looking for projects at url '%s'", self.url)

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

            builds = builds['builds']
            for build in builds:
                yield build
                nbuilds += 1

            njobs += 1

        logger.info("Total number of jobs: %i/%i", njobs, len(jobs))
        logger.info("Total number of builds: %i", nbuilds)

    @classmethod
    def has_archiving(cls):
        """Returns whether it supports archiving items on the fetch process.

        :returns: this backend supports items archiving
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
        return CATEGORY_BUILD

    def _init_client(self, from_archive=False):
        """Init client"""

        return JenkinsClient(self.url, self.blacklist_jobs, self.detail_depth,
                             self.sleep_time,
                             archive=self.archive, from_archive=from_archive)


class JenkinsClient(HttpClient):
    """Jenkins API client.

    This class implements a simple client to retrieve jobs/builds from
    projects in a Jenkins node. The amount of data returned for each request
    depends on the detail_depth value selected (minimun and default is 1).
    Note that increasing the detail_depth may considerably slow down the
    fetch operation and cause connection broken errors.

    :param url: URL of jenkins node: https://build.opnfv.org/ci
    :param blacklist_jobs: exclude the jobs of this list while fetching
    :param detail_depth: set the detail level of the data returned by the API
    :param sleep_time: minimun waiting time due to a timeout connection exception
    :param archive: an archive to store/read fetched data
    :param from_archive: it tells whether to write/read the archive

    :raises HTTPError: when an error occurs doing the request
    """
    MAX_RETRIES = 5

    def __init__(self, url, blacklist_jobs=None, detail_depth=DETAIL_DEPTH, sleep_time=SLEEP_TIME,
                 archive=None, from_archive=False):
        super().__init__(url, sleep_time=sleep_time, extra_status_forcelist=[410, 502, 503],
                         archive=archive, from_archive=from_archive)
        self.blacklist_jobs = blacklist_jobs
        self.detail_depth = detail_depth

    def get_jobs(self):
        """ Retrieve all jobs"""

        url_jenkins = urijoin(self.base_url, "api", "json")

        response = self.fetch(url_jenkins)
        return response.text

    def get_builds(self, job_name):
        """ Retrieve all builds from a job"""

        if self.blacklist_jobs and job_name in self.blacklist_jobs:
            logging.info("Not getting blacklisted job: %s", job_name)
            return

        payload = {'depth': self.detail_depth}
        url_build = urijoin(self.base_url, "job", job_name, "api", "json")

        response = self.fetch(url_build, payload=payload)
        return response.text


class JenkinsCommand(BackendCommand):
    """Class to run Jenkins backend from the command line."""

    BACKEND = Jenkins

    @staticmethod
    def setup_cmd_parser():
        """Returns the Jenkins argument parser."""

        parser = BackendCommandArgumentParser(archive=True)

        # Jenkins options
        group = parser.parser.add_argument_group('Jenkins arguments')
        group.add_argument('--blacklist-jobs', dest='blacklist_jobs',
                           nargs='*',
                           help="Wrong jobs that must not be retrieved.")

        group.add_argument('--detail-depth', dest='detail_depth',
                           type=int, default=DETAIL_DEPTH,
                           help="Detail level of the Jenkins data.")

        group.add_argument('--sleep-time', dest='sleep_time',
                           type=int, default=SLEEP_TIME,
                           help="Minimun time to wait after a Timeout connection error.")

        # Required arguments
        parser.parser.add_argument('url',
                                   help="URL of the Jenkins server")

        return parser
