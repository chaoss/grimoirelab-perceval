# -*- coding: utf-8 -*-
#
# Copyright (C) 2016 Bitergia
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
#     Alvaro del Castillo <acs@bitergia.com>
#

import datetime
import json
import logging
import os.path

import dateutil
import requests

from ..backend import Backend, BackendCommand, metadata
from ..cache import Cache
from ..errors import BackendError, CacheError
from ..utils import (DEFAULT_DATETIME,
                     datetime_to_utc,
                     str_to_datetime,
                     datetime_to_utc,
                     urljoin)


logger = logging.getLogger(__name__)

MAX_RECENT_DAYS = 30  # max number of days included in MediaWiki recent changes


class MediaWiki(Backend):
    """MediaWiki backend for Perceval.

    This class retrieves the wiki pages and edits from a  MediaWiki site.
    To initialize this class the URL must be provided. The origin
    of the data will be set to this URL.

    It uses different APIs to support pre and post 1.27 MediaWiki versions.
    The pre 1.27 approach performance is better but it needs different
    logic for full an incremental retrieval.

    In pre 1.27 the incremental approach uses the recent changes API which just
    covers MAX_RECENT_DAYS. If the from_date used is older, all the pages must
    be retrieved and the consumer of the items must filter itself.

    Both approach return a common format: a page with all its revisions. It
    is different how the pages list is generated.

    The page and revisions data downloaded are the standard. More data could
    be gathered using additional properties.

    Deleted pages are not analyzed.

    :param url: MediaWiki url
    :param tag: label used to mark the data
    :param cache: cache object to store raw data
    """
    version = '0.5.0'

    def __init__(self, url, tag=None, cache=None):
        origin = url

        super().__init__(origin, tag=tag, cache=cache)
        self.url = url
        self.client = MediaWikiClient(url)
        self._test_mode = False

    @metadata
    def fetch(self, from_date=DEFAULT_DATETIME, reviews_api=False):
        """Fetch the pages from the backend url.

        The method retrieves, from a MediaWiki url, the
        wiki pages.

        :param reviews_api: use the reviews API available in MediaWiki >= 1.27


        :returns: a generator of pages
        """

        self._purge_cache_queue()

        if from_date == DEFAULT_DATETIME:
            from_date = None
        else:
            from_date = datetime_to_utc(from_date)

        mediawiki_version = self.client.get_version()
        logger.info("MediaWiki version: %s", mediawiki_version)
        self._push_cache_queue(json.dumps({"reviews_api":reviews_api}))
        self._flush_cache_queue()

        if reviews_api:
            if (mediawiki_version[0] == 1 and mediawiki_version[1] >= 27) or \
                mediawiki_version[0] > 1:
                fetcher = self.__fetch_1_27(from_date)
            else:
                logger.warning("Reviews API only available in MediaWiki >= 1.27")
                logger.warning("Using the Pages API instead")
                fetcher = self.__fetch_pre1_27(from_date)
        else:
            fetcher = self.__fetch_pre1_27(from_date)

        for page_reviews in fetcher:
            yield page_reviews

    @metadata
    def fetch_from_cache(self):
        """Fetch the pages from the cache.

        :returns: a generator of pages

        :raises CacheError: raised when an error occurs accessing the
            cache
        """
        if not self.cache:
            raise CacheError(cause="cache instance was not provided")

        cache_items = self.cache.retrieve()

        pages_dicts = ['allrevisions', 'allpages', 'recentchanges']
        pages_done = []  # pages already retrieved in reviews API
        reviews_api_json = json.loads(next(cache_items))
        if 'reviews_api' not in reviews_api_json:
            raise CacheError(cause="reviews_api not found at cache file start.")
        reviews_api = reviews_api_json['reviews_api']

        # pages -> revisions
        for items in cache_items:
            data_json = json.loads(items)
            if 'reviews_api' in data_json:
                # New perceval execution
                reviews_api = data_json['reviews_api']
                pages_done = []
                continue
            for pages_dict in pages_dicts:
                if pages_dict in data_json['query']:
                    pages_json = data_json['query'][pages_dict]
                    for page in pages_json:
                        if reviews_api:
                            if page['pageid'] in pages_done:
                                # The page was already returned for previous revisions
                                continue
                            pages_done.append(page['pageid'])
                        page_reviews = self.__build_page_reviews(page, json.loads(next(cache_items)))
                        if not page_reviews:
                            continue
                        yield page_reviews

    @classmethod
    def has_caching(cls):
        """Returns whether it supports caching items on the fetch process.

        :returns: this backend supports items cache
        """
        return True

    @classmethod
    def has_resuming(cls):
        """Returns whether it supports to resume the fetch process.

        :returns: this backend does not support items resuming
        """
        return False

    @staticmethod
    def metadata_id(item):
        """Extracts the identifier from a MediaWiki page."""
        return str(item['pageid'])

    @staticmethod
    def metadata_updated_on(item):
        """Extracts the update field from a MediaWiki item.

        The timestamp is extracted from 'update' field.
        This date is a UNIX timestamp but needs to be converted to
        a float value.

        :param item: item generated by the backend

        :returns: a UNIX timestamp
        """
        return float(item['update'])

    @staticmethod
    def metadata_category(item):
        """Extracts the category from a MediaWiki item.

        This backend only generates one type of item which is
        'page'.
        """
        return 'page'

    def __get_max_date(self, reviews):
        """"Get the max date in unixtime format from reviews."""
        max_ts = 0
        for review in reviews:
            ts = str_to_datetime(review['timestamp'])
            ts = datetime_to_utc(ts)
            if ts.timestamp() > max_ts:
                max_ts = ts.timestamp()
        return max_ts


    def __get_namespaces_contents(self):
        # The pages are organized in namespaces of different types
        # Only contents namespaces are analyzed in this backend
        raw_namespaces = self.client.get_namespaces()
        namespaces = json.loads(raw_namespaces)["query"]["namespaces"]
        namespaces_contents = [ns for ns in namespaces if 'content' in namespaces[ns].keys()]

        return namespaces_contents

    def __fetch_1_27(self, from_date=None):
        """Fetch the pages from the backend url for MediaWiki >=1.27

        The method retrieves, from a MediaWiki url, the
        wiki pages.

        :returns: a generator of pages
        """

        logger.info("Looking for pages at url '%s'", self.url)

        self._purge_cache_queue()
        npages = 0  # number of pages processed
        pages_done = []  # pages already retrieved in reviews API

        namespaces_contents = self.__get_namespaces_contents()

        arvcontinue = '' # pagination for getting revisions and their pages
        while arvcontinue is not None:
            raw_pages = self.client.get_pages_from_allrevisions(namespaces_contents, from_date, arvcontinue)
            self._push_cache_queue(raw_pages)
            data_json = json.loads(raw_pages)
            if 'continue' in data_json:
                arvcontinue = data_json['continue']['arvcontinue']
            else:
                arvcontinue = None
            pages_json = data_json['query']['allrevisions']
            for page in pages_json:
                if page['pageid'] in pages_done:
                    # The page was already returned for previous revisions
                    continue
                pages_done.append(page['pageid'])
                yield self.__get_page_reviews(page)
                npages += 1
            self._flush_cache_queue()

        logger.info("Total number of pages: %i", npages)

    def __get_page_reviews(self, page):
        revisions_raw = self.client.get_revisions(page['title'])
        self._push_cache_queue(revisions_raw)
        self._flush_cache_queue()
        page_reviews = self.__build_page_reviews(page, json.loads(revisions_raw))
        return page_reviews

    def __fetch_pre1_27(self, from_date=None):
        """Fetch the pages from the backend url.

        The method retrieves, from a MediaWiki url, the
        wiki pages.

        :returns: a generator of pages
        """

        def fetch_incremental_changes(namespaces_contents):
            # Use recent changes API to get the pages from date
            npages = 0  # number of pages processed
            rccontinue = ''
            hole_created = True  # To detect that incremental is not complete
            while rccontinue is not None:
                raw_pages = self.client.get_recent_pages(namespaces_contents, rccontinue)
                self._push_cache_queue(raw_pages)
                self._flush_cache_queue()
                data_json = json.loads(raw_pages)
                if 'query-continue' in data_json:
                    # < 1.27
                    rccontinue = data_json['query-continue']['recentchanges']['rccontinue']
                elif 'continue' in data_json:
                    # >= 1.27
                    rccontinue = data_json['continue']['rccontinue']
                else:
                    rccontinue = None
                pages_json = data_json['query']['recentchanges']
                for page in pages_json:
                    page_ts = dateutil.parser.parse(page['timestamp'])
                    if  from_date >= page_ts:
                        # The rest of recent changes are older than from_date
                        logger.debug("All recent changes newer than %s processed.", from_date)
                        rccontinue = None
                        hole_created = False
                        break
                    page_reviews = self.__get_page_reviews(page)
                    if not page_reviews:
                        # Page without reviews are not managed
                        continue
                    yield page_reviews
                    npages += 1
            if hole_created:
                logger.error("Incremental update NOT completed. Hole in history created.")
            logger.info("Total number of pages: %i", npages)

        def fetch_all_pages(namespaces_contents):
            # Use get all pages API to get pages
            npages = 0  # number of pages processed

            for ns in namespaces_contents:
                apcontinue = '' # pagination for getting pages
                logger.debug("Getting pages for namespace: %s", ns)
                while apcontinue is not None:
                    raw_pages = self.client.get_pages(ns, apcontinue)
                    self._push_cache_queue(raw_pages)
                    self._flush_cache_queue()
                    data_json = json.loads(raw_pages)
                    if 'query-continue' in data_json:
                        # < 1.27
                        apcontinue = data_json['query-continue']['allpages']['apcontinue']
                    elif 'continue' in data_json:
                        # >= 1.27
                        apcontinue = data_json['continue']['apcontinue']
                    else:
                        apcontinue = None
                    pages_json = data_json['query']['allpages']
                    for page in pages_json:
                        yield self.__get_page_reviews(page)
                        npages += 1
            logger.info("Total number of pages: %i", npages)

        logger.info("Looking for pages at url '%s'", self.url)

        # from_date can not be older than MAX_RECENT_DAYS days ago
        if from_date:
            if self._test_mode:
                logger.warning("Test mode active; MAX_RECENT_DAYS limit ignored")
            elif (datetime.datetime.now(dateutil.tz.tzlocal()) - from_date).days >= MAX_RECENT_DAYS:
                cause = "Can't get incremental pages older than %i days." % MAX_RECENT_DAYS
                cause += " Do a complete analysis without from_date for older changes."
                raise BackendError(cause=cause)

        self._purge_cache_queue()

        namespaces_contents= self.__get_namespaces_contents()

        if not from_date:
            return fetch_all_pages(namespaces_contents)
        else:
            return fetch_incremental_changes(namespaces_contents)

    def __build_page_reviews(self, page, reviews):
        page['revisions'] = None
        page['update'] = None
        if str(page["pageid"]) in reviews["query"]["pages"]:
            reviews_json = reviews["query"]["pages"][str(page["pageid"])]
            if 'revisions' in reviews_json:
                page["revisions"] = reviews_json['revisions']
                page['update'] = self.__get_max_date(page['revisions'])
        else:
            logger.error("Revisions not found in %s", reviews["query"]["pages"])
            logger.error("for page: %s", page)
            page = None
        return page


