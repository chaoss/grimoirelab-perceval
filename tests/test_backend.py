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

import sys

if not '..' in sys.path:
    sys.path.insert(0, '..')

import argparse
import datetime
import unittest

from perceval.backend import Backend, BackendCommand, metadata


class TestBackend(unittest.TestCase):
    """Unit tests for Backend"""

    def test_version(self):
        """Test whether the backend version is initialized"""

        self.assertEqual(Backend.version, '0.1')

        b = Backend('test')
        self.assertEqual(b.version, '0.1')

    def test_origin(self):
        """Test whether origin value is initialized"""

        b = Backend('test')
        self.assertEqual(b.origin, 'test')

    def test_cache_value_error(self):
        """Test whether it raises a error on invalid cache istances"""

        with self.assertRaises(ValueError):
            Backend('test', cache=8)


class TestBackendCommand(unittest.TestCase):
    """Unit tests for BackendCommand"""

    def test_parsing_on_init(self):
        """Test if the arguments are parsed when the class is initialized"""

        args = ['-u', 'jsmith', '-p', '1234', '-t', 'abcd',
                '--from-date', '2015-01-01']

        cmd = BackendCommand(*args)

        self.assertIsInstance(cmd.parsed_args, argparse.Namespace)
        self.assertEqual(cmd.parsed_args.backend_user, 'jsmith')
        self.assertEqual(cmd.parsed_args.backend_password, '1234')
        self.assertEqual(cmd.parsed_args.backend_token, 'abcd')
        self.assertEqual(cmd.parsed_args.from_date, '2015-01-01')

    def test_argument_parser(self):
        """Test if it returns a argument parser object"""

        parser = BackendCommand.create_argument_parser()
        self.assertIsInstance(parser, argparse.ArgumentParser)


def mock_fnc_date(item):
    return '2016-01-01'


class MockDecoratorBackend(Backend):
    """Mock backend to test metadata decorators"""

    version = '0.1.0'

    def __init__(self, origin):
        super().__init__(origin)

    @metadata(mock_fnc_date)
    def fetch(self):
        for x in range(5):
            item = {'item' : x}
            yield item


class TestMetadata(unittest.TestCase):
    """Test metadata decorator"""

    def test_decorator(self):
        backend = MockDecoratorBackend('test')
        before = datetime.datetime.now().timestamp()
        items = [item for item in backend.fetch()]
        after = datetime.datetime.now().timestamp()

        for x in range(5):
            item = items[x]
            metadata = item['__metadata__']

            self.assertEqual(item['item'], x)
            self.assertEqual(metadata['backend_name'], 'MockDecoratorBackend')
            self.assertEqual(metadata['backend_version'], '0.1.0')
            self.assertEqual(metadata['origin'], 'test')
            self.assertEqual(metadata['updated_on'], '2016-01-01')
            self.assertGreater(metadata['timestamp'], before)
            self.assertLess(metadata['timestamp'], after)

            before = metadata['timestamp']


if __name__ == "__main__":
    unittest.main()
