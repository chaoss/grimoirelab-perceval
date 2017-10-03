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
#     Valerio Cosentino <valcos@bitergia.com>
#

import hmac
import hashlib
import json
import logging
import requests
import time

from grimoirelab.toolkit.datetime import (datetime_utcnow,
                                          datetime_to_utc,
                                          str_to_datetime)
from grimoirelab.toolkit.uris import urijoin

from ...backend import (Backend,
                        BackendCommand,
                        BackendCommandArgumentParser,
                        metadata)
from ...errors import CacheError
from ...utils import DEFAULT_DATETIME


LAUNCHPAD_URL = "https://launchpad.net/"
LAUNCHPAD_API_URL = 'https://api.launchpad.net/1.0/'

TARGET_ISSUE_FIELDS = ['bug_link', 'owner_link', 'assignee_link']
ITEMS_PER_PAGE = 75
SLEEP_TIME = 300

logger = logging.getLogger(__name__)


class Launchpad(Backend):
    """Launchpad backend for Perceval.

    This class allows the fetch the issues stored in Launchpad.

    :param distribution: Launchpad distribution
    :param package: Distribution package
    :param consumer_key: App consumer key
    :param api_token: Launchpad auth token to access the API
    :param tag: label used to mark the data
    :param cache: use issues already retrieved in cache
    :param sleep_for_rate: sleep until rate limit is reset
    :param min_rate_to_sleep: minimun rate needed to sleep until
           it will be reset
    """
    version = '0.1.0'

    def __init__(self, distribution, package=None,
                 consumer_key=None, api_token=None,
                 items_per_page=ITEMS_PER_PAGE, sleep_time=SLEEP_TIME,
                 tag=None, cache=None):

        origin = urijoin(LAUNCHPAD_URL, distribution)

        super().__init__(origin, tag=tag, cache=cache)
        self.distribution = distribution
        self.package = package
        self.client = LaunchpadClient(distribution, package=package,
                                      consumer_key=consumer_key, api_token=api_token,
                                      items_per_page=items_per_page,
                                      sleep_time=sleep_time)

        self._users = {}  # internal users cache

    @metadata
    def fetch(self, from_date=DEFAULT_DATETIME):
        """Fetch the issues from a project (distribution/package).

        The method retrieves, from a Launchpad project, the issues
        updated since the given date.

        :param from_date: obtain issues updated since this date

        :returns: a generator of issues
        """
        if not from_date:
            from_date = DEFAULT_DATETIME

        logger.info("Fetching issues of '%s' distribution from %s",
                    self.distribution, str(from_date))

        self._purge_cache_queue()

        from_date = datetime_to_utc(from_date)
        nissues = 0

        for issue in self._fetch(from_date):
            yield issue
            nissues += 1

        logger.info("Fetch process completed: %s issues fetched", nissues)

    @metadata
    def fetch_from_cache(self):
        """Fetch the issues from the cache.

        It returns the issues stored in the cache object provided during
        the initialization of the object. If this method is called but
        no cache object was provided, the method will raise a `CacheError`
        exception.

        :returns: a generator of items
        :raises CacheError: raised when an error occurs accessing the
            cache
        """
        if not self.cache:
            raise CacheError(cause="cache instance was not provided")

        cache_items = self.cache.retrieve()
        raw_item = next(cache_items)

        while raw_item != '{}{}':

            if raw_item == '{ISSUES}':
                issues = self.__fetch_issues_from_cache(cache_items)

            raw_item = next(cache_items)
            for issue in issues:
                issue = self.__init_extra_issue_fields(issue)

                while raw_item != '{ISSUE-END}':
                    try:
                        if raw_item == '{OWNER}':
                            issue['owner_data'] = self.__fetch_user_from_cache(cache_items)
                        elif raw_item == '{ASSIGNEE}':
                            issue['assignee_data'] = self.__fetch_user_from_cache(cache_items)
                        elif raw_item == '{ISSUE-CORE-START}':
                            data = self.__fetch_issue_content_from_cache(cache_items)
                            issue['bug_data'] = data[0]
                            issue['activity_data'] = data[1]
                            issue['messages_data'] = data[2]
                            issue['attachments_data'] = data[3]

                        raw_item = next(cache_items)

                    except StopIteration:
                        # this should be never executed, the while condition prevents
                        # to trigger the StopIteration exception
                        break

                raw_item = next(cache_items)
                yield issue

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
        return 'issue'

    def __fetch_issue_content_from_cache(self, cache_items):
        """Fetch issue content from cache"""

        raw_issue_content = next(cache_items)
        issue_content = json.loads(raw_issue_content)

        raw_data = next(cache_items)

        activities = []
        messages = []
        attachments = []
        while raw_data != '{ISSUE-CORE-END}':
            if raw_data == '{ACTIVITIES}':
                activities.extend(self.__fetch_issue_activities_from_cache(cache_items))
            elif raw_data == '{MESSAGES}':
                messages.extend(self.__fetch_issue_messages_from_cache(cache_items))
            elif raw_data == '{ATTACHMENTS}':
                attachments.extend(self.__fetch_issue_attachments_from_cache(cache_items))

            raw_data = next(cache_items)

        return issue_content, activities, messages, attachments

    def __fetch_issue_messages_from_cache(self, cache_items):
        """Fetch issue messages from cache"""

        messages_raw = next(cache_items)
        messages = json.loads(messages_raw)

        for msg in messages['entries']:
            _ = next(cache_items)
            msg['owner_data'] = self.__fetch_user_from_cache(cache_items)

        return messages['entries']

    def __fetch_issue_attachments_from_cache(self, cache_items):
        """Fetch issue attachments from cache"""

        attachments_raw = next(cache_items)
        attachments = json.loads(attachments_raw)

        return attachments['entries']

    def __fetch_issue_activities_from_cache(self, cache_items):
        """Fetch issue activities from cache"""

        activities_raw = next(cache_items)
        activities = json.loads(activities_raw)

        for act in activities['entries']:
            _ = next(cache_items)
            act['person_data'] = self.__fetch_user_from_cache(cache_items)

        return activities['entries']

    def __fetch_user_from_cache(self, cache_items):
        """Fetch user from cache"""

        _ = next(cache_items)
        raw_user = next(cache_items)
        user = json.loads(raw_user)

        return user

    def __fetch_issues_from_cache(self, cache_items):
        """Fetch issues from cache"""

        raw_issues = next(cache_items)
        issues = json.loads(raw_issues)['entries']
        return issues

    def __init_extra_issue_fields(self, issue):
        """Add fields to an issue"""

        issue['bug_data'] = {}
        issue['owner_data'] = {}
        issue['assignee_data'] = {}

        return issue

    def __extract_issue_id(self, bug_link):
        """Extract issue id from bug link"""

        return bug_link.split('/')[-1]

    def _fetch(self, from_date):
        """Fetch the issues from a project (distribution/package)"""

        issues_groups = self.client.issues(start=from_date)

        for raw_issues in issues_groups:
            self._push_cache_queue('{ISSUES}')
            self._push_cache_queue(raw_issues)

            issues = json.loads(raw_issues)['entries']
            for issue in issues:
                issue = self.__init_extra_issue_fields(issue)
                issue_id = self.__extract_issue_id(issue['bug_link'])

                for field in TARGET_ISSUE_FIELDS:

                    if not issue[field]:
                        continue

                    if field == 'bug_link':
                        self._push_cache_queue('{ISSUE-CORE-START}')
                        issue['bug_data'] = self.__fetch_issue_data(issue_id)
                        issue['activity_data'] = [activity for activity in self.__fetch_issue_activities(issue_id)]
                        issue['messages_data'] = [message for message in self.__fetch_issue_messages(issue_id)]
                        issue['attachments_data'] = [attachment for attachment in self.__fetch_issue_attachments(issue_id)]
                        self._push_cache_queue('{ISSUE-CORE-END}')
                    elif field == 'assignee_link':
                        issue['assignee_data'] = self.__fetch_user_data('{ASSIGNEE}', issue[field])
                    elif field == 'owner_link':
                        issue['owner_data'] = self.__fetch_user_data('{OWNER}', issue[field])

                self._push_cache_queue('{ISSUE-END}')

                yield issue

            self._flush_cache_queue()

        self._push_cache_queue('{}{}')
        self._flush_cache_queue()

    def __fetch_issue_data(self, issue_id):
        """Get data associated to an issue"""

        raw_issue = self.client.issue(issue_id)
        self._push_cache_queue(raw_issue)
        issue = json.loads(raw_issue)

        return issue

    def __fetch_issue_attachments(self, issue_id):
        """Get attachments of an issue"""

        for attachments_raw in self.client.issue_collection(issue_id, "attachments"):
            attachments = json.loads(attachments_raw)
            self._push_cache_queue('{ATTACHMENTS}')
            self._push_cache_queue(attachments_raw)

            for attachment in attachments['entries']:
                yield attachment

    def __fetch_issue_messages(self, issue_id):
        """Get messages of an issue"""

        for messages_raw in self.client.issue_collection(issue_id, "messages"):
            messages = json.loads(messages_raw)
            self._push_cache_queue('{MESSAGES}')
            self._push_cache_queue(messages_raw)

            for msg in messages['entries']:
                msg['owner_data'] = self.__fetch_user_data('{OWNER}', msg['owner_link'])
                yield msg

    def __fetch_issue_activities(self, issue_id):
        """Get activities on an issue"""

        for activities_raw in self.client.issue_collection(issue_id, "activity"):
            activities = json.loads(activities_raw)
            self._push_cache_queue('{ACTIVITIES}')
            self._push_cache_queue(activities_raw)

            for act in activities['entries']:
                act['person_data'] = self.__fetch_user_data('{PERSON}', act['person_link'])
                yield act

    def __fetch_user_data(self, tag_type, user_link):
        """Get data associated to an user"""

        user_name = self.client.user_name(user_link)
        self._push_cache_queue(tag_type)
        self._push_cache_queue('{USER}')

        user = {}

        if not user_name:
            self._push_cache_queue('{}')
            return user

        user_raw = self.client.user(user_name)
        self._push_cache_queue(user_raw)

        user = json.loads(user_raw)

        return user


