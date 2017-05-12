#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2015-2017 Bitergia
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
# Foundation, 51 Franklin Street, Fifth Floor, Boston, MA 02110-1335, USA.
#
# Authors:
#     Santiago Dueñas <sduenas@bitergia.com>
#

import argparse
import datetime
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
import unittest.mock

import dateutil.tz

from grimoirelab.toolkit.datetime import InvalidDateError

if '..' not in sys.path:
    sys.path.insert(0, '..')

from perceval import __version__
from perceval.backend import (Backend,
                              BackendCommandArgumentParser,
                              BackendCommand,
                              metadata,
                              uuid)
from perceval.cache import Cache
from perceval.utils import DEFAULT_DATETIME


class TestBackend(unittest.TestCase):
    """Unit tests for Backend"""

    def setUp(self):
        self.test_path = tempfile.mkdtemp(prefix='perceval_')

    def tearDown(self):
        shutil.rmtree(self.test_path)

    def test_version(self):
        """Test whether the backend version is initialized"""

        self.assertEqual(Backend.version, '0.5')

        b = Backend('test')
        self.assertEqual(b.version, '0.5')

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

    def test_cache(self):
        """Test whether cache value is initializated"""

        cache_path = os.path.join(self.test_path, 'mockrepo')
        cache = Cache(cache_path)

        b = Backend('test', cache=cache)
        self.assertEqual(b.cache, cache)

        b = Backend('test')
        self.assertEqual(b.cache, None)

        b.cache = cache
        self.assertEqual(b.cache, cache)

    def test_cache_value_error(self):
        """Test whether it raises a error on invalid cache istances"""

        with self.assertRaises(ValueError):
            Backend('test', cache=8)

        b = Backend('test')

        with self.assertRaises(ValueError):
            b.cache = 8


