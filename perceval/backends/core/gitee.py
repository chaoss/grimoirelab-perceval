#!/usr/bin/env python3
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
#     Willem Jiang <willem.jiang@gmail.com>

import json
import logging

import requests
from grimoirelab_toolkit.datetime import (datetime_to_utc,
                                          datetime_utcnow,
                                          str_to_datetime)
from grimoirelab_toolkit.uris import urijoin

from perceval.backend import (Backend,
                              BackendCommand,
                              BackendCommandArgumentParser,
                              DEFAULT_SEARCH_FIELD)
from perceval.client import HttpClient, RateLimitHandler
from perceval.utils import DEFAULT_DATETIME, DEFAULT_LAST_DATETIME

CATEGORY_ISSUE = "issue"
CATEGORY_PULL_REQUEST = "pull_request"
CATEGORY_REPO = 'repository'

GITEE_URL = "https://gitee.com/"
GITEE_API_URL = "https://gitee.com/api/v5"


# Range before sleeping until rate limit reset
MIN_RATE_LIMIT = 10
MAX_RATE_LIMIT = 500

# Use this factor of the current token's remaining API points before switching to the next token
TOKEN_USAGE_BEFORE_SWITCH = 0.1

MAX_CATEGORY_ITEMS_PER_PAGE = 100
PER_PAGE = 100

# Default sleep time and retries to deal with connection/server problems
DEFAULT_SLEEP_TIME = 1
MAX_RETRIES = 5

TARGET_ISSUE_FIELDS = ['user', 'assignee', 'assignees', 'comments', 'reactions']
TARGET_PULL_FIELDS = ['user', 'review_comments', 'requested_reviewers', "merged_by", "commits"]

logger = logging.getLogger(__name__)


