#!/usr/bin/env python3
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
#     Valerio Cosentino <valcos@bitergia.com>
#     Miguel Ángel Fernández <mafesan@bitergia.com>
#

import bz2
import datetime
import email
import gzip
import os
import shutil
import tempfile
import unittest
import zipfile

from perceval.errors import ParseError
from perceval.utils import (check_compressed_file_type,
                            message_to_dict,
                            months_range,
                            remove_invalid_xml_chars,
                            xml_to_dict)


def read_file(filename, mode='r'):
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), filename), mode) as f:
        content = f.read()
    return content


class TestCheckCompressedFileType(unittest.TestCase):
    """Unit tests for check_compressed_file_type function"""

    @classmethod
    def setUpClass(cls):
        cls.tmp_path = tempfile.mkdtemp(prefix='perceval_')

        cls.files = {
            'bz2': os.path.join(cls.tmp_path, 'bz2'),
            'gz': os.path.join(cls.tmp_path, 'gz'),
            'zip': os.path.join(cls.tmp_path, 'zip')
        }

        # Copy compressed files
        for ftype, fname in cls.files.items():
            if ftype == 'bz2':
                mod = bz2
            elif ftype == 'gz':
                mod = gzip
            else:
                mod = zipfile

            if mod == zipfile:
                with zipfile.ZipFile(fname, 'w') as f_out:
                    f_out.write(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data/mbox/mbox_single.mbox'))
            else:
                with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data/mbox/mbox_single.mbox'),
                          'rb') as f_in:
                    with mod.open(fname, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)

        # Copy a plain file
        shutil.copy(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 'data/utils/mbox_single.mbox'), cls.tmp_path)

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


class TestMonthsRange(unittest.TestCase):
    """Unit tests for months_range function"""

    def test_range(self):
        """Check if it generates a range on months"""

        from_date = datetime.datetime(2016, 11, 10)
        to_date = datetime.datetime(2017, 3, 30)

        expected = [
            (datetime.datetime(2016, 11, 1),
             datetime.datetime(2016, 12, 1)),
            (datetime.datetime(2016, 12, 1),
             datetime.datetime(2017, 1, 1)),
            (datetime.datetime(2017, 1, 1),
             datetime.datetime(2017, 2, 1)),
            (datetime.datetime(2017, 2, 1),
             datetime.datetime(2017, 3, 1))
        ]

        result = [r for r in months_range(from_date, to_date)]
        self.assertListEqual(result, expected)

    def test_range_outbounds(self):
        """Test if the range is empty when to_date is lower than from_date"""

        from_date = datetime.datetime(2017, 3, 30)
        to_date = datetime.datetime(2016, 11, 10)

        result = [r for r in months_range(from_date, to_date)]
        self.assertListEqual(result, [])

    def test_range_same_month(self):
        """Test if the range is empty when both dates are on the same month"""

        from_date = datetime.datetime(2016, 11, 10)
        to_date = datetime.datetime(2016, 11, 30)

        result = [r for r in months_range(from_date, to_date)]
        self.assertListEqual(result, [])


class TestMessagetoDict(unittest.TestCase):
    """Unit tests for message_to_dict"""

    def test_convert_message(self):
        """Test whether it converts an email message"""

        raw_email = read_file('data/utils/email_single.txt')
        msg = email.message_from_string(raw_email)

        message = message_to_dict(msg)
        message = {k: v for k, v in message.items()}

        expected = {
            'From': 'goran at domain.com ( Göran Lastname )',
            'Date': 'Wed, 01 Dec 2010 14:26:40 +0100',
            'Subject': '[List-name] Protocol Buffers anyone?',
            'Message-ID': '<4CF64D10.9020206@domain.com>',
            'unixfrom': None,
            'body': {
                'plain': "Hi!\n\nA message in English, with a signature "
                         "with a different encoding.\n\nregards, G?ran"
                         "\n\n\n",
            }
        }

        self.assertDictEqual(message, expected)

    def test_convert_multipart_message(self):
        """Test if it converts email messages with multipart bodies"""

        # Multipart message with defined encoding
        raw_email = read_file('data/utils/email_multipart_encoding.txt')
        msg = email.message_from_string(raw_email)

        message = message_to_dict(msg)

        plain_body = message['body']['plain']
        html_body = message['body']['html']
        self.assertEqual(plain_body, 'technology.esl Committers,\n\n'
                                     'This automatically generated message marks the successful completion of\n'
                                     'voting for Chuwei Huang to receive full Committer status on the\n'
                                     'technology.esl project. The next step is for the PMC to approve this vote,\n'
                                     'followed by the EMO processing the paperwork and provisioning the account.\n\n\n\n'
                                     'Vote summary: 4/0/0 with 0 not voting\n\n'
                                     '  +1  Thomas Guiu\n\n'
                                     '  +1  Jin Liu\n\n'
                                     '  +1  Yves YANG\n\n'
                                     '  +1  Bo Zhou\n\n\n\n'
                                     'If you have any questions, please do not hesitate to contact your project\n'
                                     'lead, PMC member, or the EMO <emo@example.org>\n\n\n\n\n\n')
        self.assertEqual(len(html_body), 3103)

        # Multipart message without defined encoding
        raw_email = read_file('data/utils/email_multipart_no_encoding.txt')
        msg = email.message_from_string(raw_email)

        message = message_to_dict(msg)

        plain_body = message['body']['plain']
        html_body = message['body']['html']
        self.assertEqual(plain_body, 'I am fairly new to eclipse. I am evaluating the use of eclipse for a generic\n'
                                     'UI framework that is not necessarily related to code generation.\n'
                                     'Eclipse is very flexible and adding functionality seems straightforward. I\n'
                                     'can still use the project concept for what I need but there are things in\n'
                                     'the Workbench window that I don\'t want. For example the Open perspective\n'
                                     'icon, or some of the menus, like the Windows and project menu .\n\n'
                                     'I understand that by using retargetable actions I can have my view taking\n'
                                     'over most of the actions, but I could not figure out how to block the core\n'
                                     'plug-in to put their own actions. In the workbench plug-in (org.eclipse.ui)\n'
                                     'I could not find where menus are defined and where actionsviews for all\n'
                                     'generic toolbars are defined.\n\nHow do I do this?\nCan this be done?\n'
                                     'Is anybody using eclipse as a generic UI framework?\n\nI appreciate any help.\n\n'
                                     'Thanks,\n\nDaniel Nehren\n\n')
        self.assertEqual(len(html_body), 1557)


class TestRemoveInvalidXMLChars(unittest.TestCase):
    """Unit tests for remove_invalid_xml_characters"""

    def test_remove_chars(self):
        raw_xml = read_file('data/utils/bugzilla_bugs_invalid_chars.xml')
        purged_xml = remove_invalid_xml_chars(raw_xml)

        self.assertNotEqual(purged_xml, raw_xml)
        self.assertEqual(len(purged_xml), len(raw_xml))


class TestXMLtoDict(unittest.TestCase):
    """Unit tests for xml_to_dict"""

    def test_xml_to_dict(self):
        """Check whether it converts a XML file to a dict"""

        raw_xml = read_file('data/utils/bugzilla_bug.xml')
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

        raw_xml = read_file('data/utils/bugzilla_bugs_invalid_chars.xml')
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

        raw_xml = read_file('data/utils/xml_invalid.xml')

        self.assertRaises(ParseError, xml_to_dict, raw_xml)


if __name__ == "__main__":
    unittest.main()
