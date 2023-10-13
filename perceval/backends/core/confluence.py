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
#     Santiago Dueñas <sduenas@bitergia.com>
#     Stephan Barth <stephan.barth@gmail.com>
#     Valerio Cosentino <valcos@bitergia.com>
#     Jesus M. Gonzalez-Barahona <jgb@gsyc.es>
#     Maurizio Pillitu <maoo@apache.org>
#     Harshal Mittal <harshalmittal4@gmail.com>
#

import base64
import logging
import json

import requests

from grimoirelab_toolkit.datetime import datetime_to_utc, str_to_datetime
from grimoirelab_toolkit.uris import urijoin

from ...backend import (Backend,
                        BackendCommand,
                        BackendCommandArgumentParser,
                        DEFAULT_SEARCH_FIELD)
from ...client import HttpClient
from ...utils import DEFAULT_DATETIME

CATEGORY_HISTORICAL_CONTENT = "historical content"
MAX_CONTENTS = 200
SEARCH_ANCESTOR_IDS = 'ancestor_ids'
SEARCH_CONTENT_ID = 'content_id'
SEARCH_CONTENT_VERSION_NUMBER = 'version_number'


logger = logging.getLogger(__name__)


class Confluence(Backend):
    """Confluence backend.

    This class allows the fetch the historical contents (content
    versions) stored on a Confluence server. Initialize this class
    passing the URL os this server. The `url` will be set as the
    origin of the data.

    :param url: URL of the server
    :param tag: label used to mark the data
    :param archive: archive to store/retrieve items
    :param ssl_verify: enable/disable SSL verification
    :param spaces: name of spaces to fetch, (default the entire instance)
    :param max_contents: maximum number of contents to fetch per request
    :param user: Confluence user name. It is required for Confluence Cloud,
                 optional for Confluence Data Center and server editions 7.9 and later
    :param api_token: Confluence user's personal access token or api token
    """
    version = '0.15.0'

    CATEGORIES = [CATEGORY_HISTORICAL_CONTENT]

    def __init__(self, url, tag=None, archive=None, ssl_verify=True,
                 spaces=None, max_contents=MAX_CONTENTS,
                 user=None, api_token=None):
        origin = url

        super().__init__(origin, tag=tag, archive=archive, ssl_verify=ssl_verify)
        self.url = url
        self.client = None
        self.spaces = spaces
        self.max_contents = max_contents
        self.user = user
        self.api_token = api_token

    def search_fields(self, item):
        """Add search fields to an item.

        It adds the values of `metadata_id` plus the page ancestor IDs,
        the content ID and the content version number.

        :param item: the item to extract the search fields values

        :returns: a dict of search fields
        """
        search_fields = {
            DEFAULT_SEARCH_FIELD: self.metadata_id(item),
            SEARCH_ANCESTOR_IDS: None,
            SEARCH_CONTENT_ID: None,
            SEARCH_CONTENT_VERSION_NUMBER: None
        }

        ancestors_ids = []

        ancestors = item.get('ancestors', None)
        if ancestors:
            for ancestor in ancestors:
                if 'id' in ancestor:
                    ancestors_ids.append(ancestor['id'])

        search_fields[SEARCH_ANCESTOR_IDS] = ancestors_ids
        search_fields[SEARCH_CONTENT_ID] = item['id']
        search_fields[SEARCH_CONTENT_VERSION_NUMBER] = item['version']['number']

        return search_fields

    def fetch(self, category=CATEGORY_HISTORICAL_CONTENT,
              from_date=DEFAULT_DATETIME,
              max_contents=MAX_CONTENTS):
        """Fetch the contents by version from the server.

        This method fetches the different historical versions (or
        snapshots) of the contents stored in the server that were
        updated since the given date. Only those snapshots created
        or updated after `from_date` will be returned.

        Take into account that the seconds of `from_date` parameter will
        be ignored because the Confluence REST API only accepts the date
        and hours and minutes for timestamps values.

        :param category: the category of items to fetch
        :param from_date: obtain historical versions of contents updated
            since this date
        :param max_contents: maximum number of contents to fetch per request

        :returns: a generator of historical versions
        """
        if not from_date:
            from_date = DEFAULT_DATETIME

        from_date = datetime_to_utc(from_date)

        kwargs = {
            'from_date': from_date,
            'max_contents': max_contents
        }

        items = super().fetch(category, **kwargs)

        return items

    def fetch_items(self, category, **kwargs):
        """Fetch the contents

        :param category: the category of items to fetch
        :param kwargs: backend arguments

        :returns: a generator of items
        """

        from_date = kwargs.get('from_date', DEFAULT_DATETIME)
        max_contents = kwargs.get('max_contents', MAX_CONTENTS)

        logger.info("Fetching historical contents of '%s' from %s max contents per query %s",
                    self.url, str(from_date), str(max_contents))

        nhcs = 0

        contents = self.__fetch_contents_summary(from_date, max_contents)
        contents = [content for content in contents]

        for content in contents:
            cid = content['id']
            content_url = urijoin(self.origin, content['_links']['webui'])

            hcs = self.__fetch_historical_contents(cid, from_date)

            for hc in hcs:
                hc['content_url'] = content_url
                hc['ancestors'] = content.get('ancestors', [])

                yield hc
                nhcs += 1

        logger.info("Fetch process completed: %s historical contents fetched",
                    nhcs)

    @classmethod
    def has_archiving(cls):
        """Returns whether it supports archiving items on the fetch process.

        :returns: this backend supports items archive
        """
        return True

    @classmethod
    def has_resuming(cls):
        """Returns whether it supports to resume the fetch process.

        :returns: this backend supports items resuming
        """
        return True

    @staticmethod
    def metadata_id(item):
        """Extracts the identifier from a Confluence item.

        This identifier will be the mix of two fields because a
        historical content does not have any unique identifier.
        In this case, 'id' and 'version' values are combined because
        it should not be possible to have two equal version numbers
        for the same content. The value to return will follow the
        pattern: <content>#v<version> (i.e 28979#v10).
        """
        cid = item['id']
        cversion = item['version']['number']

        return str(cid) + '#v' + str(cversion)

    @staticmethod
    def metadata_updated_on(item):
        """Extracts and coverts the update time from a Confluence item.

        The timestamp is extracted from 'when' field on 'version' section.
        This date is converted to UNIX timestamp format.

        :param item: item generated by the backend

        :returns: a UNIX timestamp
        """
        ts = item['version']['when']
        ts = str_to_datetime(ts)

        return ts.timestamp()

    @staticmethod
    def metadata_category(item):
        """Extracts the category from a Confluence item.

        This backend only generates one type of item which is
        'historical content'.
        """
        return CATEGORY_HISTORICAL_CONTENT

    @staticmethod
    def parse_contents_summary(raw_json):
        """Parse a Confluence summary JSON list.

        The method parses a JSON stream and returns an iterator
        of diccionaries. Each dictionary is a content summary.

        :param raw_json: JSON string to parse

        :returns: a generator of parsed content summaries.
        """
        summary = json.loads(raw_json)

        contents = summary['results']
        for c in contents:
            yield c

    @staticmethod
    def parse_historical_content(raw_json):
        """Parse a Confluence historical content JSON stream.

        This method parses a JSON stream and returns a dictionary
        that contains the data of a historical content.

        :param raw_json: JSON string to parse

        :returns: a dict with historical content
        """
        hc = json.loads(raw_json)
        return hc

    def _init_client(self, from_archive=False):
        """Init client"""

        return ConfluenceClient(self.url, archive=self.archive, from_archive=from_archive,
                                ssl_verify=self.ssl_verify, spaces=self.spaces,
                                max_contents=self.max_contents,
                                user=self.user, api_token=self.api_token)

    def __fetch_contents_summary(self, from_date, max_contents):
        logger.debug("Fetching contents summary from %s", str(from_date))
        for page in self.client.contents(from_date=from_date, max_contents=max_contents):
            for cs in self.parse_contents_summary(page):
                yield cs

    def __fetch_historical_contents(self, cid, from_date):
        logger.debug("Fetching historical contents of %s content", cid)

        fetching = True
        version = 1

        while fetching:
            logger.debug("Fetching and parsing historical content #%s for %s ",
                         str(version), cid)

            try:
                raw_hc = self.client.historical_content(cid, version)
            except requests.exceptions.HTTPError as e:
                code = e.response.status_code

                # Common problems found: removed and private contents
                if code not in (404, 500):
                    raise e

                logger.warning("Error retrieving content %s v#%s; skipping",
                               cid, version)
                logger.warning("Exception: %s", str(e))
                break

            hc = self.parse_historical_content(raw_hc)

            # if 'when' attribute is not present, the historical content is skipped
            if 'when' not in hc['version']:
                logger.debug("Content %s v%s skipped due to missing 'when' attribute",
                             hc['id'], str(hc['version']['number']))

                fetching = not hc['history']['latest']
                version += 1
                continue

            # Return those versions that were created after 'from_date'
            when = str_to_datetime(hc['version']['when'])
            if when >= from_date:
                yield hc
            else:
                logger.debug("Content %s v%s updated before %s; skipped",
                             hc['id'], str(hc['version']['number']), str(from_date))

            # Check whether it retrieved the latest version
            fetching = not hc['history']['latest']
            version += 1


