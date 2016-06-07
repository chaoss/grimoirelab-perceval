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
#     Alvaro del Castillo San Felix <acs@bitergia.com>
#

import json
import logging

import requests

from ..errors import BackendError
from ..utils import (DEFAULT_DATETIME,
                     datetime_to_utc,
                     urljoin)


logger = logging.getLogger(__name__)


MAX_BUGS = 500 # Maximum number of bugs per query


class BugzillaRESTClient:
    """Bugzilla REST API client.

    This class implements a simple client to retrieve distinct
    kind of data from a Bugzilla > 5.0 repository using its
    REST API.

    When `user` and `password` parameters are given it logs in
    the server. Further requests will use the token obtained
    during the sign in phase.

    :param base_url: URL of the Bugzilla server
    :param user: Bugzilla user
    :param password: user password
    :param api_token: api token for user; when this is provided
        `user` and `password` parameters will be ignored

    :raises BackendError: when an error occurs initilizing the
        client
    """
    URL = "%(base)s/rest/%(resource)s"

    # API resources
    RBUG = 'bug'
    RATTACHMENT = 'attachment'
    RCOMMENT = 'comment'
    RHISTORY = 'history'
    RLOGIN = 'login'

    # Resource parameters
    PBUGZILLA_LOGIN = 'login'
    PBUGZILLA_PASSWORD = 'password'
    PBUGZILLA_TOKEN = 'token'
    PLAST_CHANGE_TIME = 'last_change_time'
    PLIMIT = 'limit'
    POFFSET = 'offset'
    PORDER = 'order'
    PINCLUDE_FIELDS = 'include_fields'
    PEXCLUDE_FIELDS = 'exclude_fields'

    # Predefined values
    VCHANGE_DATE_ORDER = 'changeddate'
    VINCLUDE_ALL = '_all'
    VEXCLUDE_ATTCH_DATA = 'data'

    def __init__(self, base_url, user=None, password=None, api_token=None):
        self.base_url = base_url
        self.api_token = api_token if api_token else None

        if user is not None and password is not None:
            self.login(user, password)

    def login(self, user, password):
        """Authenticate a user in the server.

        :param user: Bugzilla user
        :param password: user password
        """
        params = {
            self.PBUGZILLA_LOGIN : user,
            self.PBUGZILLA_PASSWORD : password
        }

        try:
            r = self.call(self.RLOGIN, params)
        except requests.exceptions.HTTPError as e:
            cause = ("Bugzilla REST client could not authenticate user %s. "
                "See exception: %s") % (user, str(e))
            raise BackendError(cause=cause)

        data = json.loads(r)
        self.api_token = data['token']

    def bugs(self, from_date=DEFAULT_DATETIME, offset=None, max_bugs=MAX_BUGS):
        """Get the information of a list of bugs.

        :param from_date: retrieve bugs that where updated from that date;
            dates are converted to UTC
        :param offset: starting position for the search; i.e to return 11th
            element, set this value to 10.
        :param max_bugs: maximum number of bugs to reteurn per query
        """
        date = datetime_to_utc(from_date)
        date = date.strftime("%Y-%m-%dT%H:%M:%SZ")

        params = {
            self.PLAST_CHANGE_TIME : date,
            self.PLIMIT : max_bugs,
            self.PORDER : self.VCHANGE_DATE_ORDER,
            self.PINCLUDE_FIELDS : self.VINCLUDE_ALL
        }

        if offset:
            params[self.POFFSET] = offset

        response = self.call(self.RBUG, params)

        return response

    def comments(self, bug_id):
        """Get the comments of the given bug.

        :param bug_id: bug identifier
        """
        resource = urljoin(self.RBUG, bug_id, self.RCOMMENT)
        params = {}

        response = self.call(resource, params)

        return response

    def history(self, bug_id):
        """Get the history of the given bug.

        :param bug_id: bug identifier
        """
        resource = urljoin(self.RBUG, bug_id, self.RHISTORY)
        params = {}

        response = self.call(resource, params)

        return response

    def attachments(self, bug_id):
        """Get the attachments of the given bug.

        :param bug_id: bug identifier
        """
        resource = urljoin(self.RBUG, bug_id, self.RATTACHMENT)
        params = {
            self.PEXCLUDE_FIELDS : self.VEXCLUDE_ATTCH_DATA
        }

        response = self.call(resource, params)

        return response

    def call(self, resource, params):
        """Retrive the given resource.

        :param resource: resource to retrieve
        :param params: dict with the HTTP parameters needed to retrieve
            the given resource
        """
        url = self.URL % {'base' : self.base_url, 'resource' : resource}

        if self.api_token:
            params[self.PBUGZILLA_TOKEN] = self.api_token

        logger.debug("Bugzilla REST client requests: %s params: %s",
                     resource, str(params))

        r = requests.get(url, params=params)
        r.raise_for_status()

        return r.text
