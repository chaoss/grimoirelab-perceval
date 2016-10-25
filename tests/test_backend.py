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

import argparse
import datetime
import sys
import unittest

if not '..' in sys.path:
    sys.path.insert(0, '..')

from perceval import __version__
from perceval.backend import (Backend,
                              BackendCommand,
                              metadata,
                              uuid)


class TestBackend(unittest.TestCase):
    """Unit tests for Backend"""

    def test_version(self):
        """Test whether the backend version is initialized"""

        self.assertEqual(Backend.version, '0.4')

        b = Backend('test')
        self.assertEqual(b.version, '0.4')

    def test_origin(self):
        """Test whether origin value is initialized"""

        b = Backend('test')
        self.assertEqual(b.origin, 'test')

    def test_tag(self):
        """Test whether tag value is initializated"""

        b = Backend('test')
        self.assertEqual(b.origin, 'test')
        self.assertEqual(b.tag, 'test')

        b = Backend('test', tag='mytag')
        self.assertEqual(b.origin, 'test')
        self.assertEqual(b.tag, 'mytag')

    def test_cache_value_error(self):
        """Test whether it raises a error on invalid cache istances"""

        with self.assertRaises(ValueError):
            Backend('test', cache=8)


class TestBackendCommand(unittest.TestCase):
    """Unit tests for BackendCommand"""

    def test_parsing_on_init(self):
        """Test if the arguments are parsed when the class is initialized"""

        args = ['-u', 'jsmith', '-p', '1234', '-t', 'abcd',
                '--from-date', '2015-01-01', '--tag', 'test']

        cmd = BackendCommand(*args)

        self.assertIsInstance(cmd.parsed_args, argparse.Namespace)
        self.assertEqual(cmd.parsed_args.backend_user, 'jsmith')
        self.assertEqual(cmd.parsed_args.backend_password, '1234')
        self.assertEqual(cmd.parsed_args.backend_token, 'abcd')
        self.assertEqual(cmd.parsed_args.from_date, '2015-01-01')
        self.assertEqual(cmd.parsed_args.tag, 'test')

    def test_argument_parser(self):
        """Test if it returns a argument parser object"""

        parser = BackendCommand.create_argument_parser()
        self.assertIsInstance(parser, argparse.ArgumentParser)


class MockDecoratorBackend(Backend):
    """Mock backend to test metadata decorators"""

    version = '0.2.0'

    def __init__(self, origin, tag=None):
        super().__init__(origin, tag=tag)

    @metadata
    def fetch(self, from_date=None):
        for x in range(5):
            item = {'item' : x}
            yield item

    @metadata
    def fetch_from_cache(self):
        for x in range(5):
            item = {'item' : x}
            yield item

    @staticmethod
    def metadata_id(item):
        return str(item['item'])

    @staticmethod
    def metadata_updated_on(item):
        return '2016-01-01'

    @staticmethod
    def metadata_category(item):
        return 'mock_item'


class TestMetadata(unittest.TestCase):
    """Test metadata decorator"""

    def test_decorator(self):
        backend = MockDecoratorBackend('test', 'mytag')
        before = datetime.datetime.now().timestamp()
        items = [item for item in backend.fetch()]
        after = datetime.datetime.now().timestamp()

        for x in range(5):
            item = items[x]

            expected_uuid = uuid('test', str(x))

            self.assertEqual(item['data']['item'], x)
            self.assertEqual(item['backend_name'], 'MockDecoratorBackend')
            self.assertEqual(item['backend_version'], '0.2.0')
            self.assertEqual(item['perceval_version'], __version__)
            self.assertEqual(item['origin'], 'test')
            self.assertEqual(item['uuid'], expected_uuid)
            self.assertEqual(item['updated_on'], '2016-01-01')
            self.assertEqual(item['category'], 'mock_item')
            self.assertEqual(item['tag'], 'mytag')
            self.assertGreater(item['timestamp'], before)
            self.assertLess(item['timestamp'], after)

            before = item['timestamp']


class TestUUID(unittest.TestCase):
    """Unit tests for uuid function"""

    def test_uuid(self):
        """Check whether the function returns the expected UUID"""

        result = uuid('1', '2', '3', '4')
        self.assertEqual(result, 'e7b71c81f5a0723e2237f157dba81777ce7c6c21')

        result = uuid('http://example.com/', '1234567')
        self.assertEqual(result, '47509b2f0d4ffc513ca9230838a69aa841d7f055')

    def test_non_str_value(self):
        """Check whether a UUID cannot be generated when a given value is not a str"""

        self.assertRaises(ValueError, uuid, '1', '2', 3, '4')
        self.assertRaises(ValueError, uuid, 0, '1', '2', '3')
        self.assertRaises(ValueError, uuid, '1', '2', '3', 4.0)

    def test_none_value(self):
        """Check whether a UUID cannot be generated when a given value is None"""

        self.assertRaises(ValueError, uuid, '1', '2', None, '3')
        self.assertRaises(ValueError, uuid, None, '1', '2', '3')
        self.assertRaises(ValueError, uuid, '1', '2', '3', None)

    def test_empty_value(self):
        """Check whether a UUID cannot be generated when a given value is empty"""

        self.assertRaises(ValueError, uuid, '1', '', '2', '3')
        self.assertRaises(ValueError, uuid, '', '1', '2', '3')
        self.assertRaises(ValueError, uuid, '1', '2', '3', '')


if __name__ == "__main__":
    unittest.main()
