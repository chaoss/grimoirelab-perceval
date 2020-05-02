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
#     Valerio Cosentino <valcos@bitergia.com>
#     Santiago Dueñas <sduenas@bitergia.com>
#     Jesus M. Gonzalez-Barahona <jgb@gsyc.es>
#     Harshal Mittal <harshalmittal4@gmail.com>
#

import json
import logging
import requests

from grimoirelab_toolkit.datetime import (datetime_to_utc,
                                          str_to_datetime)
from grimoirelab_toolkit.uris import urijoin

from ...backend import (Backend,
                        BackendCommand,
                        BackendCommandArgumentParser,
                        DEFAULT_SEARCH_FIELD)
from ...client import HttpClient
from ...utils import DEFAULT_DATETIME

CATEGORY_ISSUE = "issue"

LAUNCHPAD_URL = "https://launchpad.net/"
LAUNCHPAD_API_URL = 'https://api.launchpad.net/1.0'

TARGET_ISSUE_FIELDS = ['bug_link', 'owner_link', 'assignee_link']
ITEMS_PER_PAGE = 75
SLEEP_TIME = 300

logger = logging.getLogger(__name__)


class Launchpad(Backend):
    """Launchpad backend for Perceval.

    This class allows the fetch the issues stored in Launchpad.

    :param distribution: Launchpad distribution
    :param package: Distribution package
    :param items_per_page: number of items in a retrieved page
    :param sleep_time: time (in seconds) to sleep in case
        of connection problems
    :param tag: label used to mark the data
    :param archive: archive to store/retrieve items
    :param ssl_verify: enable/disable SSL verification
    """
    version = '0.8.1'

    CATEGORIES = [CATEGORY_ISSUE]

    def __init__(self, distribution, package=None,
                 items_per_page=ITEMS_PER_PAGE, sleep_time=SLEEP_TIME,
                 tag=None, archive=None, ssl_verify=True):

        origin = urijoin(LAUNCHPAD_URL, distribution)

        super().__init__(origin, tag=tag, archive=archive, ssl_verify=ssl_verify)
        self.distribution = distribution
        self.package = package
        self.items_per_page = items_per_page
        self.sleep_time = sleep_time

        self.client = None
        self._users = {}  # internal users cache

    def search_fields(self, item):
        """Add search fields to an item.

        It adds the values of `metadata_id` plus additional values depending on the
        item category. For the categories `issue` and `pull_request`, the search
        fields include the issue/pull request number, labels, state and the name of
        the milestone. For the category `repository`, license and language are set
        as search fields.

        :param item: the item to extract the search fields values

        :returns: a dict of search fields
        """
        search_fields = {
            DEFAULT_SEARCH_FIELD: self.metadata_id(item),
            'distribution': self.distribution
        }

        return search_fields

    def fetch(self, category=CATEGORY_ISSUE, from_date=DEFAULT_DATETIME):
        """Fetch the issues from a project (distribution/package).

        The method retrieves, from a Launchpad project, the issues
        updated since the given date.

        :param category: the category of items to fetch
        :param from_date: obtain issues updated since this date

        :returns: a generator of issues
        """
        if not from_date:
            from_date = DEFAULT_DATETIME

        from_date = datetime_to_utc(from_date)

        kwargs = {'from_date': from_date}
        items = super().fetch(category, **kwargs)

        return items

    def fetch_items(self, category, **kwargs):
        """Fetch the issues

        :param category: the category of items to fetch
        :param kwargs: backend arguments

        :returns: a generator of items
        """
        from_date = kwargs['from_date']

        logger.info("Fetching issues of '%s' distribution from %s",
                    self.distribution, str(from_date))

        nissues = 0

        for issue in self._fetch_issues(from_date):
            yield issue
            nissues += 1

        logger.info("Fetch process completed: %s issues fetched", nissues)

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
        """Extracts the identifier from a Launchpad item."""

        return str(item['bug_data']['id'])

    @staticmethod
    def metadata_updated_on(item):
        """Extracts the update time from a Launchpad item.

        The timestamp used is extracted from 'date_last_updated' field.
        This date is converted to UNIX timestamp format. As Launchpad
        dates are in UTC in ISO 8601 (e.g., '2008-03-26T01:43:15.603905+00:00')
        the conversion is straightforward.

        :param item: item generated by the backend

        :returns: a UNIX timestamp
        """
        ts = item['bug_data']['date_last_updated']
        ts = str_to_datetime(ts)

        return ts.timestamp()

    @staticmethod
    def metadata_category(item):
        """Extracts the category from a Launchpad item.

        This backend only generates one type of item which is
        'issue'.
        """
        return CATEGORY_ISSUE

    def _init_client(self, from_archive=False):
        """Init client"""

        return LaunchpadClient(self.distribution, self.package, self.items_per_page,
                               self.sleep_time, self.archive, from_archive, self.ssl_verify)

    def __init_extra_issue_fields(self, issue):
        """Add fields to an issue"""

        issue['bug_data'] = {}
        issue['owner_data'] = {}
        issue['assignee_data'] = {}

        return issue

    def __extract_issue_id(self, bug_link):
        """Extract issue id from bug link"""

        return bug_link.split('/')[-1]

    def _fetch_issues(self, from_date):
        """Fetch the issues from a project (distribution/package)"""

        issues_groups = self.client.issues(start=from_date)

        for raw_issues in issues_groups:

            issues = json.loads(raw_issues)['entries']
            for issue in issues:
                issue = self.__init_extra_issue_fields(issue)
                issue_id = self.__extract_issue_id(issue['bug_link'])

                for field in TARGET_ISSUE_FIELDS:

                    if not issue[field]:
                        continue

                    if field == 'bug_link':
                        issue['bug_data'] = self.__fetch_issue_data(issue_id)
                        issue['activity_data'] = [activity for activity in self.__fetch_issue_activities(issue_id)]
                        issue['messages_data'] = [message for message in self.__fetch_issue_messages(issue_id)]
                        issue['attachments_data'] = [attachment for attachment in
                                                     self.__fetch_issue_attachments(issue_id)]
                    elif field == 'assignee_link':
                        issue['assignee_data'] = self.__fetch_user_data('{ASSIGNEE}', issue[field])
                    elif field == 'owner_link':
                        issue['owner_data'] = self.__fetch_user_data('{OWNER}', issue[field])

                yield issue

    def __fetch_issue_data(self, issue_id):
        """Get data associated to an issue"""

        raw_issue = self.client.issue(issue_id)
        issue = json.loads(raw_issue)

        return issue

    def __fetch_issue_attachments(self, issue_id):
        """Get attachments of an issue"""

        for attachments_raw in self.client.issue_collection(issue_id, "attachments"):
            attachments = json.loads(attachments_raw)

            for attachment in attachments['entries']:
                yield attachment

    def __fetch_issue_messages(self, issue_id):
        """Get messages of an issue"""

        for messages_raw in self.client.issue_collection(issue_id, "messages"):
            messages = json.loads(messages_raw)

            for msg in messages['entries']:
                msg['owner_data'] = self.__fetch_user_data('{OWNER}', msg['owner_link'])
                yield msg

    def __fetch_issue_activities(self, issue_id):
        """Get activities on an issue"""

        for activities_raw in self.client.issue_collection(issue_id, "activity"):
            activities = json.loads(activities_raw)

            for act in activities['entries']:
                act['person_data'] = self.__fetch_user_data('{PERSON}', act['person_link'])
                yield act

    def __fetch_user_data(self, tag_type, user_link):
        """Get data associated to an user"""

        user_name = self.client.user_name(user_link)

        user = {}

        if not user_name:
            return user

        user_raw = self.client.user(user_name)
        user = json.loads(user_raw)

        return user


