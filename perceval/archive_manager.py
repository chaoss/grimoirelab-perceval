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
#     Valerio Cosentino <valcos@bitergia.com>
#

import datetime
import os

from grimoirelab.toolkit.datetime import str_to_datetime, datetime_to_utc

from .archive import Archive
from .utils import DEFAULT_DATETIME

from perceval.errors import ArchiveError

ARCHIVE_DEFAULT_PATH = '~/.perceval/archive/'
STORAGE_EXT = ".sqlite3"


def now_to_str():
    """return a str value of the current time"""

    now = datetime.datetime.utcnow()
    return now.strftime("%Y-%m-%d %H:%M:%S")


class ArchiveManager:
    """Manager for handle archives in Perceval.

    This class allows to manage archives for a
    further recovery.
    """

    def __init__(self, origin, backend_name, backend_version, archive_root_path=ARCHIVE_DEFAULT_PATH):

        self.archive_folder_path = os.path.join(archive_root_path, origin, backend_name, backend_version)

        if not os.path.exists(self.archive_folder_path):
            os.makedirs(self.archive_folder_path)

        self.backend_name = backend_name
        self.backend_version = backend_version
        self.archive = None

    def load(self, fetched_at):
        """load an already existing archive"""

        self.__set_archive(fetched_at)

    def new(self):
        """create a new archive"""

        self.__set_archive(new=True)

    def __set_archive(self, fetched_at=now_to_str(), new=False):
        """set archive"""

        archive_path = os.path.join(self.archive_folder_path, fetched_at + STORAGE_EXT)

        if not os.path.exists(archive_path) and not new:
            raise ArchiveError(cause="Archive %s not found!" % fetched_at)

        self.archive = Archive(archive_path, new=new)

    def delete(self, target_name):
        """delete an archive identified by its name in folder path"""

        path = self.archive_folder_path
        for f in os.listdir(path):
            if os.path.isfile(os.path.join(path, f)) and f.startswith(target_name) and f.endswith(STORAGE_EXT):
                os.remove(os.path.join(path, f))
                break

    def delete_all(self):
        """delete all archives in folder path"""

        path = self.archive_folder_path
        [os.remove(os.path.join(path, f)) for f in os.listdir(path)
         if os.path.isfile(os.path.join(path, f)) and f.endswith(STORAGE_EXT)]

    def archives(self, from_date=DEFAULT_DATETIME):
        """list archives in folder path"""

        path = self.archive_folder_path
        archives = [f.replace(STORAGE_EXT, "") for f in os.listdir(path)
                    if os.path.isfile(os.path.join(path, f)) and f.endswith(STORAGE_EXT)]

        return [f for f in sorted(archives) if str_to_datetime(f) >= datetime_to_utc(from_date)]

    def store(self, command, data, params=None):
        """Store data source information.

        :command: data source command
        :params: params command
        :data: response data
        """

        self.archive.store(command, params, data, self.backend_name, self.backend_version)

    def retrieve(self, command, params=None):
        """Retrieve the data stored in the database.

        This method returns the data source content corresponding to the hash_request derived from the command and params

        :returns: the data that corresponds to the command and params
        """

        return self.archive.retrieve(command, params)
