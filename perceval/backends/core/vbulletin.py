# -*- coding: utf-8 -*-
#
# Copyright (C) 2016-2017 Bitergia
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
#    Stuart Langridge <sil@kryogenix.org>
#

import json
import logging
import platform
import uuid
import urllib
import hashlib
import copy

import requests

from ...backend import (Backend,
                        BackendCommand,
                        BackendCommandArgumentParser,
                        metadata)
from ...errors import CacheError
from ...utils import (DEFAULT_DATETIME,
                      datetime_to_utc,
                      str_to_datetime,
                      urljoin)


logger = logging.getLogger(__name__)


class vBulletin(Backend):
    """vBulletin backend for Perceval.

    This class retrieves the forums threaded in a vBulletin board.
    To initialize this class the URL must be provided. The `url`
    will be set as the origin of the data.

    :param url: vBulletin forum URL
    :param tag: label used to mark the data
    :param cache: cache object to store raw data
    """
    version = '0.1.0'

    def __init__(self, url, api_token=None, tag=None, cache=None):
        origin = url

        super().__init__(origin, tag=tag, cache=cache)
        self.url = url
        self.client = vBulletinClient(url, self.version, api_key=api_token)

    @metadata
    def fetch(self, from_date=DEFAULT_DATETIME):
        """Fetch the threads from the vBulletin board.

        The method retrieves from a vBulletin board the threads
        updated since the given date.

        :param from_date: obtain threads updated since this date

        :returns: a generator of threads
        """
        if not from_date:
            from_date = DEFAULT_DATETIME
        else:
            from_date = datetime_to_utc(from_date)

        logger.info("Looking for forums at '%s', updated from '%s'",
                    self.url, str(from_date))

        # this is complicated by sub-forums; we can't get a list of all forums, so we get a list of
        # all _toplevel_ forums, and then as we process each one we find out about its subforums and
        # add them to the list to process
        toplevel = self.client.forums_page()
        forum_ids_to_fetch = self._get_forum_ids_from_forumbits(json.loads(toplevel)["response"]["forumbits"])
        forums_yielded = set([])

        while forum_ids_to_fetch:
            next_forum_id = forum_ids_to_fetch.pop()
            if next_forum_id in forums_yielded: continue
            details = self.client.forum(next_forum_id)
            threadlist, new_forum_ids = self._parse_forum_details(details, from_date)
            forums_yielded.add(next_forum_id) # even if we don't actually do anything with it
            if threadlist:
                for t in threadlist:
                    yield t

    def _parse_forum_details(self, details, from_date):
        d = json.loads(details)
        response = d.get("response")
        if not response: return (None, [])
        sub_forumbits = response.get("forumbits")
        if sub_forumbits:
            sub_forumids = self._get_forum_ids_from_forumbits(sub_forumbits)
        else:
            sub_forumids = []
        threadbits = response.get("threadbits")
        foruminfo = response.get("foruminfo")
        if foruminfo and threadbits:
            threads = [
                x["thread"] for x in threadbits
            ]
            qualifying_threads = []
            for t in threads:
                ts = "%s %s" % (t['lastpostdate'], t['lastposttime'])
                ts = str_to_datetime(ts)
                if ts.timestamp() > from_date.timestamp():
                    t["timestamp"] = ts.timestamp()
                    qualifying_threads.append(t)
            if qualifying_threads:
                threadlist = sorted(qualifying_threads, key=lambda x: x["timestamp"])
                for t in threadlist: t["forum"] = foruminfo
                return (threadlist, sub_forumids)

        return (None, sub_forumids)

    def _get_forum_ids_from_forumbits(self, forumbits):
        ids = []
        if (type(forumbits) != list):
            logger.debug("weird, forumbits is unexpectedly not a list", forumbits)
            return []
        for f in forumbits:
            ff = f.get("forum")
            if ff:
                fid = ff.get("forumid")
                if fid:
                    ids.append(fid)
            childff = f.get("childforumbits")
            if childff:
                ids += self._get_forum_ids_from_forumbits(childff)
        return ids

    @classmethod
    def has_caching(cls):
        """Returns whether it supports caching items on the fetch process.

        :returns: this backend supports items cache
        """
        return False

    @classmethod
    def has_resuming(cls):
        """Returns whether it supports to resume the fetch process.

        :returns: this backend supports items resuming
        """
        return False

    @staticmethod
    def metadata_id(item):
        """Extracts the identifier from a vBulletin forum."""

        return str(item['threadid'])

    @staticmethod
    def metadata_updated_on(item):
        """Extracts the update time from a vBulletin item.

        The timestamp used is extracted from 'last_threaded_at' field.
        This date is converted to UNIX timestamp format taking into
        account the timezone of the date.

        :param item: item generated by the backend

        :returns: a UNIX timestamp
        """
        return item.get("timestamp", 0)

    @staticmethod
    def metadata_category(item):
        """Extracts the category from a vBulletin item.

        This backend only generates one type of item which is
        'forum'.
        """
        return 'forum'


