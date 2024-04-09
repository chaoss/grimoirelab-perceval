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
#     Alvaro del Castillo <acs@bitergia.com>
#     Valerio Cosentino <valcos@bitergia.com>
#     Jesus M. Gonzalez-Barahona <jgb@gsyc.es>
#     Harshal Mittal <harshalmittal4@gmail.com>
#

import json
import logging

import dateutil

from grimoirelab_toolkit.datetime import (datetime_to_utc,
                                          datetime_utcnow,
                                          str_to_datetime)
from grimoirelab_toolkit.uris import urijoin

from ...backend import (Backend,
                        BackendCommand,
                        BackendCommandArgumentParser)
from ...client import HttpClient
from ...errors import BackendError
from ...utils import DEFAULT_DATETIME

CATEGORY_PAGE = 'page'

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
    :param archive: archive to store/retrieve items
    :param ssl_verify: enable/disable SSL verification
    """
    version = '1.0.0'

    CATEGORIES = [CATEGORY_PAGE]

    def __init__(self, url, tag=None, archive=None, ssl_verify=True):
        origin = url

        super().__init__(origin, tag=tag, archive=archive, ssl_verify=ssl_verify)
        self.url = url
        self.client = None

    def fetch(self, category=CATEGORY_PAGE, from_date=DEFAULT_DATETIME, reviews_api=False):
        """Fetch the pages from the backend url.

        The method retrieves, from a MediaWiki url, the
        wiki pages.

        :param category: the category of items to fetch
        :param from_date: obtain pages updated since this date
        :param reviews_api: use the reviews API available in MediaWiki >= 1.27

        :returns: a generator of pages
        """
        if from_date == DEFAULT_DATETIME:
            from_date = None
        else:
            from_date = datetime_to_utc(from_date)

        kwargs = {"from_date": from_date, "reviews_api": reviews_api}
        items = super().fetch(category, **kwargs)

        return items

    def fetch_items(self, category, **kwargs):
        """Fetch the pages

        :param category: the category of items to fetch
        :param kwargs: backend arguments

        :returns: a generator of items
        """
        from_date = kwargs['from_date']
        reviews_api = kwargs['reviews_api']

        mediawiki_version = self.client.get_version()
        logger.info("MediaWiki version: %s", mediawiki_version)

        if reviews_api:
            if (mediawiki_version[0] == 1 and mediawiki_version[1] >= 27) or mediawiki_version[0] > 1:
                fetcher = self.__fetch_1_27(from_date)
            else:
                logger.warning("Reviews API only available in MediaWiki >= 1.27")
                logger.warning("Using the Pages API instead")
                fetcher = self.__fetch_pre1_27(from_date)
        else:
            fetcher = self.__fetch_pre1_27(from_date)

        for page_reviews in fetcher:
            yield page_reviews

    @classmethod
    def has_archiving(cls):
        """Returns whether it supports archiving items on the fetch process.

        :returns: this backend supports items archive
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
        return CATEGORY_PAGE

    def _init_client(self, from_archive=False):
        """Init client"""

        return MediaWikiClient(self.url, self.archive, from_archive, self.ssl_verify)

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

        npages = 0  # number of pages processed
        tpages = 0  # number of total pages
        pages_done = []  # pages already retrieved in reviews API

        namespaces_contents = self.__get_namespaces_contents()

        arvcontinue = ''  # pagination for getting revisions and their pages
        while arvcontinue is not None:
            raw_pages = self.client.get_pages_from_allrevisions(namespaces_contents, from_date, arvcontinue)
            data_json = json.loads(raw_pages)
            arvcontinue = data_json['continue']['arvcontinue'] if 'continue' in data_json else None
            pages_json = data_json['query']['allrevisions']
            for page in pages_json:

                if page['pageid'] in pages_done:
                    logger.debug("Page %s already processed; skipped", page['pageid'])
                    continue

                tpages += 1
                pages_done.append(page['pageid'])
                page_reviews = self.__get_page_reviews(page)

                if not page_reviews:
                    logger.warning("Revisions not found in %s [page id: %s], page skipped",
                                   page['title'], page['pageid'])
                    continue

                yield page_reviews
                npages += 1

        logger.info("Total number of pages: %i, skipped %i", tpages, tpages - npages)

    def __get_page_reviews(self, page):
        revisions_raw = self.client.get_revisions(page['pageid'])
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
            tpages = 0  # number of total pages
            pages_done = []  # pages already retrieved in reviews API

            rccontinue = ''
            hole_created = True  # To detect that incremental is not complete
            while rccontinue is not None:
                raw_pages = self.client.get_recent_pages(namespaces_contents, rccontinue)
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
                    if from_date >= page_ts:
                        # The rest of recent changes are older than from_date
                        logger.debug("All recent changes newer than %s processed.", from_date)
                        rccontinue = None
                        hole_created = False
                        break

                    if 'pageid' not in page:
                        logger.warning("Missing pageid in page %s; skipped", page)
                        continue

                    if page['pageid'] in pages_done:
                        logger.debug("Page %s already processed; skipped", page['pageid'])
                        continue

                    tpages += 1
                    pages_done.append(page['pageid'])
                    page_reviews = self.__get_page_reviews(page)

                    if not page_reviews:
                        logger.warning("Revisions not found in %s [page id: %s], page skipped",
                                       page['title'], page['pageid'])
                        continue

                    yield page_reviews
                    npages += 1
            if hole_created:
                logger.error("Incremental update NOT completed. Hole in history created.")
            logger.info("Total number of pages: %i, skipped %i", tpages, tpages - npages)

        def fetch_all_pages(namespaces_contents):
            # Use get all pages API to get pages
            npages = 0  # number of pages processed
            tpages = 0  # number of total pages
            pages_done = []  # pages already retrieved in reviews API

            for ns in namespaces_contents:
                apcontinue = ''  # pagination for getting pages
                logger.debug("Getting pages for namespace: %s", ns)
                while apcontinue is not None:
                    raw_pages = self.client.get_pages(ns, apcontinue)
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

                        if page['pageid'] in pages_done:
                            logger.debug("Page %s already processed; skipped", page['pageid'])
                            continue

                        tpages += 1
                        pages_done.append(page['pageid'])
                        page_reviews = self.__get_page_reviews(page)

                        if not page_reviews:
                            logger.warning("Revisions not found in %s [page id: %s], page skipped",
                                           page['title'], page['pageid'])
                            continue

                        yield page_reviews
                        npages += 1
            logger.info("Total number of pages: %i, skipped %i", tpages, tpages - npages)

        logger.info("Looking for pages at url '%s'", self.url)

        # from_date can not be older than MAX_RECENT_DAYS days ago
        if from_date:
            if (datetime_utcnow() - from_date).days >= MAX_RECENT_DAYS:
                cause = "Can't get incremental pages older than %i days." % MAX_RECENT_DAYS
                cause += " Do a complete analysis without from_date for older changes."
                raise BackendError(cause=cause)

        namespaces_contents = self.__get_namespaces_contents()

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
                page = None
        else:
            logger.warning("Revisions not found in %s [page id: %s], page skipped",
                           page['title'], page['pageid'])
            page = None
        return page


