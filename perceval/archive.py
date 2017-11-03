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

import hashlib
import json
import pickle
import sqlite3



ARCHIVE_DEFAULT_PATH = '~/.perceval/archive/'
STORAGE_EXT = ".sqlite3"


def dict_to_string(json_data):
    """convert a dict to str"""

    return json.dumps(json_data, sort_keys=True)


class Archive:
    """Basic storage for Perceval.

    This class allows to archive items for a
    further recovery. Items are stored in a Sqlite db.

    The archive also provides the methods `backup` and `recover` that
    prevents from possible failures.
    """

    def __init__(self, archive_path, new=False):

        self.archive_path = archive_path
        self.db = sqlite3.connect(self.archive_path)

        if new:
            cursor = self.db.cursor()
            cursor.execute("DROP TABLE IF EXISTS archive")
            self.db.commit()

            create_stmt = "CREATE TABLE archive(" \
                          "id INTEGER PRIMARY KEY AUTOINCREMENT, " \
                          "backend_type TEXT, " \
                          "backend_version TEXT, " \
                          "command TEXT, " \
                          "params TEXT, " \
                          "hash VARCHAR(256) UNIQUE NOT NULL , " \
                          "response BLOB)"

            cursor.execute(create_stmt)
            self.db.commit()

            cursor.close()

    def store(self, command, params, data, backend_name, backend_version):
        """Store data source information.

        :command: data source command
        :params: command params
        :data: response data
        """
        cursor = self.db.cursor()

        params = dict_to_string(params)
        hash_request = self.make_digest(command, params)
        response = pickle.dumps(data, 0)

        insert_stmt = "INSERT OR IGNORE INTO archive(" \
                      "id, backend_type, backend_version, command, params, hash, response) " \
                      "VALUES(?,?,?,?,?,?,?)"
        cursor.execute(insert_stmt, (None, backend_name, backend_version,
                                     command, params, hash_request, response))
        self.db.commit()
        cursor.close()

    def retrieve(self, command, params):
        """Retrieve the data stored in the database.

        This method returns the data source content corresponding to the hash_request derived from the command and params

        :returns: the data that corresponds to the command and params
        """

        found = None
        self.db.row_factory = sqlite3.Row
        cursor = self.db.cursor()
        params = dict_to_string(params)
        hash_request = self.make_digest(command, params)
        select_stmt = "SELECT response FROM archive WHERE hash_request = ?"
        args = (hash_request,)
        cursor.execute(select_stmt, args)

        row = cursor.fetchone()
        cursor.close()

        if row:
            found = pickle.loads(row['response'])

        return found

    def make_digest(self, command, params):
        """return a unique sha for a given command and params"""

        content = str(command + "@" + params).encode('utf-8')
        h = hashlib.md5(content)
        return h.hexdigest()
