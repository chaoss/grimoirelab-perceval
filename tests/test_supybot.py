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
#     Harshal Mittal <harshalmittal4@gmail.com>
#

import datetime
import os
import pkg_resources
import shutil
import tempfile
import unittest

pkg_resources.declare_namespace('perceval.backends')

from perceval.backend import BackendCommandArgumentParser
from perceval.errors import ParseError
from perceval.utils import DEFAULT_DATETIME
from perceval.backends.core.supybot import (Supybot,
                                            SupybotCommand,
                                            SupybotParser)


class TestSupybotBackend(unittest.TestCase):
    """Supybot backend unit tests"""

    @classmethod
    def setUpClass(cls):
        cls.tmp_path = tempfile.mkdtemp(prefix='perceval_')
        shutil.copy(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data/supybot/supybot_2012_10_17.log'),
                    os.path.join(cls.tmp_path, '#supybot_2012-10-17.log'))
        shutil.copy(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data/supybot/supybot_2012_10_18.log'),
                    os.path.join(cls.tmp_path, '#supybot_2012-10-18.log'))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp_path)

    def test_initialization(self):
        """Test whether attributes are initializated"""

        backend = Supybot('http://example.com/', self.tmp_path, tag='test')

        self.assertEqual(backend.uri, 'http://example.com/')
        self.assertEqual(backend.dirpath, self.tmp_path)
        self.assertEqual(backend.origin, 'http://example.com/')
        self.assertEqual(backend.tag, 'test')

        # When tag is empty or None it will be set to
        # the value in uri
        backend = Supybot('http://example.com/', self.tmp_path)
        self.assertEqual(backend.origin, 'http://example.com/')
        self.assertEqual(backend.tag, 'http://example.com/')

        backend = Supybot('http://example.com/', self.tmp_path, tag='')
        self.assertEqual(backend.origin, 'http://example.com/')
        self.assertEqual(backend.tag, 'http://example.com/')

    def test_has_archiving(self):
        """Test if it returns False when has_archiving is called"""

        self.assertEqual(Supybot.has_archiving(), False)

    def test_has_resuming(self):
        """Test if it returns True when has_resuming is called"""

        self.assertEqual(Supybot.has_resuming(), True)

    def test_fetch(self):
        """Test if it parses a set of log files"""

        backend = Supybot('http://example.com/', self.tmp_path)
        messages = [m for m in backend.fetch()]

        expected = [('benpol', 'comment', '86cd62e954f3c81f2efd336b163b673419e722c4', 1350465381.0),
                    ('benpol', 'comment', 'c3d38be79806e98b50d308f4fdf078ed89aef68c', 1350465389.0),
                    ('benpol', 'comment', '7f68a35c1515a82e2731312eb38b07b7d62f66a0', 1350465395.0),
                    ('MikeMcClurg', 'server', '175bf289ff1340275b358dad90887e031628942d', 1350465410.0),
                    ('Tv_', 'server', '1952a9ee3b87144f608aa2a84271ff7d6871e1c8', 1350465411.0),
                    ('benpol', 'comment', '17730fed09f82ea9d0a770ec6167df5a9ea9060c', 1350465447.0),
                    ('benpol', 'comment', '6d1b61c2839218c170c9bd775edcb02caaf921f5', 1350465460.0),
                    ('Tv_', 'comment', '395fa8fb2e6aafa8f3618746dcc56f2fdfe35eac', 1350465528.0),
                    ('jamespage', 'comment', '056408f3064b80e69490fd65ff0d066431592b0f', 1350552630.0),
                    ('LarsFronius_', 'server', '319701fa6768a935d08ae5d5afb2d058122030d4', 1350552630.0),
                    ('bchrisman', 'server', '291faf2760c39f672e9900d509908e77153e930a', 1350552658.0),
                    ('scuttlemonkey', 'comment', '768843f086ef41b2346eff72c8f2935b0e23148c', 1350552785.0),
                    ('loicd', 'server', 'f4cdf0c9c3219d5931f704438d85a7665ad6d99e', 1350584011.0),
                    ('sagelap1', 'server', 'ac3dd25dbcaf068f061a20263140a34cb354950d', 1350584041.0),
                    ('guyfry', 'comment', 'cdd33f7c0f436b6f5299b969f27932a5454d15bb', 1350588930.0),
                    ('guyfry', 'comment', '4d055dc4d487c3860391a2bf8b08ce48d97b11ca', 1350588930.0)]

        self.assertEqual(len(messages), len(expected))

        for x in range(len(messages)):
            message = messages[x]
            self.assertEqual(message['data']['nick'], expected[x][0])
            self.assertEqual(message['data']['type'], expected[x][1])
            self.assertEqual(message['origin'], 'http://example.com/')
            self.assertEqual(message['uuid'], expected[x][2])
            self.assertEqual(message['updated_on'], expected[x][3])
            self.assertEqual(message['category'], 'message')
            self.assertEqual(message['tag'], 'http://example.com/')

    def test_search_fields(self):
        """Test whether the search_fields is properly set"""

        backend = Supybot('http://example.com/', self.tmp_path)
        messages = [m for m in backend.fetch()]

        message = messages[0]
        self.assertEqual(backend.metadata_id(message['data']), message['search_fields']['item_id'])

        message = messages[1]
        self.assertEqual(backend.metadata_id(message['data']), message['search_fields']['item_id'])

        message = messages[2]
        self.assertEqual(backend.metadata_id(message['data']), message['search_fields']['item_id'])

        message = messages[3]
        self.assertEqual(backend.metadata_id(message['data']), message['search_fields']['item_id'])

    def test_fetch_from_date(self):
        """Test whether a list of messages is returned since a given date"""

        from_date = datetime.datetime(2012, 10, 18, 9, 33, 5)

        backend = Supybot('http://example.com/', self.tmp_path)
        messages = [m for m in backend.fetch(from_date=from_date)]

        expected = [('scuttlemonkey', 'comment', '768843f086ef41b2346eff72c8f2935b0e23148c', 1350552785.0),
                    ('loicd', 'server', 'f4cdf0c9c3219d5931f704438d85a7665ad6d99e', 1350584011.0),
                    ('sagelap1', 'server', 'ac3dd25dbcaf068f061a20263140a34cb354950d', 1350584041.0),
                    ('guyfry', 'comment', 'cdd33f7c0f436b6f5299b969f27932a5454d15bb', 1350588930.0),
                    ('guyfry', 'comment', '4d055dc4d487c3860391a2bf8b08ce48d97b11ca', 1350588930.0)]

        for x in range(len(messages)):
            message = messages[x]
            self.assertEqual(message['data']['nick'], expected[x][0])
            self.assertEqual(message['data']['type'], expected[x][1])
            self.assertEqual(message['origin'], 'http://example.com/')
            self.assertEqual(message['uuid'], expected[x][2])
            self.assertEqual(message['updated_on'], expected[x][3])
            self.assertEqual(message['category'], 'message')
            self.assertEqual(message['tag'], 'http://example.com/')

    def test_parse_supybot_log(self):
        """Test whether it parses a log"""

        # Empty lines and empty comment lines are ignored
        messages = Supybot.parse_supybot_log(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                          'data/supybot/supybot_valid.log'))
        messages = [m for m in messages]

        self.assertEqual(len(messages), 97)

        msg = messages[1]
        self.assertEqual(msg['timestamp'], '2012-10-17T09:16:29+0000')
        self.assertEqual(msg['type'], SupybotParser.TCOMMENT)
        self.assertEqual(msg['nick'], 'benpol')
        self.assertEqual(msg['body'], "they're related to fragmentation?")

        msg = messages[-2]
        self.assertEqual(msg['timestamp'], '2012-10-17T23:42:10+0000')
        self.assertEqual(msg['type'], SupybotParser.TCOMMENT)
        self.assertEqual(msg['nick'], 'supy-bot')
        self.assertEqual(msg['body'], "[backend] Fix bug #23: invalid timestamp")

        msg = messages[-1]
        self.assertEqual(msg['timestamp'], '2012-10-17T23:42:26+0000')
        self.assertEqual(msg['type'], SupybotParser.TCOMMENT)
        self.assertEqual(msg['nick'], 'gregaf')
        self.assertEqual(msg['body'], "but I may be wrong or debugging at the wrong level...")

    def test_parse_supybot_invalid_log(self):
        """Test whether it raises an exception when the log is invalid"""

        with self.assertRaises(ParseError):
            messages = Supybot.parse_supybot_log(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                              'data/supybot/supybot_invalid_msg.log'))
            _ = [message for message in messages]


