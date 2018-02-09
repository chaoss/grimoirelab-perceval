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
#     Santiago Dueñas <sduenas@bitergia.com>
#

import os
import uuid

from .archive import Archive
from .errors import ArchiveError

STORAGE_EXT = ".sqlite3"


class ArchiveManager:
    """Manager for handling archives in Perceval.

    This class allows to manage archives for a
    further recovery.

    :param: archive_folder_path: path where the archives are stored
    """

    def __init__(self, archive_folder_path):

        self.archive_folder_path = archive_folder_path

        if not os.path.exists(self.archive_folder_path):
            os.makedirs(self.archive_folder_path)

    def create_archive(self):
        """Create a new archive"""

        archive_name = uuid.uuid4().hex
        archive_path = os.path.join(self.archive_folder_path, archive_name + STORAGE_EXT)
        archive = Archive.create(archive_path)

        return archive

    def load_archive(self, origin, backend_name, backend_version, item_category, archive_date):
        """Load an archive

        :param: origin: identifier of the repository
        :param: backend_name: name of the backend
        :param: backend_version: version of the backend
        :param: item_category: category of the items fetched
        :param: archive_date: string representation of a date identifying an archive
        """

        archive_paths = ArchiveManager._stored_archives(self.archive_folder_path)

        found = None
        for archive_path in archive_paths:
            archive = Archive(archive_path)

            if archive.created_on == archive_date and archive.origin == origin and \
               archive.backend_name == backend_name and \
               archive.backend_version == backend_version and \
               archive.item_category == item_category:

                found = archive
                break

        if not found:
            raise ArchiveError(cause="Archive %s, %s, %s, %s, %s  not found!"
                                     % (origin, backend_name, backend_version, item_category, archive_date))

        return found

    @staticmethod
    def delete_archive(archive):
        """Delete an archive

        :param: archive: Archive object to delete
        """

        ArchiveManager._delete_archive(archive.archive_path)

    def collect_archives(self, origin, backend_name, backend_version, item_category, from_date):
        """List archives in folder path

        :param: origin: identifier of the repository
        :param: backend_name: name of the backend
        :param: backend_version: version of the backend
        :param: item_category: category of the items fetched
        :param: from_date: creation date from when the archives are retrieved

        :return list of archives
        """
        archives = []
        archive_paths = ArchiveManager._stored_archives(self.archive_folder_path)

        for archive_path in archive_paths:
            archive = Archive(archive_path)

            if archive.origin != origin:
                continue
            elif archive.backend_name != backend_name:
                continue
            elif archive.item_category != item_category:
                continue
            elif archive.backend_version < backend_version:
                continue
            elif archive.created_on < from_date:
                continue

            archives.append(archive)

        return archives

    def delete_archives(self):
        """Delete all archives in folder path"""

        archive_paths = ArchiveManager._stored_archives(self.archive_folder_path)

        for archive_path in archive_paths:
            ArchiveManager._delete_archive(archive_path)

    @staticmethod
    def _delete_archive(archive_path):
        os.remove(archive_path)

    @staticmethod
    def _stored_archives(folder_path):
        return [os.path.join(folder_path, f) for f in os.listdir(folder_path)
                if os.path.isfile(os.path.join(folder_path, f)) and f.endswith(STORAGE_EXT)]
