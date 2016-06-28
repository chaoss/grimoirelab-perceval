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

if not '..' in sys.path:
    sys.path.insert(0, '..')

from perceval.backends.supybot import (SupybotParser)
from perceval.errors import ParseError


class TestSupybotParser(unittest.TestCase):
    """SupybotParser unit tests"""

    def test_parser(self):
        """Test whether it parses a valid Supybot IRC log stream"""

        with open("data/supybot_valid.log", 'r') as f:
            parser = SupybotParser(f)
            items = [item for item in parser.parse()]

        self.assertEqual(len(items), 95)

        item = items[1]
        self.assertEqual(item['timestamp'], '2012-10-17T09:16:29+0000')
        self.assertEqual(item['type'], SupybotParser.TCOMMENT)
        self.assertEqual(item['nick'], 'benpol')
        self.assertEqual(item['body'], "they're related to fragmentation?")

        item = items[2]
        self.assertEqual(item['timestamp'], '2012-10-17T09:16:50+0000')
        self.assertEqual(item['type'], SupybotParser.TSERVER)
        self.assertEqual(item['nick'], 'MikeMcClurg')
        self.assertEqual(item['body'], "MikeMcClurg has quit IRC")

        item = items[-1]
        self.assertEqual(item['timestamp'], '2012-10-17T23:42:26+0000')
        self.assertEqual(item['type'], SupybotParser.TCOMMENT)
        self.assertEqual(item['nick'], 'gregaf')
        self.assertEqual(item['body'], "but I may be wrong or debugging at the wrong level...")

        # Count the number of messages parsed by type
        ncomments = 0
        nserver = 0

        for item in items:
            if item['type'] == SupybotParser.TCOMMENT:
                ncomments += 1
            else:
                nserver += 1

        self.assertEqual(ncomments, 49)
        self.assertEqual(nserver, 46)

    def test_parse_invalid_date(self):
        """Test whether it raises an exception when a date is invalid"""

        with self.assertRaisesRegex(ParseError, "date expected on line 4"):
            with open("data/supybot_invalid_date.log", 'r') as f:
                parser = SupybotParser(f)
                _ = [item for item in parser.parse()]

    def test_parse_invalid_message(self):
        """Test whether it raises an exception when an invalid line is found"""

        with self.assertRaisesRegex(ParseError, "invalid message on line 9"):
            with open("data/supybot_invalid_msg.log", 'r') as f:
                parser = SupybotParser(f)
                _ = [item for item in parser.parse()]

    def test_timestamp_pattern(self):
        """Test the validation of timestamp lines"""

        pattern = SupybotParser.SUPYBOT_TIMESTAMP_REGEX

        # These should have valid dates and messages
        s = "2016-06-28T14:18:55+0000  <mg> Hello!"
        m = pattern.match(s)
        self.assertEqual(m.group('ts'), "2016-06-28T14:18:55+0000")
        self.assertEqual(m.group('msg'), "<mg> Hello!")

        s = "2016-06-28T14:18:55+0230  <mg> Hello!"
        m = pattern.match(s)
        self.assertEqual(m.group('ts'), "2016-06-28T14:18:55+0230")
        self.assertEqual(m.group('msg'), "<mg> Hello!")

        s = "2016-06-28T14:18:55-0230  <mg> Hello!"
        m = pattern.match(s)
        self.assertEqual(m.group('ts'), "2016-06-28T14:18:55-0230")
        self.assertEqual(m.group('msg'), "<mg> Hello!")

        s = "2016-06-28T14:18:55-0230  Whatever I put here is a valid message    "
        m = pattern.match(s)
        self.assertEqual(m.group('ts'), "2016-06-28T14:18:55-0230")
        self.assertEqual(m.group('msg'), "Whatever I put here is a valid message    ")

        # These messages are not valid

        # The message starts with spaces
        s = "  2016-06-28  <mg> Hello!"
        m = pattern.match(s)
        self.assertIsNone(m)

        # Time is missing
        s = "2016-06-28  <mg> Hello!"
        m = pattern.match(s)
        self.assertIsNone(m)

        # Timezone is missing
        s = "2016-06-28T14:18:55  <mg> Hello!"
        m = pattern.match(s)
        self.assertIsNone(m)

        # Timestamp order invalid
        s = "28-06-2016T14:18:55+0000  <mg> Hello!"
        m = pattern.match(s)
        self.assertIsNone(m)

        # There are not two spaces between the body of the message and the date
        s = "28-06-2016T14:18:55+0000 <mg> Hello!"
        m = pattern.match(s)
        self.assertIsNone(m)

    def test_comment_pattern(self):
        """Test the validation of comment lines"""

        pattern = SupybotParser.SUPYBOT_COMMENT_REGEX

        # These should have valid nicks and messages
        s = "<mynick> hello!"
        m = pattern.match(s)
        self.assertEqual(m.group('nick'), 'mynick')
        self.assertEqual(m.group('body'), "hello!")

        s = "<mynick> this is a long message!"
        m = pattern.match(s)
        self.assertEqual(m.group('nick'), 'mynick')
        self.assertEqual(m.group('body'), "this is a long message!")

        # These messages are not valid

        # There are spaces at the beginning of the message
        s = "  <mynick> hello!"
        m = pattern.match(s)
        self.assertIsNone(m)

        # Invalid nick patterns
        s = "mynick> hello!"
        m = pattern.match(s)
        self.assertIsNone(m)

        s = "<mynick hello!"
        m = pattern.match(s)
        self.assertIsNone(m)

    def test_server_pattern(self):
        """Test the validation of sever lines"""

        pattern = SupybotParser.SUPYBOT_SERVER_REGEX

        # These should have valid nicks and adm actions
        s = "*** someone quit"
        m = pattern.match(s)
        self.assertEqual(m.group('nick'), 'someone')
        self.assertEqual(m.group('body'), "someone quit")

        s = "*** someone joined #channel"
        m = pattern.match(s)
        self.assertEqual(m.group('nick'), 'someone')
        self.assertEqual(m.group('body'), "someone joined #channel")

        s = "*** X is now known as Y"
        m = pattern.match(s)
        self.assertEqual(m.group('nick'), 'X')
        self.assertEqual(m.group('body'), "X is now known as Y")

        # These messages are not valid

        # Not starts with ***
        s = "** X is now known as Y"
        m = pattern.match(s)
        self.assertIsNone(m)

        s = " *** X is now known as Y"
        m = pattern.match(s)
        self.assertIsNone(m)

        # There is not a message
        s = "*** X "
        m = pattern.match(s)
        self.assertIsNone(m)

    def test_empty_pattern(self):
        """Test the validation of empty lines"""

        pattern = SupybotParser.SUPYBOT_EMPTY_REGEX

        # These should be valid empty lines
        s = "         "
        m = pattern.match(s)
        self.assertIsNotNone(m)

        s = ""
        m = pattern.match(s)
        self.assertIsNotNone(m)

        s = " \t    \t \r"
        m = pattern.match(s)
        self.assertIsNotNone(m)


if __name__ == "__main__":
    unittest.main()
