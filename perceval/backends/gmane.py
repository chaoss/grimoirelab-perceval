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
#     Germán Poo-Caamaño <gpoo@gnome.org>
#
# Note: some ot this code was based on parts of the MailingListStats project
#

import functools
import json
import logging
import os
import posixpath

import requests

from .mbox import MailingList, MBox
from ..backend import BackendCommand, metadata
from ..errors import RepositoryError
from ..utils import urljoin


logger = logging.getLogger(__name__)


DEFAULT_OFFSET = 0
MAX_MESSAGES = 2000 # Maximum number of messages per query


def gmane_metadata(func):
    """Gmane metadata decorator.

    This decorator takes items overrides `metadata` decorator to add extra
    information related to Gmane.
    """
    @functools.wraps(func)
    def decorator(self, *args, **kwargs):
        offset = kwargs.get('offset', DEFAULT_OFFSET)

        for item in func(self, *args, **kwargs):
            item['offset'] = offset
            offset += 1
            yield item
    return decorator


class Gmane(MBox):
    """Gmane backend.

    The Gmane backend allows to fetch the email messages from a mailing
    list stored on Gmane. Initialize this class passing the mailing list
    address (i.e: my-mailing-list@example.com) and the directory path
    where the mbox files will be stored.

    The origin of the data will be set to to the URL under Gmane stores
    that list; usually it is similar to the next address:
    'http://dir.gmane.org/gmane.comp.example.mylist'

    :param mailing_list_address: address of the mailing list
    :param dirpath: directory path where the mboxes are stored
    :param tag: label used to mark the data
    :param cache: cache object to store raw data

    :raises  RepositoryError: when the given mailing list repository
        is not stored by Gmane
    """
    version = '0.4.0'

    def __init__(self, mailing_list_address, dirpath,
                 tag=None, cache=None):
        self.mailing_list = GmaneMailingList(mailing_list_address, dirpath)

        url = self.mailing_list.url

        super().__init__(url, dirpath, tag=tag, cache=cache)
        self.url = url

    @gmane_metadata
    @metadata
    def fetch(self, offset=DEFAULT_OFFSET):
        """Fetch the messages from Gmane.

        The method fetches the messages stored in Gmane related
        to the mailing list.

        :param offset: obtain messages from this offset

        :returns: a generator of messages
        """
        logger.info("Looking for messages from '%s' offset %s)",
                    self.url, offset)

        fetched = self.mailing_list.fetch(offset=offset)
        valid_filepaths = [f[1] for f in fetched]

        # Dates are converted to UTC in the next method
        messages = self._fetch_and_parse_messages(self.mailing_list,
                                                  valid_filepaths)

        for message in messages:
            yield message

        logger.info("Fetch process completed")

    def _fetch_and_parse_messages(self, mailing_list, valid_filepaths):
        """Overrides _fetch_and_parse_messages of MBox"""

        nmsgs, imsgs, tmsgs = (0, 0, 0)

        for mbox in mailing_list.mboxes:
            if not mbox.filepath in valid_filepaths:
                continue

            try:
                tmp_path = self._copy_mbox(mbox)

                for message in self.parse_mbox(tmp_path):
                    tmsgs += 1

                    if not self._validate_message(message):
                        imsgs += 1
                        continue

                    # Convert 'CaseInsensitiveDict' to dict
                    message = self._casedict_to_dict(message)

                    nmsgs += 1
                    logger.debug("Message %s parsed", message['unixfrom'])

                    yield message
            except OSError as e:
                logger.warning("Ignoring %s mbox due to: %s", mbox.filepath, str(e))
            except Exception as e:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
                raise e
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)

        logger.info("Done. %s/%s messages fetched; %s ignored",
                    nmsgs, tmsgs, imsgs)

    @classmethod
    def has_caching(cls):
        """Returns whether it supports caching items on the fetch process.

        :returns: this backend does not support items cache
        """
        return False

    @classmethod
    def has_resuming(cls):
        """Returns whether it supports to resume the fetch process.

        :returns: this backend supports items resuming
        """
        return True


class GmaneCommand(BackendCommand):
    """Class to run Gmane backend from the command line."""

    def __init__(self, *args):
        super().__init__(*args)

        self.mailing_list = self.parsed_args.mailing_list
        self.outfile = self.parsed_args.outfile
        self.tag = self.parsed_args.tag
        self.offset = self.parsed_args.offset

        if not self.parsed_args.mboxes_path:
            base_path = os.path.expanduser('~/.perceval/mailinglists/')
            self.mboxes_path = os.path.join(base_path, self.mailing_list)
        else:
            self.mboxes_path = self.parsed_args.mboxes_path

        cache = None

        self.backend = Gmane(self.mailing_list, self.mboxes_path,
                             tag=self.tag, cache=cache)

    def run(self):
        """Fetch and print the email messages.

        This method runs the backend to fetch the email messages from
        the given mailing list. Messages are converted to JSON objects
        and printed to the defined output.
        """
        messages = self.backend.fetch(offset=self.offset)

        try:
            for message in messages:
                obj = json.dumps(message, indent=4, sort_keys=True)
                self.outfile.write(obj)
                self.outfile.write('\n')
        except IOError as e:
            raise RuntimeError(str(e))
        except Exception as e:
            raise RuntimeError(str(e))

    @classmethod
    def create_argument_parser(cls):
        """Returns the Gmane argument parser."""

        parser = super().create_argument_parser()

        # Remove --from-date argument from parent parser
        # because it is not needed by this backend
        action = parser._option_string_actions['--from-date']
        parser._handle_conflict_resolve(None, [('--from-date', action)])

        # Optional arguments
        parser.add_argument('--offset', dest='offset',
                            type=int, default=0,
                            help='Offset to start fetching messages')
        parser.add_argument('--mboxes-path', dest='mboxes_path',
                            help='Path where mbox files will be stored')

        # Required arguments
        parser.add_argument('mailing_list',
                            help='Mailing list address on Gmane')

        return parser