class Gitee(Backend):
    """Gitee backend for Perceval.

    This class allows the fetch the issues stored in Gitee repostory.
    ```
    Gitee(
        owner='chaoss', repository='grimoirelab',
        api_token=[TOKEN-1, TOKEN-2, ...], sleep_for_rate=True,
        sleep_time=300
    )
    ```
    """

    CATEGORIES = [CATEGORY_ISSUE, CATEGORY_PULL_REQUEST]

    CLASSIFIED_FIELDS = [
        ['user_data'],
        ['merged_by_data'],
        ['assignee_data'],
        ['assignees_data'],
        ['requested_reviewers_data'],
        ['comments_data', 'user_data'],
        ['comments_data', 'reactions_data', 'user_data'],
        ['reviews_data', 'user_data'],
        ['review_comments_data', 'user_data'],
        ['review_comments_data', 'reactions_data', 'user_data']
    ]

    def __init__(self, owner=None, repository=None,
                 api_token=None, base_url=None,
                 tag=None, archive=None,
                 sleep_for_rate=False, min_rate_to_sleep=MIN_RATE_LIMIT,
                 max_retries=MAX_RETRIES, sleep_time=DEFAULT_SLEEP_TIME,
                 max_items=MAX_CATEGORY_ITEMS_PER_PAGE, ssl_verify=True):
        if api_token is None:
            api_token = []
        origin = base_url if base_url else GITEE_URL
        origin = urijoin(origin, owner, repository)

        super().__init__(origin, tag=tag, archive=archive, ssl_verify=ssl_verify)

        self.owner = owner
        self.repository = repository
        self.api_token = api_token
        self.base_url = base_url

        self.sleep_for_rate = sleep_for_rate
        self.min_rate_to_sleep = min_rate_to_sleep
        self.max_retries = max_retries
        self.sleep_time = sleep_time
        self.max_items = max_items

        self.client = None
        self.exclude_user_data = False
        self._users = {}  # internal users cache

    def fetch(self, category=CATEGORY_ISSUE, from_date=DEFAULT_DATETIME, to_date=DEFAULT_LAST_DATETIME,
              filter_classified=False):
        """Fetch the issues/pull requests from the repository.

        The method retrieves, from a GitHub repository, the issues/pull requests
        updated since the given date.

        :param category: the category of items to fetch
        :param from_date: obtain issues/pull requests updated since this date
        :param to_date: obtain issues/pull requests until a specific date (included)
        :param filter_classified: remove classified fields from the resulting items

        :returns: a generator of issues
        """
        self.exclude_user_data = filter_classified

        if self.exclude_user_data:
            logger.info("Excluding user data. Personal user information won't be collected from the API.")

        if not from_date:
            from_date = DEFAULT_DATETIME
        if not to_date:
            to_date = DEFAULT_LAST_DATETIME

        from_date = datetime_to_utc(from_date)
        to_date = datetime_to_utc(to_date)

        kwargs = {
            'from_date': from_date,
            'to_date': to_date
        }
        items = super().fetch(category,
                              filter_classified=filter_classified,
                              **kwargs)

        return items

    def _init_client(self, from_archive=False):
        """Init client"""

        return GiteeClient(self.owner, self.repository, self.api_token, self.base_url,
                           self.sleep_for_rate, self.min_rate_to_sleep,
                           self.sleep_time, self.max_retries, self.max_items,
                           self.archive, from_archive, self.ssl_verify)

    def __fetch_issues(self, from_date, to_date):
        """Fetch the issues"""

        issues_groups = self.client.issues(from_date=from_date)

        for raw_issues in issues_groups:
            issues = json.loads(raw_issues)
            for issue in issues:

                if str_to_datetime(issue['updated_at']) > to_date:
                    return

                self.__init_extra_issue_fields(issue)
                for field in TARGET_ISSUE_FIELDS:

                    if not issue[field]:
                        continue

                    if field == 'user':
                        issue[field + '_data'] = self.__get_user(issue[field]['login'])
                    elif field == 'assignee':
                        issue[field + '_data'] = self.__get_issue_assignee(issue[field])
                    elif field == 'assignees':
                        issue[field + '_data'] = self.__get_issue_assignees(issue[field])
                    elif field == 'comments':
                        issue[field + '_data'] = self.__get_issue_comments(issue['number'])
                yield issue

    def __fetch_pull_requests(self, from_date, to_date):
        """Fetch the pull requests"""

        raw_pulls = self.client.pulls(from_date=from_date)
        for raw_pull in raw_pulls:
            pull = json.loads(raw_pull)

            if str_to_datetime(pull['updated_at']) > to_date:
                return

            self.__init_extra_pull_fields(pull)

            pull['reviews_data'] = self.__get_pull_reviews(pull['number'])

            for field in TARGET_PULL_FIELDS:
                if not pull[field]:
                    continue

                if field == 'user':
                    pull[field + '_data'] = self.__get_user(pull[field]['login'])
                elif field == 'merged_by':
                    pull[field + '_data'] = self.__get_user(pull[field]['login'])
                elif field == 'review_comments':
                    pull[field + '_data'] = self.__get_pull_review_comments(pull['number'])
                elif field == 'requested_reviewers':
                    pull[field + '_data'] = self.__get_pull_requested_reviewers(pull['number'])
                elif field == 'commits':
                    pull[field + '_data'] = self.__get_pull_commits(pull['number'])

            yield pull

    def __get_issue_reactions(self, issue_number, total_count):
        """Get issue reactions"""

        reactions = []

        if total_count == 0:
            return reactions

        group_reactions = self.client.issue_reactions(issue_number)

        for raw_reactions in group_reactions:

            for reaction in json.loads(raw_reactions):
                reaction['user_data'] = self.__get_user(reaction['user']['login'])
                reactions.append(reaction)

        return reactions

    def __get_issue_comments(self, issue_number):
        """Get issue comments"""

        comments = []
        group_comments = self.client.issue_comments(issue_number)

        for raw_comments in group_comments:

            for comment in json.loads(raw_comments):
                comment_id = comment.get('id')
                comment['user_data'] = self.__get_user(comment['user']['login'])
                comment['reactions_data'] = \
                    self.__get_issue_comment_reactions(comment_id, comment['reactions']['total_count'])
                comments.append(comment)

        return comments

    def __get_issue_comment_reactions(self, comment_id, total_count):
        """Get reactions on issue comments"""

        reactions = []

        if total_count == 0:
            return reactions

        group_reactions = self.client.issue_comment_reactions(comment_id)

        for raw_reactions in group_reactions:

            for reaction in json.loads(raw_reactions):
                reaction['user_data'] = self.__get_user(reaction['user']['login'])
                reactions.append(reaction)

        return reactions

    def __get_issue_assignee(self, raw_assignee):
        """Get issue assignee"""

        assignee = self.__get_user(raw_assignee['login'])

        return assignee

    def __get_issue_assignees(self, raw_assignees):
        """Get issue assignees"""

        assignees = []
        for ra in raw_assignees:
            assignees.append(self.__get_user(ra['login']))

        return assignees

    def __get_pull_requested_reviewers(self, pr_number):
        """Get pull request requested reviewers"""

        requested_reviewers = []
        group_requested_reviewers = self.client.pull_requested_reviewers(pr_number)

        for raw_requested_reviewers in group_requested_reviewers:
            group_requested_reviewers = json.loads(raw_requested_reviewers)

            # GH Enterprise returns list of users instead of dict (issue #523)
            if isinstance(group_requested_reviewers, list):
                group_requested_reviewers = {'users': group_requested_reviewers}

            for requested_reviewer in group_requested_reviewers['users']:
                if requested_reviewer and 'login' in requested_reviewer:
                    user_data = self.__get_user(requested_reviewer['login'])
                    requested_reviewers.append(user_data)
                else:
                    logger.warning('Impossible to identify requested reviewer for pull request %s',
                                   pr_number)

        return requested_reviewers

    def __get_pull_commits(self, pr_number):
        """Get pull request commit hashes"""

        hashes = []
        group_pull_commits = self.client.pull_commits(pr_number)

        for raw_pull_commits in group_pull_commits:

            for commit in json.loads(raw_pull_commits):
                commit_hash = commit['sha']
                hashes.append(commit_hash)

        return hashes

    def __get_pull_review_comments(self, pr_number):
        """Get pull request review comments"""

        comments = []
        group_comments = self.client.pull_review_comments(pr_number)

        for raw_comments in group_comments:

            for comment in json.loads(raw_comments):
                comment_id = comment.get('id')

                user = comment.get('user', None)
                if not user:
                    logger.warning("Missing user info for %s", comment['url'])
                    comment['user_data'] = None
                else:
                    comment['user_data'] = self.__get_user(user['login'])

                comment['reactions_data'] = \
                    self.__get_pull_review_comment_reactions(comment_id, comment['reactions']['total_count'])
                comments.append(comment)

        return comments

    def __get_pull_reviews(self, pr_number):
        """Get pull request reviews"""

        reviews = []
        group_reviews = self.client.pull_reviews(pr_number)

        for raw_reviews in group_reviews:

            for review in json.loads(raw_reviews):
                user = review.get('user', None)
                if not user:
                    logger.warning("Missing user info for %s", review['html_url'])
                    review['user_data'] = None
                else:
                    review['user_data'] = self.__get_user(user['login'])

                reviews.append(review)
        return reviews

    def __get_pull_review_comment_reactions(self, comment_id, total_count):
        """Get pull review comment reactions"""

        reactions = []

        if total_count == 0:
            return reactions

        group_reactions = self.client.pull_review_comment_reactions(comment_id)

        for raw_reactions in group_reactions:

            for reaction in json.loads(raw_reactions):
                reaction['user_data'] = self.__get_user(reaction['user']['login'])
                reactions.append(reaction)

        return reactions

    def __get_user(self, login):
        """Get user and org data for the login"""

        if not login or self.exclude_user_data:
            return None

        user_raw = self.client.user(login)
        user = json.loads(user_raw)
        user_orgs_raw = \
            self.client.user_orgs(login)
        user['organizations'] = json.loads(user_orgs_raw)

        return user

    def __init_extra_issue_fields(self, issue):
        """Add fields to an issue"""

        issue['user_data'] = {}
        issue['assignee_data'] = {}
        issue['assignees_data'] = []
        issue['comments_data'] = []
        issue['reactions_data'] = []

    def __init_extra_pull_fields(self, pull):
        """Add fields to a pull request"""

        pull['user_data'] = {}
        pull['review_comments_data'] = {}
        pull['reviews_data'] = []
        pull['requested_reviewers_data'] = []
        pull['merged_by_data'] = []
        pull['commits_data'] = []


