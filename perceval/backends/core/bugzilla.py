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
#     Alvaro del Castillo San Felix <acs@bitergia.com>
#     Stephan Barth <stephan.barth@gmail.com>
#     Valerio Cosentino <valcos@bitergia.com>
#     Jesus M. Gonzalez-Barahona <jgb@gsyc.es>
#     Harshal Mittal <harshalmittal4@gmail.com>
#

import csv
import datetime
import logging
import re

import bs4
import dateutil.tz

from grimoirelab_toolkit.datetime import str_to_datetime

from ...backend import (Backend,
                        BackendCommand,
                        BackendCommandArgumentParser)
from ...client import HttpClient
from ...errors import BackendError, ParseError
from ...utils import DEFAULT_DATETIME, xml_to_dict

CATEGORY_BUG = "bug"
MAX_BUGS = 200  # Maximum number of bugs per query
MAX_BUGS_CSV = 10000  # Maximum number of bugs per CSV query

logger = logging.getLogger(__name__)


class Bugzilla(Backend):
    """Bugzilla backend.

    This class allows the fetch the bugs stored in Bugzilla
    repository. To initialize this class the URL of the server
    must be provided. The `url` will be set as the origin of
    the data.

    :param url: Bugzilla server URL
    :param user: Bugzilla user
    :param password: Bugzilla user password
    :param max_bugs: maximum number of bugs requested on the same query
    :param tag: label used to mark the data
    :param archive: archive to store/retrieve items
    :param ssl_verify: enable/disable SSL verification
    """
    version = '0.12.0'

    CATEGORIES = [CATEGORY_BUG]
    EXTRA_SEARCH_FIELDS = {
        'product': ['product', 0, '__text__'],
        'component': ['component', 0, '__text__']
    }

    def __init__(self, url, user=None, password=None,
                 max_bugs=MAX_BUGS, max_bugs_csv=MAX_BUGS_CSV,
                 tag=None, archive=None, ssl_verify=True):
        origin = url

        super().__init__(origin, tag=tag, archive=archive, ssl_verify=ssl_verify)
        self.url = url
        self.user = user
        self.password = password
        self.max_bugs_csv = max_bugs_csv
        self.client = None
        self.max_bugs = max(1, max_bugs)

    def fetch(self, category=CATEGORY_BUG, from_date=DEFAULT_DATETIME):
        """Fetch the bugs from the repository.

        The method retrieves, from a Bugzilla repository, the bugs
        updated since the given date.

        :param category: the category of items to fetch
        :param from_date: obtain bugs updated since this date

        :returns: a generator of bugs
        """
        if not from_date:
            from_date = DEFAULT_DATETIME

        kwargs = {"from_date": from_date}
        items = super().fetch(category, **kwargs)

        return items

    def fetch_items(self, category, **kwargs):
        """Fetch the bugs

        :param category: the category of items to fetch
        :param kwargs: backend arguments

        :returns: a generator of items
        """

        from_date = kwargs['from_date']

        logger.info("Looking for bugs: '%s' updated from '%s'",
                    self.url, str(from_date))

        buglist = [bug for bug in self.__fetch_buglist(from_date)]

        nbugs = 0
        tbugs = len(buglist)

        for i in range(0, tbugs, self.max_bugs):
            chunk = buglist[i:i + self.max_bugs]
            bugs_ids = [b['bug_id'] for b in chunk]

            logger.info("Fetching bugs: %s/%s", i, tbugs)
            bugs = self.__fetch_and_parse_bugs_details(bugs_ids)

            for bug in bugs:
                bug_id = bug['bug_id'][0]['__text__']
                bug['activity'] = self.__fetch_and_parse_bug_activity(bug_id)
                nbugs += 1
                yield bug

        logger.info("Fetch process completed: %s/%s bugs fetched",
                    nbugs, tbugs)

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
        """Extracts the identifier from a Bugzilla item."""

        return item['bug_id'][0]['__text__']

    @staticmethod
    def metadata_updated_on(item):
        """Extracts and coverts the update time from a Bugzilla item.

        The timestamp is extracted from 'delta_ts' field. This date is
        converted to UNIX timestamp format. Due Bugzilla servers ignore
        the timezone on HTTP requests, it will be ignored during the
        conversion, too.

        :param item: item generated by the backend

        :returns: a UNIX timestamp
        """
        ts = item['delta_ts'][0]['__text__']
        ts = str_to_datetime(ts)
        ts = ts.replace(tzinfo=dateutil.tz.tzutc())

        return ts.timestamp()

    @staticmethod
    def metadata_category(item):
        """Extracts the category from a Bugzilla item.

        This backend only generates one type of item which is
        'bug'.
        """
        return CATEGORY_BUG

    @staticmethod
    def parse_buglist(raw_csv):
        """Parse a Bugzilla CSV bug list.

        The method parses the CSV file and returns an iterator of
        dictionaries. Each one of this, contains the summary of a bug.

        :param raw_csv: CSV string to parse

        :returns: a generator of parsed bugs
        """
        reader = csv.DictReader(raw_csv.split('\n'),
                                delimiter=',', quotechar='"')
        for row in reader:
            yield row

    @staticmethod
    def parse_bugs_details(raw_xml):
        """Parse a Bugilla bugs details XML stream.

        This method returns a generator which parses the given XML,
        producing an iterator of dictionaries. Each dictionary stores
        the information related to a parsed bug.

        If the given XML is invalid or does not contains any bug, the
        method will raise a ParseError exception.

        :param raw_xml: XML string to parse

        :returns: a generator of parsed bugs

        :raises ParseError: raised when an error occurs parsing
            the given XML stream
        """
        bugs = xml_to_dict(raw_xml)

        if 'bug' not in bugs:
            cause = "No bugs found. XML stream seems to be invalid."
            raise ParseError(cause=cause)

        for bug in bugs['bug']:
            yield bug

    @staticmethod
    def parse_bug_activity(raw_html):
        """Parse a Bugzilla bug activity HTML stream.

        This method extracts the information about activity from the
        given HTML stream. The bug activity is stored into a HTML
        table. Each parsed activity event is returned into a dictionary.

        If the given HTML is invalid, the method will raise a ParseError
        exception.

        :param raw_html: HTML string to parse

        :returns: a generator of parsed activity events

        :raises ParseError: raised when an error occurs parsing
            the given HTML stream
        """
        def is_activity_empty(bs):
            EMPTY_ACTIVITY = "No changes have been made to this (?:bug|issue) yet."
            tag = bs.find(text=re.compile(EMPTY_ACTIVITY))
            return tag is not None

        def find_activity_table(bs):
            # The first table with 5 columns is the table of activity
            tables = bs.find_all('table')

            for tb in tables:
                nheaders = len(tb.tr.find_all('th', recursive=False))
                if nheaders == 5:
                    return tb
            raise ParseError(cause="Table of bug activity not found.")

        def remove_tags(bs):
            HTML_TAGS_TO_REMOVE = ['a', 'i', 'span']

            for tag in bs.find_all(HTML_TAGS_TO_REMOVE):
                tag.replaceWith(tag.text)

        def format_text(bs):
            strings = [s.strip(' \n\t') for s in bs.stripped_strings]
            s = ' '.join(strings)
            return s

        # Parsing starts here
        bs = bs4.BeautifulSoup(raw_html, 'html.parser')

        if is_activity_empty(bs):
            fields = []
        else:
            activity_tb = find_activity_table(bs)
            remove_tags(activity_tb)
            fields = activity_tb.find_all('td')

        while fields:
            # First two fields: 'Who' and 'When'.
            who = fields.pop(0)
            when = fields.pop(0)

            # The attribute 'rowspan' of 'who' field tells how many
            # changes were made on the same date.
            n = int(who.get('rowspan'))

            # Next fields are split into chunks of three elements:
            # 'What', 'Removed' and 'Added'. These chunks share
            # 'Who' and 'When' values.
            for _ in range(n):
                what = fields.pop(0)
                removed = fields.pop(0)
                added = fields.pop(0)
                event = {'Who': format_text(who),
                         'When': format_text(when),
                         'What': format_text(what),
                         'Removed': format_text(removed),
                         'Added': format_text(added)}
                yield event

    def _init_client(self, from_archive=False):
        """Init client"""

        return BugzillaClient(self.url, user=self.user, password=self.password,
                              max_bugs_csv=self.max_bugs_csv,
                              archive=self.archive, from_archive=from_archive, ssl_verify=self.ssl_verify)

    def __fetch_buglist(self, from_date):
        buglist = self.__fetch_and_parse_buglist_page(from_date)

        while buglist:
            bug = buglist.pop(0)
            last_date = bug['changeddate']
            yield bug

            # Bugzilla does not support pagination. Due to this,
            # the next list of bugs is requested adding one second
            # to the last date obtained.
            if not buglist:
                from_date = str_to_datetime(last_date)
                from_date += datetime.timedelta(seconds=1)
                buglist = self.__fetch_and_parse_buglist_page(from_date)

    def __fetch_and_parse_buglist_page(self, from_date):
        logger.debug("Fetching and parsing buglist page from %s", str(from_date))
        raw_csv = self.client.buglist(from_date=from_date)
        buglist = self.parse_buglist(raw_csv)
        return [bug for bug in buglist]

    def __fetch_and_parse_bugs_details(self, *bug_ids):
        logger.debug("Fetching and parsing bugs details")
        raw_bugs = self.client.bugs(*bug_ids)
        return self.parse_bugs_details(raw_bugs)

    def __fetch_and_parse_bug_activity(self, bug_id):
        logger.debug("Fetching and parsing bug #%s activity", bug_id)
        raw_activity = self.client.bug_activity(bug_id)
        activity = self.parse_bug_activity(raw_activity)
        return [event for event in activity]


