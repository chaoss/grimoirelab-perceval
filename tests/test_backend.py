#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2015-2018 Bitergia
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
import sqlite3
import tempfile
import unittest
import unittest.mock

import dateutil.tz

from grimoirelab.toolkit.datetime import (InvalidDateError,
                                          datetime_utcnow,
                                          str_to_datetime)

from perceval.backends.core import __version__
from perceval.archive import Archive, ArchiveManager
from perceval.backend import (Backend,
                              BackendCommandArgumentParser,
                              BackendCommand,
                              uuid,
                              fetch,
                              fetch_from_archive)
from perceval.errors import ArchiveError, BackendError
from perceval.utils import DEFAULT_DATETIME
from base import TestCaseBackendArchive


class MockedBackend(Backend):
    """Mocked backend for testing"""

    version = '0.2.0'
    CATEGORY = "mock_item"
    CATEGORIES = [CATEGORY]
    ITEMS = 5

    def __init__(self, origin, tag=None, archive=None):
        super().__init__(origin, tag=tag, archive=archive)
        self._fetch_from_archive = False

    def fetch_items(self, category, **kwargs):
        for x in range(MockedBackend.ITEMS):
            if self._fetch_from_archive:
                item = self.archive.retrieve(str(x), None, None)
                yield item
            else:
                item = {'item': x}
                if self.archive:
                    self.archive.store(str(x), None, None, item)
                yield item

    def fetch(self, category=CATEGORY):
        return super().fetch(category)

    def _init_client(self, from_archive=False):
        self._fetch_from_archive = from_archive
        return None

    @staticmethod
    def metadata_id(item):
        return str(item['item'])

    @staticmethod
    def metadata_updated_on(item):
        return '2016-01-01'

    @staticmethod
    def metadata_category(item):
        return MockedBackend.CATEGORY


class CommandBackend(MockedBackend):
    """Backend used for testing in BackendCommand tests"""

    def fetch_items(self, category, **kwargs):
        for item in super().fetch_items(category, **kwargs):
            if self._fetch_from_archive:
                item['archive'] = True
            yield item


class ErrorCommandBackend(CommandBackend):
    """Backend which raises an exception while fetching items"""

    def fetch_items(self, category, **kwargs):
        for item in super().fetch_items(category, **kwargs):
            yield item
            raise BackendError(cause="Unhandled exception")


class MockedBackendCommand(BackendCommand):
    """Mocked backend command class used for testing"""

    BACKEND = CommandBackend

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
                                              archive=True)
        parser.parser.add_argument('origin')
        parser.parser.add_argument('--subtype', dest='subtype')

        return parser


class NoArchiveBackendCommand(BackendCommand):
    """Mocked backend command class used for testing which does not support archive"""

    BACKEND = CommandBackend

    def __init__(self, *args):
        super().__init__(*args)

    def _pre_init(self):
        setattr(self.parsed_args, 'pre_init', True)

    def _post_init(self):
        setattr(self.parsed_args, 'post_init', True)

    @staticmethod
    def setup_cmd_parser():
        parser = BackendCommandArgumentParser(from_date=True,
                                              archive=False)
        parser.parser.add_argument('origin')
        parser.parser.add_argument('--subtype', dest='subtype')

        return parser


