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

import logging
import os
import posixpath

import requests

from .mbox import MailingList
from ..errors import RepositoryError
from ..utils import urljoin


logger = logging.getLogger(__name__)


DEFAULT_OFFSET = 0
MAX_MESSAGES = 2000 # Maximum number of messages per query


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

    def fetch(self, from_offset=DEFAULT_OFFSET):
        """Fetch the messages from Gmane and store them in mbox files.

        Stores the messages in mboxes files in the path given during the
        initialization of this object. Messages are fetched from the given
        offset.

        :param from_offset: start to fetch messages from the given index

        :returns: a list of tuples, storing the links and paths of the
            fetched archives
        """
        logger.info("Downloading messages from '%s' and offset %s",
                    self.url, str(from_offset))
        logger.debug("Storing messages in '%s'", self.dirpath)

        fetched = []
        mailing_list = posixpath.basename(self.url)
        offset = from_offset

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
