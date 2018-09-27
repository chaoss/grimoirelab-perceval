# -*- coding: utf-8 -*-
#
# Copyright (C) 2015-2018 Bitergia
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
#     Assad Montasser <assad.montasser@ow2.org>
#     Valerio Cosentino <valcos@bitergia.com>
#

import json
import logging
import requests

import urllib.parse

from grimoirelab_toolkit.datetime import (datetime_to_utc,
                                          datetime_utcnow,
                                          str_to_datetime)
from grimoirelab_toolkit.uris import urijoin

from ...backend import (Backend,
                        BackendCommand,
                        BackendCommandArgumentParser)
from ...client import HttpClient, RateLimitHandler
from ...utils import DEFAULT_DATETIME

CATEGORY_ISSUE = "issue"
CATEGORY_MERGE_REQUEST = "merge_request"

GITLAB_URL = "https://gitlab.com/"
GITLAB_API_URL = "https://gitlab.com/api/v4"

# Range before sleeping until rate limit reset
MIN_RATE_LIMIT = 10
MAX_RATE_LIMIT = 500

PER_PAGE = 100

# Default sleep time and retries to deal with connection/server problems
DEFAULT_SLEEP_TIME = 1
MAX_RETRIES = 5

TARGET_ISSUE_FIELDS = ['user_notes_count', 'award_emoji']

logger = logging.getLogger(__name__)