class MediaWikiClient:
    """MediaWiki API client.

    This class implements a simple client to retrieve pages from
    projects in a MediaWiki node.

    :param url: URL of mediawiki site: https://wiki.mozilla.org

    :raises HTTPError: when an error occurs doing the request
    """

    def __init__(self, url):
        self.url = url
        self.api_url = urljoin(self.url, "api.php")
        self.limit = "max"  # Always get the max number of items

    def call(self, params):
        """Run an API command.
        :param cgi: cgi command to run on the server
        :param params: dict with the HTTP parameters needed to run
            the given command
        """
        logger.debug("MediaWiki client calls API: %s params: %s",
                     self.api_url, str(params))

        req = requests.get(self.api_url, params=params)
        req.raise_for_status()

        return req.text

    def get_namespaces(self):
        """ Retrieve all contents namespaces."""

        params = {
            "action":"query",
            "meta":"siteinfo",
            "siprop":"namespaces",
            "format":"json"
        }

        return self.call(params)

    def get_version(self):
        params = {
            "action":"query",
            "meta":"siteinfo",
            "format":"json"
        }

        try:
            res = self.call(params)
            siteinfo = json.loads(res)
            siteinfo = siteinfo["query"]["general"]
        except Exception:
            logger.error(res)
            cause = "Wrong MediaWiki API: " + self.url
            raise BackendError(cause=cause)

        version = siteinfo['generator']
        # MediaWiki 1.28.0-wmf.7, MediaWiki 1.19alpha
        version = version.split(" ")[1]  # Removes MediaWiki
        version_major = int(version.split(".")[0])
        version_minor = int(version.split(".")[1][0:2])

        return [version_major, version_minor]

    def get_pages(self, namespace, apcontinue=''):
        """Retrieve all pages from a namespace starting from apcontinue."""
        params = {
            "action":"query",
            "list":"allpages",
            "aplimit":self.limit,
            "apnamespace":namespace,
            "format":"json"
        }
        if apcontinue:
            params['apcontinue'] = apcontinue

        return self.call(params)

    def get_recent_pages(self, namespaces, rccontinue=''):
        """Retrieve recent pages from all namespaces starting from rccontinue."""

        params = {
            "action":"query",
            "list":"recentchanges",
            "rclimit":self.limit,
            "rcnamespace":"|".join(namespaces),
            "rcprop":"title|timestamp|ids",
            "format":"json"
        }
        if rccontinue:
            params['rccontinue'] = rccontinue


        return self.call(params)

    def get_revisions(self, title, last_date=None):
        # TODO: Iterate if more than self.max reviews (500)

        if last_date:
            last_date_str = last_date.isoformat()

        params = {
            "action":"query",
            "prop":"revisions",
            "titles":title,
            "rvdir":"newer",
            "rvlimit":self.limit,
            "format":"json"
        }
        if last_date:
            params['rvstart'] = last_date_str

        return self.call(params)

    def get_pages_from_allrevisions(self, namespaces, from_date=None, arvcontinue=None):

        if from_date:
            if from_date.tzinfo != dateutil.tz.tzutc():
                raise ValueError("Datetime is not in UTC timezone")

            from_date_str = from_date.strftime("%Y-%m-%dT%H:%M:%SZ")

        params = {
            "action":"query",
            "list":"allrevisions",
            "arvnamespace":"|".join(namespaces),
            "arvdir":"newer",
            "arvlimit":self.limit,
            "arvprop":"ids",
            "format":"json"
        }

        if arvcontinue:
            params['arvcontinue'] = arvcontinue
        else:
            if from_date:
                params['arvstart'] = from_date_str

        return self.call(params)


