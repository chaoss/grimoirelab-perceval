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
#     Alvaro del Castillo San Felix <acs@bitergia.com>
#     Valerio Cosentino <valcos@bitergia.com>
#     Santiago Dueñas <sduenas@bitergia.com>
#     Alberto Martín <alberto.martin@bitergia.com>
#     Jesus M. Gonzalez-Barahona <jgb@gsyc.es>
#     Lukasz Gryglicki <lukaszgryglicki@o2.pl>
#     Venu Vardhan Reddy Tekula <venuvardhanreddytekula8@gmail.com>
#     Harshal Mittal <harshalmittal4@gmail.com>
#     Aniruddha Karajgi <akarajgi0@gmail.com>
#     Cedric Williams <cewilliams@paypal.com>
#     JJMerchante <jj.merchante@gmail.com>
#     Quan Zhou <quan@bitergia.com>
#

import datetime
import json
import logging

import dateutil.tz
import jwt
import requests
from grimoirelab_toolkit.datetime import (datetime_to_utc,
                                          datetime_utcnow,
                                          str_to_datetime)
from grimoirelab_toolkit.uris import urijoin

from ...backend import (Backend,
                        BackendCommand,
                        BackendCommandArgumentParser,
                        DEFAULT_SEARCH_FIELD)
from ...client import HttpClient, RateLimitHandler
from ...utils import DEFAULT_LAST_DATETIME


CATEGORY_ISSUE = "issue"
CATEGORY_PULL_REQUEST = "pull_request"
CATEGORY_REPO = 'repository'

GITHUB_URL = "https://github.com/"
GITHUB_API_URL = "https://api.github.com"
GITHUB_APP_INSTALLATION = 'app/installations'
GITHUB_APP_ACCESS_TOKEN = 'access_tokens'
GITHUB_APP_INSTALLATION_REPOSITORIES = 'installation/repositories'

# Range before sleeping until rate limit reset
MIN_RATE_LIMIT = 10
MAX_RATE_LIMIT = 500
# Use this factor of the current token's remaining API points before switching to the next token
TOKEN_USAGE_BEFORE_SWITCH = 0.1

MAX_CATEGORY_ITEMS_PER_PAGE = 100

# Default sleep time and retries to deal with connection/server problems
DEFAULT_SLEEP_TIME = 1
MAX_RETRIES = 5

# GitHub issues API doesn't return issues using 1970-01-01
# https://github.com/chaoss/grimoirelab-perceval/issues/865
GITHUB_DEFAULT_DATETIME = datetime.datetime(1980, 1, 1, 0, 0, 0,
                                            tzinfo=dateutil.tz.tzutc())

TARGET_ISSUE_FIELDS = ['user', 'assignee', 'assignees', 'comments', 'reactions']
TARGET_PULL_FIELDS = ['user', 'review_comments', 'requested_reviewers', "merged_by", "commits"]

logger = logging.getLogger(__name__)