class GmaneMailingList(MailingList):
    """Manage mailing list archives stored by Gmane.

    This class gives access to remote and local messages from a
    mailing list stored by Gmane. Due to the nature of Gmane
    and how messages are stored, this class does not manage
    overlaped mboxes nor duplicated messages. Messages must be
    filtered on later stages.

    :param mailing_list_address: address of the mailing list (i.e:
        my-mailing-list@example.com)
    :param dirpath: path to the local mboxes archives

    :raises  RepositoryError: when the given mailing list repository
        is not stored by Gmane
    """
    def __init__(self, mailing_list_address, dirpath):
        self.client = GmaneClient()
        self._url = self.client.mailing_list_url(mailing_list_address)
        super().__init__(self._url, dirpath)

    def fetch(self, offset=DEFAULT_OFFSET):
        """Fetch the messages from Gmane and store them in mbox files.

        Stores the messages in mboxes files in the path given during the
        initialization of this object. Messages are fetched from the given
        offset.

        :param offset: start to fetch messages from the given index

        :returns: a list of tuples, storing the links and paths of the
            fetched archives
        """
        logger.info("Downloading messages from '%s' and offset %s",
                    self.url, str(offset))
        logger.debug("Storing messages in '%s'", self.dirpath)

        if not os.path.exists(self.dirpath):
            os.makedirs(self.dirpath)

        fetched = []
        mailing_list = posixpath.basename(self.url)

        while True:
            messages = self.client.messages(mailing_list, offset,
                                            max_messages=MAX_MESSAGES)

            # In Gmane, an empty page means we reached the last message.
            if len(messages) == 0:
                break

            filepath = os.path.join(self.dirpath, str(offset))

            success = self._store_messages(filepath, offset, messages)

            if success:
                fetched.append((offset, filepath))

            offset += MAX_MESSAGES

        logger.info("Messages from Gmane %s downloaded", self.url)

        return fetched

    @property
    def mboxes(self):
        """Get the mboxes managed by this mailing list.

        Returns the archives sorted by offset in ascending order.

        :returns: a list of `.MBoxArchive` objects
        """
        archives = []

        for mbox in super().mboxes:
            try:
                offset = int(os.path.basename(mbox.filepath))
                archives.append((offset, mbox))
            except ValueError:
                logger.debug("Ignoring %s archive because its filename is not valid",
                             mbox.filepath)
                continue

        archives.sort(key=lambda x: x[0])

        return [a[1] for a in archives]

    @property
    def url(self):
        """Gmane URL for this mailing list"""
        return self._url

    def _store_messages(self, filepath, offset, messages):
        try:
            with open(filepath, 'wb') as fd:
                fd.write(messages)
        except OSError as e:
            logger.warning("Ignoring messages from %s with offset %s due to: %s",
                           self.url, offset, str(e))
            return False

        logger.debug("%s messages with offset %s downloaded and stored in %s",
                     self.url, offset, filepath)
        return True


class GmaneClient:
    """Gmane client.

    This class implements a simple client to access mailing lists
    stored in Gmane.
    """
    GMANE_DOMAIN = 'gmane.org'
    GMANE_DOWNLOAD_RTYPE = 'download'
    GMANE_LISTID_RTYPE = 'list'

    URL = "http://%(prefix)s.%(domain)s/%(resource)s"


    def messages(self, mailing_list, offset, max_messages=MAX_MESSAGES):
        """Fetch a set of messages from the given mailing list.

        Given the mailing list identifier used by Gmane and a offset,
        this method fetches a set of messages.

        :param mailing_list: mailing list identifier on Gmane
        :param offset: start to fetch from here
        :param max_messages: maximum number of messages to fetch
        """
        end_offset = offset + max_messages
        resource = urljoin(mailing_list, offset, end_offset)

        r = self.fetch(self.GMANE_DOWNLOAD_RTYPE, resource)

        return r.content

    def mailing_list_url(self, mailing_list_address):
        """Get the Gmane URL that stores the given mailing list address.

        :param mailing_list_address: address of the mailing list (i.e:
            my-mailing-list@example.com)

        :raises RepositoryError: when the given mailing list repository
            is not stored by Gmane
        """
        r = self.fetch(self.GMANE_LISTID_RTYPE, mailing_list_address)

        if len(r.history) == 0:
            cause = "%s mailing list not found in Gmane"
            raise RepositoryError(cause=cause)

        return r.url

    def fetch(self, rtype, resource):
        """Fetch the given resource.

        :param rtype: type of the resource
        :param resource: resource to fetch
        """
        url = self.URL % {
                          'prefix' : rtype,
                          'domain' : self.GMANE_DOMAIN,
                          'resource' : resource
                         }

        logger.debug("Gmane client requests: %s, rtype: %s resource: %s",
                     url, rtype, resource)

        r = requests.get(url)
        r.raise_for_status()

        return r
