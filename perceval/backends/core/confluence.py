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
import json
import os.path

import requests

from ...backend import Backend, BackendCommand, metadata
from ...cache import Cache
from ...errors import CacheError
from ...utils import (DEFAULT_DATETIME,
                      datetime_to_utc,
                      str_to_datetime,
                      urljoin)


logger = logging.getLogger(__name__)


MAX_CONTENTS = 200


class Confluence(Backend):
    """Confluence backend.

    This class allows the fetch the historical contents (content
    versions) stored on a Confluence server. Initialize this class
    passing the URL os this server. The `url` will be set as the
    origin of the data.

    :param url: URL of the server
    :param tag: label used to mark the data
    :param cache: cache object to store raw data
    """
    version = '0.4.0'

    def __init__(self, url, tag=None, cache=None):
        origin = url

        super().__init__(origin, tag=tag, cache=cache)
        self.url = url
        self.client = ConfluenceClient(url)

    @metadata
    def fetch(self, from_date=DEFAULT_DATETIME):
        """Fetch the contents by version from the server.

        This method fetches the different historical versions (or
        snapshots) of the contents stored in the server that were
        updated since the given date. Only those snapshots created
        or updated after `from_date` will be returned.

        Take into account that the seconds of `from_date` parameter will
        be ignored because the Confluence REST API only accepts the date
        and hours and minutes for timestamps values.

        :param from_date: obtain historical versions of contents updated
            since this date

        :returns: a generator of historical versions
        """
        logger.info("Fetching historical contents of '%s' from %s",
                    self.url, str(from_date))

        self._purge_cache_queue()

        from_date = datetime_to_utc(from_date)

        nhcs = 0

        contents = self.__fetch_contents_summary(from_date)
        cids = [content['id'] for content in contents]

        for cid in cids:
            hcs = self.__fetch_historical_contents(cid, from_date)

            for hc in hcs:
                yield hc
                nhcs += 1

            self._flush_cache_queue()

        logger.info("Fetch process completed: %s historical contents fetched",
                    nhcs)

    @metadata
    def fetch_from_cache(self):
        """Fetch historical contents from the cache.

        :returns: a generator of contents

        :raises CacheError: raised when an error occurs accessing the
            cache
        """
        if not self.cache:
            raise CacheError(cause="cache instance was not provided")

        logger.info("Retrieving cached historical contents: '%s'", self.url)

        cache_items = self.cache.retrieve()

        nhcs = 0

        for raw_json in cache_items:
            hc = self.parse_historical_content(raw_json)
            nhcs += 1
            yield hc

        logger.info("Retrieval process completed: %s historical contents retrieved from cache",
                    nhcs)

    def __fetch_contents_summary(self, from_date):
        logger.debug("Fetching contents summary from %s", str(from_date))
        for page in self.client.contents(from_date=from_date):
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

                # Common problems found: removed and privated contents
                if code not in (404, 500):
                    raise e

                logger.warning("Error retrieving content %s v#%s; skipping",
                               cid, version)
                logger.warning("Exception: %s", str(e))
                break

            hc = self.parse_historical_content(raw_hc)

            # Return those versions that were created after 'from_date'
            when = str_to_datetime(hc['version']['when'])

            if when >= from_date:
                self._push_cache_queue(raw_hc)
                yield hc
            else:
                logger.debug("Content %s v%s updated before %s; skipped",
                             hc['id'], str(hc['version']['number']), str(from_date))

            # Check whether it retrieved the latest version
            fetching = not hc['history']['latest']
            version += 1

    @classmethod
    def has_caching(cls):
        """Returns whether it supports caching items on the fetch process.

        :returns: this backend supports items cache
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
        return 'historical content'

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


class ConfluenceCommand(BackendCommand):
    """Class to run Confluence backend from the command line."""

    def __init__(self, *args):
        super().__init__(*args)

        self.url = self.parsed_args.url
        self.from_date = str_to_datetime(self.parsed_args.from_date)
        self.tag = self.parsed_args.tag
        self.outfile = self.parsed_args.outfile

        if not self.parsed_args.no_cache:
            if not self.parsed_args.cache_path:
                base_path = os.path.expanduser('~/.perceval/cache/')
            else:
                base_path = self.parsed_args.cache_path

            cache_path = os.path.join(base_path, self.url)

            cache = Cache(cache_path)

            if self.parsed_args.clean_cache:
                cache.clean()
            else:
                cache.backup()
        else:
            cache = None

        self.backend = Confluence(self.url,
                                  tag=self.tag,
                                  cache=cache)

    def run(self):
        """Fetch and print the contents.

        This method runs the backend to fetch the historical contents
        from the given repository. Contents are converted to JSON objects
        and printed to the defined output.
        """
        if self.parsed_args.fetch_cache:
            hcs = self.backend.fetch_from_cache()
        else:
            hcs = self.backend.fetch(from_date=self.from_date)

        try:
            for hc in hcs:
                obj = json.dumps(hc, indent=4, sort_keys=True)
                self.outfile.write(obj)
                self.outfile.write('\n')
        except IOError as e:
            raise RuntimeError(str(e))
        except Exception as e:
            if self.backend.cache:
                self.backend.cache.recover()
            raise RuntimeError(str(e))

    @classmethod
    def create_argument_parser(cls):
        """Returns the Confluence argument parser."""

        parser = super().create_argument_parser()

        # Required arguments
        parser.add_argument('url',
                            help="URL of the Confluence server")

        return parser


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
        self.base_url = base_url.rstrip('/')

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
