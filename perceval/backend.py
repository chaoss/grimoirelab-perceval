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
import hashlib
import importlib
import json
import logging
import os
import pkgutil
import sys

from grimoirelab_toolkit.introspect import find_signature_parameters
from grimoirelab_toolkit.datetime import (datetime_utcnow,
                                          str_to_datetime)
from .archive import Archive, ArchiveManager
from .errors import ArchiveError, BackendError
from ._version import __version__


logger = logging.getLogger(__name__)

ARCHIVES_DEFAULT_PATH = '~/.perceval/archives/'


class Backend:
    """Abstract class for backends.

    Base class to fetch data from a repository. This repository
    will be named as 'origin'. During the initialization, an `Archive`
    object can be provided for archiving raw data from the repositories.

    Derivated classes have to implement `fetch_items`, `has_archiving` and
    `has_resuming` methods. Otherwise, `NotImplementedError`
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
    :param archive: archive to store/retrieve data

    :raises ValueError: raised when `archive` is not an instance of
        `Archive` class
    """
    version = '0.7.0'

    CATEGORIES = []

    def __init__(self, origin, tag=None, archive=None):
        self._origin = origin
        self.tag = tag if tag else origin
        self.archive = archive or None

    @property
    def origin(self):
        return self._origin

    @property
    def archive(self):
        return self._archive

    @archive.setter
    def archive(self, obj):
        if obj and not isinstance(obj, Archive):
            msg = "obj is not an instance of Archive. %s object given" \
                % (str(type(obj)))
            raise ValueError(msg)

        self._archive = obj

    @property
    def categories(self):
        return self.CATEGORIES

    def fetch_items(self, category, **kwargs):
        raise NotImplementedError

    def fetch(self, category, **kwargs):
        """Fetch items from the repository.

        The method retrieves items from a repository.

        :param category: the category of the items fetched
        :param kwargs: a list of other parameters (e.g., from_date, offset, etc.
        specific for each backend)

        :returns: a generator of items
        """
        if category not in self.categories:
            cause = "%s category not valid for %s" % (category, self.__class__.__name__)
            raise BackendError(cause=cause)

        if self.archive:
            self.archive.init_metadata(self.origin, self.__class__.__name__, self.version, category,
                                       kwargs)

        self.client = self._init_client()

        for item in self.fetch_items(category, **kwargs):
            yield self.metadata(item)

    def fetch_from_archive(self):
        """Fetch the questions from an archive.

        It returns the items stored within an archive. If this method is called but
        no archive was provided, the method will raise a `ArchiveError` exception.

        :returns: a generator of items
        :raises ArchiveError: raised when an error occurs accessing an archive
        """
        if not self.archive:
            raise ArchiveError(cause="archive instance was not provided")

        self.client = self._init_client(from_archive=True)

        for item in self.fetch_items(self.archive.category, **self.archive.backend_params):
            yield self.metadata(item)

    def metadata(self, item):
        """Add metadata to an item.

        It adds metadata to a given item such as how and
        when it was fetched. The contents from the original item will
        be stored under the 'data' keyword.

        :param item: an item fetched by a backend
        """
        item = {
            'backend_name': self.__class__.__name__,
            'backend_version': self.version,
            'perceval_version': __version__,
            'timestamp': datetime_utcnow().timestamp(),
            'origin': self.origin,
            'uuid': uuid(self.origin, self.metadata_id(item)),
            'updated_on': self.metadata_updated_on(item),
            'category': self.metadata_category(item),
            'tag': self.tag,
            'data': item,
        }

        return item

    @classmethod
    def has_archiving(cls):
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

    def _init_client(self, from_archive=False):
        raise NotImplementedError