class GitLab(Backend):
    """GitLab backend for Perceval.

    This class allows the fetch the issues stored in GitLab
    repository.

    :param owner: GitLab owner
    :param repository: GitLab repository from the owner
    :param api_token: GitLab auth token to access the API
    :param base_url: GitLab URL in enterprise edition case;
        when no value is set the backend will be fetch the data
        from the GitLab public site.
    :param tag: label used to mark the data
    :param archive: archive to store/retrieve items
    :param sleep_for_rate: sleep until rate limit is reset
    :param min_rate_to_sleep: minimun rate needed to sleep until
         it will be reset
    :param max_retries: number of max retries to a data source
        before raising a RetryError exception
    :param sleep_time: time to sleep in case
    """
    version = '0.5.1'

    CATEGORIES = [CATEGORY_ISSUE, CATEGORY_MERGE_REQUEST]

    def __init__(self, owner=None, repository=None,
                 api_token=None, base_url=None, tag=None, archive=None,
                 sleep_for_rate=False, min_rate_to_sleep=MIN_RATE_LIMIT,
                 max_retries=MAX_RETRIES, sleep_time=DEFAULT_SLEEP_TIME):
        origin = base_url if base_url else GITLAB_URL
        origin = urijoin(origin, owner, repository)

        super().__init__(origin, tag=tag, archive=archive)
        self.base_url = base_url
        self.owner = owner
        self.repository = repository
        self.api_token = api_token
        self.sleep_for_rate = sleep_for_rate
        self.min_rate_to_sleep = min_rate_to_sleep
        self.max_retries = max_retries
        self.sleep_time = sleep_time
        self.client = None
        self._users = {}  # internal users cache

    def fetch(self, category=CATEGORY_ISSUE, from_date=DEFAULT_DATETIME):
        """Fetch the issues/merge requests from the repository.

        The method retrieves, from a GitLab repository, the issues/merge requests
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
        """Fetch the items (issues or merge_requests)

        :param category: the category of items to fetch
        :param kwargs: backend arguments

        :returns: a generator of items
        """
        from_date = kwargs['from_date']

        if category == CATEGORY_ISSUE:
            items = self.__fetch_issues(from_date)
        else:
            items = self.__fetch_merge_requests(from_date)

        return items

    @classmethod
    def has_archiving(cls):
        """Returns whether it supports archivng items on the fetch process.

        :returns: this backend supports items archive
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
        """Extracts the identifier from a GitLab item."""

        return str(item['id'])

    @staticmethod
    def metadata_updated_on(item):
        """Extracts the update time from a GitLab item.

        The timestamp used is extracted from 'updated_at' field.
        This date is converted to UNIX timestamp format. As GitLab
        dates are in UTC the conversion is straightforward.

        :param item: item generated by the backend

        :returns: a UNIX timestamp
        """
        ts = item['updated_at']
        ts = str_to_datetime(ts)

        return ts.timestamp()

    @staticmethod
    def metadata_category(item):
        """Extracts the category from a GitLab item.

        This backend only generates one type of item which is
        'issue'.
        """
        if "merged_by" in item:
            category = CATEGORY_MERGE_REQUEST
        else:
            category = CATEGORY_ISSUE

        return category

    def _init_client(self, from_archive=False):
        """Init client"""

        return GitLabClient(self.owner, self.repository, self.api_token, self.base_url,
                            self.sleep_for_rate, self.min_rate_to_sleep,
                            self.sleep_time, self.max_retries,
                            self.archive, from_archive)

    def __fetch_issues(self, from_date):
        """Fetch the issues"""

        issues_groups = self.client.issues(from_date=from_date)

        for raw_issues in issues_groups:
            issues = json.loads(raw_issues)
            for issue in issues:
                self.__init_issue_extra_fields(issue)

                issue['notes_data'] = \
                    self.__get_issue_notes(issue['iid'])
                issue['award_emoji_data'] = \
                    self.__get_award_emoji(GitLabClient.ISSUES, issue['iid'])

                yield issue

    def __get_issue_notes(self, issue_id):
        """Get issue notes"""

        notes = []

        group_notes = self.client.notes(GitLabClient.ISSUES, issue_id)

        for raw_notes in group_notes:

            for note in json.loads(raw_notes):
                note_id = note['id']
                note['award_emoji_data'] = \
                    self.__get_note_award_emoji(GitLabClient.ISSUES, issue_id, note_id)
                notes.append(note)

        return notes

    def __fetch_merge_requests(self, from_date):
        """Fetch the merge requests"""

        merges_groups = self.client.merges(from_date=from_date)

        for raw_merges in merges_groups:
            merges = json.loads(raw_merges)
            for merge in merges:
                merge_id = merge['iid']

                # The single merge_request API call returns a more
                # complete merge request, thus we inflate it with
                # other data (e.g., notes, emojis, versions)
                merge_full_raw = self.client.merge(merge_id)
                merge_full = json.loads(merge_full_raw)

                self.__init_merge_extra_fields(merge_full)

                merge_full['notes_data'] = self.__get_merge_notes(merge_id)
                merge_full['award_emoji_data'] = self.__get_award_emoji(GitLabClient.MERGES, merge_id)
                merge_full['versions_data'] = self.__get_merge_versions(merge_id)

                yield merge_full

    def __get_merge_notes(self, merge_id):
        """Get merge notes"""

        notes = []

        group_notes = self.client.notes(GitLabClient.MERGES, merge_id)

        for raw_notes in group_notes:
            for note in json.loads(raw_notes):
                note_id = note['id']
                note['award_emoji_data'] = \
                    self.__get_note_award_emoji(GitLabClient.MERGES, merge_id, note_id)
                notes.append(note)

        return notes

    def __get_merge_versions(self, merge_id):
        """Get merge versions"""

        versions = []

        group_versions = self.client.merge_versions(merge_id)

        for raw_versions in group_versions:
            for version in json.loads(raw_versions):
                version_id = version['id']
                version_full_raw = self.client.merge_version(merge_id, version_id)
                version_full = json.loads(version_full_raw)

                version_full.pop('diffs', None)
                versions.append(version_full)

        return versions

    def __get_award_emoji(self, item_type, item_id):
        """Get award emojis for issue/merge request"""

        emojis = []

        group_emojis = self.client.emojis(item_type, item_id)
        for raw_emojis in group_emojis:

            for emoji in json.loads(raw_emojis):
                emojis.append(emoji)

        return emojis

    def __get_note_award_emoji(self, item_type, item_id, note_id):
        """Fetch emojis for a note of an issue/merge request"""

        emojis = []

        group_emojis = self.client.note_emojis(item_type, item_id, note_id)
        try:
            for raw_emojis in group_emojis:

                for emoji in json.loads(raw_emojis):
                    emojis.append(emoji)
        except requests.exceptions.HTTPError as error:
            if error.response.status_code == 404:
                logger.warning("Emojis not available for %s ",
                               urijoin(item_type, str(item_id), GitLabClient.NOTES,
                                       str(note_id), GitLabClient.EMOJI))
                return emojis

        return emojis

    def __init_issue_extra_fields(self, issue):
        """Add fields to an issue"""

        issue['notes_data'] = []
        issue['award_emoji_data'] = []

    def __init_merge_extra_fields(self, merge):
        """Add fields to a merge requests"""

        merge['notes_data'] = []
        merge['award_emoji_data'] = []
        merge['versions_data'] = []