class TestBackendCommandArgumentParser(unittest.TestCase):
    """Unit tests for BackendCommandArgumentParser"""

    def test_argument_parser(self):
        """Test if an argument parser object is created on initialization"""

        parser = BackendCommandArgumentParser()
        self.assertIsInstance(parser.parser, argparse.ArgumentParser)

    def test_parse_default_args(self):
        """Test if the default configured arguments are parsed"""

        args = ['--tag', 'test']

        parser = BackendCommandArgumentParser()
        parsed_args = parser.parse(*args)

        self.assertIsInstance(parsed_args, argparse.Namespace)
        self.assertEqual(parsed_args.tag, 'test')

    def test_parse_with_aliases(self):
        """Test if a set of aliases is created after parsing"""

        aliases = {
            'label': 'tag',
            'label2': 'tag',
            'newdate': 'from_date',
            'from_date': 'tag',
            'notfound': 'backend_token'
        }
        parser = BackendCommandArgumentParser(from_date=True,
                                              aliases=aliases)

        args = ['--tag', 'test', '--from-date', '2015-01-01']
        parsed_args = parser.parse(*args)

        expected_dt = datetime.datetime(2015, 1, 1, 0, 0,
                                        tzinfo=dateutil.tz.tzutc())

        self.assertIsInstance(parsed_args, argparse.Namespace)
        self.assertEqual(parsed_args.tag, 'test')
        self.assertEqual(parsed_args.from_date, expected_dt)

        # Check aliases
        self.assertEqual(parsed_args.label, 'test')
        self.assertEqual(parsed_args.label2, 'test')
        self.assertEqual(parsed_args.newdate, expected_dt)
        self.assertNotIn('notfound', parsed_args)

    def test_parse_date_args(self):
        """Test if date parameters are parsed"""

        parser = BackendCommandArgumentParser(from_date=True,
                                              to_date=True)

        # Check default value
        args = []
        parsed_args = parser.parse(*args)

        self.assertEqual(parsed_args.from_date, DEFAULT_DATETIME)
        self.assertEqual(parsed_args.to_date, None)

        # Check argument 'from-date'
        args = ['--from-date', '2015-01-01']
        parsed_args = parser.parse(*args)

        expected = datetime.datetime(2015, 1, 1, 0, 0,
                                     tzinfo=dateutil.tz.tzutc())
        self.assertEqual(parsed_args.from_date, expected)
        self.assertEqual(parsed_args.to_date, None)

        # Invalid 'from-date'
        args = ['--from-date', 'asdf']

        with self.assertRaises(InvalidDateError):
            parsed_args = parser.parse(*args)

        # Check argument 'to-date'
        args = ['--to-date', '2016-01-01']
        parsed_args = parser.parse(*args)

        expected_dt = datetime.datetime(2016, 1, 1, 0, 0,
                                        tzinfo=dateutil.tz.tzutc())
        self.assertEqual(parsed_args.from_date, DEFAULT_DATETIME)
        self.assertEqual(parsed_args.to_date, expected_dt)

        # Invalid 'to-date'
        args = ['--to-date', 'asdf']

        with self.assertRaises(InvalidDateError):
            parsed_args = parser.parse(*args)

        # Check both arguments
        args = ['--from-date', '2015-01-01', '--to-date', '2016-01-01']
        parsed_args = parser.parse(*args)

        self.assertEqual(parsed_args.from_date, expected)
        self.assertEqual(parsed_args.to_date, expected_dt)

    def test_parse_offset_arg(self):
        """Test if offset parameter is parsed"""

        parser = BackendCommandArgumentParser(offset=True)

        # Check default value
        args = []
        parsed_args = parser.parse(*args)

        self.assertEqual(parsed_args.offset, 0)

        # Check argument
        args = ['--offset', '88']
        parsed_args = parser.parse(*args)

        self.assertEqual(parsed_args.offset, 88)

    def test_incompatible_date_and_offset(self):
        """Test if date and offset arguments are incompatible"""

        with self.assertRaises(AttributeError):
            _ = BackendCommandArgumentParser(from_date=True,
                                             offset=True)
        with self.assertRaises(AttributeError):
            _ = BackendCommandArgumentParser(to_date=True,
                                             offset=True)
        with self.assertRaises(AttributeError):
            _ = BackendCommandArgumentParser(from_date=True,
                                             to_date=True,
                                             offset=True)

    def test_parse_auth_args(self):
        """Test if the authtentication arguments are parsed"""

        args = ['-u', 'jsmith', '-p', '1234', '-t', 'abcd']

        parser = BackendCommandArgumentParser(basic_auth=True,
                                              token_auth=True)
        parsed_args = parser.parse(*args)

        self.assertIsInstance(parsed_args, argparse.Namespace)
        self.assertEqual(parsed_args.user, 'jsmith')
        self.assertEqual(parsed_args.password, '1234')
        self.assertEqual(parsed_args.api_token, 'abcd')

    def test_parse_cache_args(self):
        """Test if the authtentication arguments are parsed"""

        args = ['--cache-path', '/tmp/cache',
                '--clean-cache', '--fetch-cache']

        parser = BackendCommandArgumentParser(cache=True)
        parsed_args = parser.parse(*args)

        self.assertIsInstance(parsed_args, argparse.Namespace)
        self.assertEqual(parsed_args.cache_path, '/tmp/cache')
        self.assertEqual(parsed_args.clean_cache, True)
        self.assertEqual(parsed_args.fetch_cache, True)
        self.assertEqual(parsed_args.no_cache, False)

    def test_incompatible_fetch_cache_and_no_cache(self):
        """Test if fetch-cache and no-cache arguments are incompatible"""

        args = ['--fetch-cache', '--no-cache']
        parser = BackendCommandArgumentParser(cache=True)

        with self.assertRaises(AttributeError):
            _ = parser.parse(*args)


