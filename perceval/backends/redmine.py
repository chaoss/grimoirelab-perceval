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

from ..utils import DEFAULT_DATETIME, datetime_to_utc, urljoin


logger = logging.getLogger(__name__)


MAX_ISSUES = 100  # Maximum number of issues per query


class RedmineClient:
    """Redmine API client.

    This class implements a client that retrieves issues from
    a Redmine server. Remine servers provides a REST API that
    returns its results in JSON format.

    :param base_url: URL of the Phabricator server
    :param api_token: token to get access to restricted data
        stored in the server
    """
    URL = '%(base)s/%(resource)s'

    RISSUES = 'issues'

    PINCLUDE = 'include'
    PKEY = 'key'
    PLIMIT = 'limit'
    POFFSET = 'offset'
    PSORT = 'sort'
    PSTATUS_ID = 'status_id'
    PUPDATED_ON = 'updated_on'

    CJSON = '.json'
    CATTACHMENTS = 'attachments'
    CCHANGESETS = 'changesets'
    CCHILDREN = 'children'
    CJOURNALS = 'journals'
    CRELATIONS = 'relations'
    CWATCHERS = 'watchers'

    def __init__(self, base_url, api_token=None):
        self.base_url = base_url.rstrip('/')
        self.api_token = api_token

    def issues(self, from_date=DEFAULT_DATETIME,
               offset=None, max_issues=MAX_ISSUES):
        """Get the information of a list of issues.

        :param from_date: retrieve issues that where updated from that date;
            dates are converted to UTC
        :param offset: starting position for the search
        :param max_issues: maximum number of issues to reteurn per query
        """
        resource = self.RISSUES + self.CJSON

        ts = datetime_to_utc(from_date)
        ts = ts.strftime("%Y-%m-%dT%H:%M:%SZ")

        # By default, Redmine returns open issues only.
        # Parameter 'status_id' is set to get all the statuses.
        params = {
            self.PSTATUS_ID : '*',
            self.PSORT : self.PUPDATED_ON,
            self.PUPDATED_ON : '>=' + ts,
            self.PLIMIT : max_issues
        }

        if offset:
            params[self.POFFSET] = offset

        response = self._call(resource, params)

        return response

    def issue(self, issue_id):
        """Get the information of the given issue.

        :param issue_id: issue identifier
        """
        resource = urljoin(self.RISSUES, str(issue_id) + self.CJSON)

        params = {
            self.PINCLUDE : ','.join([self.CATTACHMENTS, self.CCHANGESETS,
                                      self.CCHILDREN, self.CJOURNALS,
                                      self.CRELATIONS, self.CWATCHERS])
        }

        response = self._call(resource, params)

        return response

    def _call(self, resource, params):
        """Call to get a resource.

        :param method: resource to get
        :param params: dict with the HTTP parameters needed to get
            the given resource
        """
        url = self.URL % {'base' : self.base_url, 'resource' : resource}

        if self.api_token:
            params[self.PKEY] = self.api_token

        logger.debug("Redmine client requests: %s params: %s",
                     resource, str(params))

        r = requests.get(url, params=params, verify=False)
        r.raise_for_status()

        return r.text
