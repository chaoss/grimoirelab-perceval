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
import hashlib
import json
import os
import pickle
import sqlite3


ARCHIVE_DEFAULT_PATH = '~/.perceval/archive/'
STORAGE_EXT = ".sqlite3"


def now_to_str():
    """return a str value of the current time"""

    now = datetime.datetime.now()
    return now.strftime("%Y-%m-%d--%H-%M")


class Archive:
    """Basic cache for Perceval.

    This class allows to archive items for a
    further recovery. Items are stored in a Sqlite db.

    The archive also provides the methods `backup` and `recover` that
    prevents from possible failures.
    """

    def __init__(self, origin, backend_name, backend_version, archive_root_path=ARCHIVE_DEFAULT_PATH):

        self.archive_folder_path = os.path.join(archive_root_path, origin, backend_name, backend_version)

        if not os.path.exists(self.archive_folder_path):
            os.makedirs(self.archive_folder_path)

        self.backend_name = backend_name
        self.backend_version = backend_version

    def set_storage(self, fetched_at=now_to_str()):
        """set storage (init or load storage)"""

        self.fetched_at = fetched_at
        self.archive_path = os.path.join(self.archive_folder_path, fetched_at + STORAGE_EXT)
        self.db = sqlite3.connect(self.archive_path)

        cursor = self.db.cursor()
        create_stmt = "CREATE TABLE IF NOT EXISTS storage(" \
                      "id INTEGER PRIMARY KEY AUTOINCREMENT, " \
                      "backend_type TEXT, " \
                      "backend_version TEXT, " \
                      "url TEXT, " \
                      "payload TEXT, " \
                      "hash_request VARCHAR(256) UNIQUE NOT NULL , " \
                      "response BLOB, " \
                      "fetched_at TIMESTAMP)"

        cursor.execute(create_stmt)
        self.db.commit()

    def delete(self, target_name):
        """delete an archive in folder path"""

        path = self.archive_folder_path
        [os.remove(os.path.join(path, f)) for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))
         and f.startswith(target_name)
         and f.endswith(STORAGE_EXT)]

    def delete_all(self):
        """delete all archives in folder path"""

        path = self.archive_folder_path
        [os.remove(os.path.join(path, f)) for f in os.listdir(path) if os.path.isfile(os.path.join(path, f)) and f.endswith(STORAGE_EXT)]

    def archives(self):
        """list archives in folder path"""

        path = self.archive_folder_path
        [print(f) for f in os.listdir(path) if os.path.isfile(os.path.join(path, f)) and f.endswith(STORAGE_EXT)]

    def store(self, url, payload, data):
        """Store data source information.

        :url: url request
        :payload: payload request
        :data: response data
        """
        cursor = self.db.cursor()
        hash_request = self.make_digest(url, payload)
        response = pickle.dumps(data, 0)

        insert_stmt = "INSERT OR IGNORE INTO storage(" \
                      "id, backend_type, backend_version, url, payload, hash_request, response, fetched_at) " \
                      "VALUES(?,?,?,?,?,?,?,?)"
        cursor.execute(insert_stmt, (None, self.backend_name, self.backend_version,
                                     url, json.dumps(payload, sort_keys=True), hash_request, response, self.fetched_at))
        self.db.commit()

    def retrieve(self, url, payload):
        """Retrieve the data stored in the database.

        This method returns the api content corresponding to the hash_request derived from the url and payload

        :returns: the data that corresponds to the url and payload
        """

        found = None
        self.db.row_factory = sqlite3.Row
        cursor = self.db.cursor()
        hash_request = self.make_digest(url, payload)
        select_stmt = "SELECT response FROM storage WHERE hash_request = ?"
        args = (hash_request,)
        cursor.execute(select_stmt, args)

        row = cursor.fetchone()
        cursor.close()

        if row:
            found = pickle.loads(row['response'])

        return found

    def make_digest(self, url, payload):
        """return a unique sha for a given url and payload"""

        payload_str = json.dumps(payload, sort_keys=True)
        content = str(url + "@" + payload_str).encode('utf-8')
        h = hashlib.md5(content)
        return h.hexdigest()