class TestBackend(unittest.TestCase):
    """Unit tests for Backend"""

    def setUp(self):
        self.test_path = tempfile.mkdtemp(prefix='perceval_')

    def tearDown(self):
        shutil.rmtree(self.test_path)

    def test_version(self):
        """Test whether the backend version is initialized"""

        b = MockedBackend('test')
        self.assertEqual(b.version, MockedBackend.version)

    def test_origin(self):
        """Test whether origin value is initialized"""

        b = Backend('test')
        self.assertEqual(b.origin, 'test')

    def test_has_archiving(self):
        """Test whether an NotImplementedError exception is thrown"""

        b = Backend('test')

        with self.assertRaises(NotImplementedError):
            b.has_archiving()

    def test_has_resuming(self):
        """Test whether an NotImplementedError exception is thrown"""

        b = Backend('test')

        with self.assertRaises(NotImplementedError):
            b.has_resuming()

    def test_metadata_id(self):
        """Test whether an NotImplementedError exception is thrown"""

        b = Backend('test')

        with self.assertRaises(NotImplementedError):
            b.metadata_id(None)

    def test_metadata_updated_on(self):
        """Test whether an NotImplementedError exception is thrown"""

        b = Backend('test')

        with self.assertRaises(NotImplementedError):
            b.metadata_updated_on(None)

    def test_metadata_category(self):
        """Test whether an NotImplementedError exception is thrown"""

        b = Backend('test')

        with self.assertRaises(NotImplementedError):
            b.metadata_category(None)

    def test_tag(self):
        """Test whether tag value is initializated"""

        b = Backend('test')
        self.assertEqual(b.origin, 'test')
        self.assertEqual(b.tag, 'test')

        b = Backend('test', tag='mytag')
        self.assertEqual(b.origin, 'test')
        self.assertEqual(b.tag, 'mytag')

    def test_archive(self):
        """Test whether archive value is initializated"""

        archive_path = os.path.join(self.test_path, 'myarchive')
        archive = Archive.create(archive_path)

        b = Backend('test', archive=archive)
        self.assertEqual(b.archive, archive)

        b = Backend('test')
        self.assertEqual(b.archive, None)

        b.archive = archive
        self.assertEqual(b.archive, archive)

    def test_archive_value_error(self):
        """Test whether it raises a error on invalid archive istances"""

        with self.assertRaises(ValueError):
            Backend('test', archive=8)

        b = Backend('test')

        with self.assertRaises(ValueError):
            b.archive = 8

    def test_init_archive(self):
        """Test whether the archive is properly initialized when executing the fetch method"""

        archive_path = os.path.join(self.test_path, 'myarchive')
        archive = Archive.create(archive_path)
        b = MockedBackend('test', archive=archive)

        _ = [item for item in b.fetch()]

        self.assertEqual(b.archive.backend_name, b.__class__.__name__)
        self.assertEqual(b.archive.backend_version, b.version)
        self.assertEqual(b.archive.origin, b.origin)
        self.assertEqual(b.archive.category, MockedBackend.CATEGORY)

    def test_fetch_wrong_category(self):
        """Check that an error is thrown if the category is not valid"""

        b = MockedBackend('test')

        with self.assertRaises(BackendError):
            _ = [item for item in b.fetch(category="acme")]

    def test_fetch_client_not_provided(self):
        """Test whether an NotImplementedError exception is thrown"""

        b = Backend('test')
        b.CATEGORIES = [MockedBackend.CATEGORY]

        with self.assertRaises(NotImplementedError):
            _ = [item for item in b.fetch(category=MockedBackend.CATEGORY)]

    def test_init_client_not_implemented(self):
        """Test whether an NotImplementedError exception is thrown"""

        b = Backend('test')

        with self.assertRaises(NotImplementedError):
            b._init_client()

    def test_fetch_items(self):
        """Test whether an NotImplementedError exception is thrown"""

        b = Backend('test')

        with self.assertRaises(NotImplementedError):
            b.fetch_items(MockedBackend.CATEGORY)