class TestSupybotCommand(unittest.TestCase):
    """Supybot unit tests"""

    def test_backend_class(self):
        """Test if the backend class is Supybot"""

        self.assertIs(SupybotCommand.BACKEND, Supybot)

    def test_setup_cmd_parser(self):
        """Test if it parser object is correctly initialized"""

        parser = SupybotCommand.setup_cmd_parser()
        self.assertIsInstance(parser, BackendCommandArgumentParser)
        self.assertEqual(parser._backend, Supybot)

        args = ['--tag', 'test',
                '--from-date', '1970-01-01',
                'http://example.com', '/tmp/supybot']

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.tag, 'test')
        self.assertEqual(parsed_args.uri, 'http://example.com')
        self.assertEqual(parsed_args.dirpath, '/tmp/supybot')
        self.assertEqual(parsed_args.from_date, DEFAULT_DATETIME)


class TestSupybotParser(unittest.TestCase):
    """SupybotParser unit tests"""

    def test_parser(self):
        """Test whether it parses a valid Supybot IRC log stream"""

        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "data/supybot/supybot_valid.log"), 'r') as f:
            parser = SupybotParser(f)
            items = [item for item in parser.parse()]

        self.assertEqual(len(items), 97)

        item = items[1]
        self.assertEqual(item['timestamp'], '2012-10-17T09:16:29+0000')
        self.assertEqual(item['type'], SupybotParser.TCOMMENT)
        self.assertEqual(item['nick'], 'benpol')
        self.assertEqual(item['body'], "they're related to fragmentation?")

        item = items[2]
        self.assertEqual(item['timestamp'], '2012-10-17T09:16:35+0000')
        self.assertEqual(item['type'], SupybotParser.TCOMMENT)
        self.assertEqual(item['nick'], 'benpol')
        self.assertEqual(item['body'], "benpol is wondering...")

        item = items[3]
        self.assertEqual(item['timestamp'], '2012-10-17T09:16:50+0000')
        self.assertEqual(item['type'], SupybotParser.TSERVER)
        self.assertEqual(item['nick'], 'MikeMcClurg')
        self.assertEqual(item['body'], "MikeMcClurg has quit IRC")

        item = items[-2]
        self.assertEqual(item['timestamp'], '2012-10-17T23:42:10+0000')
        self.assertEqual(item['type'], SupybotParser.TCOMMENT)
        self.assertEqual(item['nick'], 'supy-bot')
        self.assertEqual(item['body'], "[backend] Fix bug #23: invalid timestamp")

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

        self.assertEqual(ncomments, 51)
        self.assertEqual(nserver, 46)

    def test_parse_invalid_date(self):
        """Test whether it raises an exception when a date is invalid"""

        with self.assertRaisesRegex(ParseError, "date expected on line 4"):
            with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "data/supybot/supybot_invalid_date.log"), 'r') as f:
                parser = SupybotParser(f)
                _ = [item for item in parser.parse()]

    def test_parse_invalid_message(self):
        """Test whether it raises an exception when an invalid line is found"""

        with self.assertRaisesRegex(ParseError, "invalid message on line 9"):
            with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "data/supybot/supybot_invalid_msg.log"), 'r') as f:
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

    def test_comment_action_pattern(self):
        """Test the validation of comment action lines"""

        pattern = SupybotParser.SUPYBOT_COMMENT_ACTION_REGEX

        # These should have valid nicks and messages
        s = "* mynick is waving hello"
        m = pattern.match(s)
        self.assertEqual(m.group('nick'), 'mynick')
        self.assertEqual(m.group('body'), "mynick is waving hello")

        s = "*mynick is waving goodbye"
        m = pattern.match(s)
        self.assertEqual(m.group('nick'), 'mynick')
        self.assertEqual(m.group('body'), "mynick is waving goodbye")

        # These messages are not valid

        # There are spaces at the beginning of the message
        s = " * mynick hello!"
        m = pattern.match(s)
        self.assertIsNone(m)

        # No message
        s = "* mynick "
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

    def test_bot_pattern(self):
        """Test the validation of bot lines"""

        pattern = SupybotParser.SUPYBOT_BOT_REGEX

        # These should have valid nicks and messages
        s = "-mybot- a message"
        m = pattern.match(s)
        self.assertEqual(m.group('nick'), 'mybot')
        self.assertEqual(m.group('body'), "a message")

        s = "-skynet-bot- [remove] skynet removed the internet #801"
        m = pattern.match(s)
        self.assertEqual(m.group('nick'), 'skynet-bot')
        self.assertEqual(m.group('body'), "[remove] skynet removed the internet #801")

        # These messages are not valid

        # Bot name not ends with - ***
        s = "-mybot a message"
        m = pattern.match(s)
        self.assertIsNone(m)

        # No message
        s = "-mybot-"
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

    def test_empty_comment_pattern(self):
        """Test the validation of empty comment lines"""

        pattern = SupybotParser.SUPYBOT_EMPTY_COMMENT_REGEX

        # These should be valid empty lines
        s = "<nick>"
        m = pattern.match(s)
        self.assertIsNotNone(m)

        s = "<nick>      \t \r "
        m = pattern.match(s)
        self.assertIsNotNone(m)

        # This is not a valid empty line
        s = "<nick>           \tmessage"
        m = pattern.match(s)
        self.assertIsNone(m)

    def test_empty_comment_action_pattern(self):
        """Test the validation of empty comment action lines"""

        pattern = SupybotParser.SUPYBOT_EMPTY_COMMENT_ACTION_REGEX

        # These should be valid empty lines
        s = "* nick"
        m = pattern.match(s)
        self.assertIsNotNone(m)

        s = "*nick"
        m = pattern.match(s)
        self.assertIsNotNone(m)

        s = "* nick      \t \r"
        m = pattern.match(s)
        self.assertIsNotNone(m)

        # These are not valid empty lines
        s = "* nick      \tmessage"
        m = pattern.match(s)
        self.assertIsNone(m)

        s = "*nick  message"
        m = pattern.match(s)
        self.assertIsNone(m)

    def test_empty_bot_pattern(self):
        """Test the validation of empty bot lines"""

        pattern = SupybotParser.SUPYBOT_EMPTY_BOT_REGEX

        # These should be valid empty lines
        s = "-mybot-"
        m = pattern.match(s)
        self.assertIsNotNone(m)

        s = "-mybot-  \t"
        m = pattern.match(s)
        self.assertIsNotNone(m)

        # These are not valid empty lines
        s = "-mybot-   message"
        m = pattern.match(s)
        self.assertIsNone(m)


if __name__ == "__main__":
    unittest.main()
