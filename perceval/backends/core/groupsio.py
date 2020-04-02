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
#     Harshal Mittal <harshalmittal4@gmail.com>
#     Santiago Dueñas <sduenas@bitergia.com>
#

import logging
import os
import requests

from grimoirelab_toolkit.datetime import datetime_to_utc
from grimoirelab_toolkit.uris import urijoin

from .mbox import MBox, MailingList, CATEGORY_MESSAGE
from ...backend import (BackendCommand,
                        BackendCommandArgumentParser,
                        DEFAULT_SEARCH_FIELD)
from ...errors import BackendError
from ...utils import DEFAULT_DATETIME

MBOX_FILE = 'messages.zip'

GROUPSIO_URL = 'https://groups.io/'
GROUPSIO_API_URL = 'https://groups.io/api/v1'

PER_PAGE = 100


logger = logging.getLogger(__name__)


class Groupsio(MBox):
    """Groups.io backend.

    This class allows the fetch the messages of a Groups.io group.
    Initialize this class passing the name of the group, the
    directory path where the mbox files will be fetched and
    stored, and the email and password of the Groupsio user.
    The origin of the data will be set to the url of the group
    on Groups.io.

    In order to know the group names where you are subscribed,
    you can use the following script:
    https://gist.github.com/valeriocos/2e2231e17fd3052800303bf99bd0c7c4

    :param group_name: Name of the group
    :param dirpath: directory path where the mboxes are stored
    :param email: Groupsio user email
    :param password: Groupsio user password
    :param tag: label used to mark the data
    :param archive: archive to store/retrieve items
    :param ssl_verify: enable/disable SSL verification
    """
    version = '0.4.2'

    CATEGORIES = [CATEGORY_MESSAGE]

    def __init__(self, group_name, dirpath, email, password, tag=None, archive=None, ssl_verify=True):
        url = urijoin(GROUPSIO_URL, 'g', group_name)
        super().__init__(url, dirpath, tag=tag, archive=archive, ssl_verify=ssl_verify)
        self.email = email
        self.password = password
        self.group_name = group_name

    def search_fields(self, item):
        """Add search fields to an item.

        It adds the values of `metadata_id` plus the `group_name`

        :param item: the item to extract the search fields values

        :returns: a dict of search fields
        """
        search_fields = {
            DEFAULT_SEARCH_FIELD: self.metadata_id(item)
        }

        origin_parts = self.origin.split('/')
        search_fields['group_name'] = origin_parts[-1]

        return search_fields

    def fetch(self, category=CATEGORY_MESSAGE, from_date=DEFAULT_DATETIME):
        """Fetch the messages from a Groups.io group.

        The method fetches the mbox files from a remote Groups.io group
        and retrieves the messages stored on them.

        :param category: the category of items to fetch
        :param from_date: obtain messages since this date

        :returns: a generator of messages
        """
        items = super().fetch(category, from_date)

        return items

    def fetch_items(self, category, **kwargs):
        """Fetch the messages

        :param category: the category of items to fetch
        :param kwargs: backend arguments

        :returns: a generator of items
        """
        from_date = kwargs['from_date']

        logger.info("Looking for messages from '%s' since %s",
                    self.uri, str(from_date))

        mailing_list = GroupsioClient(self.group_name, self.dirpath,
                                      self.email, self.password, self.ssl_verify)
        mailing_list.fetch(from_date)

        messages = self._fetch_and_parse_messages(mailing_list, from_date)

        for message in messages:
            yield message

        logger.info("Fetch process completed")

    @classmethod
    def has_archiving(cls):
        """Returns whether it supports archiving items on the fetch process.

        :returns: this backend does not support items archive
        """
        return False

    @classmethod
    def has_resuming(cls):
        """Returns whether it supports to resume the fetch process.

        :returns: this backend supports items resuming
        """
        return True


