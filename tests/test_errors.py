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

import unittest

import perceval.errors as errors


# Mock classes to test BaseError class
class MockErrorNoArgs(errors.BaseError):
    message = "Mock error without args"


class MockErrorArgs(errors.BaseError):
    message = "Mock error with args. Error: %(code)s %(msg)s"


class TestBaseError(unittest.TestCase):

    def test_subblass_with_no_args(self):
        """Check subclasses that do not require arguments.

        Arguments passed to the constructor should be ignored.
        """
        e = MockErrorNoArgs(code=1, msg='Fatal error')

        self.assertEqual("Mock error without args", str(e))

    def test_subclass_args(self):
        """Check subclasses that require arguments"""

        e = MockErrorArgs(code=1, msg='Fatal error')

        self.assertEqual("Mock error with args. Error: 1 Fatal error",
                         str(e))

    def test_subclass_invalid_args(self):
        """Check when required arguments are not given.

        When this happens, it raises a KeyError exception.
        """
        kwargs = {'code': 1, 'error': 'Fatal error'}
        self.assertRaises(KeyError, MockErrorArgs, **kwargs)


class TestArchiveError(unittest.TestCase):

    def test_message(self):
        """Make sure that prints the correct error"""

        e = errors.ArchiveError(cause='archive item not found')
        self.assertEqual('archive item not found', str(e))


class TestArchiveManagerError(unittest.TestCase):

    def test_message(self):
        """Make sure that prints the correct error"""

        e = errors.ArchiveManagerError(cause='archive not found')
        self.assertEqual('archive not found', str(e))


class TestBackendError(unittest.TestCase):

    def test_message(self):
        """Make sure that prints the correct error"""

        e = errors.BackendError(cause='mock error on backend')
        self.assertEqual('mock error on backend', str(e))


class TestRepositoryError(unittest.TestCase):

    def test_message(self):
        """Make sure that prints the correct error"""

        e = errors.RepositoryError(cause='error cloning repository')
        self.assertEqual('error cloning repository', str(e))


class TestRateLimitError(unittest.TestCase):

    def test_message(self):
        """Make sure that prints the correct error"""

        e = errors.RateLimitError(cause="client rate exhausted",
                                  seconds_to_reset=10)
        self.assertEqual("client rate exhausted; 10 seconds to rate reset",
                         str(e))

    def test_seconds_to_reset_property(self):
        """Test property"""

        e = errors.RateLimitError(cause="client rate exhausted",
                                  seconds_to_reset=10)
        self.assertEqual(e.seconds_to_reset, 10)


class TestParseError(unittest.TestCase):

    def test_message(self):
        """Make sure that prints the correct error"""

        e = errors.ParseError(cause='error on line 10')
        self.assertEqual('error on line 10', str(e))


class TestBackendCommandArgumentParserError(unittest.TestCase):

    def test_message(self):
        """Make sure that prints the correct error"""

        e = errors.BackendCommandArgumentParserError(cause='mock error on backend command argument parser')
        self.assertEqual('mock error on backend command argument parser', str(e))


if __name__ == "__main__":
    unittest.main()
