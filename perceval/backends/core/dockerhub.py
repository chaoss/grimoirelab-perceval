# -*- coding: utf-8 -*-
#
# Copyright (C) 2015-2017 Bitergia
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
#     Santiago Dueñas <sduenas@bitergia.com>
#

import logging

import requests

from grimoirelab.toolkit.uris import urijoin


logger = logging.getLogger(__name__)


DOCKERHUB_URL = "https://hub.docker.com/"
DOCKERHUB_API_URL = urijoin(DOCKERHUB_URL, 'v2')


class DockerHubClient:
    """DockerHub API client.

    Client for fetching information from the DockerHub server
    using its REST API v2.
    """
    RREPOSITORY = 'repositories'

    def repository(self, owner, repository):
        """Fetch information about a repository."""

        resource = urijoin(self.RREPOSITORY, owner, repository)
        response = self._fetch(resource, {})

        return response

    def _fetch(self, resource, params):
        """Fetch a resource.

        :param resource: resource to fetch
        :param params: dict with the HTTP parameters needed to call
            the given method
        """
        url = urijoin(DOCKERHUB_API_URL, resource)

        logger.debug("DockerHub client requests: %s params: %s",
                     resource, str(params))

        r = requests.get(url, params=params)
        r.raise_for_status()

        return r.text