class MediaWikiCommand(BackendCommand):
    """Class to run MediaWiki backend from the command line."""

    def __init__(self, *args):
        super().__init__(*args)
        self.url = self.parsed_args.url
        self.from_date = str_to_datetime(self.parsed_args.from_date)
        self.tag = self.parsed_args.tag
        self.outfile = self.parsed_args.outfile
        self.reviews_api = self.parsed_args.reviews_api

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

        self.backend = MediaWiki(self.url, tag=self.tag, cache=cache)

    def run(self):
        """Fetch and print the pages and their revisions.

        This method runs the backend to fetch the wiki pages and revisions of a
        given url. Builds are converted to JSON objects and printed to the
        defined output.
        """
        if self.parsed_args.fetch_cache:
            pages = self.backend.fetch_from_cache()
        else:
            pages = self.backend.fetch(from_date=self.from_date,
                                       reviews_api=self.reviews_api)

        try:
            for build in pages:
                obj = json.dumps(build, indent=4, sort_keys=True)
                self.outfile.write(obj)
                self.outfile.write('\n')
        except requests.exceptions.HTTPError as e:
            raise requests.exceptions.HTTPError(str(e.response.json()))
        except IOError as e:
            raise RuntimeError(str(e))
        except Exception as e:
            if self.backend.cache:
                self.backend.cache.recover()
            raise RuntimeError(str(e))

    @classmethod
    def create_argument_parser(cls):
        """Returns the MediaWiki argument parser."""

        parser = super().create_argument_parser()

        # MediaWiki options
        group = parser.add_argument_group('MediaWiki arguments')

        group.add_argument("--reviews-api", action='store_true',
                           help="Use the experimental Reviews API in MediaWiki >= 1.27")


        # Required arguments
        group.add_argument('url', help="URL of the MediaWiki server")

        return parser
