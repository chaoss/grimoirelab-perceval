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
import functools
import hashlib
import importlib
import os
import pkgutil
import sys

from datetime import datetime as dt

from ._version import __version__
from .cache import Cache
from .utils import DEFAULT_DATETIME


class Backend:
    """Abstract class for backends.

    Base class to fetch data from a repository. This repository
    will be named as 'origin'. During the initialization, a `Cache`
    object can be provided for caching raw data from the repositories.

    Derivated classes have to implement `fetch`, `fetch_from_cache`,
    `has_caching` and `has_resuming` methods. Otherwise, `NotImplementedError`
    exception will be raised. Metadata decorator can be used together with
    fetch methods but requires the implementation of `metadata_id`,
    `metadata_updated_on` and `metadata_category` static methods.

    The fetched items can be tagged using the `tag` parameter. It will
    be useful to trace data. When it is set to `None` or to an empty
    string, the tag will be the same that the `origin` attribute.

    To track which version of the backend was used during the fetching
    process, this class provides a `version` attribute that each backend
    may override.

    :param origin: identifier of the repository
    :param tag: tag items using this label
    :param cache: object to cache raw data

    :raises ValueError: raised when `cache` is not an instance of
        `Cache` class
    """
    version = '0.4'

    def __init__(self, origin, tag=None, cache=None):
        if cache and not isinstance(cache, Cache):
            msg = "cache is not an instance of Cache. %s object given" \
                % (str(type(cache)))
            raise ValueError(msg)

        self._origin = origin
        self.tag = tag if tag else origin
        self.cache = cache
        self.cache_queue = []

    @property
    def origin(self):
        return self._origin

    def fetch(self, from_date=DEFAULT_DATETIME):
        raise NotImplementedError

    def fetch_from_cache(self):
        raise NotImplementedError

    @classmethod
    def has_caching(cls):
        raise NotImplementedError

    @classmethod
    def has_resuming(cls):
        raise NotImplementedError

    @staticmethod
    def metadata_id(item):
        raise NotImplementedError

    @staticmethod
    def metadata_updated_on(item):
        raise NotImplementedError

    @staticmethod
    def metadata_category(item):
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
        group.add_argument('--tag', dest='tag',
                           help="tag the items generated during the fetching process")

        # Cache arguments
        group = parser.add_argument_group('cache arguments')
        group.add_argument('--cache-path', dest='cache_path', default=None,
                           help="directory path to the cache")
        group.add_argument('--clean-cache', dest='clean_cache', action='store_true',
                           help="clean the cache before the fetching process")
        group.add_argument('--no-cache', dest='no_cache', action='store_true',
                           help="do not store data in the cache")
        group.add_argument('--fetch-cache', dest='fetch_cache', action='store_true',
                           help="fetch data from the cache")

        # Output arguments
        group = parser.add_argument_group('output arguments')
        group.add_argument('-o', '--output', type=argparse.FileType('w'),
                           dest='outfile', default=sys.stdout,
                           help="output file")

        return parser


def metadata(func):
    """Add metadata to an item.

    Decorator that adds metadata to a given item such as how and
    when it was fetched. The contents from the original item will
    be stored under the 'data' keyword.

    Take into account that this decorator can only be called from a
    'Backend' class due it needs access to some of the attributes
    and methods of this class.
    """
    @functools.wraps(func)
    def decorator(self, *args, **kwargs):
        for data in func(self, *args, **kwargs):
            item = {
                    'backend_name' : self.__class__.__name__,
                    'backend_version' : self.version,
                    'perceval_version' : __version__,
                    'timestamp' : dt.utcnow().timestamp(),
                    'origin' : self.origin,
                    'uuid' : uuid(self.origin, self.metadata_id(data)),
                    'updated_on' : self.metadata_updated_on(data),
                    'category' : self.metadata_category(data),
                    'tag' : self.tag,
                    'data' : data,
                   }
            yield item
    return decorator


def uuid(*args):
    """Generate a UUID based on the given parameters.

    The UUID will be the SHA1 of the concatenation of the values
    from the list. The separator bewteedn these values is ':'.
    Each value must be a non-empty string, otherwise, the function
    will raise an exception.

    :param *args: list of arguments used to generate the UUID

    :returns: a universal unique identifier

    :raises ValueError: when anyone of the values is not a string,
        is empty or `None`.
    """
    def check_value(v):
        if not isinstance(v, str):
            raise ValueError("%s value is not a string instance" % str(v))
        elif not v:
            raise ValueError("value cannot be None or empty")
        else:
            return v

    s = ':'.join(map(check_value, args))

    sha1 = hashlib.sha1(s.encode('utf-8'))
    uuid_sha1 = sha1.hexdigest()

    return uuid_sha1


def find_backends(top_package):
    """Find available backends.

    Look for the Perceval backends and commands under `top_package`
    and its sub-packages. When `top_package` defines a namespace,
    backends under that same namespace will be found too.

    :param top_package: package storing backends

    :returns: a tuple with two dicts: one with `Backend` classes and one
        with `BackendCommand` classes
    """
    candidates = pkgutil.walk_packages(top_package.__path__,
                                       prefix=top_package.__name__ + '.')

    modules = [name for _, name, is_pkg in candidates if not is_pkg]

    return _import_backends(modules)


def _import_backends(modules):
    for module in modules:
        importlib.import_module(module)

    bkls = _filter_classes(Backend.__subclasses__(), modules)
    ckls = _filter_classes(BackendCommand.__subclasses__(), modules)

    backends = {name: kls for name, kls in bkls}
    commands = {name: klass for name, klass in ckls}

    return backends, commands


def _filter_classes(klasses, modules):
    for kls in klasses:
        m = kls.__module__

        if m not in modules:
            continue

        name = m.split('.')[-1]

        yield name, kls