class GitHub(Backend):
    """GitHub backend for Perceval.

    This class allows the fetch the issues stored in GitHub
    repository. Note that since version 0.20.0, the `api_token` accepts
    a list of tokens, thus the backend must be initialized as follows:
    ```
    GitHub(
        owner='chaoss', repository='grimoirelab',
        api_token=[TOKEN-1, TOKEN-2, ...], sleep_for_rate=True,
        sleep_time=300
    )
    ```

    :param owner: GitHub owner
    :param repository: GitHub repository from the owner
    :param api_token: list of GitHub auth tokens to access the API
    :param github_app_id: GitHub App ID
    :param github_app_pk_filepath: GitHub App private key PEM file path
    :param base_url: GitHub URL in enterprise edition case;
        when no value is set the backend will be fetch the data
        from the GitHub public site.
    :param tag: label used to mark the data
    :param archive: archive to store/retrieve items
    :param sleep_for_rate: sleep until rate limit is reset
    :param min_rate_to_sleep: minimum rate needed to sleep until
         it will be reset
    :param max_retries: number of max retries to a data source
        before raising a RetryError exception
    :param max_items: max number of category items (e.g., issues,
        pull requests) per query
    :param sleep_time: time to sleep in case
        of connection problems
    :param ssl_verify: enable/disable SSL verification
    """
    version = '1.0.0'

    CATEGORIES = [CATEGORY_ISSUE, CATEGORY_PULL_REQUEST, CATEGORY_REPO]

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
                 api_token=None, github_app_id=None, github_app_pk_filepath=None,
                 base_url=None, tag=None, archive=None,
                 sleep_for_rate=False, min_rate_to_sleep=MIN_RATE_LIMIT,
                 max_retries=MAX_RETRIES, sleep_time=DEFAULT_SLEEP_TIME,
                 max_items=MAX_CATEGORY_ITEMS_PER_PAGE, ssl_verify=True):
        if api_token is None:
            api_token = []
        origin = base_url if base_url else GITHUB_URL
        origin = urijoin(origin, owner, repository)

        super().__init__(origin, tag=tag, archive=archive, ssl_verify=ssl_verify)

        self.owner = owner
        self.repository = repository
        self.api_token = api_token
        self.github_app_id = github_app_id
        self.github_app_pk_filepath = github_app_pk_filepath
        self.base_url = base_url

        self.sleep_for_rate = sleep_for_rate
        self.min_rate_to_sleep = min_rate_to_sleep
        self.max_retries = max_retries
        self.sleep_time = sleep_time
        self.max_items = max_items

        self.client = None
        self.exclude_user_data = False
        self._users = {}  # internal users cache

    def search_fields(self, item):
        """Add search fields to an item.

        It adds the values of `metadata_id` plus the `owner` and `repo`.

        :param item: the item to extract the search fields values

        :returns: a dict of search fields
        """
        search_fields = {
            DEFAULT_SEARCH_FIELD: self.metadata_id(item),
            'owner': self.owner,
            'repo': self.repository
        }

        return search_fields

    def fetch(self, category=CATEGORY_ISSUE, from_date=GITHUB_DEFAULT_DATETIME, to_date=DEFAULT_LAST_DATETIME,
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
            from_date = GITHUB_DEFAULT_DATETIME
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

    def fetch_items(self, category, **kwargs):
        """Fetch the items (issues or pull_requests or repo information)

        :param category: the category of items to fetch
        :param kwargs: backend arguments

        :returns: a generator of items
        """
        from_date = kwargs['from_date']
        to_date = kwargs['to_date']

        if category == CATEGORY_ISSUE:
            items = self.__fetch_issues(from_date, to_date)
        elif category == CATEGORY_PULL_REQUEST:
            items = self.__fetch_pull_requests(from_date, to_date)
        else:
            items = self.__fetch_repo_info()

        return items

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
        """Extracts the identifier from a GitHub item."""

        if "forks_count" in item:
            return str(item['fetched_on'])
        else:
            return str(item['id'])

    @staticmethod
    def metadata_updated_on(item):
        """Extracts the update time from a GitHub item.

        The timestamp used is extracted from 'updated_at' field.
        This date is converted to UNIX timestamp format. As GitHub
        dates are in UTC the conversion is straightforward.

        :param item: item generated by the backend

        :returns: a UNIX timestamp
        """
        if "forks_count" in item:
            return item['fetched_on']
        else:
            ts = item['updated_at']
            ts = str_to_datetime(ts)

            return ts.timestamp()

    @staticmethod
    def metadata_category(item):
        """Extracts the category from a GitHub item.

        This backend generates three types of item which are
        'issue', 'pull_request' and 'repo' information.
        """

        if "base" in item:
            category = CATEGORY_PULL_REQUEST
        elif "forks_count" in item:
            category = CATEGORY_REPO
        else:
            category = CATEGORY_ISSUE

        return category

    def _init_client(self, from_archive=False):
        """Init client"""

        return GitHubClient(self.owner, self.repository, self.api_token,
                            self.github_app_id, self.github_app_pk_filepath, self.base_url,
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
                        issue[field + '_data'] = self.__get_user_data(issue[field])
                    elif field == 'assignee':
                        issue[field + '_data'] = self.__get_issue_assignee(issue[field])
                    elif field == 'assignees':
                        issue[field + '_data'] = self.__get_issue_assignees(issue[field])
                    elif field == 'comments':
                        issue[field + '_data'] = self.__get_issue_comments(issue['number'])
                    elif field == 'reactions':
                        issue[field + '_data'] = \
                            self.__get_issue_reactions(issue['number'], issue['reactions']['total_count'])

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
                    pull[field + '_data'] = self.__get_user_data(pull[field])
                elif field == 'merged_by':
                    pull[field + '_data'] = self.__get_user_data(pull[field])
                elif field == 'review_comments':
                    pull[field + '_data'] = self.__get_pull_review_comments(pull['number'])
                elif field == 'requested_reviewers':
                    pull[field + '_data'] = self.__get_pull_requested_reviewers(pull['number'])
                elif field == 'commits':
                    pull[field + '_data'] = self.__get_pull_commits(pull['number'])

            yield pull

    def __fetch_repo_info(self):
        """Get repo info about stars, watchers and forks"""

        raw_repo = self.client.repo()
        repo = json.loads(raw_repo)

        fetched_on = datetime_utcnow()
        repo['fetched_on'] = fetched_on.timestamp()

        yield repo

    def __get_issue_reactions(self, issue_number, total_count):
        """Get issue reactions"""

        reactions = []

        if total_count == 0:
            return reactions

        group_reactions = self.client.issue_reactions(issue_number)

        for raw_reactions in group_reactions:

            for reaction in json.loads(raw_reactions):
                user = reaction.get('user', None)
                reaction['user_data'] = self.__get_user_data(user) if user else None
                reactions.append(reaction)

        return reactions

    def __get_issue_comments(self, issue_number):
        """Get issue comments"""

        comments = []
        group_comments = self.client.issue_comments(issue_number)

        for raw_comments in group_comments:

            for comment in json.loads(raw_comments):
                comment_id = comment.get('id')
                comment['user_data'] = self.__get_user_data(comment['user'])
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
                user = reaction.get('user', None)
                reaction['user_data'] = self.__get_user_data(user) if user else None
                reactions.append(reaction)

        return reactions

    def __get_issue_assignee(self, raw_assignee):
        """Get issue assignee"""

        assignee = self.__get_user_data(raw_assignee)

        return assignee

    def __get_issue_assignees(self, raw_assignees):
        """Get issue assignees"""

        assignees = []
        for ra in raw_assignees:
            assignees.append(self.__get_user_data(ra))

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
                    user_data = self.__get_user_data(requested_reviewer)
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
                    comment['user_data'] = self.__get_user_data(user)

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
                    review['user_data'] = self.__get_user_data(user)

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
                user = reaction.get('user', None)
                reaction['user_data'] = self.__get_user_data(user) if user else None
                reactions.append(reaction)

        return reactions

    def __get_user_data(self, user):
        """Get user and org data for a user"""

        login = user.get('login', None)

        if not login or self.exclude_user_data:
            return None

        user_raw = self.client.user(login)
        user_data = json.loads(user_raw)
        if not user_data:
            user_data = user.copy()
            user_data['name'] = login

        user_orgs_raw = \
            self.client.user_orgs(login)
        user_data['organizations'] = json.loads(user_orgs_raw)

        return user_data

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


class GitHubClient(HttpClient, RateLimitHandler):
    """Client for retieving information from GitHub API

    :param owner: GitHub owner
    :param repository: GitHub repository from the owner
    :param tokens: list of GitHub auth tokens to access the API
    :param github_app_id: GitHub App ID
    :param github_app_pk_filepath: GitHub App private key PEM file path
    :param base_url: GitHub URL in enterprise edition case;
        when no value is set the backend will be fetch the data
        from the GitHub public site.
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

    # API resources
    RISSUES = 'issues'
    RREACTIONS = 'reactions'
    RCOMMENTS = 'comments'
    RREPOS = 'repos'
    RPULLS = 'pulls'
    RREQUESTED_REVIEWERS = 'requested_reviewers'
    RREVIEWS = 'reviews'
    RUSERS = 'users'
    RORGS = 'orgs'
    RRATE_LIMIT = 'rate_limit'
    RCOMMITS = 'commits'

    # API headers
    HAUTHORIZATION = 'Authorization'
    HACCEPT = 'Accept'

    # Resource parameters
    PSTATE = 'state'
    PPER_PAGE = 'per_page'
    PDIRECTION = 'direction'
    PSORT = 'sort'
    PSINCE = 'since'

    # Predefined values
    VDIRECTION_ASC = 'asc'
    VSORT_UPDATED = 'updated'
    VSTATE_ALL = 'all'
    VACCEPT = 'application/vnd.github.squirrel-girl-preview'
    VACCEPT_V3 = 'application/vnd.github.v3+json'

    _users = {}       # users cache
    _users_orgs = {}  # users orgs cache

    def __init__(self, owner, repository, tokens=None, github_app_id=None, github_app_pk_filepath=None,
                 base_url=None, sleep_for_rate=False, min_rate_to_sleep=MIN_RATE_LIMIT,
                 sleep_time=DEFAULT_SLEEP_TIME, max_retries=MAX_RETRIES,
                 max_items=MAX_CATEGORY_ITEMS_PER_PAGE, archive=None, from_archive=False, ssl_verify=True):
        self.owner = owner
        self.repository = repository
        self.tokens = tokens
        if self.tokens:
            self.n_tokens = len(self.tokens)
        else:
            self.n_tokens = 0
        self.current_token = None
        self.last_rate_limit_checked = None
        self.max_items = max_items
        self.github_app_id = github_app_id
        self.github_app_pk_filepath = github_app_pk_filepath

        if base_url:
            base_url = urijoin(base_url, 'api', 'v3')
        else:
            base_url = GITHUB_API_URL

        super().__init__(base_url, sleep_time=sleep_time, max_retries=max_retries,
                         extra_headers=self._set_extra_headers(),
                         extra_status_forcelist=self.EXTRA_STATUS_FORCELIST,
                         archive=archive, from_archive=from_archive, ssl_verify=ssl_verify)
        super().setup_rate_limit_handler(sleep_for_rate=sleep_for_rate, min_rate_to_sleep=min_rate_to_sleep)

        # Choose best API token (with maximum API points remaining)
        if not self.from_archive:
            self._choose_best_api_token()

    def calculate_time_to_reset(self):
        """Calculate the seconds to reset the token requests, by obtaining the different
        between the current date and the next date when the token is fully regenerated.
        """

        time_to_reset = self.rate_limit_reset_ts - (datetime_utcnow().replace(microsecond=0).timestamp() + 1)
        time_to_reset = 0 if time_to_reset < 0 else time_to_reset

        return time_to_reset

    def issue_reactions(self, issue_number):
        """Get reactions of an issue"""

        payload = {
            self.PPER_PAGE: self.max_items,
            self.PDIRECTION: self.VDIRECTION_ASC,
            self.PSORT: self.VSORT_UPDATED
        }

        path = urijoin(self.RISSUES, str(issue_number), self.RREACTIONS)
        return self.fetch_items(path, payload)

    def issue_comment_reactions(self, comment_id):
        """Get reactions of an issue comment"""

        payload = {
            self.PPER_PAGE: self.max_items,
            self.PDIRECTION: self.VDIRECTION_ASC,
            self.PSORT: self.VSORT_UPDATED
        }

        path = urijoin(self.RISSUES, self.RCOMMENTS, str(comment_id), self.RREACTIONS)
        return self.fetch_items(path, payload)

    def issue_comments(self, issue_number):
        """Get the issue comments from pagination"""

        payload = {
            self.PPER_PAGE: self.max_items,
            self.PDIRECTION: self.VDIRECTION_ASC,
            self.PSORT: self.VSORT_UPDATED
        }

        path = urijoin(self.RISSUES, str(issue_number), self.RCOMMENTS)
        return self.fetch_items(path, payload)

    def issues(self, from_date=None):
        """Fetch the issues from the repository.

        The method retrieves, from a GitHub repository, the issues
        updated since the given date.

        :param from_date: obtain issues updated since this date

        :returns: a generator of issues
        """
        payload = {
            self.PSTATE: self.VSTATE_ALL,
            self.PPER_PAGE: self.max_items,
            self.PDIRECTION: self.VDIRECTION_ASC,
            self.PSORT: self.VSORT_UPDATED
        }

        if from_date:
            payload[self.PSINCE] = from_date.isoformat()

        path = urijoin(self.RISSUES)
        return self.fetch_items(path, payload)

    def pulls(self, from_date=None):
        """Fetch the pull requests from the repository.

        The method retrieves, from a GitHub repository, the pull requests
        updated since the given date.

        :param from_date: obtain pull requests updated since this date

        :returns: a generator of pull requests
        """
        issues_groups = self.issues(from_date=from_date)

        for raw_issues in issues_groups:
            issues = json.loads(raw_issues)
            for issue in issues:

                if "pull_request" not in issue:
                    continue

                pull_number = issue["number"]
                path = urijoin(self.base_url, self.RREPOS, self.owner, self.repository, self.RPULLS, pull_number)
                r = self.fetch(path)
                pull = r.text
                yield pull

    def repo(self):
        """Get repository data"""

        path = urijoin(self.base_url, self.RREPOS, self.owner, self.repository)

        r = self.fetch(path)
        repo = r.text

        return repo

    def pull_requested_reviewers(self, pr_number):
        """Get pull requested reviewers"""

        requested_reviewers_url = urijoin(self.RPULLS, str(pr_number), self.RREQUESTED_REVIEWERS)
        return self.fetch_items(requested_reviewers_url, {})

    def pull_commits(self, pr_number):
        """Get pull request commits"""

        payload = {
            self.PPER_PAGE: self.max_items
        }

        commit_url = urijoin(self.RPULLS, str(pr_number), self.RCOMMITS)
        return self.fetch_items(commit_url, payload)

    def pull_review_comments(self, pr_number):
        """Get pull request review comments"""

        payload = {
            self.PPER_PAGE: self.max_items,
            self.PDIRECTION: self.VDIRECTION_ASC,
            self.PSORT: self.VSORT_UPDATED
        }

        comments_url = urijoin(self.RPULLS, str(pr_number), self.RCOMMENTS)
        return self.fetch_items(comments_url, payload)

    def pull_reviews(self, pr_number):
        """Get pull request reviews"""

        payload = {
            self.PPER_PAGE: self.max_items,
            self.PDIRECTION: self.VDIRECTION_ASC,
            self.PSORT: self.VSORT_UPDATED
        }

        reviews_url = urijoin(self.RPULLS, str(pr_number), self.RREVIEWS)
        return self.fetch_items(reviews_url, payload)

    def pull_review_comment_reactions(self, comment_id):
        """Get reactions of a review comment"""

        payload = {
            self.PPER_PAGE: self.max_items,
            self.PDIRECTION: self.VDIRECTION_ASC,
            self.PSORT: self.VSORT_UPDATED
        }

        path = urijoin(self.RPULLS, self.RCOMMENTS, str(comment_id), self.RREACTIONS)
        return self.fetch_items(path, payload)

    def user(self, login):
        """Get the user information and update the user cache"""
        user = None

        if login in self._users:
            return self._users[login]

        url_user = urijoin(self.base_url, self.RUSERS, login)

        logger.debug("Getting info for %s" % url_user)

        try:
            r = self.fetch(url_user)
            user = r.text
        except requests.exceptions.HTTPError as error:
            # When the login is no longer exist or the token has no permission
            if error.response.status_code == 404:
                logger.error("Can't get github login: %s", error)
                user = '{}'
            else:
                raise error

        self._users[login] = user
        return user

    def user_orgs(self, login):
        """Get the user public organizations"""
        if login in self._users_orgs:
            return self._users_orgs[login]

        url = urijoin(self.base_url, self.RUSERS, login, self.RORGS)
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
        except requests.exceptions.RetryError as error:
            logger.error("Can't get github login orgs: %s", error)
            orgs = '[]'

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
        if not self.from_archive:
            self.sleep_for_rate_limit()

        if not self.from_archive:
            if self._need_check_tokens() and self.sleep_for_rate and self.github_app_id:
                logger.debug("GitHub APP with {} ID: access token expired, creating new one".format(self.github_app_id))
                self._choose_best_api_token()

        response = super().fetch(url, payload, headers, method, stream, auth)

        if not self.from_archive:
            if self._need_check_tokens():
                self._choose_best_api_token()
            else:
                self.update_rate_limit(response)

        return response

    def fetch_items(self, path, payload):
        """Return the items from github API using links pagination"""

        page = 0  # current page
        url_next = urijoin(self.base_url, self.RREPOS, self.owner, self.repository, path)
        logger.debug("Get GitHub paginated items from " + url_next)

        response = self.fetch(url_next, payload=payload)

        items = response.text
        page += 1

        logger.debug(f"Page: {page}")

        while items:
            yield items

            items = None

            if 'next' in response.links:
                url_next = response.links['next']['url']
                response = self.fetch(url_next, payload=payload)
                page += 1

                items = response.text
                logger.debug(f"Page: {page}")

    def _get_token_rate_limit(self, token):
        """Return token's remaining API points"""

        rate_url = urijoin(self.base_url, self.RRATE_LIMIT)
        self.session.headers.update({self.HAUTHORIZATION: 'token ' + token})
        remaining = 0
        try:
            headers = super().fetch(rate_url).headers
            if self.rate_limit_header in headers:
                remaining = int(headers[self.rate_limit_header])
        except requests.exceptions.HTTPError as error:
            logger.warning("Rate limit not initialized: %s", error)
        return remaining

    def _get_tokens_rate_limits(self):
        """Return array of all tokens remaining API points"""

        remainings = [0] * self.n_tokens
        # Turn off archiving when checking rates, because that would cause
        # archive key conflict (the same URLs giving different responses)
        arch = self.archive
        self.archive = None
        for idx, token in enumerate(self.tokens):
            # Pass flag to skip disabling archiving because this function doies it
            remainings[idx] = self._get_token_rate_limit(token)
        # Restore archiving to whatever state it was
        self.archive = arch
        logger.debug("Remaining API points: {}".format(remainings))
        return remainings

    def _choose_best_api_token(self):
        """Check all API tokens defined and choose one with most remaining API points"""
        if self.github_app_id:
            self._update_access_token()

        # Return if no tokens given
        if self.n_tokens == 0:
            return

        # If multiple tokens given, choose best
        token_idx = 0
        if self.n_tokens > 1:
            remainings = self._get_tokens_rate_limits()
            token_idx = remainings.index(max(remainings))
            logger.debug("Remaining API points: {}, choosen index: {}".format(remainings, token_idx))

        # If we have any tokens - use best of them
        self.current_token = self.tokens[token_idx]
        self.session.headers.update({self.HAUTHORIZATION: 'token ' + self.current_token})
        # Update rate limit data for the current token
        self._update_current_rate_limit()

    def _update_access_token(self):
        """Create a new access token."""

        jwt_token = self._create_jwt_token()
        headers = {
            self.HAUTHORIZATION: "Bearer {}".format(jwt_token),
            self.HACCEPT: self.VACCEPT_V3
        }
        installation_id = self._get_installation_id(headers)
        access_token = self._create_access_token(headers, installation_id)
        logger.debug("GitHub APP access token created for {} installation ID".format(installation_id))
        self.tokens = [access_token]
        self.n_tokens = 1

    def _create_jwt_token(self):
        """Create JWT token given the GitHub App ID and the private key PEM file.
        We need this token to authenticate as a GitHub App

        :returns: JWT token
        """
        now = int(datetime.datetime.now().timestamp())
        payload = {
            "iat": now,
            # JWT expiration time (10 minute maximum)
            "exp": now + (10 * 60),
            "iss": self.github_app_id
        }
        private_key = self._read_pem()
        jwt_token = jwt.encode(payload, private_key, algorithm="RS256")
        return jwt_token

    def _read_pem(self):
        """Read private key PEM file.

        The path of the file is stored in 'github_app_pk_filepath'.
        """
        with open(self.github_app_pk_filepath, 'r') as private_file:
            private_key = private_file.read()
        return private_key

    def _get_installation_id(self, headers):
        """Get installation ID given the GitHub login

        :param headers: request headers with JWT token

        :returns: Installation ID
        """
        installation_id = None
        url = urijoin(self.base_url, GITHUB_APP_INSTALLATION)
        r = self.session.get(url, headers=headers)
        data = r.json()
        for i in data:
            if i['account']['login'] == self.owner:
                installation_id = i['id']
                break
        return installation_id

    def _create_access_token(self, headers, installation_id):
        """Create GitHub access token given the installation ID.
        To access the API.

        :param headers: requests headers with JWT token
        :param installation_id: GitHub APP installation ID

        :returns: GitHub access token
        """
        url = urijoin(self.base_url, GITHUB_APP_INSTALLATION, installation_id, GITHUB_APP_ACCESS_TOKEN)
        r = self.session.post(url, headers=headers)
        access_token = r.json()['token']
        self._authenticate_access_token(access_token)
        return access_token

    def _authenticate_access_token(self, access_token):
        """Authenticate the GitHub access token

        :param access_token: GitHub access token
        """
        headers = {
            self.HAUTHORIZATION: "token {}".format(access_token),
            self.HACCEPT: self.VACCEPT_V3
        }
        url = urijoin(self.base_url, GITHUB_APP_INSTALLATION_REPOSITORIES)
        _ = self.session.get(url, headers=headers)

    def _need_check_tokens(self):
        """Check if we need to switch GitHub API tokens"""

        # When we use GitHub APP and the rate limit is MIN_RATE_LIMIT we
        # have to create a new access token
        if self.rate_limit == MIN_RATE_LIMIT and self.github_app_id:
            return True

        if self.n_tokens <= 1 or self.rate_limit is None:
            return False
        elif self.last_rate_limit_checked is None:
            self.last_rate_limit_checked = self.rate_limit
            return True

        # If approaching minimum rate limit for sleep
        approaching_limit = float(self.min_rate_to_sleep) * (1.0 + TOKEN_USAGE_BEFORE_SWITCH) + 1
        if self.rate_limit <= approaching_limit:
            self.last_rate_limit_checked = self.rate_limit
            return True

        # Only switch token when used predefined factor of the current token's remaining API points
        ratio = float(self.rate_limit) / float(self.last_rate_limit_checked)
        if ratio < 1.0 - TOKEN_USAGE_BEFORE_SWITCH:
            self.last_rate_limit_checked = self.rate_limit
            return True
        elif ratio > 1.0:
            self.last_rate_limit_checked = self.rate_limit
            return False
        else:
            return False

    def _update_current_rate_limit(self):
        """Update rate limits data for the current token"""

        url = urijoin(self.base_url, self.RRATE_LIMIT)
        try:
            # Turn off archiving when checking rates, because that would cause
            # archive key conflict (the same URLs giving different responses)
            arch = self.archive
            self.archive = None
            response = super().fetch(url)
            self.archive = arch
            self.update_rate_limit(response)
            self.last_rate_limit_checked = self.rate_limit
        except requests.exceptions.HTTPError as error:
            if error.response.status_code == 404:
                logger.warning("Rate limit not initialized: %s", error)
            elif error.response.status_code == 401:
                logger.debug("GitHub APP with {} ID: access token expired, creating new one".format(self.github_app_id))
                self._update_access_token()
            else:
                raise error

    def _set_extra_headers(self):
        """Set extra headers for session"""

        headers = {}
        headers.update({self.HACCEPT: self.VACCEPT})
        return headers

    @staticmethod
    def sanitize_for_archive(url, headers, payload):
        """Sanitize payload of a HTTP request by removing the
        token information before storing/retrieving archived items

        :param: url: HTTP url request
        :param: headers: HTTP headers request
        :param: payload: HTTP payload request

        :returns url, headers and the sanitized payload
        """
        if not headers:
            return url, headers, payload

        if GitHubClient.HAUTHORIZATION in headers:
            headers.pop(GitHubClient.HAUTHORIZATION, None)

        return url, headers, payload


class GitHubCommand(BackendCommand):
    """Class to run GitHub backend from the command line."""

    BACKEND = GitHub

    @classmethod
    def setup_cmd_parser(cls):
        """Returns the GitHub argument parser."""

        parser = BackendCommandArgumentParser(cls.BACKEND,
                                              to_date=True,
                                              token_auth=False,
                                              archive=True,
                                              ssl_verify=True)
        # GitHub options
        group = parser.parser.add_argument_group('GitHub arguments')
        group.add_argument('--enterprise-url', dest='base_url',
                           help="Base URL for GitHub Enterprise instance")
        group.add_argument('--sleep-for-rate', dest='sleep_for_rate',
                           action='store_true',
                           help="sleep for getting more rate")
        group.add_argument('--min-rate-to-sleep', dest='min_rate_to_sleep',
                           default=MIN_RATE_LIMIT, type=int,
                           help="sleep until reset when the rate limit reaches this value")
        # GitHub token(s)
        group.add_argument('-t', '--api-token', dest='api_token',
                           nargs='+',
                           default=[],
                           help="list of GitHub API tokens")

        # GitHub App
        group.add_argument('--github-app-id', dest='github_app_id',
                           help="GitHub APP ID")
        group.add_argument('--github-app-pk-filepath', dest='github_app_pk_filepath',
                           help="GitHub App private key PEM file")

        # Generic client options

        # GitHub issues API doesn't return issues using 1970-01-01
        # https://github.com/chaoss/grimoirelab-perceval/issues/865
        group.add_argument('--from-date', dest='from_date',
                           default='1980-01-01',
                           type=str_to_datetime,
                           help="fetch items updated since this \
                                 date (in any ISO 8601 format, e.g., 'YYYY-MM-DD HH:mm:SS +|-HH:MM')")
        group.add_argument('--max-items', dest='max_items',
                           default=MAX_CATEGORY_ITEMS_PER_PAGE, type=int,
                           help="Max number of category items per query.")
        group.add_argument('--max-retries', dest='max_retries',
                           default=MAX_RETRIES, type=int,
                           help="number of API call retries")
        group.add_argument('--sleep-time', dest='sleep_time',
                           default=DEFAULT_SLEEP_TIME, type=int,
                           help="sleeping time between API call retries")

        # Positional arguments
        parser.parser.add_argument('owner',
                                   help="GitHub owner")
        parser.parser.add_argument('repository',
                                   help="GitHub repository")

        return parser
