#!/usr/bin/env python3
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

import datetime
import sys
import unittest

if not '..' in sys.path:
    sys.path.insert(0, '..')

from perceval.errors import InvalidDateError, ParseError
from perceval.utils import str_to_datetime, urljoin, xml_to_dict


def read_file(filename):
    with open(filename, 'r') as f:
        content = f.read()
    return content


class TestStrToDatetime(unittest.TestCase):
    """Unit tests for str_to_datetime function"""

    def test_dates(self):
        """Check if it converts some dates to datetime objects"""

        date = str_to_datetime('2001-12-01')
        self.assertIsInstance(date, datetime.datetime)
        self.assertEqual(date, datetime.datetime(2001, 12, 1))

        date = str_to_datetime('13-01-2001')
        self.assertIsInstance(date, datetime.datetime)
        self.assertEqual(date, datetime.datetime(2001, 1, 13))

        date = str_to_datetime('12-01-01')
        self.assertIsInstance(date, datetime.datetime)
        self.assertEqual(date, datetime.datetime(2001, 12, 1))

        date = str_to_datetime('2001-12-01 23:15:32')
        self.assertIsInstance(date, datetime.datetime)
        self.assertEqual(date, datetime.datetime(2001, 12, 1, 23, 15, 32))

    def test_invalid_date(self):
        """Check whether it fails with an invalid date"""

        self.assertRaises(InvalidDateError, str_to_datetime, '2001-13-01')
        self.assertRaises(InvalidDateError, str_to_datetime, '2001-04-31')

    def test_invalid_format(self):
        """Check whether it fails with invalid formats"""

        self.assertRaises(InvalidDateError, str_to_datetime, '2001-12-01mm')
        self.assertRaises(InvalidDateError, str_to_datetime, 'nodate')
        self.assertRaises(InvalidDateError, str_to_datetime, None)
        self.assertRaises(InvalidDateError, str_to_datetime, '')


class TestURLJoin(unittest.TestCase):
    """Unit tests for urljoin"""

    def test_join(self):
        """Test basic joins"""

        base_url = 'http://example.com/'
        base_url_alt = 'http://example.com'
        path0 = 'owner'
        path1 = 'repository'
        path2 = '/owner/repository'
        path3 = 'issues/8'

        url = urljoin(base_url, path0, path1)
        self.assertEqual(url, 'http://example.com/owner/repository')

        url = urljoin(base_url, path2)
        self.assertEqual(url, 'http://example.com/owner/repository')

        url = urljoin(base_url, path0, path1, path3)
        self.assertEqual(url, 'http://example.com/owner/repository/issues/8')

        url = urljoin(base_url_alt, path0, path1)
        self.assertEqual(url, 'http://example.com/owner/repository')


class TestXMLtoDict(unittest.TestCase):
    """Unit tests for xml_to_dict"""

    def test_xml_to_dict(self):
        """Check whether it converts a XML file to a dict"""

        raw_xml = read_file('data/bugzilla_bug.xml')
        d = xml_to_dict(raw_xml)

        self.assertIsInstance(d, dict)
        self.assertEqual(d['version'], '4.2.1')
        self.assertEqual(len(d['bug']), 1)

        bug = d['bug'][0]
        self.assertEqual(bug['short_desc'][0]['__text__'], 'Mock bug for testing purposes')
        self.assertEqual(bug['reporter'][0]['name'], 'Santiago Dueñas')
        self.assertEqual(bug['reporter'][0]['__text__'], 'sduenas@example.org')
        self.assertEqual(len(bug['cc']), 3)
        self.assertEqual(len(bug['long_desc']), 4)

        long_desc = bug['long_desc'][2]
        self.assertEqual(long_desc['isprivate'], '0')
        self.assertEqual(long_desc['thetext'][0]['__text__'], 'Invalid patch')

    def test_invalid_xml(self):
        """Check whether it raises an exception when the XML is invalid"""

        raw_xml = read_file('data/xml_invalid.xml')

        self.assertRaises(ParseError, xml_to_dict, raw_xml)


if __name__ == "__main__":
    unittest.main()