class ConfluenceCommand(BackendCommand):
    """Class to run Confluence backend from the command line."""

    BACKEND = Confluence

    @classmethod
    def setup_cmd_parser(cls):
        """Returns the Bugzilla argument parser."""

        parser = BackendCommandArgumentParser(cls.BACKEND,
                                              from_date=True,
                                              basic_auth=True,
                                              token_auth=True,
                                              archive=True,
                                              ssl_verify=True)

        # Required arguments
        parser.parser.add_argument('url',
                                   help="URL of the Confluence server")
        # Optional arguments
        parser.parser.add_argument('--spaces', nargs='+',
                                   help="List of spaces to fetch")
        parser.parser.add_argument('--max-contents', dest='max_contents',
                                   type=int, default=MAX_CONTENTS,
                                   help="Maximum number of contents requested on the same query")

        return parser


class ConfluenceClient(HttpClient):
    """Confluence REST API client.

    This class implements a client to retrieve contents from a
    Confluence server using its REST API.

    :param base_url: URL of the Confluence server
    :param archive: an archive to store/read fetched data
    :param from_archive: it tells whether to write/read the archive
    :param ssl_verify: enable/disable SSL verification
    :param spaces: name of spaces to fetch, (default the entire instance)
    :param max_contents: maximum number of contents to fetch per request
    :param user: Confluence user name
    :param api_token: Confluence user's personal access token or api token
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
    PANCESTORS = 'ancestors'

    # Common values
    VCQL = "lastModified>='%(date)s' order by lastModified"
    VCQL_SPACE = "space in (%(spaces)s) and lastModified>='%(date)s' order by lastModified"
    VEXPAND = ['body.storage', 'history', 'version']
    VHISTORICAL = 'historical'

    def __init__(self, base_url, archive=None, from_archive=False, ssl_verify=True,
                 spaces=None, max_contents=MAX_CONTENTS,
                 user=None, api_token=None):
        auth_header = {}
        if api_token:
            if user is None:
                # Confluence Data Center and server editions 7.9 and later can use personal access tokens without a username
                # See https://confluence.atlassian.com/enterprise/using-personal-access-tokens-1026032365.html
                auth_header = {'Authorization': 'Bearer ' + api_token}
            else:
                # For Confluence Cloud, username and token are required
                # See https://support.atlassian.com/atlassian-account/docs/manage-api-tokens-for-your-atlassian-account/
                auth_encoded = base64.b64encode((user + ':' + api_token).encode('utf-8')).decode('utf-8')
                auth_header = {'Authorization': 'Basic ' + auth_encoded}

        super().__init__(base_url.rstrip('/'),
                         archive=archive,
                         from_archive=from_archive,
                         ssl_verify=ssl_verify,
                         extra_headers=auth_header)
        self.spaces = spaces
        self.max_contents = max_contents

    def contents(self, from_date=DEFAULT_DATETIME,
                 offset=None, max_contents=MAX_CONTENTS):
        """Get the contents of a repository.

        This method returns an iterator that manages the pagination
        over contents. Take into account that the seconds of `from_date`
        parameter will be ignored because the API only works with
        hours and minutes.

        :param from_date: fetch the contents updated since this date
        :param offset: fetch the contents starting from this offset
        :param max_contents: maximum number of contents to fetch per request
        """
        resource = self.RCONTENTS + '/' + self.MSEARCH

        # Set confluence query parameter (cql)
        date = from_date.strftime("%Y-%m-%d %H:%M")

        cql = self.VCQL % {'date': date}
        if self.spaces:
            spaces = ", ".join(self.spaces)
            cql = self.VCQL_SPACE % {'date': date, 'spaces': spaces}

        # Set parameters
        params = {
            self.PCQL: cql,
            self.PLIMIT: max_contents,
            self.PEXPAND: self.PANCESTORS
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
            self.PVERSION: version,
            self.PSTATUS: self.VHISTORICAL,
            self.PEXPAND: ','.join(self.VEXPAND)
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
        url = self.URL % {'base': self.base_url, 'resource': resource}

        logger.debug("Confluence client requests: %s params: %s",
                     resource, str(params))

        while True:
            r = self.fetch(url, payload=params)
            yield r.text

            # Pagination is available when 'next' link exists
            j = r.json()
            if '_links' not in j:
                break
            if 'next' not in j['_links']:
                break

            url = urijoin(self.base_url, j['_links']['next'])
            params = {}