class GitLabClient(HttpClient, RateLimitHandler):
    """Client for retieving information from GitLab API

    :param owner: GitLab owner
    :param repository: GitLab owner's repository
    :param token: GitLab auth token to access the API
    :param base_url: GitLab URL in enterprise edition case;
        when no value is set the backend will be fetch the data
        from the GitLab public site.
     :param sleep_for_rate: sleep until rate limit is reset
     :param min_rate_to_sleep: minimun rate needed to sleep until
          it will be reset
     :param sleep_time: time to sleep in case
         of connection problems
    :param max_retries: number of max retries to a data source
         before raising a RetryError exception
    :param archive: an archive to store/read fetched data
    :param from_archive: it tells whether to write/read the archive
    """

    RATE_LIMIT_HEADER = "RateLimit-Remaining"
    RATE_LIMIT_RESET_HEADER = "RateLimit-Reset"

    ISSUES = "issues"
    MERGES = "merge_requests"
    NOTES = "notes"
    EMOJI = "award_emoji"
    PROJECTS = "projects"
    VERSIONS = "versions"

    _users = {}       # users cache

    def __init__(self, owner, repository, token, base_url=None,
                 sleep_for_rate=False, min_rate_to_sleep=MIN_RATE_LIMIT,
                 sleep_time=DEFAULT_SLEEP_TIME, max_retries=MAX_RETRIES,
                 archive=None, from_archive=False):
        self.owner = owner
        self.repository = repository
        self.token = token
        self.rate_limit = None
        self.sleep_for_rate = sleep_for_rate

        if base_url:
            parts = urllib.parse.urlparse(base_url)
            base_url = parts.scheme + '://' + parts.netloc + '/api/v4'
        else:
            base_url = GITLAB_API_URL

        super().__init__(base_url, sleep_time=sleep_time, max_retries=max_retries,
                         extra_headers=self._set_extra_headers(), extra_retry_after_status=[502],
                         archive=archive, from_archive=from_archive)
        super().setup_rate_limit_handler(rate_limit_header=self.RATE_LIMIT_HEADER,
                                         rate_limit_reset_header=self.RATE_LIMIT_RESET_HEADER,
                                         sleep_for_rate=sleep_for_rate,
                                         min_rate_to_sleep=min_rate_to_sleep)

        self._init_rate_limit()

    def issues(self, from_date=None):
        """Get the issues from pagination"""

        payload = {
            'state': 'all',
            'order_by': 'updated_at',
            'sort': 'asc',
            'per_page': PER_PAGE
        }

        if from_date:
            payload['updated_after'] = from_date.isoformat()

        return self.fetch_items(GitLabClient.ISSUES, payload)

    def merges(self, from_date=None):
        """Get the merge requests from pagination"""

        payload = {
            'state': 'all',
            'order_by': 'updated_at',
            'sort': 'asc',
            'view': 'simple',
            'per_page': PER_PAGE
        }

        if from_date:
            payload['updated_after'] = from_date.isoformat()

        return self.fetch_items(GitLabClient.MERGES, payload)

    def merge(self, merge_id):
        """Get the merge full data"""

        path = urijoin(self.base_url,
                       GitLabClient.PROJECTS, self.owner + '%2F' + self.repository,
                       GitLabClient.MERGES, merge_id)

        response = self.fetch(path)

        return response.text

    def merge_versions(self, merge_id):
        """Get the merge versions from pagination"""

        payload = {
            'order_by': 'updated_at',
            'sort': 'asc',
            'per_page': PER_PAGE
        }

        path = urijoin(GitLabClient.MERGES, str(merge_id), GitLabClient.VERSIONS)
        return self.fetch_items(path, payload)

    def merge_version(self, merge_id, version_id):
        """Get merge version detail"""

        path = urijoin(self.base_url,
                       GitLabClient.PROJECTS, self.owner + '%2F' + self.repository,
                       GitLabClient.MERGES, merge_id, GitLabClient.VERSIONS, version_id)

        response = self.fetch(path)

        return response.text

    def notes(self, item_type, item_id):
        """Get the notes from pagination"""

        payload = {
            'order_by': 'updated_at',
            'sort': 'asc',
            'per_page': PER_PAGE
        }

        path = urijoin(item_type, str(item_id), GitLabClient.NOTES)

        return self.fetch_items(path, payload)

    def emojis(self, item_type, item_id):
        """Get emojis from pagination"""

        payload = {
            'order_by': 'updated_at',
            'sort': 'asc',
            'per_page': PER_PAGE
        }

        path = urijoin(item_type, str(item_id), GitLabClient.EMOJI)

        return self.fetch_items(path, payload)

    def note_emojis(self, item_type, item_id, note_id):
        """Get emojis of a note"""

        payload = {
            'order_by': 'updated_at',
            'sort': 'asc',
            'per_page': PER_PAGE
        }

        path = urijoin(item_type, str(item_id), GitLabClient.NOTES,
                       str(note_id), GitLabClient.EMOJI)

        return self.fetch_items(path, payload)

    def calculate_time_to_reset(self):
        """Calculate the seconds to reset the token requests, by obtaining the different
        between the current date and the next date when the token is fully regenerated.
        """

        time_to_reset = self.rate_limit_reset_ts - (datetime_utcnow().replace(microsecond=0).timestamp() + 1)

        if time_to_reset < 0:
            time_to_reset = 0

        return time_to_reset

    def fetch(self, url, payload=None, headers=None, method=HttpClient.GET, stream=False):
        """Fetch the data from a given URL.

        :param url: link to the resource
        :param payload: payload of the request
        :param headers: headers of the request
        :param method: type of request call (GET or POST)
        :param stream: defer downloading the response body until the response content is available

        :returns a response object
        """
        if not self.from_archive:
            self.sleep_for_rate_limit()

        response = super().fetch(url, payload, headers, method, stream)

        if not self.from_archive:
            self.update_rate_limit(response)

        return response

    def fetch_items(self, path, payload):
        """Return the items from GitLab API using links pagination"""

        page = 0  # current page
        last_page = None  # last page
        url_next = urijoin(self.base_url, GitLabClient.PROJECTS, self.owner + '%2F' + self.repository, path)

        logger.debug("Get GitLab paginated items from " + url_next)

        response = self.fetch(url_next, payload=payload)

        items = response.text
        page += 1

        if 'last' in response.links:
            last_url = response.links['last']['url']
            last_page = last_url.split('&page=')[1].split('&')[0]
            last_page = int(last_page)
            logger.debug("Page: %i/%i" % (page, last_page))

        while items:
            yield items

            items = None

            if 'next' in response.links:
                url_next = response.links['next']['url']  # Loving requests :)
                response = self.fetch(url_next, payload=payload)
                page += 1

                items = response.text
                logger.debug("Page: %i/%i" % (page, last_page))

    @staticmethod
    def sanitize_for_archive(url, headers, payload):
        """Sanitize payload of a HTTP request by removing the token information
        before storing/retrieving archived items

        :param: url: HTTP url request
        :param: headers: HTTP headers request
        :param: payload: HTTP payload request

        :returns url, headers and the sanitized payload
        """
        if headers and 'PRIVATE-TOKEN' in headers:
            headers.pop('PRIVATE-TOKEN', None)

        return url, headers, payload

    def _set_extra_headers(self):
        """Set extra headers for session"""

        headers = {}
        if self.token:
            headers = {'PRIVATE-TOKEN': self.token}

        return headers

    def _init_rate_limit(self):
        """Initialize rate limit information"""

        url = urijoin(self.base_url, 'projects', self.owner + '%2F' + self.repository)
        try:
            response = super().fetch(url)
            self.update_rate_limit(response)
        except requests.exceptions.HTTPError as error:
            if error.response.status_code == 401:
                raise error
            else:
                logger.warning("Rate limit not initialized: %s", error)


