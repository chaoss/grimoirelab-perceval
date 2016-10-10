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
import os.path
import shutil
import sys
import tempfile
import unittest

import bz2
import gzip

import dateutil.tz

if not '..' in sys.path:
    sys.path.insert(0, '..')

from perceval.errors import InvalidDateError, ParseError
from perceval.utils import (check_compressed_file_type,
                            datetime_to_utc,
                            remove_invalid_xml_chars,
                            str_to_datetime,
                            unixtime_to_datetime,
                            urljoin,
                            xml_to_dict)


def read_file(filename):
    with open(filename, 'r') as f:
        content = f.read()
    return content


class TestCheckCompressedFileType(unittest.TestCase):
    """Unit tests for check_compressed_file_type function"""

    @classmethod
    def setUpClass(cls):
        cls.tmp_path = tempfile.mkdtemp(prefix='perceval_')

        cls.files = {'bz2' : os.path.join(cls.tmp_path, 'bz2'),
                     'gz'  : os.path.join(cls.tmp_path, 'gz')}

        # Copy compressed files
        for ftype, fname in cls.files.items():
            if ftype == 'bz2':
                mod = bz2
            else:
                mod = gzip

            with open('data/mbox_single.mbox', 'rb') as f_in:
                with mod.open(fname, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)

        # Copy a plain file
        shutil.copy('data/mbox_single.mbox', cls.tmp_path)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp_path)

    def test_compressed_type(self):
        """Test the type of some compressed files"""

        for ftype, fname in self.files.items():
            filetype = check_compressed_file_type(fname)
            self.assertEqual(filetype, ftype)

    def test_not_supported_type(self):
        """Test a non supported file"""

        fname = os.path.join(self.tmp_path, 'mbox_single.mbox')
        filetype = check_compressed_file_type(fname)
        self.assertEqual(filetype, None)


class TestDatetimeToUTC(unittest.TestCase):
    """Unit tests for datetime_to_utc function"""

    def test_conversion(self):
        """Check if it converts some timestamps to timestamps with UTC+0"""

        date = datetime.datetime(2001, 12, 1, 23, 15, 32,
                                 tzinfo=dateutil.tz.tzoffset(None, -21600))
        expected = datetime.datetime(2001, 12, 2, 5, 15, 32,
                                     tzinfo=dateutil.tz.tzutc())
        utc = datetime_to_utc(date)
        self.assertIsInstance(utc, datetime.datetime)
        self.assertEqual(utc, expected)

        date = datetime.datetime(2001, 12, 1, 23, 15, 32,
                                 tzinfo=dateutil.tz.tzutc())
        expected = datetime.datetime(2001, 12, 1, 23, 15, 32,
                                     tzinfo=dateutil.tz.tzutc())
        utc = datetime_to_utc(date)
        self.assertIsInstance(utc, datetime.datetime)
        self.assertEqual(utc, expected)

        date = datetime.datetime(2001, 12, 1, 23, 15, 32)
        expected = datetime.datetime(2001, 12, 1, 23, 15, 32,
                                     tzinfo=dateutil.tz.tzutc())
        utc = datetime_to_utc(date)
        self.assertIsInstance(utc, datetime.datetime)
        self.assertEqual(utc, expected)

    def test_invalid_datetime(self):
        """Check if it raises an exception on invalid instances"""

        self.assertRaises(InvalidDateError, datetime_to_utc, "2016-01-01 01:00:00 +0800")
        self.assertRaises(InvalidDateError, datetime_to_utc, None)
        self.assertRaises(InvalidDateError, datetime_to_utc, 1)


