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
import functools
import hashlib
import importlib
import json
import pkgutil
import sys

from datetime import datetime as dt

from grimoirelab.toolkit.introspect import find_signature_parameters
from grimoirelab.toolkit.datetime import str_to_datetime

from ._version import __version__
from .cache import Cache, setup_cache
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
    version = '0.5'

    def __init__(self, origin, tag=None, cache=None):
        self._origin = origin
        self.tag = tag if tag else origin
        self.cache = cache or None
        self.cache_queue = []

    @property
    def origin(self):
        return self._origin

    @property
    def cache(self):
        return self._cache

    @cache.setter
    def cache(self, obj):
        if obj and not isinstance(obj, Cache):
            msg = "obj is not an instance of Cache. %s object given" \
                % (str(type(obj)))
            raise ValueError(msg)

        self._cache = obj

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


class BackendCommandArgumentParser:
    """Manage and parse backend command arguments.

    This class defines and parses a set of arguments common to
    backends commands. Some parameters like cache or the different
    types of authentication can be set during the initialization
    of the instance.

    :param from_date: set from_date argument
    :param to_date: set to_date argument
    :param offset: set offset argument
    :param basic_auth: set basic authentication arguments
    :param token_auth: set token/key authentication arguments
    :param cache: set caching arguments
    :param aliases: define aliases for parsed arguments

    :raises AttributeArror: when both `from_date` and `offset` are set
        to `True`
    """
    def __init__(self, from_date=False, to_date=False, offset=False,
                 basic_auth=False, token_auth=False,
                 cache=False, aliases=None):
        self._from_date = from_date
        self._to_date = to_date
        self._cache = cache

        self.aliases = aliases or {}
        self.parser = argparse.ArgumentParser()

        group = self.parser.add_argument_group('general arguments')
        group.add_argument('--tag', dest='tag',
                           help="tag the items generated during the fetching process")

        if (from_date or to_date) and offset:
            raise AttributeError("date and offset parameters are incompatible")

        if from_date:
            group.add_argument('--from-date', dest='from_date',
                               default='1970-01-01',
                               help="fetch items updated since this date")
        if to_date:
            group.add_argument('--to-date', dest='to_date',
                               help="fetch items updated before this date")
        if offset:
            group.add_argument('--offset', dest='offset',
                               type=int, default=0,
                               help="offset to start fetching items")

        if basic_auth or token_auth:
            self._set_auth_arguments(basic_auth=basic_auth,
                                     token_auth=token_auth)

        if cache:
            self._set_cache_arguments()

        self._set_output_arguments()

    def parse(self, *args):
        """Parse a list of arguments.

        Parse argument strings needed to run a backend command. The result
        will be a `argparse.Namespace` object populated with the values
        obtained after the validation of the parameters.

        :param args: argument strings

        :result: an object with the parsed values
        """
        parsed_args = self.parser.parse_args(args)

        if self._from_date:
            parsed_args.from_date = str_to_datetime(parsed_args.from_date)
        if self._to_date and parsed_args.to_date:
            parsed_args.to_date = str_to_datetime(parsed_args.to_date)

        if self._cache and parsed_args.fetch_cache and parsed_args.no_cache:
            raise AttributeError("fetch-cache and no-cache arguments are not compatible")

        # Set aliases
        for alias, arg in self.aliases.items():
            if (alias not in parsed_args) and (arg in parsed_args):
                value = getattr(parsed_args, arg, None)
                setattr(parsed_args, alias, value)

        return parsed_args

    def _set_auth_arguments(self, basic_auth=True, token_auth=False):
        """Activate authentication arguments parsing"""

        group = self.parser.add_argument_group('authentication arguments')

        if basic_auth:
            group.add_argument('-u', '--backend-user', dest='user',
                               help="backend user")
            group.add_argument('-p', '--backend-password', dest='password',
                               help="backend password")
        if token_auth:
            group.add_argument('-t', '--api-token', dest='api_token',
                               help="backend authentication token / API key")

    def _set_cache_arguments(self):
        """Activate cache arguments parsing"""

        group = self.parser.add_argument_group('cache arguments')
        group.add_argument('--cache-path', dest='cache_path', default=None,
                           help="directory path to the cache")
        group.add_argument('--clean-cache', dest='clean_cache', action='store_true',
                           help="clean the cache before the fetching process")
        group.add_argument('--no-cache', dest='no_cache', action='store_true',
                           help="do not store data in the cache")
        group.add_argument('--fetch-cache', dest='fetch_cache', action='store_true',
                           help="fetch data from the cache")

    def _set_output_arguments(self):
        """Activate output arguments parsing"""

        group = self.parser.add_argument_group('output arguments')
        group.add_argument('-o', '--output', type=argparse.FileType('w'),
                           dest='outfile', default=sys.stdout,
                           help="output file")


