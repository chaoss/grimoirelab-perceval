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
#     Alvaro del Castillo San Felix <acs@bitergia.com>
#

import os
import shutil
import shelve


CACHE_DEFAULT_PATH = '~/.perceval/cache/'


class Cache:
    """Basic cache for Perceval.

    This class allows to cache items (Python objects of any type) for a
    further recovery. Items are stored in order in `dirname` directory
    path. Items are also retrieved following the same storage order.

    The cache also provides the methods `backup` and `recover` that
    prevents from possible failures.
    """

    CACHE_PREFIX = 'perceval_cache'

    def __init__(self, dirname):
        self.cache_path = dirname
        self.items_path = os.path.join(self.cache_path, 'items')
        self.recovery_path = os.path.join(self.cache_path, 'recovery')
        self.cache_files = os.path.join(self.items_path, self.CACHE_PREFIX)

        if not os.path.exists(self.cache_path):
            os.makedirs(self.cache_path)
        if not os.path.exists(self.items_path):
            os.makedirs(self.items_path)
        if not os.path.exists(self.recovery_path):
            os.makedirs(self.recovery_path)

    def store(self, *items):
        """Store a set of items in the cache.

        The items will be stored in the cache in the given order. Thus,
        they can be recover in the same way.

        :params items: list of items to store
        """
        with shelve.open(self.cache_files) as cache:
            key = len(cache.keys())

            for item in items:
                cache[str(key)] = item
                key += 1

    def retrieve(self):
        """Retrieve the items stored in the cache.

        This method is a generator that returns all the cache items
        in the same order they were stored.

        :returns: the items stored in the cache
        """
        with shelve.open(self.cache_files) as cache:
            keys = [int(key) for key in list(cache.keys())]
            keys.sort()

            for key in keys:
                yield cache[str(key)]

    def backup(self):
        """Make a backup of the cache.

        The method saves the items stored in the cache to the recovery
        backup. Any previous backup will be deleted.
        """
        shutil.rmtree(self.recovery_path)
        shutil.copytree(self.items_path, self.recovery_path)

    def clean(self, erase=False):
        """Clear the cache.

        Cache contents will be removed but saved to the recovery backup.
        When the parameter `erase` is set, recovery data will be also
        removed.

        :param erase: remove recovery data, too.
        """
        if not erase:
            self.backup()
        else:
            shutil.rmtree(self.recovery_path)
            os.makedirs(self.recovery_path)

        shutil.rmtree(self.items_path)
        os.makedirs(self.items_path)

    def recover(self):
        """Restore cache contents from the recovery backup.

        Cache items will be recovery from the cache backup,
        if it is available.
        """
        shutil.rmtree(self.items_path)
        shutil.copytree(self.recovery_path, self.items_path)


def setup_cache(repository, cache_path=None, clean_cache=False):
    """Create and configure a cache object.

    Create a new cache object for `repository` and store it under
    the Perceval's default cache directory. When `cache_path` is
    given, the default directory will be replace by that value.

    If the cache already exists, a backup with its contents will be
    done. When `clean_cache` is set, the current cache will be
    removed and the backup will not be generated.

    :param cache_path: path to the directory to store cache data
    :param clean_cache: clean the contents of the cache, do not
        a backup

    :returns: a `Cache` instance
    """
    if not cache_path:
        base_path = os.path.expanduser(CACHE_DEFAULT_PATH)
    else:
        base_path = cache_path

    cache_path = os.path.join(base_path, repository)
    cache = Cache(cache_path)

    if clean_cache:
        cache.clean()
    else:
        cache.backup()

    return cache