class MediaWikiClient(HttpClient):
    """MediaWiki API client.

    This class implements a simple client to retrieve pages from
    projects in a MediaWiki node.

    :param url: URL of mediawiki site: https://wiki.mozilla.org
    :param archive: an archive to store/retrieved the fetched data
    :param from_archive: define whether the archive is used to store/read data
    :param ssl_verify: enable/disable SSL verification

    :raises HTTPError: when an error occurs doing the request
    """
    # Resource parameters
    PACTION = "action"
    PMETA = "meta"
    PSIPROP = "siprop"
    PFORMAT = "format"
    PLIST = "list"
    PAP_LIMIT = "aplimit"
    PAP_NAMESPACE = "apnamespace"
    PAP_CONTINUE = "apcontinue"
    PRC_LIMIT = "rclimit"
    PRC_NAMESPACE = "rcnamespace"
    PRC_PROP = "rcprop"
    PRC_CONTINUE = "rccontinue"
    PPROP = "prop"
    PPAGE_IDS = "pageids"
    PRV_DIR = "rvdir"
    PRV_LIMIT = "rvlimit"
    PRV_START = "rvstart"
    PARV_NAMESPACE = "arvnamespace"
    PARV_DIR = "arvdir"
    PARV_LIMIT = "arvlimit"
    PARV_PROP = "arvprop"
    PARV_CONTINUE = "arvcontinue"
    PARV_START = "arvstart"

    # Predefined values
    VQUERY = "query"
    VSITE_INFO = "siteinfo"
    VNAMESPACES = "namespaces"
    VJSON = "json"
    VALL_PAGES = "allpages"
    VRECENT_CHANGES = "recentchanges"
    VRC_PROP = "title|timestamp|ids"
    VREVISIONS = "revisions"
    VNEWER = "newer"
    VALL_REVISIONS = "allrevisions"
    VIDS = "ids"

    def __init__(self, url, archive=None, from_archive=False, ssl_verify=True):
        super().__init__(urijoin(url, "api.php"), archive=archive, from_archive=from_archive, ssl_verify=ssl_verify)
        self.limit = "max"  # Always get the max number of items

    def call(self, params):
        """Run an API command.
        :param cgi: cgi command to run on the server
        :param params: dict with the HTTP parameters needed to run
            the given command
        """
        logger.debug("MediaWiki client calls API: %s params: %s",
                     self.base_url, str(params))

        req = self.fetch(self.base_url, payload=params)
        return req.text

    def get_namespaces(self):
        """ Retrieve all contents namespaces."""

        params = {
            self.PACTION: self.VQUERY,
            self.PMETA: self.VSITE_INFO,
            self.PSIPROP: self.VNAMESPACES,
            self.PFORMAT: self.VJSON
        }

        return self.call(params)

    def get_version(self):
        params = {
            self.PACTION: self.VQUERY,
            self.PMETA: self.VSITE_INFO,
            self.PFORMAT: self.VJSON
        }

        try:
            res = self.call(params)
            siteinfo = json.loads(res)
            siteinfo = siteinfo["query"]["general"]
        except Exception as ex:
            logger.error(ex)
            cause = "Wrong MediaWiki API: " + self.base_url
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
            self.PACTION: self.VQUERY,
            self.PLIST: self.VALL_PAGES,
            self.PAP_LIMIT: self.limit,
            self.PAP_NAMESPACE: namespace,
            self.PFORMAT: self.VJSON
        }
        if apcontinue:
            params[self.PAP_CONTINUE] = apcontinue

        return self.call(params)

    def get_recent_pages(self, namespaces, rccontinue=''):
        """Retrieve recent pages from all namespaces starting from rccontinue."""

        namespaces.sort()
        params = {
            self.PACTION: self.VQUERY,
            self.PLIST: self.VRECENT_CHANGES,
            self.PRC_LIMIT: self.limit,
            self.PRC_NAMESPACE: "|".join(namespaces),
            self.PRC_PROP: self.VRC_PROP,
            self.PFORMAT: self.VJSON
        }
        if rccontinue:
            params[self.PRC_CONTINUE] = rccontinue

        return self.call(params)

    def get_revisions(self, pageid, last_date=None):
        # TODO: Iterate if more than self.max reviews (500)

        if last_date:
            last_date_str = last_date.isoformat()

        params = {
            self.PACTION: self.VQUERY,
            self.PPROP: self.VREVISIONS,
            self.PPAGE_IDS: pageid,
            self.PRV_DIR: self.VNEWER,
            self.PRV_LIMIT: self.limit,
            self.PFORMAT: self.VJSON
        }
        if last_date:
            params[self.PRV_START] = last_date_str

        return self.call(params)

    def get_pages_from_allrevisions(self, namespaces, from_date=None, arvcontinue=None):

        if from_date:
            if from_date.tzinfo != dateutil.tz.tzutc():
                raise ValueError("Datetime is not in UTC timezone")

            from_date_str = from_date.strftime("%Y-%m-%dT%H:%M:%SZ")

        namespaces.sort()
        params = {
            self.PACTION: self.VQUERY,
            self.PLIST: self.VALL_REVISIONS,
            self.PARV_NAMESPACE: "|".join(namespaces),
            self.PARV_DIR: self.VNEWER,
            self.PARV_LIMIT: self.limit,
            self.PARV_PROP: self.VIDS,
            self.PFORMAT: self.VJSON
        }

        if arvcontinue:
            params[self.PARV_CONTINUE] = arvcontinue
        else:
            if from_date:
                params[self.PARV_START] = from_date_str

        return self.call(params)


class MediaWikiCommand(BackendCommand):
    """Class to run MediaWiki backend from the command line."""

    BACKEND = MediaWiki

    @classmethod
    def setup_cmd_parser(cls):
        """Returns the MediaWiki argument parser."""

        parser = BackendCommandArgumentParser(cls.BACKEND,
                                              from_date=True,
                                              archive=True,
                                              ssl_verify=True)

        # MediaWiki options
        group = parser.parser.add_argument_group('MediaWiki arguments')
        group.add_argument('--reviews-api', action='store_true',
                           help="Use the experimental Reviews API in MediaWiki >= 1.27")

        # Required arguments
        parser.parser.add_argument('url',
                                   help="URL of the MediaWiki server")

        return parser
