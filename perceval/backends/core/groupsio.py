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
#     Valerio Cosentino <valcos@bitergia.com>
#

import logging
import os
import requests
from requests.auth import HTTPBasicAuth

from grimoirelab_toolkit.uris import urijoin

from .mbox import MBox, MailingList, CATEGORY_MESSAGE
from ...backend import (BackendCommand,
                        BackendCommandArgumentParser)
from ...utils import DEFAULT_DATETIME

MBOX_FILE = 'messages.zip'

GROUPSIO_URL = 'https://groups.io/'
GROUPSIO_API_URL = 'https://api.groups.io/v1/'


logger = logging.getLogger(__name__)


class Groupsio(MBox):
    """Groups.io backend.

    This class allows the fetch the messages of a Groups.io group.
    Initialize this class passing the name of the group and the
    directory path where the mbox files will be fetched and
    stored. The origin of the data will be set to the url of the
    group on Groups.io.

    :param group_name: Name of the group
    :param dirpath: directory path where the mboxes are stored
    :param api_token: GitHub auth token to access the API
    :param verify: allows to disable SSL verification
    :param tag: label used to mark the data
    :param archive: archive to store/retrieve items
    """
    version = '0.1.0'

    CATEGORIES = [CATEGORY_MESSAGE]

    def __init__(self, group_name, dirpath, api_token, verify=True, tag=None, archive=None):
        url = urijoin(GROUPSIO_URL, 'g', group_name)
        super().__init__(url, dirpath, tag=tag, archive=archive)
        self.group_name = group_name
        self.api_token = api_token
        self.verify = verify

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
                                      self.api_token, self.verify)
        mailing_list.fetch()

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
    :param api_token: GitHub auth token to access the API
    :param verify: allows to disable SSL verification
    """
    def __init__(self, group_name, dirpath, api_token, verify=True):
        url = urijoin(GROUPSIO_URL, 'g', group_name)
        super().__init__(url, dirpath)
        self.group_name = group_name
        self.api_token = api_token
        self.verify = verify

    def fetch(self):
        """Fetch the mbox files from the remote archiver.

        Stores the archives in the path given during the initialization
        of this object. Those archives which a not valid extension will
        be ignored.

        Groups.io archives are returned as a .zip file, which contains
        one file in mbox format.

        :returns: a list of tuples, storing the links and paths of the
            fetched archives
        """
        logger.info("Downloading mboxes from '%s'", self.uri)
        logger.debug("Storing mboxes in '%s'", self.dirpath)

        if not os.path.exists(self.dirpath):
            os.makedirs(self.dirpath)

        url = urijoin(GROUPSIO_API_URL, 'downloadarchives')
        payload = {'group_name': self.group_name}
        auth = HTTPBasicAuth(self.api_token, '')

        filepath = os.path.join(self.dirpath, MBOX_FILE)
        success = self._download_archive(url, payload, auth, filepath)

        return success

    def _download_archive(self, url, payload, auth, filepath):
        try:
            r = requests.get(url, params=payload, auth=auth, stream=True, verify=self.verify)
            r.raise_for_status()
            self._write_archive(r, filepath)
        except requests.exceptions.HTTPError as e:
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

    @staticmethod
    def setup_cmd_parser():
        """Returns the Groupsio argument parser."""

        parser = BackendCommandArgumentParser(from_date=True,
                                              token_auth=True)

        # Optional arguments
        group = parser.parser.add_argument_group('Groupsio arguments')
        group.add_argument('--mboxes-path', dest='mboxes_path',
                           help="Path where mbox files will be stored")
        group.add_argument('--no-verify', dest='verify',
                           action='store_false',
                           help="Value 'True' enable SSL verification")

        # Required arguments
        parser.parser.add_argument('group_name',
                                   help="Name of the group on Groups.io")

        return parser