class TestBackendArchive(TestCaseBackendArchive):
    """Unit tests for Backend using the archive"""

    def setUp(self):
        super().setUp()
        self.backend_write_archive = MockedBackend('test', archive=self.archive)
        self.backend_read_archive = MockedBackend('test', archive=self.archive)

    def tearDown(self):
        shutil.rmtree(self.test_path)

    def test_fetch_from_archive(self):
        """Test whether the method fetch_from_archive works properly"""

        self._test_fetch_from_archive()

    def test_fetch_from_archive_not_provided(self):
        """Test whether an exception is thrown when an archive is not provided"""

        b = MockedBackend('test')

        with self.assertRaises(ArchiveError):
            _ = [item for item in b.fetch_from_archive()]

    def test_fetch_client_not_implemented(self):
        """Test whether an NotImplementedError exception is thrown"""

        b = Backend('test', archive=self.archive)

        with self.assertRaises(NotImplementedError):
            _ = [item for item in b.fetch_from_archive()]


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

    def test_parse_archive_args(self):
        """Test if achiving arguments are parsed"""

        args = ['--archive-path', '/tmp/archive',
                '--fetch-archive',
                '--archived-since', '2016-01-01',
                '--category', 'mocked']

        parser = BackendCommandArgumentParser(archive=True)
        parsed_args = parser.parse(*args)

        expected_dt = datetime.datetime(2016, 1, 1, 0, 0,
                                        tzinfo=dateutil.tz.tzutc())

        self.assertIsInstance(parsed_args, argparse.Namespace)
        self.assertEqual(parsed_args.archive_path, '/tmp/archive')
        self.assertEqual(parsed_args.fetch_archive, True)
        self.assertEqual(parsed_args.no_archive, False)
        self.assertEqual(parsed_args.archived_since, expected_dt)

    def test_incompatible_fetch_archive_and_no_archive(self):
        """Test if fetch-archive and no-archive arguments are incompatible"""

        args = ['--fetch-archive', '--no-archive']
        parser = BackendCommandArgumentParser(archive=True)

        with self.assertRaises(AttributeError):
            _ = parser.parse(*args)

    def test_fetch_archive_needs_category(self):
        """Test if fetch-archive needs a category"""

        args = ['--fetch-archive']
        parser = BackendCommandArgumentParser(archive=True)

        with self.assertRaises(AttributeError):
            _ = parser.parse(*args)

    def test_remove_empty_category(self):
        """Test whether category argument is removed when no value is given"""

        args = []
        parser = BackendCommandArgumentParser(archive=True)
        parsed_args = parser.parse(*args)

        with self.assertRaises(AttributeError):
            _ = parsed_args.category

        # An empty string is parsed
        args = ['--category', '']
        parser = BackendCommandArgumentParser(archive=True)
        parsed_args = parser.parse(*args)

        self.assertEqual(parsed_args.category, '')


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
                '--category', 'mock_item', '--archive-path', self.test_path,
                '--fetch-archive', '--archived-since', '2015-01-01',
                '--from-date', '2015-01-01', '--tag', 'test',
                '--output', self.fout_path, 'http://example.com/']

        dt_expected = datetime.datetime(2015, 1, 1, 0, 0,
                                        tzinfo=dateutil.tz.tzutc())

        cmd = MockedBackendCommand(*args)

        self.assertIsInstance(cmd.parsed_args, argparse.Namespace)
        self.assertEqual(cmd.parsed_args.user, 'jsmith')
        self.assertEqual(cmd.parsed_args.password, '1234')
        self.assertEqual(cmd.parsed_args.api_token, 'abcd')
        self.assertEqual(cmd.parsed_args.archive_path, self.test_path)
        self.assertEqual(cmd.parsed_args.fetch_archive, True)
        self.assertEqual(cmd.parsed_args.archived_since, dt_expected)
        self.assertEqual(cmd.parsed_args.from_date, dt_expected)
        self.assertEqual(cmd.parsed_args.tag, 'test')

        self.assertIsInstance(cmd.outfile, io.TextIOWrapper)
        self.assertEqual(cmd.outfile.name, self.fout_path)

        manager = cmd.archive_manager
        self.assertIsInstance(manager, ArchiveManager)
        self.assertEqual(manager.dirpath, self.test_path)

        cmd.outfile.close()

    def test_setup_cmd_parser(self):
        """Test whether an NotImplementedError exception is thrown"""

        with self.assertRaises(NotImplementedError):
            BackendCommand.setup_cmd_parser()

    @unittest.mock.patch('os.path.expanduser')
    def test_archive_manager_on_init(self, mock_expanduser):
        """Test if the archive manager is set when the class is initialized"""

        mock_expanduser.return_value = self.test_path

        args = ['-u', 'jsmith', '-p', '1234', '-t', 'abcd',
                '--from-date', '2015-01-01', '--tag', 'test',
                '--output', self.fout_path, 'http://example.com/']

        cmd = MockedBackendCommand(*args)

        manager = cmd.archive_manager
        self.assertIsInstance(manager, ArchiveManager)
        self.assertEqual(os.path.exists(manager.dirpath), True)
        self.assertEqual(manager.dirpath, self.test_path)

        # Due to '--no-archive' is given, Archive Manager isn't set
        args = ['-u', 'jsmith', '-p', '1234', '-t', 'abcd',
                '--no-archive', '--from-date', '2015-01-01',
                '--tag', 'test', '--output', self.fout_path,
                'http://example.com/']

        cmd = MockedBackendCommand(*args)
        self.assertEqual(cmd.archive_manager, None)

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
                '--archive-path', self.test_path, '--category', 'mock_item',
                '--subtype', 'mocksubtype',
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

    def test_run_fetch_from_archive(self):
        """Test whether the command runs when fetch from archive is set"""

        args = ['--archive-path', self.test_path,
                '--from-date', '2015-01-01', '--tag', 'test',
                '--category', 'mock_item',
                '--subtype', 'mocksubtype',
                '--output', self.fout_path, 'http://example.com/']

        cmd = MockedBackendCommand(*args)
        cmd.run()
        cmd.outfile.close()

        items = [item for item in convert_cmd_output_to_json(self.fout_path)]

        self.assertEqual(len(items), 5)

        args = ['--archive-path', self.test_path, '--fetch-archive',
                '--from-date', '2015-01-01', '--tag', 'test', '--category', 'mock_item',
                '--subtype', 'mocksubtype',
                '--output', self.fout_path, 'http://example.com/']

        cmd = MockedBackendCommand(*args)
        cmd.run()
        cmd.outfile.close()

        items = [item for item in convert_cmd_output_to_json(self.fout_path)]
        self.assertEqual(len(items), 5)

        for x in range(5):
            item = items[x]
            expected_uuid = uuid('http://example.com/', str(x))

            # ArchiveMockedBackend sets 'archive' value when
            # 'fetch-archive' option is set. This helps to know
            # the code is really running
            self.assertEqual(item['data']['item'], x)
            self.assertEqual(item['data']['archive'], True)
            self.assertEqual(item['origin'], 'http://example.com/')
            self.assertEqual(item['uuid'], expected_uuid)
            self.assertEqual(item['tag'], 'test')

    def test_run_no_archive(self):
        """Test whether the command runs when archive is not set"""

        args = ['--no-archive', '--from-date', '2015-01-01',
                '--tag', 'test', '--output', self.fout_path,
                '--category', 'mock_item',
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

    def test_run_not_supported_archive(self):
        """Test whether the comand runs when archive is not supported"""

        args = ['--from-date', '2015-01-01',
                '--tag', 'test', '--output', self.fout_path,
                '--category', 'mock_item',
                'http://example.com/']

        cmd = NoArchiveBackendCommand(*args)
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


class TestFetch(unittest.TestCase):
    """Unit tests for fetch function"""

    def setUp(self):
        self.test_path = tempfile.mkdtemp(prefix='perceval_')

    def tearDown(self):
        shutil.rmtree(self.test_path)

    def test_items(self):
        """Test whether a set of items is returned"""

        args = {
            'origin': 'http://example.com/',
            'category': 'mock_item',
            'tag': 'test',
            'subtype': 'mocksubtype',
            'from-date': str_to_datetime('2015-01-01')
        }

        items = fetch(CommandBackend, args, manager=None)
        items = [item for item in items]

        self.assertEqual(len(items), 5)

        for x in range(5):
            item = items[x]
            expected_uuid = uuid('http://example.com/', str(x))

            self.assertEqual(item['data']['item'], x)
            self.assertEqual(item['origin'], 'http://example.com/')
            self.assertEqual(item['uuid'], expected_uuid)
            self.assertEqual(item['tag'], 'test')

    def test_items_storing_archive(self):
        """Test whether items are stored in an archive"""

        manager = ArchiveManager(self.test_path)

        args = {
            'origin': 'http://example.com/',
            'category': 'mock_item',
            'tag': 'test',
            'subtype': 'mocksubtype',
            'from-date': str_to_datetime('2015-01-01')
        }

        items = fetch(CommandBackend, args, manager=manager)
        items = [item for item in items]

        self.assertEqual(len(items), 5)

        for x in range(5):
            item = items[x]
            expected_uuid = uuid('http://example.com/', str(x))

            self.assertEqual(item['data']['item'], x)
            self.assertEqual(item['origin'], 'http://example.com/')
            self.assertEqual(item['uuid'], expected_uuid)
            self.assertEqual(item['tag'], 'test')

        filepaths = manager.search('http://example.com/', 'CommandBackend',
                                   'mock_item', str_to_datetime('1970-01-01'))

        self.assertEqual(len(filepaths), 1)

        archive = Archive(filepaths[0])
        self.assertEqual(archive._count_table_rows('archive'), 5)

    def test_remove_archive_on_error(self):
        """Test whether an archive is removed when an unhandled exception occurs"""

        manager = ArchiveManager(self.test_path)

        args = {
            'origin': 'http://example.com/',
            'category': 'mock_item',
            'tag': 'test',
            'subtype': 'mocksubtype',
            'from-date': str_to_datetime('2015-01-01')
        }

        items = fetch(ErrorCommandBackend, args, manager=manager)

        with self.assertRaises(BackendError):
            _ = [item for item in items]

        filepaths = manager.search('http://example.com/', 'ErrorCommandBackend',
                                   'mock_item', str_to_datetime('1970-01-01'))

        self.assertEqual(len(filepaths), 0)


class TestFetchFromArchive(unittest.TestCase):
    """Unit tests for fetch_from_archive function"""

    def setUp(self):
        self.test_path = tempfile.mkdtemp(prefix='perceval_')

    def tearDown(self):
        shutil.rmtree(self.test_path)

    def test_archive(self):
        """Test whether a set of items is fetched from the archive"""

        manager = ArchiveManager(self.test_path)

        args = {
            'origin': 'http://example.com/',
            'category': 'mock_item',
            'tag': 'test',
            'subtype': 'mocksubtype',
            'from-date': str_to_datetime('2015-01-01')
        }

        # First, fetch the items twice to check if several archive
        # are used
        items = fetch(CommandBackend, args, manager=manager)
        items = [item for item in items]
        self.assertEqual(len(items), 5)

        items = fetch(CommandBackend, args, manager=manager)
        items = [item for item in items]
        self.assertEqual(len(items), 5)

        # Fetch items from the archive
        items = fetch_from_archive(CommandBackend, args, manager,
                                   'mock_item', str_to_datetime('1970-01-01'))
        items = [item for item in items]

        self.assertEqual(len(items), 10)

        for x in range(2):
            for y in range(5):
                item = items[y + (x * 5)]
                expected_uuid = uuid('http://example.com/', str(y))

                self.assertEqual(item['data']['item'], y)
                self.assertEqual(item['data']['archive'], True)
                self.assertEqual(item['origin'], 'http://example.com/')
                self.assertEqual(item['uuid'], expected_uuid)
                self.assertEqual(item['tag'], 'test')

    def test_archived_after(self):
        """Test if only those items archived after a date are returned"""

        manager = ArchiveManager(self.test_path)

        args = {
            'origin': 'http://example.com/',
            'category': 'mock_item',
            'tag': 'test',
            'subtype': 'mocksubtype',
            'from-date': str_to_datetime('2015-01-01')
        }

        items = fetch(CommandBackend, args, manager=manager)
        items = [item for item in items]
        self.assertEqual(len(items), 5)

        archived_dt = datetime_utcnow()

        items = fetch(CommandBackend, args, manager=manager)
        items = [item for item in items]
        self.assertEqual(len(items), 5)

        # Fetch items from the archive
        items = fetch_from_archive(CommandBackend, args, manager,
                                   'mock_item', str_to_datetime('1970-01-01'))
        items = [item for item in items]
        self.assertEqual(len(items), 10)

        # Fetch items archived after the given date
        items = fetch_from_archive(CommandBackend, args, manager,
                                   'mock_item', archived_dt)
        items = [item for item in items]
        self.assertEqual(len(items), 5)

    def test_no_archived_items(self):
        """Test when no archived items are available"""

        manager = ArchiveManager(self.test_path)

        args = {
            'origin': 'http://example.com/',
            'category': 'mock_item',
            'tag': 'test',
            'subtype': 'mocksubtype',
            'from-date': str_to_datetime('2015-01-01')
        }

        items = fetch(CommandBackend, args, manager=manager)
        items = [item for item in items]
        self.assertEqual(len(items), 5)

        # There aren't items for this category
        items = fetch_from_archive(CommandBackend, args, manager,
                                   'alt_item', str_to_datetime('1970-01-01'))
        items = [item for item in items]
        self.assertEqual(len(items), 0)

    def test_ignore_corrupted_archive(self):
        """Check if a corrupted archive is ignored while fetching from archive"""

        def delete_rows(db, table_name):
            conn = sqlite3.connect(db)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM " + table_name)
            cursor.close()
            conn.commit()

        manager = ArchiveManager(self.test_path)

        args = {
            'origin': 'http://example.com/',
            'category': 'mock_item',
            'tag': 'test',
            'subtype': 'mocksubtype',
            'from-date': str_to_datetime('2015-01-01')
        }

        # First, fetch the items twice to check if several archive
        # are used
        items = fetch(CommandBackend, args, manager=manager)
        items = [item for item in items]
        self.assertEqual(len(items), 5)

        items = fetch(CommandBackend, args, manager=manager)
        items = [item for item in items]
        self.assertEqual(len(items), 5)

        # Find archive names to delete the rows of one of them to make it
        # corrupted
        filepaths = manager.search('http://example.com/', 'CommandBackend',
                                   'mock_item', str_to_datetime('1970-01-01'))
        self.assertEqual(len(filepaths), 2)

        to_remove = filepaths[0]
        delete_rows(to_remove, 'archive')

        # Fetch items from the archive
        items = fetch_from_archive(CommandBackend, args, manager,
                                   'mock_item', str_to_datetime('1970-01-01'))
        items = [item for item in items]

        self.assertEqual(len(items), 5)

        for x in range(5):
            item = items[x]
            expected_uuid = uuid('http://example.com/', str(x))

            self.assertEqual(item['data']['item'], x)
            self.assertEqual(item['data']['archive'], True)
            self.assertEqual(item['origin'], 'http://example.com/')
            self.assertEqual(item['uuid'], expected_uuid)
            self.assertEqual(item['tag'], 'test')


if __name__ == "__main__":
    unittest.main()
