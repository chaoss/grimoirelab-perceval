# -*- coding: utf-8 -*-
#
# Copyright (C) 2015-2016 Bitergia
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
#     Santiago Dueñas <sduenas@bitergia.com>
#

import json
import logging
import os.path

import requests

from ..backend import Backend, BackendCommand, metadata
from ..cache import Cache
from ..errors import BaseError, CacheError
from ..utils import DEFAULT_DATETIME, datetime_to_utc, str_to_datetime


logger = logging.getLogger(__name__)


class Phabricator(Backend):
    """Phabricator backend.

    This class allows to fetch the tasks stored on a Phabricator
    server. Initialize this class passing the URL of this server
    and the API token. The origin of the data will be set to this
    URL.

    :param url: URL of the server
    :param api_token: token needed to use the API
    :param tag: label used to mark the data
    :param cache: cache object to store raw data
    """
    version = '0.5.0'

    def __init__(self, url, api_token, tag=None, cache=None):
        origin = url

        super().__init__(origin, tag=tag, cache=cache)
        self.url = url
        self.client = ConduitClient(url, api_token)
        self._users = {}
        self._projects = {}

    @metadata
    def fetch(self, from_date=DEFAULT_DATETIME):
        """Fetch the tasks from the server.

        This method fetches the tasks stored on the server that were
        updated since the given date. The transactions data related
        to each task is also included within them.

        :param from_date: obtain tasks updated since this date

        :returns: a generator of tasks
        """
        logger.info("Fetching tasks of '%s' from %s", self.url, str(from_date))

        self._purge_cache_queue()

        from_date = datetime_to_utc(from_date)

        ntasks = 0

        for task in self.__fetch_tasks(from_date):
            yield task
            ntasks += 1

        logger.info("Fetch process completed: %s tasks fetched", ntasks)

    @metadata
    def fetch_from_cache(self):
        """Fetch the tasks from the cache.

        It returns the tasks stored in the cache object, provided during
        the initialization of the object. If this method is called but
        no cache object was provided, the method will raise a `CacheError`
        exception.

        :returns: a generator of tasks

        :raises CacheError: raised when an error occurs accesing the
            cache
        """
        if not self.cache:
            raise CacheError(cause="cache instance was not provided")

        logger.info("Retrieving cached tasks: '%s'", self.url)

        ntasks = 0

        try:
            for task in self.__fetch_tasks_from_cache():
                yield task
                ntasks += 1
        except StopIteration:
            # Fatal error. The code should not reach here.
            # Cache should had stored an activity item per parsed bug.
            cause = "cache is exhausted but more items were expected"
            raise CacheError(cause=cause)

        logger.info("Retrieval process completed: %s tasks retrieved from cache",
                    ntasks)

    def __fetch_tasks(self, from_date):
        for raw_tasks in self.client.tasks(from_date=from_date):
            self._push_cache_queue(raw_tasks)

            tasks = [t for t in self.parse_tasks(raw_tasks)]

            if not tasks:
                break

            tasks_ids = [t['id'] for t in tasks]
            tasks_trans = self.__fetch_and_parse_tasks_transactions(*tasks_ids)

            for task in tasks:
                # Task check point
                self._push_cache_queue('{TASK}')

                tid = str(task['id'])
                author_id = task['fields']['authorPHID']
                owner_id = task['fields']['ownerPHID']

                task['fields']['authorData'] = self.__get_or_fetch_user(author_id)

                if owner_id:
                    task['fields']['ownerData'] = self.__get_or_fetch_user(owner_id)

                # Users checkpoint
                self._push_cache_queue('{ENDUSERS}')

                project_ids = task['attachments']['projects']['projectPHIDs']
                task_projects = [self.__get_or_fetch_project(project_id) \
                                 for project_id in project_ids]

                # Projects checkpoint
                self._push_cache_queue('{ENDPROJECTS}')

                task['transactions'] = tasks_trans[tid]
                task['projects'] = task_projects

                yield task

            # Checkpoint. A tasks set finish here.
            self._push_cache_queue('{}')
            self._flush_cache_queue()

    def __fetch_tasks_from_cache(self):
        cache_items = self.cache.retrieve()
        cached_users = {}
        cached_projects = {}

        while True:
            try:
                raw_tasks = next(cache_items)
            except StopIteration:
                break

            tasks = [t for t in self.parse_tasks(raw_tasks)]

            if not tasks:
                break

            raw_trans = next(cache_items)
            tasks_trans = self.parse_tasks_transactions(raw_trans)

            # Retrieve cached users from the transactions
            users = self.__retrive_cached_users(cache_items)
            for user in users:
                user_id = user['phid']
                cached_users[user_id] = user

            # Retrieve cached tasks users and projects
            raw_checkpoint = next(cache_items)
            checkpoint = raw_checkpoint == '{}'

            while not checkpoint:
                users = self.__retrive_cached_users(cache_items)
                for user in users:
                    user_id = user['phid']
                    cached_users[user_id] = user

                projects = self.__retrieve_cached_projects(cache_items)
                for project in projects:
                    project_id = project['phid']
                    cached_projects[project_id] = project

                raw_checkpoint = next(cache_items)
                checkpoint = raw_checkpoint == '{}'

            task_builder = self.__build_cached_tasks(tasks, tasks_trans,
                                                     cached_users, cached_projects)

            for task in task_builder:
                yield task

    def __get_or_fetch_user(self, user_id):
        if user_id in self._users:
            return self._users[user_id]

        logger.debug("User %s not found on client cache; fetching it", user_id)

        if user_id.startswith('PHID-USER-'):
            user = self.__fetch_and_parse_users(user_id)[0]
        else:
            logger.debug("User %s is not a real user. Using PHID API to fetch it", user_id)
            user = self.__fetch_and_parse_phids(user_id)[0]
        self._users[user_id] = user
        return user

    def __get_or_fetch_project(self, project_id):
        if project_id in self._projects:
            return self._projects[project_id]

        logger.debug("Project %s not found on client cache; fetching it", project_id)
        project = self.__fetch_and_parse_phids(project_id)[0]
        self._projects[project_id] = project
        return project

    def __retrive_cached_users(self, cache_items):
        checkpoint = False

        while not checkpoint:
            raw_item = next(cache_items)

            if raw_item in ('{ENDUSERS}', '{ENDTRANS}'):
                checkpoint = True
            elif raw_item == '{PHID}':
                raw_item = next(cache_items)
                phids = [phid for phid in self.parse_phids(raw_item)]
                yield phids[0]
            else:
                users = [user for user in self.parse_users(raw_item)]
                yield users[0]

    def __retrieve_cached_projects(self, cache_items):
        checkpoint = False

        while not checkpoint:
            raw_item = next(cache_items)

            if raw_item == '{ENDPROJECTS}':
                checkpoint = True
            else:
                raw_item = next(cache_items)
                phids = [phid for phid in self.parse_phids(raw_item)]
                yield phids[0]

    def __fetch_and_parse_tasks_transactions(self, *tasks_ids):
        logger.debug("Fetching and parsing tasks transactions")

        raw_json = self.client.transactions(*tasks_ids)
        self._push_cache_queue(raw_json)
        tasks_trans = self.parse_tasks_transactions(raw_json)

        for trans in tasks_trans.values():
            for tt in trans:
                author_id = tt['authorPHID']
                author = self.__get_or_fetch_user(author_id)
                tt['authorData'] = author

        # Transactions checkpoint
        self._push_cache_queue('{ENDTRANS}')

        return tasks_trans

    def __fetch_and_parse_users(self, *users_ids):
        logger.debug("Fetching and parsing users data")
        raw_json = self.client.users(*users_ids)
        self._push_cache_queue(raw_json)
        users = self.parse_users(raw_json)
        return [user for user in users]

    def __fetch_and_parse_phids(self, *phids):
        logger.debug("Fetching and parsing phids data")
        raw_json = self.client.phids(*phids)
        # PHID checkpoint
        self._push_cache_queue('{PHID}')
        self._push_cache_queue(raw_json)
        result = self.parse_phids(raw_json)
        return [phid for phid in result]

    def __build_cached_tasks(self, tasks, transactions,
                             cached_users, cached_projects):
        for task in tasks:
            tid = str(task['id'])
            author_id = task['fields']['authorPHID']
            owner_id = task['fields']['ownerPHID']

            task['fields']['authorData'] = cached_users[author_id]

            if owner_id:
                task['fields']['ownerData'] = cached_users[owner_id]

            # Build tasks transactions
            task_trans = transactions[tid]

            for tt in task_trans:
                user_id = tt['authorPHID']
                tt['authorData'] = cached_users[user_id]

            # Build tasks projects
            projects_ids = task['attachments']['projects']['projectPHIDs']
            task_projects = [cached_projects[project_id] \
                             for project_id in projects_ids]

            task['transactions'] = task_trans
            task['projects'] = task_projects

            yield task

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
        """Extracts the identifier from a Phabricator item."""

        return str(item['id'])

    @staticmethod
    def metadata_updated_on(item):
        """Extracts and coverts the update time from a Phabricator item.

        The timestamp is extracted from 'dateModified' field. This date is
        in UNIX timestamp format but needs to be converted to a float
        number.

        :param item: item generated by the backend

        :returns: a UNIX timestamp
        """
        return float(item['fields']['dateModified'])

    @staticmethod
    def metadata_category(item):
        """Extracts the category from a Phabricator item.

        This backend only generates one type of item which is
        'task'.
        """
        return 'task'

    @staticmethod
    def parse_tasks(raw_json):
        """Parse a Phabricator tasks JSON stream.

        The method parses a JSON stream and returns a list iterator.
        Each item is a dictionary that contains the task parsed data.

        :param raw_json: JSON string to parse

        :returns: a generator of parsed tasks
        """
        results = json.loads(raw_json)

        tasks = results['result']['data']
        for t in tasks:
            yield t

    @staticmethod
    def parse_tasks_transactions(raw_json):
        """Parse a Phabricator tasks transactions JSON stream.

        The method parses a JSON stream and returns a dictionary
        with the parsed transactions.

        :param raw_json: JSON string to parse

        :returns: a dict with the parsed transactions
        """
        results = json.loads(raw_json)
        return results['result']

    @staticmethod
    def parse_users(raw_json):
        """Parse a Phabricator users JSON stream.

        The method parses a JSON stream and returns a list iterator.
        Each item is a dictionary that contais the user parsed data.

        :param raw_json: JSON string to parse

        :returns: a generator of parsed users
        """
        results = json.loads(raw_json)

        users = results['result']
        for u in users:
            yield u

    @staticmethod
    def parse_phids(raw_json):
        """Parse a Phabicator PHIDs JSON stream.

        This method parses a JSON stream and returns a list iterator.
        Each item is a dictionary that contains the PHID parsed data.

        :param raw_json: JSON string to parse

        :returns: a generator of parsed PHIDs
        """
        results = json.loads(raw_json)
        for phid in results['result'].values():
            yield phid


