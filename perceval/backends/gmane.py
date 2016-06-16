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

import requests

from ..errors import RepositoryError
from ..utils import urljoin


logger = logging.getLogger(__name__)


MAX_MESSAGES = 2000 # Maximum number of messages per query


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

        return r.text

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

        logger.debug("Gmane client requests: %s resource: %s",
                     rtype, resource)
        print(url)

        r = requests.get(url)
        r.raise_for_status()

        return r
