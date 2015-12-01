# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 Bitergia
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
import sys

from .cache import Cache
from .utils import DEFAULT_DATETIME


class Backend:
    """Abstract class for backends.

    Base class to fetch data from a repository. During the
    initialization, a `Cache` object can be provided for caching
    raw data from the repositories.

    Derivated classes have to implement `fetch` and `fetch_from_cache`
    methods. Otherwise, `NotImplementedError` exception will be raised.

    :param cache: object to cache raw data

    :raises ValueError: raised when `cache` is not an instance of
        `Cache` class
    """
    def __init__(self, cache=None):
        if cache and not isinstance(cache, Cache):
            msg = "cache is not an instance of Cache. %s object given" \
                % (str(type(cache)))
            raise ValueError(msg)

        self.cache = cache
        self.cache_queue = []

    def fetch(self, from_date=DEFAULT_DATETIME):
        raise NotImplementedError

    def fetch_from_cache(self):
        raise NotImplementedError

    def _purge_cache_queue(self):
        self.cache_queue = []

    def _flush_cache_queue(self):
        if not self.cache:
            return
        self.cache.store(*self.cache_queue)
        self._purge_cache_queue()

    def _push_cache_queue(self, item):
        if not self.cache:
            return
        self.cache_queue.append(item)


class BackendCommand:
    """Abstract class to run backends from the command line.

    When the class is initialized, it parses the given arguments using
    the defined argument parser on the class method. Those arguments
    will be stored in the attribute 'parsed_args'.

    The method 'run' must be implemented to exectute the backend.
    """
    def __init__(self, *args):
        parser = self.create_argument_parser()
        self.parsed_args = parser.parse_args(args)

    def run(self):
        raise NotImplementedError

    @classmethod
    def create_argument_parser(cls):
        """Returns a generic argument parser."""

        parser = argparse.ArgumentParser()

        # Options
        group = parser.add_argument_group('general arguments')
        group.add_argument('-u', '--backend-user', dest='backend_user',
                           help="backend user")
        group.add_argument('-p', '--backend-password', dest='backend_password',
                           help="backend password")
        group.add_argument('-t', '--backend-token', dest='backend_token',
                           help="backend authentication token")
        group.add_argument('--from-date', dest='from_date', default='1970-01-01',
                           help="fetch items from this date")

        # Output arguments
        group = parser.add_argument_group('output arguments')
        group.add_argument('-o', '--output', type=argparse.FileType('w'),
                           dest='outfile', default=sys.stdout,
                           help="output file")

        return parser