class PhabricatorCommand(BackendCommand):
    """Class to run Phabricator backend from the command line."""

    def __init__(self, *args):
        super().__init__(*args)

        self.url = self.parsed_args.url
        self.backend_token = self.parsed_args.backend_token
        self.from_date = str_to_datetime(self.parsed_args.from_date)
        self.outfile = self.parsed_args.outfile
        self.tag = self.parsed_args.tag

        if not self.parsed_args.no_cache:
            if not self.parsed_args.cache_path:
                base_path = os.path.expanduser('~/.perceval/cache/')
            else:
                base_path = self.parsed_args.cache_path

            cache_path = os.path.join(base_path, self.url)

            cache = Cache(cache_path)

            if self.parsed_args.clean_cache:
                cache.clean()
            else:
                cache.backup()
        else:
            cache = None

        self.backend = Phabricator(self.url,
                                   self.backend_token,
                                   tag=self.tag,
                                   cache=cache)

    def run(self):
        """Fetch and print the tasks.

        This method runs the backend to fetch the tasks from the
        Phabricator server. Tasks are converted to JSON objects and
        printed to the defined output.
        """
        if self.parsed_args.fetch_cache:
            tasks = self.backend.fetch_from_cache()
        else:
            tasks = self.backend.fetch(from_date=self.from_date)

        try:
            for task in tasks:
                obj = json.dumps(task, indent=4, sort_keys=True)
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
        """Returns the Phabricator argument parser."""

        parser = super().create_argument_parser()

        # Backend token is required
        action = parser._option_string_actions['--backend-token']
        action.required = True

        # Required arguments
        parser.add_argument('url',
                            help="URL of the Phabricator server")

        return parser


