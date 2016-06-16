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

import sys
import unittest

import httpretty

if not '..' in sys.path:
    sys.path.insert(0, '..')

from perceval.errors import RepositoryError
from perceval.backends.gmane import GmaneClient


GMANE_LIST_URL = 'http://list.gmane.org/mylist@example.com'
GMANE_INVALID_LIST_URL = 'http://list.gmane.org/invalidlist@example.com'
GMAME_DOWNLOAD_LIST_URL = 'http://download.gmane.org/gmane.comp.example.mylist'


def read_file(filename, mode='r'):
    with open(filename, mode) as f:
        content = f.read()
    return content


class TestGmaneClient(unittest.TestCase):
    """Tests for GmaneClient class"""

    @httpretty.activate
    def test_messages(self):
        """Test if a set of messages is fetched"""

        body = read_file("data/gmane_messages.mbox")

        url = GMAME_DOWNLOAD_LIST_URL + '/888/898'

        httpretty.register_uri(httpretty.GET, url,
                               status=200,
                               body=body)

        client = GmaneClient()

        response = client.messages('gmane.comp.example.mylist', 888, 10)
        self.assertEqual(response, body)

    @httpretty.activate
    def test_mailing_list_url(self):
        """Test whether it returns the URL of a mailing list in Gmane"""

        target = "http://dir.gmane.org/gmane.comp.example.mylist"

        httpretty.register_uri(httpretty.GET, GMANE_LIST_URL,
                               status=301,
                               location=target)

        httpretty.register_uri(httpretty.GET, target,
                               status=200,
                               body="")

        client = GmaneClient()

        url = client.mailing_list_url('mylist@example.com')
        self.assertEqual(url, target)

    @httpretty.activate
    def test_mailing_list_url_not_found(self):
        """Test whether it raises an exception when a mailing list is not found"""

        httpretty.register_uri(httpretty.GET, GMANE_INVALID_LIST_URL,
                               status=200,
                               body="No such list")

        client = GmaneClient()

        with self.assertRaises(RepositoryError):
            client.mailing_list_url('invalidlist@example.com')


if __name__ == "__main__":
    unittest.main(warnings='ignore')