class TestStrToDatetime(unittest.TestCase):
    """Unit tests for str_to_datetime function"""

    def test_dates(self):
        """Check if it converts some dates to datetime objects"""

        date = str_to_datetime('2001-12-01')
        expected = datetime.datetime(2001, 12, 1, tzinfo=dateutil.tz.tzutc())
        self.assertIsInstance(date, datetime.datetime)
        self.assertEqual(date, expected)

        date = str_to_datetime('13-01-2001')
        expected = datetime.datetime(2001, 1, 13, tzinfo=dateutil.tz.tzutc())
        self.assertIsInstance(date, datetime.datetime)
        self.assertEqual(date, expected)

        date = str_to_datetime('12-01-01')
        expected = datetime.datetime(2001, 12, 1, tzinfo=dateutil.tz.tzutc())
        self.assertIsInstance(date, datetime.datetime)
        self.assertEqual(date, expected)

        date = str_to_datetime('2001-12-01 23:15:32')
        expected = datetime.datetime(2001, 12, 1, 23, 15, 32,
                                     tzinfo=dateutil.tz.tzutc())
        self.assertIsInstance(date, datetime.datetime)
        self.assertEqual(date, expected)

        date = str_to_datetime('2001-12-01 23:15:32 -0600')
        expected = datetime.datetime(2001, 12, 1, 23, 15, 32,
                                     tzinfo=dateutil.tz.tzoffset(None, -21600))
        self.assertIsInstance(date, datetime.datetime)
        self.assertEqual(date, expected)

        date = str_to_datetime('2001-12-01 23:15:32Z')
        expected = datetime.datetime(2001, 12, 1, 23, 15, 32,
                                     tzinfo=dateutil.tz.tzutc())
        self.assertIsInstance(date, datetime.datetime)
        self.assertEqual(date, expected)

        date = str_to_datetime('Wed, 26 Oct 2005 15:20:32 -0100 (GMT+1)')
        expected = datetime.datetime(2005, 10, 26, 15, 20, 32,
                                     tzinfo=dateutil.tz.tzoffset(None, -3600))
        self.assertIsInstance(date, datetime.datetime)
        self.assertEqual(date, expected)

        date = str_to_datetime('Wed, 22 Jul 2009 11:15:50 +0300 (FLE Daylight Time)')
        expected = datetime.datetime(2009, 7, 22, 11, 15, 50,
                                     tzinfo=dateutil.tz.tzoffset(None, 10800))
        self.assertIsInstance(date, datetime.datetime)
        self.assertEqual(date, expected)

        date = str_to_datetime('Thu, 14 Aug 2008 02:07:59 +0200 CEST')
        expected = datetime.datetime(2008, 8, 14, 2, 7, 59,
                                     tzinfo=dateutil.tz.tzoffset(None, 7200))
        self.assertIsInstance(date, datetime.datetime)
        self.assertEqual(date, expected)

        date = str_to_datetime('Thu, 14 Aug 2008 02:07:59 +0200 +0100')
        expected = datetime.datetime(2008, 8, 14, 2, 7, 59,
                                     tzinfo=dateutil.tz.tzoffset(None, 7200))
        self.assertIsInstance(date, datetime.datetime)
        self.assertEqual(date, expected)

        # This date is invalid because the timezone section.
        # Timezone will be removed, setting UTC as default
        date = str_to_datetime('2001-12-01 02:00 +08888')
        expected = datetime.datetime(2001, 12, 1, 2, 0, 0,
                                     tzinfo=dateutil.tz.tzutc())
        self.assertIsInstance(date, datetime.datetime)
        self.assertEqual(date, expected)

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


class TestUnixTimeToDatetime(unittest.TestCase):
    """Unit tests for str_to_datetime function"""

    def test_dates(self):
        """Check if it converts some timestamps to datetime objects"""

        date = unixtime_to_datetime(0)
        expected = datetime.datetime(1970,  1, 1, 0, 0, 0,
                                     tzinfo=dateutil.tz.tzutc())
        self.assertIsInstance(date, datetime.datetime)
        self.assertEqual(date, expected)

        date = unixtime_to_datetime(1426868155.0)
        expected = datetime.datetime(2015,  3, 20, 16, 15, 55,
                                     tzinfo=dateutil.tz.tzutc())
        self.assertIsInstance(date, datetime.datetime)
        self.assertEqual(date, expected)

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


class TestRemoveInvalidXMLChars(unittest.TestCase):
    """Unit tests for remove_invalid_xml_characters"""

    def test_remove_chars(self):
        raw_xml = read_file('data/bugzilla_bugs_invalid_chars.xml')
        purged_xml = remove_invalid_xml_chars(raw_xml)

        self.assertNotEqual(purged_xml, raw_xml)
        self.assertEqual(len(purged_xml), len(raw_xml))


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

    def test_remove_invalid_xml_chars(self):
        """Check whether it removes invalid characters and parses the stream"""

        raw_xml = read_file('data/bugzilla_bugs_invalid_chars.xml')
        d = xml_to_dict(raw_xml)

        self.assertIsInstance(d, dict)
        self.assertEqual(d['version'], '4.2.1')
        self.assertEqual(len(d['bug']), 1)

        bug = d['bug'][0]
        self.assertEqual(bug['bug_id'][0]['__text__'], '25299')
        self.assertEqual(len(bug['cc']), 2)
        self.assertEqual(len(bug['long_desc']), 11)

    def test_invalid_xml(self):
        """Check whether it raises an exception when the XML is invalid"""

        raw_xml = read_file('data/xml_invalid.xml')

        self.assertRaises(ParseError, xml_to_dict, raw_xml)


if __name__ == "__main__":
    unittest.main()