class ConduitError(BaseError):
    """Raised when an error occurs using Conduit"""

    message = "%(error)s (code: %(code)s)"


class ConduitClient:
    """Conduit API Client.

    Phabricator uses Conduit as the Phabricator REST API.
    This class implements some of its methods to retrieve the
    contents from a Phabricator server.

    :param base_url: URL of the Phabricator server
    :param api_token: token to get access to restricted methods
        of the API
    """
    URL = '%(base)s/api/%(method)s'

    # Methods
    MANIPHEST_TASKS = 'maniphest.search'
    MANIPHEST_TRANSACTIONS = 'maniphest.gettasktransactions'
    PHAB_PHIDS = 'phid.query'
    PHAB_USERS = 'user.query'

    PAFTER = 'after'
    PATTACHMENTS = 'attachments'
    PCONSTRAINTS = 'constraints'
    PHIDS = 'phids'
    PIDS = 'ids'
    PPROJECTS = 'projects'
    PORDER = 'order'
    PMODIFIED_START = 'modifiedStart'

    VOUTDATED = 'outdated'

    def __init__(self, base_url, api_token):
        self.base_url = base_url.rstrip('/')
        self.api_token = api_token

    def tasks(self, from_date=DEFAULT_DATETIME):
        """Retrieve tasks.

        :param from_date: retrieve tasks that where updated from that date;
            dates are converted epoch time.
        """
        # Convert 'from_date' to epoch timestamp.
        # Zero value (1970-01-01 00:00:00) is not allowed for
        # 'modifiedStart' so it will be set to 1, by default.
        ts = int(datetime_to_utc(from_date).timestamp()) or 1

        consts = {
            self.PMODIFIED_START : ts
        }

        attachments = {
            self. PPROJECTS : True
        }

        params = {
            self.PCONSTRAINTS : consts,
            self.PATTACHMENTS : attachments,
            self.PORDER : self.VOUTDATED,
        }

        while True:
            r = self._call(self.MANIPHEST_TASKS, params)
            yield r
            j = json.loads(r)
            after = j['result']['cursor']['after']
            if not after:
                break
            params[self.PAFTER] = after

    def transactions(self, *phids):
        """Retrieve tasks transactions.

        :param phids: list of tasks identifiers
        """
        params = {
            self.PIDS : phids
        }

        response = self._call(self.MANIPHEST_TRANSACTIONS, params)

        return response

    def users(self, *phids):
        """Retrieve users.

        :params phids: list of users identifiers
        """
        params = {
            self.PHIDS : phids
        }

        response = self._call(self.PHAB_USERS, params)

        return response

    def phids(self, *phids):
        """Retrieve data about PHIDs.

        :params phids: list of PHIDs
        """
        params = {
            self.PHIDS : phids
        }

        response = self._call(self.PHAB_PHIDS, params)

        return response

    def _call(self, method, params):
        """Call a method.

        :param method: method to call
        :param params: dict with the HTTP parameters needed to call
            the given method

        :raises ConduitError: when an error is returned by the server
        """
        url = self.URL % {'base' : self.base_url, 'method' : method}

        # Conduit and POST parameters
        params['__conduit__'] = {'token' : self.api_token}

        data = {
            'params' : json.dumps(params),
            'output' : 'json',
            '__conduit__' : True
        }

        logger.debug("Phabricator Conduit client requests: %s params: %s",
                     method, str(data))

        r = requests.post(url, data=data, verify=False)
        r.raise_for_status()

        # Check for possible Conduit API errors
        result = r.json()

        if result['error_code']:
            raise ConduitError(error=result['error_info'],
                               code=result['error_code'])

        return r.text