class GroupsioClient(MailingList):
    """Manage mailing list archives stored by Groups.io.

    This class gives access to remote and local mboxes archives
    from a mailing list stored by Groups.io. This class also allows
    to keep them in sync.

    :param group_name: Name of the group
    :param dirpath: directory path where the mboxes are stored
    :param email: Groupsio user email
    :param password: Groupsio user password
    :param ssl_verify: enable/disable SSL verification
    """
    # API resources
    RDOWNLOAD_ARCHIVES = 'downloadarchives'
    RGET_SUBSCRIPTIONS = 'getsubs'
    RLOGIN = 'login'

    # Resource parameters
    PGROUP_ID = 'group_id'
    PSTART_TIME = 'start_time'
    PLIMIT = 'limit'
    PPAGE_TOKEN = 'page_token'
    PEMAIL = 'email'
    PPASSWORD = 'password'

    def __init__(self, group_name, dirpath, email, password, ssl_verify=True):
        url = urijoin(GROUPSIO_URL, 'g', group_name)
        super().__init__(url, dirpath)

        self.session = requests.Session()
        self.group_name = group_name
        self.ssl_verify = ssl_verify
        self.__login(email, password)

    def fetch(self, from_date=None):
        """Fetch the mbox files from the remote archiver.

        Stores the archives in the path given during the initialization
        of this object. Those archives which a not valid extension will
        be ignored.

        Groups.io archives are returned as a .zip file, which contains
        one file in mbox format.

        :param from_date: fetch messages after a given date (included) expressed in ISO format

        :returns: a list of tuples, storing the links and paths of the
            fetched archives
        """
        logger.info("Downloading mboxes from '%s'", self.uri)
        logger.debug("Storing mboxes in '%s'", self.dirpath)

        if not os.path.exists(self.dirpath):
            os.makedirs(self.dirpath)

        group_id, group_download_archive = self.__find_group_info()

        if not group_download_archive:
            msg = "Download archive permission disabled for the group %s" % self.group_name
            logger.error(msg)
            raise BackendError(cause=msg)

        url = urijoin(GROUPSIO_API_URL, self.RDOWNLOAD_ARCHIVES)
        payload = {
            self.PGROUP_ID: group_id
        }

        if from_date:
            payload[self.PSTART_TIME] = datetime_to_utc(from_date).isoformat()

        filepath = os.path.join(self.dirpath, MBOX_FILE)
        success = self._download_archive(url, payload, filepath)

        return success

    def subscriptions(self, per_page=PER_PAGE):
        """Fetch the groupsio paginated subscriptions for a given token

        :param per_page: number of subscriptions per page

        :returns: an iterator of subscriptions
        """
        url = urijoin(GROUPSIO_API_URL, self.RGET_SUBSCRIPTIONS)
        logger.debug("Get groupsio paginated subscriptions from " + url)

        keep_fetching = True
        payload = {
            self.PLIMIT: per_page
        }

        while keep_fetching:
            r = self.__fetch(url, payload)
            response_raw = r.json()
            subscriptions = response_raw['data']
            yield subscriptions

            total_subscriptions = response_raw['total_count']
            logger.debug("Subscriptions: %i/%i" % (response_raw['end_item'], total_subscriptions))

            payload[self.PPAGE_TOKEN] = response_raw['next_page_token']
            keep_fetching = response_raw['has_more']

    def _download_archive(self, url, payload, filepath):
        r = self.session.get(url, params=payload, stream=True, verify=self.ssl_verify)
        try:
            r.raise_for_status()
            self._write_archive(r, filepath)
        except requests.exceptions.HTTPError as e:
            logger.error("Impossible to download archives from %s. Error info: %s",
                         self.uri, str(e.response.text))
            raise e
        except OSError as e:
            logger.warning("Ignoring %s archive due to: %s", self.uri, str(e))
            return False

        logger.debug("%s archive downloaded and stored in %s", self.uri, filepath)

        return True

    @staticmethod
    def _write_archive(r, filepath):
        with open(filepath, 'wb') as fd:
            fd.write(r.raw.read())

    def __find_group_info(self):
        """Find the id and download archive permission of a group given
        its name by iterating on the list of subscriptions
        """
        group_subscriptions = self.subscriptions()

        for subscriptions in group_subscriptions:
            for sub in subscriptions:
                if sub['group_name'] == self.group_name:
                    return sub['group_id'], sub['perms']['download_archives']

        msg = "Group id not found for group name %s" % self.group_name
        raise BackendError(cause=msg)

    def __fetch(self, url, payload):
        """Fetch requests from groupsio API"""

        r = self.session.get(url, params=payload, verify=self.ssl_verify)
        try:
            r.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise e

        return r

    def __login(self, email, password):
        """Login a user to the server based on email and password.

        :param email: Groupsio user email
        :param password: Groupsio user password
        """
        url = urijoin(GROUPSIO_API_URL, self.RLOGIN)

        payload = {
            self.PEMAIL: email,
            self.PPASSWORD: password
        }

        self.session.post(url, params=payload)
        logger.debug("Groupsio email %s authenticated in %s",
                     email, GROUPSIO_API_URL)


class GroupsioCommand(BackendCommand):
    """Class to run Groupsio backend from the command line."""

    BACKEND = Groupsio

    def _pre_init(self):
        """Initialize mailing lists directory path"""

        if not self.parsed_args.mboxes_path:
            base_path = os.path.expanduser('~/.perceval/mailinglists/')
            dirpath = os.path.join(base_path, GROUPSIO_URL, 'g', self.parsed_args.group_name)
        else:
            dirpath = self.parsed_args.mboxes_path

        setattr(self.parsed_args, 'dirpath', dirpath)

    @classmethod
    def setup_cmd_parser(cls):
        """Returns the Groupsio argument parser."""

        parser = BackendCommandArgumentParser(cls.BACKEND,
                                              from_date=True,
                                              ssl_verify=True)

        # Optional arguments
        group = parser.parser.add_argument_group('Groupsio arguments')
        group.add_argument('--mboxes-path', dest='mboxes_path',
                           help="Path where mbox files will be stored")

        # Required arguments
        parser.parser.add_argument('group_name', help="Name of the group on Groups.io")
        parser.parser.add_argument('-e', '--email', dest='email', help="Groupsio user email")
        parser.parser.add_argument('-p', '--password', dest='password', help="Groupsio user password")

        return parser