class LaunchpadClient:
    """Client for retrieving information from Launchpad API"""

    # Max retries for handled HTTP errors
    MAX_RETRIES = 5
    _users = {}

    def __init__(self, distribution, package=None,
                 consumer_key=None, api_token=None,
                 items_per_page=ITEMS_PER_PAGE, sleep_time=SLEEP_TIME):
        self.consumer_key = consumer_key
        self.api_token = api_token
        self.distribution = distribution
        self.package = package
        self.items_per_page = items_per_page
        self.sleep_time = sleep_time

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
            raw_user = self.__send_request(url_user, headers=self.__get_headers())
            user = raw_user
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 410:
                logger.warning("Data is not available due to HTTP 410 Gone - %s", url_user)
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

        path = urijoin("bugs", str(issue_id))
        url_issue = self.__get_url(path)
        raw_text = self.__send_request(url_issue, headers=self.__get_headers())

        return raw_text

    def issue_collection(self, issue_id, collection_name):
        """Get a collection list of a given issue"""

        path = urijoin("bugs", str(issue_id), collection_name)
        url_collection = self.__get_url(path)
        payload = {'ws.size': self.items_per_page, 'ws.start': 0, 'order_by': 'date_last_updated'}

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

        return LAUNCHPAD_API_URL + self.distribution

    def __get_url_distribution_package(self):
        """Build URL distribution package"""

        return urijoin(self.__get_url_distribution(), "+source", self.package)

    def __get_url(self, path):
        """Build genereic URL"""

        return LAUNCHPAD_API_URL + path

    def _generate_signature(self):
        """Get HTTP request signature based on consumer_key and token"""

        sign = hmac.new(bytes(self.consumer_key.encode('utf-8')),
                        bytes(self.api_token.encode('utf-8')),
                        hashlib.sha256).hexdigest()
        return sign

    def __get_headers(self):
        """Set header for request"""

        headers = {'Content-type': 'application/json',
                   'date': datetime_utcnow().strftime('%Y-%m-%d %H:%M:%S')}

        return headers

    def __send_request(self, url, params=None, headers=None):
        """Send request"""

        if self.consumer_key and self.api_token:
            headers['Sign'] = self._generate_signature()

        retries = 0

        while retries < self.MAX_RETRIES:
            try:
                r = requests.get(url,
                                 params=params,
                                 headers=headers)
                break
            except requests.exceptions.ConnectionError:
                logger.warning("Connection was lost, the backend will sleep for " +
                               str(self.sleep_time) + "s before starting again")
                time.sleep(self.sleep_time * retries)
                retries += 1

        r.raise_for_status()

        return r.text

    def __build_payload(self, size, operation=False, startdate=None):
        """Build payload"""

        payload = {
            'ws.size': size,
            'order_by': 'date_last_updated',
            'omit_duplicates': 'false',
            'status': ["New", "Incomplete", "Opinion", "Invalid", "Won't Fix",
                       "Expired", "Confirmed", "Triaged", "In Progress",
                       "Fix Committed", "Fix Released",
                       "Incomplete (with response)",
                       "Incomplete (without response)"]
        }

        if operation:
            payload['ws.op'] = 'searchTasks'
        if startdate:
            startdate = startdate.isoformat()
            payload['modified_since'] = startdate

        return payload

    def __fetch_items(self, path, payload):
        """Return the items from Launchpad API using pagination"""

        page = 0  # current page
        url_next = path
        fetch_data = True

        while fetch_data:
            logger.debug("Fetching page: %i", page)

            try:
                raw_content = self.__send_request(url_next, payload, self.__get_headers())
                content = json.loads(raw_content)
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 410:
                    logger.warning("Data is not available due to HTTP 410 Gone - %s", url_next)
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

    @staticmethod
    def setup_cmd_parser():
        """Returns the Launchpad argument parser."""

        parser = BackendCommandArgumentParser(from_date=True,
                                              cache=True,
                                              token_auth=True)

        # Optional arguments
        group = parser.parser.add_argument_group('Launchpad arguments')
        group.add_argument('--items-per-page', dest='items_per_page',
                           help="Items per page")
        group.add_argument('--sleep-time', dest='sleep_time',
                           help="Sleep time in case of connection lost")
        group.add_argument('--consumer-key', dest='consumer_key',
                           help="Consumer key")

        # Required arguments
        parser.parser.add_argument('distribution',
                                   help="Launchpad distribution")

        return parser
