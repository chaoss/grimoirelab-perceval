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

import argparse
import datetime
import os
import shutil
import sys
import tempfile
import unittest

if not '..' in sys.path:
    sys.path.insert(0, '..')

from perceval.backends.supybot import Supybot, SupybotCommand, SupybotParser
from perceval.errors import ParseError


class TestSupybotBackend(unittest.TestCase):
    """Supybot backend unit tests"""

    @classmethod
    def setUpClass(cls):
        cls.tmp_path = tempfile.mkdtemp(prefix='perceval_')
        shutil.copy('data/supybot_2012_10_17.log',
                    os.path.join(cls.tmp_path, '#supybot_2012-10-17.log'))
        shutil.copy('data/supybot_2012_10_18.log',
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

    def test_has_caching(self):
        """Test if it returns False when has_caching is called"""

        self.assertEqual(Supybot.has_caching(), False)

    def test_has_resuming(self):
        """Test if it returns True when has_resuming is called"""

        self.assertEqual(Supybot.has_resuming(), True)

    def test_fetch(self):
        """Test if it parses a set of log files"""

        backend = Supybot('http://example.com/', self.tmp_path)
        messages = [m for m in backend.fetch()]

        expected = [('benpol', 'comment', '89b0d9fdbc3972aed183876f7f5ee2617542665c', 1350465381.0),
                    ('benpol', 'comment', '81b1fbe651b58d6a4ef6fff026658f87b7c393fc', 1350465389.0),
                    ('benpol', 'comment', 'bb72ef7fca57e89a7b46826cc0029713fbeba8d7', 1350465395.0),
                    ('MikeMcClurg', 'server', '6f873e788e289acca517a1c04eaa3e8557191f99', 1350465410.0),
                    ('Tv_', 'server', 'fe19251eb5068bb7a14892960574b565b100fb29', 1350465411.0),
                    ('benpol', 'comment', 'ec3206582c534cb725bc5153b5037089441735d3', 1350465447.0),
                    ('Tv_', 'comment', '06b6fe28cdb55247d03430e72986068fdb168723',  1350465528.0),
                    ('jamespage', 'comment', '42a71797a6bd75c01b4de9476006e73ed14c0340', 1350552630.0),
                    ('LarsFronius_', 'server', '839f98f69f4d5c22973abaf67bc2931682e9a79b', 1350552630.0),
                    ('bchrisman', 'server', '2e2ea19565203033622e005d8b5a004b4763d770', 1350552658.0),
                    ('scuttlemonkey', 'comment', 'b756d43392386c6ed0d329a45d2afcbc11a9afe0', 1350552785.0),
                    ('loicd', 'server', '5a4fc4c6bd5903ababaaa391b2a53ba1178ee75a', 1350584011.0),
                    ('sagelap1', 'server', 'c68e87799f13dc346d580cc56daec0189f232276', 1350584041.0)]

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

    def test_fetch_from_date(self):
        """Test whether a list of messages is returned since a given date"""

        from_date = datetime.datetime(2012, 10, 18, 9, 33, 5)

        backend = Supybot('http://example.com/', self.tmp_path)
        messages = [m for m in backend.fetch(from_date=from_date)]

        expected = [('scuttlemonkey', 'comment', 'b756d43392386c6ed0d329a45d2afcbc11a9afe0', 1350552785.0),
                    ('loicd', 'server', '5a4fc4c6bd5903ababaaa391b2a53ba1178ee75a', 1350584011.0),
                    ('sagelap1', 'server', 'c68e87799f13dc346d580cc56daec0189f232276', 1350584041.0)]

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
        messages = Supybot.parse_supybot_log('data/supybot_valid.log')
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
            messages = Supybot.parse_supybot_log('data/supybot_invalid_msg.log')
            _ = [message for message in messages]


class TestSupybotCommand(unittest.TestCase):
    """Supybot unit tests"""

    def test_parsing_on_init(self):
        """Test if the class is initialized"""

        args = ['--tag', 'test',
                'http://example.com', '/tmp/supybot']

        cmd = SupybotCommand(*args)
        self.assertIsInstance(cmd.parsed_args, argparse.Namespace)
        self.assertEqual(cmd.parsed_args.tag, 'test')
        self.assertEqual(cmd.parsed_args.uri, 'http://example.com')
        self.assertEqual(cmd.parsed_args.ircdir, '/tmp/supybot')
        self.assertIsInstance(cmd.backend, Supybot)

    def test_argument_parser(self):
        """Test if it returns a argument parser object"""

        parser = SupybotCommand.create_argument_parser()
        self.assertIsInstance(parser, argparse.ArgumentParser)


class TestSupybotParser(unittest.TestCase):
    """SupybotParser unit tests"""

    def test_parser(self):
        """Test whether it parses a valid Supybot IRC log stream"""

        with open("data/supybot_valid.log", 'r') as f:
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

    def test_comment_action_pattern(self):
        """Test the validation of comment action lines"""

        pattern = SupybotParser.SUPYBOT_COMMENT_ACTION_REGEX

        # These should have valid nicks and messages
        s = "* mynick is waving hello"
        m = pattern.match(s)
        self.assertEqual(m.group('nick'), 'mynick')
        self.assertEqual(m.group('body'), "mynick is waving hello")

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


if __name__ == "__main__":
    unittest.main()
