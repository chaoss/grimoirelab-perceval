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

import requests


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

    def buglist(self, from_date='1970-01-01', version=None):
        """Get a summary of bugs in CSV format.

        :param from_date: retrieve bugs that where updated from that date
        :param version: version of the server
        """
        if version in self.OLD_STYLE_VERSIONS:
            order = 'Last+Changed'
        else:
            order = 'changeddate'

        params = {
            self.PCHFIELD_FROM : from_date,
            self.PCTYPE : self.CTYPE_CSV,
            self.PORDER : order
        }

        response = self.call(self.CGI_BUGLIST, params)

        return response

    def bug(self, bug_id):
        """Get the information of a bug in XML format.

        :param bug_id: bug identifier
        """
        params = {
            self.PBUG_ID : bug_id,
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