class GiteeClient(HttpClient, RateLimitHandler):
    """Client for retieving information from GitHub API

    :param owner: Gitee owner
    :param repository: Gitee repository from the owner
    :param tokens: list of Gitee auth tokens to access the API
    :param base_url: Gitee URL in enterprise edition case;
        when no value is set the backend will be fetch the data
        from the Gitee public site.
    :param sleep_for_rate: sleep until rate limit is reset
    :param min_rate_to_sleep: minimun rate needed to sleep until
         it will be reset
    :param sleep_time: time to sleep in case
        of connection problems
    :param max_retries: number of max retries to a data source
        before raising a RetryError exception
    :param max_items: max number of category items (e.g., issues,
        pull requests) per query
    :param archive: collect issues already retrieved from an archive
    :param from_archive: it tells whether to write/read the archive
    :param ssl_verify: enable/disable SSL verification
    """
    EXTRA_STATUS_FORCELIST = [403, 500, 502, 503]

    _users = {}       # users cache
    _users_orgs = {}  # users orgs cache

    def __init__(self, owner, repository, token,
                 base_url=None, sleep_for_rate=False, min_rate_to_sleep=MIN_RATE_LIMIT,
                 sleep_time=DEFAULT_SLEEP_TIME, max_retries=MAX_RETRIES,
                 max_items=MAX_CATEGORY_ITEMS_PER_PAGE, archive=None, from_archive=False, ssl_verify=True):
        self.owner = owner
        self.repository = repository
        self.access_token = token
        # Gitee doesn't have rate limit check yet
        self.last_rate_limit_checked = None
        self.max_items = max_items

        if base_url:
            base_url = urijoin(base_url, 'api', 'v5')
        else:
            base_url = GITEE_API_URL

        super().__init__(base_url, sleep_time=sleep_time, max_retries=max_retries,
                         extra_headers=self._set_extra_headers(),
                         extra_status_forcelist=self.EXTRA_STATUS_FORCELIST,
                         archive=archive, from_archive=from_archive, ssl_verify=ssl_verify)

    def issue_comments(self, issue_number):
        """Get the issue comments """

        payload = {
            'per_page': PER_PAGE
            # we don't set the since option here
        }

        path = urijoin("issues", issue_number, "comments")
        return self.fetch_items(path, payload)

    def issues(self, from_date=None):
        """Fetch the issues from the repository.

        The method retrieves, from a GitHub repository, the issues
        updated since the given date.

        :param from_date: obtain issues updated since this date

        :returns: a generator of issues
        """
        payload = {
            'state': 'all',
            'per_page': self.max_items,
            'direction': 'asc',
            'sort': 'updated'
        }

        if from_date:
            payload['since'] = from_date.isoformat()

        path = urijoin("issues")
        return self.fetch_items(path, payload)

    def pulls(self, from_date=None):
        """Fetch the pull requests from the repository.

        The method retrieves, from a GitHub repository, the pull requests
        updated since the given date.

        :param from_date: obtain pull requests updated since this date

        :returns: a generator of pull requests
        """
        payload = {
            'state': 'all',
            'per_page': self.max_items,
            'direction': 'asc',
            'sort': 'updated'
        }

        path = urijoin("pulls")
        return self.fetch_items(path, payload)

    def repo(self):
        """Get repository data"""

        path = urijoin(self.base_url, 'repos', self.owner, self.repository)

        r = self.fetch(path)
        repo = r.text

        return repo

    def pull_requested_reviewers(self, pr_number):
        """Get pull requested reviewers"""

        requested_reviewers_url = urijoin("pulls", str(pr_number), "requested_reviewers")
        return self.fetch_items(requested_reviewers_url, {})

    def pull_commits(self, pr_number):
        """Get pull request commits"""

        payload = {
            'per_page': PER_PAGE,
        }

        commit_url = urijoin("pulls", str(pr_number), "commits")
        return self.fetch_items(commit_url, payload)

    def pull_review_comments(self, pr_number):
        """Get pull request review comments"""

        payload = {
            'per_page': PER_PAGE,
            'direction': 'asc',
            'sort': 'updated'
        }

        comments_url = urijoin("pulls", str(pr_number), "comments")
        return self.fetch_items(comments_url, payload)

    def pull_reviews(self, pr_number):
        """Get pull request reviews"""

        payload = {
            'per_page': PER_PAGE,
            'direction': 'asc',
            'sort': 'updated'
        }

        reviews_url = urijoin("pulls", str(pr_number), "reviews")
        return self.fetch_items(reviews_url, payload)

    def pull_review_comment_reactions(self, comment_id):
        """Get reactions of a review comment"""

        payload = {
            'per_page': PER_PAGE,
            'direction': 'asc',
            'sort': 'updated'
        }

        path = urijoin("pulls", "comments", str(comment_id), "reactions")
        return self.fetch_items(path, payload)

    def user(self, login):
        """Get the user information and update the user cache"""
        user = None

        if login in self._users:
            return self._users[login]

        url_user = urijoin(self.base_url, 'users', login)

        logger.debug("Getting info for %s" % url_user)

        r = self.fetch(url_user)
        user = r.text
        self._users[login] = user

        return user

    def user_orgs(self, login):
        """Get the user public organizations"""
        if login in self._users_orgs:
            return self._users_orgs[login]

        url = urijoin(self.base_url, 'users', login, 'orgs')
        try:
            r = self.fetch(url)
            orgs = r.text
        except requests.exceptions.HTTPError as error:
            # 404 not found is wrongly received sometimes
            if error.response.status_code == 404:
                logger.error("Can't get github login orgs: %s", error)
                orgs = '[]'
            else:
                raise error

        self._users_orgs[login] = orgs

        return orgs

    def fetch(self, url, payload=None, headers=None, method=HttpClient.GET, stream=False, auth=None):
        """Fetch the data from a given URL.

        :param url: link to the resource
        :param payload: payload of the request
        :param headers: headers of the request
        :param method: type of request call (GET or POST)
        :param stream: defer downloading the response body until the response content is available
        :param auth: auth of the request

        :returns a response object
        """
        # Add the access_token to the payload
        if self.access_token:
            payload["access_token"] = self.access_token

        response = super().fetch(url, payload, headers, method, stream, auth)

        # if not self.from_archive:
        #    if self._need_check_tokens():
        #        self._choose_best_api_token()
        #    else:
        #        self.update_rate_limit(response)

        return response

    def fetch_items(self, path, payload):
        """Return the items from gitee API using links pagination"""

        page = 0  # current page
        total_page = None  # total page number
        url_next = urijoin(self.base_url, 'repos', self.owner, self.repository, path)
        logger.debug("Get Gitee paginated items from " + url_next)

        response = self.fetch(url_next, payload=payload)

        items = response.text
        page += 1

        total_page = response.headers.get('total_page')
        if total_page:
            total_page = int(total_page[0])
            logger.debug("Page: %i/%i" % (page, total_page))

        while items:
            yield items
            items = None
            if 'next' in response.links:
                url_next = response.links['next']['url']
                print(url_next)
                response = self.fetch(url_next, payload=payload)
                page += 1
                items = response.text
                print("page is %i" % (page))
                logger.debug("Page: %i/%i" % (page, total_page))

    def _set_extra_headers(self):
        """Set extra headers for session"""
        headers = {}
        # set the header for request
        headers.update({'Content-Type': 'application/json;charset=UTF-8'})
        return headers