class vBulletinClient:
    """vBulletin API client.

    This class implements a simple client to retrieve forums from
    any vBulletin board, using the vBulletin API as documented at
    https://www.vbulletin.com/forum/articles/programming-documentation/mobile-api.

    :param url: URL of the vBulletin site

    :raises HTTPError: when an error occurs doing the request
    """

    def __init__(self, url, version, api_key):
        self.url = url
        self.apiaccesstoken = None
        self.apiclientid = None
        self.secret = None
        self.api_key = api_key
        self.version = version

    def forums_page(self, page=1):
        """Retrieve the #page summaries of the latest forums.

        :param page: number of page to retrieve
        """
        logging.debug("forums_page: page=%s", page)
        params = {
            "pagenumber": page
        }

        # http://example.com/latest.json
        response = self._call("forum", params=params)

        return response

    def forum(self, forum_id):
        """Retrive the forum with `forum_id` identifier.

        :param forum_id: identifier of the forum to retrieve
        """
        params = {
            "forumid": forum_id
        }

        response = self._call("forumdisplay", params=params)

        return response

    def _register(self):
        """Register with the API.

        Required to be called before anything else to get access tokens.
        """

        params = {
            "clientname": "Perceval vBulletin client",
            "clientversion": self.version,
            "platformname": platform.system(),
            "platformversion": platform.release(),
            "uniqueid": uuid.uuid4()
        }
        api_init = json.loads(self._call("api_init", params, initing=True))
        self.apiaccesstoken = api_init["apiaccesstoken"]
        self.apiclientid = api_init["apiclientid"]
        self.secret = api_init["secret"]

    def _get_request_signature(self, params):
        """Return params to sign an API request.

        Signing as per https://www.vbulletin.com/forum/articles/
        programming-documentation/mobile-api/4023442-api-overview
        involves adding the following parameters to the request:

        api_m = method name (this is already there)
        api_c = ClientID.
        api_s = Access token.
        api_sig = signature of the request
        api_v = the api version called by the request

        Signature is calculated thus:
            signstr is the querystring of the request, with
            parameters in alphabetical order
            (so a=1&api_m=whatever&b=1&...)
            signature is md5(signstr + accesstoken + clientid + secret + API key)
        """

        sorted_params = sorted(params.items())
        signstr = urllib.parse.urlencode(sorted_params)
        tosign = "%s%s%s%s%s" % (signstr, self.apiaccesstoken,
            self.apiclientid, self.secret, self.api_key)
        #logger.debug("tosign: %s", tosign)
        signature = hashlib.md5(tosign.encode("utf-8")).hexdigest()
        return {
            "api_c": self.apiclientid,
            "api_s": self.apiaccesstoken,
            "api_sig": signature,
            "api_v": 1
        }

    def _call(self, method, params, initing=False):
        """Run an API command.

        :param method: the API method to call
        :param params: dict with the HTTP parameters needed to run
            the given command
        """

        if not self.apiaccesstoken:
            if not initing:
                self._register()

        url = "%s/%s" % (self.url, "api.php")
        all_params = {"api_m": method}
        all_params.update(params)

        if not initing:
            all_params.update(self._get_request_signature(all_params))

        #logger.debug("vBulletin client calls method: %s with params: %s",
        #             method, str(params))

        r = requests.get(url, params=all_params)
        r.raise_for_status()

        #logger.debug("vBulletin client returns %s", r.text)
        return r.text


class vBulletinCommand(BackendCommand):
    """Class to run Discourse backend from the command line."""

    BACKEND = vBulletin

    @staticmethod
    def setup_cmd_parser():
        """Returns the vBulletin argument parser."""

        parser = BackendCommandArgumentParser(from_date=True,
                                              token_auth=True,
                                              cache=True)

        # Required arguments
        parser.parser.add_argument('url',
                                   help="URL of the vBulletin server")

        return parser
