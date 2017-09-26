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

import json
import logging
import hmac
import hashlib
import requests
import time

from grimoirelab.toolkit.datetime import datetime_utcnow, datetime_to_utc, str_to_datetime

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

    def __init__(self, distribution=None, consumer_key=None, api_token=None,
                 package=None, items_per_page=None, tag=None, cache=None,
                 sleep_time=None):

        super().__init__(LAUNCHPAD_API_URL, tag=tag, cache=cache)
        self.consumer_key = consumer_key
        self.distribution = distribution
        self.package = package
        self.api_token = api_token
        self.items_per_page = items_per_page
        self.sleep_time = sleep_time
        self.client = LaunchpadClient(distribution, consumer_key, api_token,
                                      package=package, items_per_page=items_per_page,
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

        self._purge_cache_queue()

        from_date = datetime_to_utc(from_date)

        issues_groups = self.client.get_issues(start=from_date)

        for raw_issues in issues_groups:
            self._push_cache_queue('{ISSUES}')
            self._push_cache_queue(raw_issues)
            self._flush_cache_queue()
            issues = json.loads(raw_issues)['entries']
            for issue in issues:
                issue_id = issue['bug_link'].split('/')[-1]

                for field in TARGET_ISSUE_FIELDS:
                    issue[field + '_data'] = {}

                    if not issue[field]:
                        continue

                    if field == 'bug_link':
                        issue[field + '_data'] = self.__get_issue_data(issue_id)

                    if field == 'assignee_link':
                        issue[field + '_data'] = self.__get_user_data('{ASSIGNEE}', issue[field])

                    if field == 'owner_link':
                        issue[field + '_data'] = self.__get_user_data('{OWNER}', issue[field])

                self._push_cache_queue('{ISSUE-END}')
                self._flush_cache_queue()

                yield issue
        self._push_cache_queue('{}{}')
        self._flush_cache_queue()

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

            for issue in issues:
                self.__init_extra_issue_fields(issue)
                raw_item = next(cache_items)

                while raw_item != '{ISSUE-END}':
                    try:
                        if raw_item == '{OWNER}':
                            issue['owner_link_data'] = self.__fetch_user_from_cache(cache_items)
                        elif raw_item == '{ASSIGNEE}':
                            issue['assignee_link_data'] = self.__fetch_user_from_cache(cache_items)
                        elif raw_item == '{ISSUE-CORE-START}':
                            issue['bug_link_data'] = self.__fetch_issue_content_from_cache(cache_items)

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

        return str(item['bug_link_data']['id'])

    @staticmethod
    def metadata_updated_on(item):
        """Extracts the update time from a Launchpad item.

        The timestamp used is extracted from 'updated_at' field.
        This date is converted to UNIX timestamp format. As Launchpad
        dates are in UTC the conversion is straightforward.

        :param item: item generated by the backend

        :returns: a UNIX timestamp
        """
        ts = item['bug_link_data']['date_last_updated']
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

        issue_content['activity_collection_link_data'] = activities
        issue_content['messages_collection_link_data'] = messages
        issue_content['attachments_collection_link_data'] = attachments

        return issue_content

    def __fetch_issue_messages_from_cache(self, cache_items):
        """Fetch issue messages from cache"""

        messages_raw = next(cache_items)
        messages = json.loads(messages_raw)

        for msg in messages['entries']:
            tag = next(cache_items)
            msg['owner_link_data'] = self.__fetch_user_from_cache(cache_items)

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
            person_tag = next(cache_items)
            act['person_link_data'] = self.__fetch_user_from_cache(cache_items)

        return activities['entries']

    def __fetch_user_from_cache(self, cache_items):
        """Fetch user from cache"""

        user_tag = next(cache_items)
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

        issue['bug_link_data'] = {}
        issue['owner_link_data'] = {}
        issue['assignee_link_data'] = {}

    def __get_issue_data(self, issue_id):
        """Get data associated to an issue"""
        raw_issue = self.client.get_issue(issue_id)

        self._push_cache_queue('{ISSUE-CORE-START}')
        self._push_cache_queue(raw_issue)
        self._flush_cache_queue()

        issue = json.loads(raw_issue)

        issue['activity_collection_link_data'] = [issue for page in self.__get_issue_activities(issue['id']) for issue in page]
        issue['messages_collection_link_data'] = [msg for page in self.__get_issue_messages(issue['id']) for msg in page]
        issue['attachments_collection_link_data'] = [att for page in self.__get_issue_attachments(issue['id']) for att in page]

        self._push_cache_queue('{ISSUE-CORE-END}')
        self._flush_cache_queue()

        return issue

    def __get_issue_attachments(self, issue_id):
        """Get attachments of an issue"""

        for attachments_raw in self.client.get_issue_collection(issue_id, "attachments"):
            attachments = json.loads(attachments_raw)
            self._push_cache_queue('{ATTACHMENTS}')
            self._push_cache_queue(attachments_raw)
            self._flush_cache_queue()

            attachments = json.loads(attachments_raw)['entries']
            yield attachments

    def __get_issue_messages(self, issue_id):
        """Get messages of an issue"""

        for messages_raw in self.client.get_issue_collection(issue_id, "messages"):
            messages = json.loads(messages_raw)
            self._push_cache_queue('{MESSAGES}')
            self._push_cache_queue(messages_raw)
            self._flush_cache_queue()

            for msg in messages['entries']:
                msg['owner_link_data'] = self.__get_user_data('{OWNER}', msg['owner_link'])
                self._flush_cache_queue()

            yield messages['entries']

    def __get_issue_activities(self, issue_id):
        """Get activities on an issue"""

        for activities_raw in self.client.get_issue_collection(issue_id, "activity"):
            self._push_cache_queue('{ACTIVITIES}')
            self._push_cache_queue(activities_raw)
            activities = json.loads(activities_raw)

            for act in activities['entries']:
                act['person_link_data'] = self.__get_user_data('{PERSON}', act['person_link'])

            yield activities['entries']

    def __get_user_data(self, tag_type, user_link):
        """Get data associated to an user"""

        user_name = self.client.get_user_name(user_link)
        self._push_cache_queue(tag_type)
        self._flush_cache_queue()
        self._push_cache_queue('{USER}')

        user = {}

        if not user_name:
            self._push_cache_queue('{}')
            self._flush_cache_queue()
            return user

        user_raw = self.client.get_user(user_name)
        self._push_cache_queue(user_raw)
        self._flush_cache_queue()

        user = json.loads(user_raw)

        return user


class LaunchpadClient:
    """Client for retrieving information from Launchpad API"""

    _users = {}

    def __init__(self, distribution, consumer_key, token, package=None,
                 items_per_page=None, sleep_time=None):
        self.distribution = distribution
        self.package = package
        self.consumer_key = consumer_key
        self.token = token
        self.items_per_page = items_per_page
        self.sleep_time = sleep_time

        if not self.items_per_page:
            self.items_per_page = ITEMS_PER_PAGE
        if not self.sleep_time:
            self.sleep_time = SLEEP_TIME

    def get_issues(self, start=None):
        """Get the issues from pagination"""

        payload = self.__get_payload(size=self.items_per_page, operation=True, startdate=start)
        path = self.__get_url_project()
        return self.__fetch_items(path=path, payload=payload)

    def get_user(self, user_name):
        """Get the user data by URL"""

        user = None

        if user_name in self._users:
            return self._users[user_name]

        url_user = self.__get_url("~" + user_name)

        logging.info("Getting info for %s" % (url_user))

        try:
            r = self.__send_request(url_user, headers=self.__get_headers())
            user = r.text
        except requests.exceptions.HTTPError:
            logger.warning("Response from %s is not in JSON-like format, user data cannot be retrieved", url_user)
            user = '{}'

        self._users[user_name] = user

        return user

    def get_user_name(self, user_link):
        """Get user name from link"""

        return user_link.split('/')[-1][1:]

    def get_issue(self, issue_id):
        """Get the issue data by its ID"""

        url_issue = self.__get_url("bugs/" + str(issue_id))
        r = self.__send_request(url_issue, headers=self.__get_headers())

        return r.text

    def get_issue_collection(self, issue_id, collection_name):
        """Get a collection list of a given issue"""

        url_collection = self.__get_url("bugs/" + str(issue_id) + "/" + collection_name)
        payload = {'ws.size': self.items_per_page, 'ws.start': 0, 'orderby': '-datecreated'}

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

        return self.__get_url_distribution() + "/+source/" + self.package

    def __get_url(self, path):
        """Build genereic URL"""

        return LAUNCHPAD_API_URL + path

    def __get_signature(self):
        """Get HTTP request signature based on consumer_key and token"""

        if self.consumer_key and self.token:
            sign = hmac.new(bytes(self.consumer_key.encode('utf-8')),
                            bytes(self.token.encode('utf-8')),
                            hashlib.sha256).hexdigest()
            return sign

    def __get_headers(self):
        """Set header for request"""

        headers = {'Content-type': 'application/json',
                   'date': datetime_utcnow().strftime('%Y-%m-%d %H:%M:%S')}

        return headers

    def __send_request(self, url, params=None, headers=None):
        """Send request"""

        while True:
            try:
                sign = self.__get_signature()
                r = requests.get(url,
                                 params=params,
                                 headers=headers.update({'Sign': sign}))
                break
            except requests.exceptions.ConnectionError:
                time.sleep(self.sleep_time)
                logger.warning("Connection was lost, the backend will sleep for " +
                               str(self.sleep_time) + "s before starting again")
                continue

        if r.status_code != 200:
            logger.warning("Wrong request: %s", r.text)
            raise requests.exceptions.HTTPError

        return r

    def __get_payload(self, size, operation=False, startdate=None):
        """Build payload"""

        payload = {'orderby': '-datecreated', 'ws.size': size}

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
        page_size = payload['ws.size']

        try:
            r = self.__send_request(url_next, payload, self.__get_headers())
            raw_content = r.text
            content = json.loads(raw_content)
        except requests.exceptions.HTTPError:
            logger.warning("Response from %s is not in JSON-like format, data cannot be retrieved", url_next)
            raw_content = '{"total_size": 0, "start": 0, "entries": []}'
            content = json.loads(raw_content)

        page += 1

        if content['total_size'] % page_size == 0:
            last_page = (content['total_size']) // page_size
        else:
            last_page = (content['total_size']) // page_size + 1

        logger.debug("Page: %i/%i" % (page, last_page))

        while raw_content:
            yield raw_content

            raw_content = None

            if 'next_collection_link' in content:
                url_next = content['next_collection_link']

                try:
                    r = self.__send_request(url_next, headers=self.__get_headers())
                    raw_content = r.text
                    content = json.loads(raw_content)
                except requests.exceptions.HTTPError:
                    logger.warning("Response from %s is not in JSON-like format, data cannot be retrieved", url_next)
                    raw_content = '{"total_size": 0, "start": 0, "entries": []}'
                    content = json.loads(raw_content)

                logger.debug("Page: %i/%i" % (page, last_page))

                page += 1


class LaunchpadCommand(BackendCommand):
    """Class to run Launchpad backend from the command line."""

    BACKEND = Launchpad

    @staticmethod
    def setup_cmd_parser():
        """Returns the Launchpad argument parser."""

        parser = BackendCommandArgumentParser(from_date=True,
                                              token_auth=True,
                                              cache=True)

        # Positional arguments
        parser.parser.add_argument('distribution',
                                   help="Launchpad distribution")
        parser.parser.add_argument('consumer_key',
                                   help="Consumer key to access the API")
        parser.parser.add_argument('api_token',
                                   help="Api token to access the API")

        return parser