class BackendCommand:
    """Abstract class to run backends from the command line.

    When the class is initialized, it parses the given arguments using
    the defined argument parser on `setump_cmd_parser` method. Those
    arguments will be stored in the attribute `parsed_args`.

    The arguments will be used to inizialize and run the `Backend` object
    assigned to this command. The backend used to run the command is stored
    under `BACKEND` class attributed. Any class derived from this and must
    set its own `Backend` class.

    Moreover, the method `setup_cmd_parser` must be implemented to exectute
    the backend.
    """
    BACKEND = None

    def __init__(self, *args):
        parser = self.setup_cmd_parser()
        self.parsed_args = parser.parse(*args)

        self._pre_init()

        parsed_args = vars(self.parsed_args)
        kw = find_signature_parameters(self.BACKEND.__init__, parsed_args)
        self.backend = self.BACKEND(**kw)
        self.backend.cache = self._initialize_cache()

        self._post_init()

        self.outfile = self.parsed_args.outfile

    def run(self):
        """Fetch and write items.

        This method runs the backend to fetch the items from the given
        origin. Items are converted to JSON objects and written to the
        defined output.

        If `fetch-cache` parameter was given as an argument during
        the inizialization of the instance, the items will be retrieved
        from the cache.
        """
        if self.backend.cache and self.parsed_args.fetch_cache:
            fetch = self.backend.fetch_from_cache
        else:
            fetch = self.backend.fetch

        parsed_args = vars(self.parsed_args)
        kw = find_signature_parameters(fetch, parsed_args)
        items = fetch(**kw)

        try:
            for item in items:
                obj = json.dumps(item, indent=4, sort_keys=True)
                self.outfile.write(obj)
                self.outfile.write('\n')
        except IOError as e:
            raise RuntimeError(str(e))
        except Exception as e:
            if self.backend.cache:
                self.backend.cache.recover()
            raise RuntimeError(str(e))

    def _pre_init(self):
        """Override to execute before backend is initialized."""
        pass

    def _post_init(self):
        """Override to execute after backend is initialized."""
        pass

    def _initialize_cache(self):
        """Initialize cache based on the parsed parameters"""

        if 'cache_path' not in self.parsed_args:
            return None

        if self.parsed_args.no_cache:
            return None

        return setup_cache(self.backend.origin,
                           cache_path=self.parsed_args.cache_path,
                           clean_cache=self.parsed_args.clean_cache)

    @staticmethod
    def setup_cmd_parser():
        raise NotImplementedError


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
                'backend_name': self.__class__.__name__,
                'backend_version': self.version,
                'perceval_version': __version__,
                'timestamp': dt.utcnow().timestamp(),
                'origin': self.origin,
                'uuid': uuid(self.origin, self.metadata_id(data)),
                'updated_on': self.metadata_updated_on(data),
                'category': self.metadata_category(data),
                'tag': self.tag,
                'data': data,
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

    sha1 = hashlib.sha1(s.encode('utf-8', errors='surrogateescape'))
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
