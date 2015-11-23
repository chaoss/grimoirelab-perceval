# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 Bitergia
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

import csv
import datetime

import requests

from ..errors import ParseError
from ..utils import DEFAULT_DATETIME, str_to_datetime, xml_to_dict


MAX_BUGS = 200 # Maximum number of bugs per query


class Bugzilla:
    """Bugzilla backend.

    This class allows the fetch the bugs stored in Bugzilla
    repository. To initialize this class the URL of the server
    must be provided.

    :param url: Bugzilla server URL
    :param max_bugs: maximum number of bugs requested on the same query
    """
    def __init__(self, url, max_bugs=MAX_BUGS):
        self.url = url
        self.max_bugs = max(1, max_bugs)
        self.client = BugzillaClient(url)

    def fetch(self, from_date=DEFAULT_DATETIME):
        """Fetch the bugs from the repository.

        The method retrieves, from a Bugzilla repository, the bugs
        updated since the given date.

        :param from_date: obtain bugs updated since this date
        """
        buglist = [bug for bug in self.__fetch_buglist(from_date)]

        for i in range(0, len(buglist), self.max_bugs):
            chunk = buglist[i:i + self.max_bugs]
            bugs_ids = [b['bug_id'] for b in chunk]

            bugs = self.__fetch_and_parse_bugs_details(bugs_ids)

            for bug in bugs:
                yield bug

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
        raw_csv = self.client.buglist(from_date=from_date)
        buglist = self.parse_buglist(raw_csv)
        return [bug for bug in buglist]

    def __fetch_and_parse_bugs_details(self, *bug_ids):
        raw_bugs = self.client.bugs(*bug_ids)
        return self.parse_bugs_details(raw_bugs)

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


class BugzillaClient:
    """Bugzilla API client.

    This class implements a simple client to retrieve distinct
    kind of data from a Bugzilla repository. Currently, it only
    supports 3.x and 4.x servers.

    :param base_url: URL of the Bugzilla server
    """

    URL = "%(base)s/%(cgi)s"
    HEADERS = {'User-Agent': 'perceval-bg-0.1'}

    # Bugzilla versions that follow the old style queries
    OLD_STYLE_VERSIONS = ['3.2.3', '3.2.2']

    # CGI methods
    CGI_BUGLIST = 'buglist.cgi'
    CGI_BUG = 'show_bug.cgi'
    CGI_BUG_ACTIVITY = 'show_activity.cgi'

    # CGI params
    PBUG_ID= 'id'
    PCHFIELD_FROM = 'chfieldfrom'
    PCTYPE = 'ctype'
    PORDER = 'order'
    PEXCLUDE_FIELD = 'excludefield'

    # Content-type values
    CTYPE_CSV = 'csv'
    CTYPE_XML = 'xml'


    def __init__(self, base_url):
        self.base_url = base_url

    def metadata(self):
        """Get metadata information in XML format."""

        params = {
            self.PCTYPE : self.CTYPE_XML
        }

        response = self.call(self.CGI_BUG, params)

        return response

    def buglist(self, from_date=DEFAULT_DATETIME, version=None):
        """Get a summary of bugs in CSV format.

        :param from_date: retrieve bugs that where updated from that date
        :param version: version of the server
        """
        if version in self.OLD_STYLE_VERSIONS:
            order = 'Last+Changed'
        else:
            order = 'changeddate'

        date = from_date.strftime("%Y-%m-%dT%H:%M:%S")

        params = {
            self.PCHFIELD_FROM : date,
            self.PCTYPE : self.CTYPE_CSV,
            self.PORDER : order
        }

        response = self.call(self.CGI_BUGLIST, params)

        return response

    def bugs(self, *bug_ids):
        """Get the information of a list of bugs in XML format.

        :param bug_ids: list of bug identifiers
        """
        params = {
            self.PBUG_ID : bug_ids,
            self.PCTYPE : self.CTYPE_XML,
            self.PEXCLUDE_FIELD : 'attachmentdata'
        }

        response = self.call(self.CGI_BUG, params)

        return response

    def bug_activity(self, bug_id):
        """Get the activity of a bug in HTML format.

        :param bug_id: bug identifier
        """
        params = {
            self.PBUG_ID : bug_id
        }

        response = self.call(self.CGI_BUG_ACTIVITY, params)

        return response

    def call(self, cgi, params):
        """Run an API command.

        :param cgi: cgi method to run on the server
        :param params: dict with the HTTP parameters needed to run
            the given method
        """
        url = self.URL % {'base' : self.base_url, 'cgi' : cgi}

        req = requests.get(url, params=params,
                           headers=self.HEADERS)
        req.raise_for_status()

        return req.text