class MockedBackend(Backend):
    """Mocked backend for testing"""

    version = '0.2.0'

    def __init__(self, origin, tag=None):
        super().__init__(origin, tag=tag)

    @metadata
    def fetch(self, from_date=None):
        for x in range(5):
            item = {'item': x}
            yield item

    @metadata
    def fetch_from_cache(self):
        for x in range(5):
            item = {
                'item': x,
                'cache': True
            }
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


class MockedBackendCommand(BackendCommand):
    """Mocked backend command class used for testing"""

    BACKEND = MockedBackend

    def __init__(self, *args):
        super().__init__(*args)

    def _pre_init(self):
        setattr(self.parsed_args, 'pre_init', True)

    def _post_init(self):
        setattr(self.parsed_args, 'post_init', True)

    @staticmethod
    def setup_cmd_parser():
        parser = BackendCommandArgumentParser(from_date=True,
                                              basic_auth=True,
                                              token_auth=True,
                                              cache=True)
        parser.parser.add_argument('origin')

        return parser


def convert_cmd_output_to_json(filepath):
    """Transforms the output of a BackendCommand into json objects"""

    with open(filepath) as fout:
        buff = None

        for line in fout.readlines():
            if line.startswith('{\n'):
                buff = line
            elif line.startswith('}\n'):
                buff += line
                obj = json.loads(buff)
                yield obj
            else:
                buff += line


