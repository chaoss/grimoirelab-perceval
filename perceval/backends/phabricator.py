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

import requests

from ..errors import BaseError
from ..utils import DEFAULT_DATETIME, datetime_to_utc


logger = logging.getLogger(__name__)


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

    PAFTER = 'after'
    PCONSTRAINTS = 'constraints'
    PIDS = 'ids'
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
        ts = int(datetime_to_utc(from_date).timestamp())
        consts = {
            self.PMODIFIED_START : ts,
        }

        params = {
            self.PCONSTRAINTS : consts,
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