class LaunchpadClient(HttpClient):
    """Client for retrieving information from Launchpad API

    :param distribution: Launchpad distribution
    :param package: Distribution package
    :param items_per_page: number of items in a retrieved page
    :param sleep_time: time (in seconds) to sleep in case
        of connection problems
    :param archive: an archive to store/read fetched data
    :param from_archive: it tells whether to write/read the archive
    :param ssl_verify: enable/disable SSL verification
    """
    _users = {}

    # API resources
    RBUGS = 'bugs'
    RSOURCE = "+source"

    # API headers
    HCONTENT_TYPE = 'Content-type'

    # Resource parameters
    PWS_SIZE = 'ws.size'
    PWS_START = 'ws.start'
    PORDER_BY = 'order_by'
    POMIT_DULPLICATES = 'omit_duplicates'
    PSTATUS = 'status'
    PWS_OP = 'ws.op'
    PMODIFIED_SINCE = 'modified_since'

    # Predefined values
    VDATE_LAST_MODIFIED = 'date_last_updated'
    VCONTENT_TYPE = 'application/json'
    VOMIT_DUPLICATES = 'false'
    VSEARCH_TASKS = 'searchTasks'
    VSTATUS = ["New", "Incomplete", "Opinion", "Invalid", "Won't Fix",
               "Expired", "Confirmed", "Triaged", "In Progress",
               "Fix Committed", "Fix Released",
               "Incomplete (with response)",
               "Incomplete (without response)"]

    def __init__(self, distribution, package=None,
                 items_per_page=ITEMS_PER_PAGE, sleep_time=SLEEP_TIME,
                 archive=None, from_archive=False, ssl_verify=True):

        self.distribution = distribution
        self.package = package
        self.items_per_page = items_per_page

        extra_headers = self.__define_headers()
        super().__init__(LAUNCHPAD_API_URL, sleep_time=sleep_time, extra_headers=extra_headers,
                         archive=archive, from_archive=from_archive, ssl_verify=ssl_verify)

    def issues(self, start=None):
        """Get the issues from pagination"""

        payload = self.__build_payload(size=self.items_per_page, operation=True, startdate=start)
        path = self.__get_url_project()
        return self.__fetch_items(path=path, payload=payload)

    def user(self, user_name):
        """Get the user data by URL"""

        user = None

        if user_name in self._users:
            return self._users[user_name]

        url_user = self.__get_url("~" + user_name)

        logger.info("Getting info for %s" % (url_user))

        try:
            raw_user = self.__send_request(url_user)
            user = raw_user
        except requests.exceptions.HTTPError as e:
            if e.response.status_code in [404, 410]:
                logger.warning("Data is not available - %s", url_user)
                user = '{}'
            else:
                raise e

        self._users[user_name] = user

        return user

    def user_name(self, user_link):
        """Get user name from link"""

        return user_link.split('/')[-1][1:]

    def issue(self, issue_id):
        """Get the issue data by its ID"""

        path = urijoin(self.RBUGS, str(issue_id))
        url_issue = self.__get_url(path)
        raw_text = self.__send_request(url_issue)

        return raw_text

    def issue_collection(self, issue_id, collection_name):
        """Get a collection list of a given issue"""

        path = urijoin(self.RBUGS, str(issue_id), collection_name)
        url_collection = self.__get_url(path)
        payload = {self.PWS_SIZE: self.items_per_page, self.PWS_START: 0, self.PORDER_BY: self.VDATE_LAST_MODIFIED}

        raw_items = self.__fetch_items(path=url_collection, payload=payload)

        return raw_items

    def __get_url_project(self):
        """Build URL project"""

        if self.package:
            url = self.__get_url_distribution_package()
        else:
            url = self.__get_url_distribution()

        return url

    def __get_url_distribution(self):
        """Build URL distribution"""

        return urijoin(self.base_url, self.distribution)

    def __get_url_distribution_package(self):
        """Build URL distribution package"""

        return urijoin(self.__get_url_distribution(), self.RSOURCE, self.package)

    def __get_url(self, path):
        """Build genereic URL"""

        return urijoin(self.base_url, path)

    def __define_headers(self):
        """Add headers to the Client default ones"""

        headers = {self.HCONTENT_TYPE: self.VCONTENT_TYPE}

        return headers

    def __send_request(self, url, params=None):
        """Send request"""

        r = self.fetch(url, payload=params)
        return r.text

    def __build_payload(self, size, operation=False, startdate=None):
        """Build payload"""

        payload = {
            self.PWS_SIZE: size,
            self.PORDER_BY: self.VDATE_LAST_MODIFIED,
            self.POMIT_DULPLICATES: self.VOMIT_DUPLICATES,
            self.PSTATUS: self.VSTATUS
        }

        if operation:
            payload[self.PWS_OP] = self.VSEARCH_TASKS
        if startdate:
            startdate = startdate.isoformat()
            payload[self.PMODIFIED_SINCE] = startdate

        return payload

    def __fetch_items(self, path, payload):
        """Return the items from Launchpad API using pagination"""

        page = 0  # current page
        url_next = path
        fetch_data = True

        while fetch_data:
            logger.debug("Fetching page: %i", page)

            try:
                raw_content = self.__send_request(url_next, payload)
                content = json.loads(raw_content)
            except requests.exceptions.HTTPError as e:
                if e.response.status_code in [410]:
                    logger.warning("Data is not available - %s", url_next)
                    raw_content = '{"total_size": 0, "start": 0, "entries": []}'
                    content = json.loads(raw_content)
                else:
                    raise e

            if 'next_collection_link' in content:
                url_next = content['next_collection_link']
                payload = None
            else:
                fetch_data = False

            yield raw_content
            page += 1


class LaunchpadCommand(BackendCommand):
    """Class to run Launchpad backend from the command line."""

    BACKEND = Launchpad

    @classmethod
    def setup_cmd_parser(cls):
        """Returns the Launchpad argument parser."""

        parser = BackendCommandArgumentParser(cls.BACKEND,
                                              from_date=True,
                                              archive=True,
                                              token_auth=False,
                                              ssl_verify=True)

        # Optional arguments
        group = parser.parser.add_argument_group('Launchpad arguments')
        group.add_argument('--items-per-page', dest='items_per_page',
                           help="Items per page")
        group.add_argument('--sleep-time', dest='sleep_time',
                           help="Sleep time in case of connection lost")
        group.add_argument('--package', dest='package',
                           help="Distribution package")

        # Required arguments
        parser.parser.add_argument('distribution',
                                   help="Launchpad distribution")

        return parser