class TestBackendCommand(unittest.TestCase):
    """Unit tests for BackendCommand"""

    def setUp(self):
        self.test_path = tempfile.mkdtemp(prefix='perceval_')
        self.fout_path = tempfile.mktemp(dir=self.test_path)

    def tearDown(self):
        shutil.rmtree(self.test_path)

    def test_parsing_on_init(self):
        """Test if the arguments are parsed when the class is initialized"""

        args = ['-u', 'jsmith', '-p', '1234', '-t', 'abcd',
                '--cache-path', self.test_path, '--fetch-cache',
                '--from-date', '2015-01-01', '--tag', 'test',
                '--output', self.fout_path, 'http://example.com/']

        dt_expected = datetime.datetime(2015, 1, 1, 0, 0,
                                        tzinfo=dateutil.tz.tzutc())

        cmd = MockedBackendCommand(*args)

        self.assertIsInstance(cmd.parsed_args, argparse.Namespace)
        self.assertEqual(cmd.parsed_args.user, 'jsmith')
        self.assertEqual(cmd.parsed_args.password, '1234')
        self.assertEqual(cmd.parsed_args.api_token, 'abcd')
        self.assertEqual(cmd.parsed_args.cache_path, self.test_path)
        self.assertEqual(cmd.parsed_args.fetch_cache, True)
        self.assertEqual(cmd.parsed_args.from_date, dt_expected)
        self.assertEqual(cmd.parsed_args.tag, 'test')

        self.assertIsInstance(cmd.outfile, io.TextIOWrapper)
        self.assertEqual(cmd.outfile.name, self.fout_path)

        self.assertIsInstance(cmd.backend, MockedBackend)
        self.assertEqual(cmd.backend.origin, 'http://example.com/')
        self.assertEqual(cmd.backend.tag, 'test')

        cmd.outfile.close()

    @unittest.mock.patch('os.path.expanduser')
    def test_cache_on_init(self, mock_expanduser):
        """Test if the cache is set when the class is initialized"""

        mock_expanduser.return_value = self.test_path

        args = ['-u', 'jsmith', '-p', '1234', '-t', 'abcd',
                '--from-date', '2015-01-01', '--tag', 'test',
                '--output', self.fout_path, 'http://example.com/']

        cmd = MockedBackendCommand(*args)

        cache = cmd.backend.cache
        self.assertIsInstance(cache, Cache)
        self.assertEqual(os.path.exists(cache.cache_path), True)
        self.assertEqual(cache.cache_path,
                         os.path.join(self.test_path, 'http://example.com/'))

        # Due to '--no-cache' is not given, no cache object is set
        args = ['-u', 'jsmith', '-p', '1234', '-t', 'abcd',
                '--no-cache', '--from-date', '2015-01-01',
                '--tag', 'test', '--output', self.fout_path,
                'http://example.com/']

        cmd = MockedBackendCommand(*args)
        self.assertEqual(cmd.backend.cache, None)

    def test_pre_init(self):
        """Test if pre_init method is called during initialization"""

        args = ['http://example.com/']

        cmd = MockedBackendCommand(*args)
        self.assertEqual(cmd.parsed_args.pre_init, True)

    def test_post_init(self):
        """Test if post_init method is called during initialization"""

        args = ['http://example.com/']

        cmd = MockedBackendCommand(*args)
        self.assertEqual(cmd.parsed_args.post_init, True)

    def test_run(self):
        """Test run method"""

        args = ['-u', 'jsmith', '-p', '1234', '-t', 'abcd',
                '--cache-path', self.test_path,
                '--from-date', '2015-01-01', '--tag', 'test',
                '--output', self.fout_path, 'http://example.com/']

        cmd = MockedBackendCommand(*args)
        cmd.run()
        cmd.outfile.close()

        items = [item for item in convert_cmd_output_to_json(self.fout_path)]

        self.assertEqual(len(items), 5)

        for x in range(5):
            item = items[x]
            expected_uuid = uuid('http://example.com/', str(x))

            self.assertEqual(item['data']['item'], x)
            self.assertEqual(item['origin'], 'http://example.com/')
            self.assertEqual(item['uuid'], expected_uuid)
            self.assertEqual(item['tag'], 'test')

        self.assertIsInstance(cmd.backend.cache, Cache)

    def test_run_fetch_cache(self):
        """Test whether the command runs when fetch from cache is set"""

        args = ['--cache-path', self.test_path, '--fetch-cache',
                '--from-date', '2015-01-01', '--tag', 'test',
                '--output', self.fout_path, 'http://example.com/']

        cmd = MockedBackendCommand(*args)
        cmd.run()
        cmd.outfile.close()

        items = [item for item in convert_cmd_output_to_json(self.fout_path)]

        self.assertEqual(len(items), 5)

        for x in range(5):
            item = items[x]
            expected_uuid = uuid('http://example.com/', str(x))

            # MockedBackend sets 'cache' value when
            # 'fetch_from_cache' is called
            self.assertEqual(item['data']['item'], x)
            self.assertEqual(item['data']['cache'], True)
            self.assertEqual(item['origin'], 'http://example.com/')
            self.assertEqual(item['uuid'], expected_uuid)
            self.assertEqual(item['tag'], 'test')

        self.assertIsInstance(cmd.backend.cache, Cache)

    def test_run_no_cache(self):
        """Test whether the command runs when cache is not set"""

        args = ['--no-cache', '--from-date', '2015-01-01',
                '--tag', 'test', '--output', self.fout_path,
                'http://example.com/']

        cmd = MockedBackendCommand(*args)
        cmd.run()
        cmd.outfile.close()

        items = [item for item in convert_cmd_output_to_json(self.fout_path)]

        self.assertEqual(len(items), 5)

        for x in range(5):
            item = items[x]
            expected_uuid = uuid('http://example.com/', str(x))

            self.assertEqual(item['data']['item'], x)
            self.assertEqual(item['origin'], 'http://example.com/')
            self.assertEqual(item['uuid'], expected_uuid)
            self.assertEqual(item['tag'], 'test')

        self.assertIsNone(cmd.backend.cache)


class TestMetadata(unittest.TestCase):
    """Test metadata decorator"""

    def test_decorator(self):
        backend = MockedBackend('test', 'mytag')
        before = datetime.datetime.utcnow().timestamp()
        items = [item for item in backend.fetch()]
        after = datetime.datetime.utcnow().timestamp()

        for x in range(5):
            item = items[x]

            expected_uuid = uuid('test', str(x))

            self.assertEqual(item['data']['item'], x)
            self.assertEqual(item['backend_name'], 'MockedBackend')
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