class GitLabCommand(BackendCommand):
    """Class to run GitLab backend from the command line."""

    BACKEND = GitLab

    @staticmethod
    def setup_cmd_parser():
        """Returns the GitLab argument parser."""

        parser = BackendCommandArgumentParser(from_date=True,
                                              token_auth=True,
                                              archive=True)

        # GitLab options
        group = parser.parser.add_argument_group('GitLab arguments')
        group.add_argument('--enterprise-url', dest='base_url',
                           help="Base URL for GitLab Enterprise instance")
        group.add_argument('--sleep-for-rate', dest='sleep_for_rate',
                           action='store_true',
                           help="sleep for getting more rate")
        group.add_argument('--min-rate-to-sleep', dest='min_rate_to_sleep',
                           default=MIN_RATE_LIMIT, type=int,
                           help="sleep until reset when the rate limit \
                               reaches this value")

        # Generic client options
        group.add_argument('--max-retries', dest='max_retries',
                           default=MAX_RETRIES, type=int,
                           help="number of API call retries")
        group.add_argument('--sleep-time', dest='sleep_time',
                           default=DEFAULT_SLEEP_TIME, type=int,
                           help="sleeping time between API call retries")

        # Positional arguments
        parser.parser.add_argument('owner',
                                   help="GitLab owner")
        parser.parser.add_argument('repository',
                                   help="GitLab repository")

        return parser
