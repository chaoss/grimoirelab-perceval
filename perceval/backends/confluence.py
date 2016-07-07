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

import logging

import requests

from ..utils import DEFAULT_DATETIME, urljoin


logger = logging.getLogger(__name__)


MAX_CONTENTS = 200


class ConfluenceClient:
    """Confluence REST API client.

    This class implements a client to retrieve contents from a
    Confluence server using its REST API.

    :param base_url: URL of the Confluence server
    """
    URL = "%(base)s/rest/api/%(resource)s"

    # API resources
    RCONTENTS = 'content'
    RHISTORY = 'history'
    RSPACE = 'space'

    # API methods
    MSEARCH = 'search'

    # API parameters
    PCQL = 'cql'
    PEXPAND = 'expand'
    PLIMIT = 'limit'
    PSTART = 'start'
    PSTATUS = 'status'
    PVERSION = 'version'

    # Common values
    VCQL = "lastModified>='%(date)s' order by lastModified"
    VEXPAND = ['body.storage', 'history', 'version']
    VHISTORICAL = 'historical'

    def __init__(self, base_url):
        self.base_url = base_url

    def contents(self, from_date=DEFAULT_DATETIME,
                 offset=None, max_contents=MAX_CONTENTS):
        """Get the contents of a repository.

        This method returns an iterator that manages the pagination
        over contents. Take into account that the seconds of `from_date`
        parameter will be ignored because the API only works with
        hours and minutes.

        :param from_date: fetch the contents updated since this date
        :param offset: fetch the contents starting from this offset
        :param limit: maximum number of contents to fetch per request
        """
        resource = self.RCONTENTS + '/' + self.MSEARCH

        # Set confluence query parameter (cql)
        date = from_date.strftime("%Y-%m-%d %H:%M")
        cql = self.VCQL % {'date' : date}

        # Set parameters
        params = {
            self.PCQL : cql,
            self.PLIMIT : max_contents
        }

        if offset:
            params[self.PSTART] = offset

        for response in self._call(resource, params):
            yield response

    def historical_content(self, content_id, version):
        """Get the snapshot of a content for the given version.

        :param content_id: fetch the snapshot of this content
        :param version: snapshot version of the content
        """
        resource = self.RCONTENTS + '/' + str(content_id)

        params = {
            self.PVERSION : version,
            self.PSTATUS : self.VHISTORICAL,
            self.PEXPAND : ','.join(self.VEXPAND)
        }

        # Only one item is returned
        response = [response for response in self._call(resource, params)]
        return response[0]

    def _call(self, resource, params):
        """Retrive the given resource.

        :param resource: resource to retrieve
        :param params: dict with the HTTP parameters needed to retrieve
            the given resource
        """
        url = self.URL % {'base' : self.base_url, 'resource' : resource}

        logger.debug("Confluence client requests: %s params: %s",
                     resource, str(params))

        while True:
            r = requests.get(url, params=params)
            r.raise_for_status()
            yield r.text

            # Pagination is available when 'next' link exists
            j = r.json()
            if not '_links' in j:
                break
            if not 'next' in j['_links']:
                break

            url = urljoin(self.base_url, j['_links']['next'])
            params = {}