class BackendCommandArgumentParser:
    """Manage and parse backend command arguments.

    This class defines and parses a set of arguments common to
    backends commands. Some parameters like archive or the different
    types of authentication can be set during the initialization
    of the instance.

    :param from_date: set from_date argument
    :param to_date: set to_date argument
    :param offset: set offset argument
    :param basic_auth: set basic authentication arguments
    :param token_auth: set token/key authentication arguments
    :param archive: set archiving arguments
    :param aliases: define aliases for parsed arguments

    :raises AttributeArror: when both `from_date` and `offset` are set
        to `True`
    """
    def __init__(self, from_date=False, to_date=False, offset=False,
                 basic_auth=False, token_auth=False, archive=False,
                 aliases=None):
        self._from_date = from_date
        self._to_date = to_date
        self._archive = archive

        self.aliases = aliases or {}
        self.parser = argparse.ArgumentParser()

        group = self.parser.add_argument_group('general arguments')
        group.add_argument('--category', dest='category',
                           help="type of the items to fetch")
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

        if archive:
            self._set_archive_arguments()

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

        # Category was not set, remove it
        if parsed_args.category is None:
            delattr(parsed_args, 'category')

        if self._from_date:
            parsed_args.from_date = str_to_datetime(parsed_args.from_date)
        if self._to_date and parsed_args.to_date:
            parsed_args.to_date = str_to_datetime(parsed_args.to_date)
        if self._archive and parsed_args.archived_since:
            parsed_args.archived_since = str_to_datetime(parsed_args.archived_since)

        if self._archive and parsed_args.fetch_archive and parsed_args.no_archive:
            raise AttributeError("fetch-archive and no-archive arguments are not compatible")
        if self._archive and parsed_args.fetch_archive and not parsed_args.category:
            raise AttributeError("fetch-archive needs a category to work with")

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

    def _set_archive_arguments(self):
        """Activate archive arguments parsing"""

        group = self.parser.add_argument_group('archive arguments')
        group.add_argument('--archive-path', dest='archive_path', default=None,
                           help="directory path to the archives")
        group.add_argument('--no-archive', dest='no_archive', action='store_true',
                           help="do not archive data")
        group.add_argument('--fetch-archive', dest='fetch_archive', action='store_true',
                           help="fetch data from the archives")
        group.add_argument('--archived-since', dest='archived_since', default='1970-01-01',
                           help="retrieve items archived since the given date")

    def _set_output_arguments(self):
        """Activate output arguments parsing"""

        group = self.parser.add_argument_group('output arguments')
        group.add_argument('-o', '--output', type=argparse.FileType('w'),
                           dest='outfile', default=sys.stdout,
                           help="output file")
        group.add_argument('--json-line', dest='json_line', action='store_true',
                           help="produce a JSON line for each output item")


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

        self.archive_manager = None

        self._pre_init()
        self._initialize_archive()
        self._post_init()

        self.outfile = self.parsed_args.outfile
        self.json_line = self.parsed_args.json_line

    def run(self):
        """Fetch and write items.

        This method runs the backend to fetch the items from the given
        origin. Items are converted to JSON objects and written to the
        defined output.

        If `fetch-archive` parameter was given as an argument during
        the inizialization of the instance, the items will be retrieved
        using the archive manager.
        """
        backend_args = vars(self.parsed_args)
        category = backend_args.pop('category', None)
        archived_since = backend_args.pop('archived_since', None)

        if self.archive_manager and self.parsed_args.fetch_archive:

            items = fetch_from_archive(self.BACKEND, backend_args,
                                       self.archive_manager,
                                       category,
                                       archived_since)
        else:
            items = fetch(self.BACKEND, backend_args, category,
                          manager=self.archive_manager)

        try:
            for item in items:
                if self.json_line:
                    obj = json.dumps(item, separators=(',', ':'), sort_keys=True)
                else:
                    obj = json.dumps(item, indent=4, sort_keys=True)
                self.outfile.write(obj)
                self.outfile.write('\n')
        except IOError as e:
            raise RuntimeError(str(e))
        except Exception as e:
            raise RuntimeError(str(e))

    def _pre_init(self):
        """Override to execute before backend is initialized."""
        pass

    def _post_init(self):
        """Override to execute after backend is initialized."""
        pass

    def _initialize_archive(self):
        """Initialize archive based on the parsed parameters"""

        if 'archive_path' not in self.parsed_args:
            manager = None
        elif self.parsed_args.no_archive:
            manager = None
        else:
            if not self.parsed_args.archive_path:
                archive_path = os.path.expanduser(ARCHIVES_DEFAULT_PATH)
            else:
                archive_path = self.parsed_args.archive_path

            manager = ArchiveManager(archive_path)

        self.archive_manager = manager

    @staticmethod
    def setup_cmd_parser():
        raise NotImplementedError


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


def fetch(backend_class, backend_args, category, manager=None):
    """Fetch items using the given backend.

    Generator to get items using the given backend class. When
    an archive manager is given, this function will store
    the fetched items in an `Archive`. If an exception is raised,
    this archive will be removed to avoid corrupted archives.

    The parameters needed to initialize the `backend` class and
    get the items are given using `backend_args` dict parameter.

    :param backend_class: backend class to fetch items
    :param backend_args: dict of arguments needed to fetch the items
    :param category: category of the items to retrieve.
       If None, it will use the default backend category
    :param manager: archive manager needed to store the items

    :returns: a generator of items
    """
    init_args = find_signature_parameters(backend_class.__init__,
                                          backend_args)
    archive = manager.create_archive() if manager else None
    init_args['archive'] = archive

    backend = backend_class(**init_args)

    if category:
        backend_args['category'] = category

    fetch_args = find_signature_parameters(backend.fetch,
                                           backend_args)
    items = backend.fetch(**fetch_args)

    try:
        for item in items:
            yield item
    except Exception as e:
        if manager:
            archive_path = archive.archive_path
            manager.remove_archive(archive_path)
        raise e


def fetch_from_archive(backend_class, backend_args, manager,
                       category, archived_after):
    """Fetch items from an archive manager.

    Generator to get the items of a category (previously fetched
    by the given backend class) from an archive manager. Only those
    items archived after the given date will be returned.

    The parameters needed to initialize `backend` and get the
    items are given using `backend_args` dict parameter.

    :param backend_class: backend class to retrive items
    :param backend_args: dict of arguments needed to retrieve the items
    :param manager: archive manager where the items will be retrieved
    :param category: category of the items to retrieve
    :param archived_after: return items archived after this date

    :returns: a generator of archived items
    """
    init_args = find_signature_parameters(backend_class.__init__,
                                          backend_args)
    backend = backend_class(**init_args)

    filepaths = manager.search(backend.origin,
                               backend.__class__.__name__,
                               category,
                               archived_after)

    for filepath in filepaths:
        backend.archive = Archive(filepath)
        items = backend.fetch_from_archive()

        try:
            for item in items:
                yield item
        except ArchiveError as e:
            logger.warning("Ignoring %s archive due to: %s", filepath, str(e))


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

    bkls = _find_classes(Backend, modules)
    ckls = _find_classes(BackendCommand, modules)

    backends = {name: kls for name, kls in bkls}
    commands = {name: klass for name, klass in ckls}

    return backends, commands


def _find_classes(parent, modules):
    parents = parent.__subclasses__()

    while parents:
        kls = parents.pop()

        m = kls.__module__

        if m not in modules:
            continue

        name = m.split('.')[-1]
        parents.extend(kls.__subclasses__())

        yield name, kls