class BugzillaCommand(BackendCommand):
    """Class to run Bugzilla backend from the command line."""

    BACKEND = Bugzilla

    @classmethod
    def setup_cmd_parser(cls):
        """Returns the Bugzilla argument parser."""

        parser = BackendCommandArgumentParser(cls.BACKEND,
                                              from_date=True,
                                              basic_auth=True,
                                              archive=True,
                                              ssl_verify=True)

        # Bugzilla options
        group = parser.parser.add_argument_group('Bugzilla arguments')
        group.add_argument('--max-bugs', dest='max_bugs',
                           type=int, default=MAX_BUGS,
                           help="Maximum number of bugs requested on the same query")
        group.add_argument('--max-bugs-csv', dest='max_bugs_csv',
                           type=int, default=MAX_BUGS_CSV,
                           help="Maximum number of bugs requested on CSV queries")

        # Required arguments
        parser.parser.add_argument('url',
                                   help="URL of the Bugzilla server")

        return parser


class BugzillaClient(HttpClient):
    """Bugzilla API client.

    This class implements a simple client to retrieve distinct
    kind of data from a Bugzilla repository. Currently, it only
    supports 3.x and 4.x servers.

    When it is initialized, it checks if the given Bugzilla is
    available and retrieves its version.

    :param base_url: URL of the Bugzilla server
    :param user: Bugzilla user
    :param password: user password
    :param max_bugs_cvs: max bugs requested per CSV query
    :param archive: an archive to store/read fetched data
    :param from_archive: it tells whether to write/read the archive
    :param ssl_verify: enable/disable SSL verification

    :raises BackendError: when an error occurs initializing the
        client
    """
    URL = "%(base)s/%(cgi)s"

    # Regular expression to check the Bugzilla version
    VERSION_REGEX = re.compile(r'.+bugzilla version="([^"]+)"',
                               flags=re.DOTALL)

    # Bugzilla versions that follow the old style queries
    OLD_STYLE_VERSIONS = ['3.2.3', '3.2.2']

    # CGI methods
    CGI_LOGIN = 'index.cgi'
    CGI_BUGLIST = 'buglist.cgi'
    CGI_BUG = 'show_bug.cgi'
    CGI_BUG_ACTIVITY = 'show_activity.cgi'

    # CGI params
    PBUGZILLA_LOGIN = 'Bugzilla_login'
    PBUGZILLA_PASSWORD = 'Bugzilla_password'
    PLIMIT = 'limit'
    PLOGIN = 'GoAheadAndLogIn'
    PLOGOUT = 'logout'
    PBUG_ID = 'id'
    PCHFIELD_FROM = 'chfieldfrom'
    PCTYPE = 'ctype'
    PORDER = 'order'
    PEXCLUDE_FIELD = 'excludefield'

    # Content-type values
    CTYPE_CSV = 'csv'
    CTYPE_XML = 'xml'

    def __init__(self, base_url, user=None, password=None,
                 max_bugs_csv=MAX_BUGS_CSV, archive=None, from_archive=False, ssl_verify=True):
        self.version = None
        super().__init__(base_url, archive=archive, from_archive=from_archive, ssl_verify=ssl_verify)

        if user is not None and password is not None:
            self.login(user, password)

        self.max_bugs_csv = max_bugs_csv

    def login(self, user, password):
        """Authenticate a user in the server.

        :param user: Bugzilla user
        :param password: user password
        """
        url = self.URL % {'base': self.base_url, 'cgi': self.CGI_LOGIN}

        payload = {
            self.PBUGZILLA_LOGIN: user,
            self.PBUGZILLA_PASSWORD: password,
            self.PLOGIN: 'Log in'
        }

        headers = {'Referer': self.base_url}

        req = self.fetch(url, payload=payload, headers=headers, method=HttpClient.POST)

        # Check if the authentication went OK. When this string
        # is found means that the authentication was successful
        if req.text.find("index.cgi?logout=1") < 0:
            cause = ("Bugzilla client could not authenticate user %s. "
                     "Please check user and password parameters. "
                     "URLs may also need a trailing '/'.") % user
            raise BackendError(cause=cause)

        logger.debug("Bugzilla user %s authenticated in %s",
                     user, self.base_url)

    def logout(self):
        """Logout from the server."""

        params = {
            self.PLOGOUT: '1'
        }

        self.call(self.CGI_LOGIN, params)
        self._close_http_session()

        logger.debug("Bugzilla user logged out from %s",
                     self.base_url)

    def metadata(self):
        """Get metadata information in XML format."""

        params = {
            self.PCTYPE: self.CTYPE_XML
        }

        response = self.call(self.CGI_BUG, params)

        return response

    def buglist(self, from_date=DEFAULT_DATETIME):
        """Get a summary of bugs in CSV format.

        :param from_date: retrieve bugs that where updated from that date
        """
        if not self.version:
            self.version = self.__fetch_version()

        if self.version in self.OLD_STYLE_VERSIONS:
            order = 'Last+Changed'
        else:
            order = 'changeddate'

        date = from_date.strftime("%Y-%m-%d %H:%M:%S")

        params = {
            self.PCHFIELD_FROM: date,
            self.PCTYPE: self.CTYPE_CSV,
            self.PLIMIT: self.max_bugs_csv,
            self.PORDER: order
        }

        response = self.call(self.CGI_BUGLIST, params)

        return response

    def bugs(self, *bug_ids):
        """Get the information of a list of bugs in XML format.

        :param bug_ids: list of bug identifiers
        """
        params = {
            self.PBUG_ID: bug_ids,
            self.PCTYPE: self.CTYPE_XML,
            self.PEXCLUDE_FIELD: 'attachmentdata'
        }

        response = self.call(self.CGI_BUG, params)

        return response

    def bug_activity(self, bug_id):
        """Get the activity of a bug in HTML format.

        :param bug_id: bug identifier
        """
        params = {
            self.PBUG_ID: bug_id
        }

        response = self.call(self.CGI_BUG_ACTIVITY, params)

        return response

    def call(self, cgi, params):
        """Run an API command.

        :param cgi: cgi command to run on the server
        :param params: dict with the HTTP parameters needed to run
            the given command
        """
        url = self.URL % {'base': self.base_url, 'cgi': cgi}

        logger.debug("Bugzilla client calls command: %s params: %s",
                     cgi, str(params))

        req = self.fetch(url, payload=params)

        return req.text

    @staticmethod
    def sanitize_for_archive(url, headers, payload):
        """Sanitize payload of a HTTP request by removing the login and password information
        before storing/retrieving archived items

        :param: url: HTTP url request
        :param: headers: HTTP headers request
        :param: payload: HTTP payload request

        :returns url, headers and the sanitized payload
        """
        if BugzillaClient.PBUGZILLA_LOGIN in payload:
            payload.pop(BugzillaClient.PBUGZILLA_LOGIN)

        if BugzillaClient.PBUGZILLA_PASSWORD in payload:
            payload.pop(BugzillaClient.PBUGZILLA_PASSWORD)

        if BugzillaClient.PLOGIN in payload:
            payload.pop(BugzillaClient.PLOGIN)

        return url, headers, payload

    def __fetch_version(self):
        response = self.metadata()
        m = re.match(self.VERSION_REGEX, response)

        if m:
            version = m.group(1)
            logger.debug("Bugzilla server is online: %s (v. %s)",
                         self.base_url, version)
            return version
        else:
            cause = "Bugzilla client could not determine the server version"
            raise BackendError(cause=cause)
