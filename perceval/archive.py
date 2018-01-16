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

import hashlib
import json
import logging
import os
import pickle
import sqlite3

from grimoirelab.toolkit.datetime import (datetime_utcnow,
                                          datetime_to_utc,
                                          str_to_datetime)

from .errors import ArchiveError


logger = logging.getLogger(__name__)


class Archive:
    """Basic class for archiving raw items fetched by Perceval.

    This class allows to archive raw items - usually HTML pages or
    JSON documents - for a further recovery. These raw items will
    be fetched, stored and retrieved back by a backend.

    Each stored item will have a hash code used as unique identifier.
    Hash codes are generated using URIs and other parameters needed
    to fetch raw items.

    When an instance of `Archive` is initialized it will expect
    to access an existing archive file. To create a new and empty
    archive used `create` class method instead. Metadata must be
    initialized calling to `init_metadata` method after creating
    a new archive.

    :param archive_path: path where this archive is stored

    :raises ArchiveError: when the archive does not exist or is invalid
    """

    ARCHIVE_TABLE = "archive"
    METADATA_TABLE = "metadata"

    # Table structure
    ARCHIVE_CREATE_STMT = "CREATE TABLE " + ARCHIVE_TABLE + " ( " \
                          "id INTEGER PRIMARY KEY AUTOINCREMENT, " \
                          "hashcode VARCHAR(256) UNIQUE NOT NULL, " \
                          "uri TEXT, " \
                          "payload BLOB, " \
                          "headers BLOB, " \
                          "data BLOB)"

    METADATA_CREATE_STMT = "CREATE TABLE " + METADATA_TABLE + " ( " \
                           "origin TEXT, " \
                           "backend_name TEXT, " \
                           "backend_version TEXT, " \
                           "item_category TEXT, " \
                           "backend_params BLOB, " \
                           "created_on TEXT)"

    def __init__(self, archive_path):
        if not os.path.exists(archive_path):
            raise ArchiveError(cause="archive %s does not exist" % (archive_path))

        self.archive_path = archive_path
        self.origin = None
        self.backend_name = None
        self.backend_version = None
        self.item_category = None
        self.backend_params = None
        self.created_on = None

        self._db = sqlite3.connect(self.archive_path)

        self._verify_archive()
        self._load_metadata()

    def __del__(self):
        conn = getattr(self, '_db', None)
        if conn:
            conn.close()

    def init_metadata(self, origin, backend_name, backend_version,
                      item_category, backend_params):
        """Init metadata information.

        Metatada is composed by basic information needed to identify
        where archived data came from and how it can be retrieved
        and built into Perceval items.

        :param: origin: identifier of the repository
        :param: backend_name: name of the backend
        :param: backend_version: version of the backend
        :param: item_category: category of the items fetched
        :param: backend_params: dict representation of the fetch parameters

        raises ArchiveError: when an error occurs initializing the metadata
        """
        created_on = datetime_to_utc(datetime_utcnow())
        created_on_dumped = created_on.isoformat()
        backend_params_dumped = pickle.dumps(backend_params, 0)

        metadata = (origin, backend_name, backend_version, item_category,
                    backend_params_dumped, created_on_dumped,)

        try:
            cursor = self._db.cursor()
            insert_stmt = "INSERT INTO " + self.METADATA_TABLE + " "\
                          "(origin, backend_name, backend_version, " \
                          "item_category, backend_params, created_on) " \
                          "VALUES (?, ?, ?, ?, ?, ?)"
            cursor.execute(insert_stmt, metadata)

            self._db.commit()
            cursor.close()
        except sqlite3.DatabaseError as e:
            msg = "metadata initialization error; cause: %s" % str(e)
            raise ArchiveError(cause=msg)

        self.origin = origin
        self.backend_name = backend_name
        self.backend_version = backend_version
        self.item_category = item_category
        self.backend_params = backend_params
        self.created_on = created_on

        logger.debug("Metadata of archive %s initialized to %s",
                     self.archive_path, metadata)

    def store(self, uri, payload, headers, data):
        """Store a raw item in this archive.

        The method will store `data` content in this archive. The unique
        identifier for that item will be generated using the rest of the
        parameters.

        :param uri: request URI
        :param payload: request payload
        :param headers: request headers
        :param data: data to store in this archive

        :raises ArchiveError: when an error occurs storing the given data
        """
        hashcode = self.make_hashcode(uri, payload, headers)
        payload_dump = pickle.dumps(payload, 0)
        headers_dump = pickle.dumps(headers, 0)
        data_dump = pickle.dumps(data, 0)

        logger.debug("Archiving %s with %s %s %s in %s",
                     hashcode, uri, payload, headers, self.archive_path)

        try:
            cursor = self._db.cursor()
            insert_stmt = "INSERT INTO " + self.ARCHIVE_TABLE + " (" \
                          "id, hashcode, uri, payload, headers, data) " \
                          "VALUES(?,?,?,?,?,?)"
            cursor.execute(insert_stmt, (None, hashcode, uri,
                                         payload_dump, headers_dump, data_dump))
            self._db.commit()
            cursor.close()
        except sqlite3.IntegrityError as e:
            msg = "data storage error; cause: duplicated entry %s" % hashcode
            raise ArchiveError(cause=msg)
        except sqlite3.DatabaseError as e:
            msg = "data storage error; cause: %s" % str(e)
            raise ArchiveError(cause=msg)

        logger.debug("%s data archived in %s", hashcode, self.archive_path)

    def retrieve(self, uri, payload, headers):
        """Retrieve a raw item from the archive.

        The method will return the `data` content corresponding to the
        hascode derived from the given parameters.

        :param uri: request URI
        :param payload: request payload
        :param headers: request headers

        :returns: the archived data

        :raises ArchiveError: when an error occurs retrieving data
        """
        hashcode = self.make_hashcode(uri, payload, headers)

        logger.debug("Retrieving entry %s with %s %s %s in %s",
                     hashcode, uri, payload, headers, self.archive_path)

        self._db.row_factory = sqlite3.Row

        try:
            cursor = self._db.cursor()
            select_stmt = "SELECT data " \
                          "FROM " + self.ARCHIVE_TABLE + " " \
                          "WHERE hashcode = ?"
            cursor.execute(select_stmt, (hashcode,))
            row = cursor.fetchone()
            cursor.close()
        except sqlite3.DatabaseError as e:
            msg = "data retrieval error; cause: %s" % str(e)
            raise ArchiveError(cause=msg)

        if row:
            found = pickle.loads(row['data'])
        else:
            msg = "entry %s not found in archive %s" % (hashcode, self.archive_path)
            raise ArchiveError(cause=msg)

        return found

    @classmethod
    def create(cls, archive_path):
        """Create a brand new archive.

         Call this method to create a new and empty archive. It will initialize
         the storage file in the path defined by `archive_path`.

        :param archive_path: absolute path where the archive file will be created

        :raises ArchiveError: when the archive file already exists
        """
        if os.path.exists(archive_path):
            msg = "archive %s already exists; remove it before creating a new one"
            raise ArchiveError(cause=msg % (archive_path))

        conn = sqlite3.connect(archive_path)

        cursor = conn.cursor()
        cursor.execute(cls.METADATA_CREATE_STMT)
        cursor.execute(cls.ARCHIVE_CREATE_STMT)
        conn.commit()

        cursor.close()
        conn.close()

        logger.debug("Creating archive %s", archive_path)
        archive = cls(archive_path)
        logger.debug("Achive %s was created", archive_path)

        return archive

    @staticmethod
    def make_hashcode(uri, payload, headers):
        """Generate a SHA1 based on the given arguments.

        Hashcodes created by this method will used as unique identifiers
        for the raw items or resources stored by this archive.

        :param uri: URI to the resource
        :param payload: payload of the request needed to fetch the resource
        :param headers: headers of the request needed to fetch the resource

        :returns: a SHA1 hash code
        """
        def dict_to_json_str(data):
            return json.dumps(data, sort_keys=True)

        content = ':'.join([uri, dict_to_json_str(payload), dict_to_json_str(headers)])
        hashcode = hashlib.sha1(content.encode('utf-8'))
        return hashcode.hexdigest()

    def _verify_archive(self):
        """Check whether the archive is valid or not.

        This method will check if tables were created and if they
        contain valid data.
        """
        nentries = self._count_table_rows(self.ARCHIVE_TABLE)
        nmetadata = self._count_table_rows(self.METADATA_TABLE)

        if nmetadata > 1:
            msg = "archive %s metadata corrupted; multiple metadata entries" % (self.archive_path)
            raise ArchiveError(cause=msg)
        if nmetadata == 0 and nentries > 0:
            msg = "archive %s metadata is empty but %s entries were achived" % (self.archive_path)
            raise ArchiveError(cause=msg)

        logger.debug("Integrity of archive %s OK; entries: %s rows, metadata: %s rows",
                     self.archive_path, nentries, nmetadata)

    def _load_metadata(self):
        """Load metadata from the archive file"""

        logger.debug("Loading metadata infomation of archive %s", self.archive_path)

        cursor = self._db.cursor()
        select_stmt = "SELECT origin, backend_name, backend_version, " \
                      "item_category, backend_params, created_on " \
                      "FROM " + self.METADATA_TABLE + " " \
                      "LIMIT 1"
        cursor.execute(select_stmt)
        row = cursor.fetchone()
        cursor.close()

        if row:
            self.origin = row[0]
            self.backend_name = row[1]
            self.backend_version = row[2]
            self.item_category = row[3]
            self.backend_params = pickle.loads(row[4])
            self.created_on = str_to_datetime(row[5])
        else:
            logger.debug("Metadata of archive %s was empty", self.archive_path)

        logger.debug("Metadata of archive %s loaded", self.archive_path)

    def _count_table_rows(self, table_name):
        """Fetch the number of rows in a table"""

        cursor = self._db.cursor()
        select_stmt = "SELECT COUNT(*) FROM " + table_name

        try:
            cursor.execute(select_stmt)
            row = cursor.fetchone()
        except sqlite3.DatabaseError as e:
            msg = "invalid archive file; cause: %s" % str(e)
            raise ArchiveError(cause=msg)
        finally:
            cursor.close()

        return row[0]
