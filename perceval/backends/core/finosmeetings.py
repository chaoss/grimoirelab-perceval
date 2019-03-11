# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2019 Fintech Open Source Foundation
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
#     Maurizio Pillitu <maoo@finos.org>
#

import base64
import logging
import datetime
import tempfile
import csv

from grimoirelab_toolkit.datetime import datetime_utcnow

from ...backend import (Backend,
                        BackendCommand,
                        BackendCommandArgumentParser)
from ...client import HttpClient

CATEGORY_ENTRY = "finos-meeting-entry"
SEPARATOR = ','
CSV_HEADER = 'email,name,org,githubid,program,activity,date'
DATE_FORMATS = '%a %b %d %H:%M:%S EDT %Y, %Y-%m-%d,%Y-%m-%d,%Y-%m,%Y'
SKIP_HEADER = True
ID_COLUMNS = 'email,name,date'
DATE_COLUMN = 'date'

logger = logging.getLogger(__name__)


class FinosMeetings(Backend):
    """FinosMeetings backend for Perceval.

    This class retrieves the entries from a CSV file.
    To initialize this class the CSV file path must be provided.
    The `file_path` will be set as the origin of the data.

    :param uri: URI pointer to FINOS meeting (CSV) data
    """
    version = '0.0.1'

    CATEGORIES = [CATEGORY_ENTRY]

    def __init__(self, uri, tag=None, archive=None):
        super().__init__(uri, tag, archive)
        self.client = None

    def fetch(self, category=CATEGORY_ENTRY):
        """Fetch the rows from the CSV.

        :returns: a generator of entries
        """
        kwargs = {}
        items = super().fetch(category, **kwargs)

        return items

    @staticmethod
    def date_to_timestamp(date, formats):
        if not formats:
            logger.warning("skipping entry due to wrong date format: '" + date + "'")
            return

        head, *tail = formats
        try:
            date_time_obj = datetime.datetime.strptime(date, head)
            return date_time_obj.timestamp()
        except Exception as e:
            return FinosMeetings.date_to_timestamp(date, tail)

    def parse_entries(self, rows):
        ret = []
        for i, row in enumerate(rows):
            if (SKIP_HEADER) and (i == 0):
                logger.debug("skipping header")
            else:
                ret.append(row)
        return ret

    def fetch_items(self, category, **kwargs):
        """Fetch the entries

        :param kwargs: backend arguments

        :returns: a generator of items
        """
        logger.info("Looking for csv rows at feed '%s'", self.origin)

        nentries = 0  # number of entries

        entries = self.client.get_entries()

        for item in self.parse_entries(entries):
            ret = {}
            # Need to pass which columns are IDs to metadata_id static function
            ret['_id_columns'] = ID_COLUMNS
            for i, column in enumerate(CSV_HEADER.split(',')):
                value = item[i]
                if isinstance(item[i], str):
                    value = item[i].strip()

                # If it's the date column, parse value and add it as 'timestamp' in the item
                if (column == DATE_COLUMN):
                    timestamp = FinosMeetings.date_to_timestamp(value, DATE_FORMATS.split(','))
                    if timestamp:
                        ret['timestamp'] = timestamp
                ret[column.strip()] = value
            if 'timestamp' in ret:
                yield ret
            nentries += 1

        logger.info("Total number of entries: %i", nentries)

    @classmethod
    def has_archiving(cls):
        """Returns whether it supports archiving entries on the fetch process.

        :returns: this backend does not support entries archive
        """
        return False

    @classmethod
    def has_resuming(cls):
        """Returns whether it supports to resume the fetch process.

        :returns: this backend does not supports entries resuming
        """
        return False

    @staticmethod
    def metadata_id(item):
        """Extracts the identifier from a CSV row, using the hash of the \
        concatenation of values, that can be configured using the \
        id_columns configuration parameter."""
        string = ""
        for column in item['_id_columns'].split(','):
            string = string + item[column] + "-"
        return string

    @staticmethod
    def metadata_category(item):
        """Extracts the category from a CSV item.

        This backend only generates one type of item which is
        'finos-meetings-entry'.
        """
        return CATEGORY_ENTRY

    @staticmethod
    def metadata_updated_on(item):
        """Extracts the update time from a Finos meeting CSV row.

        The timestamp is calculated before and stored into the 'timestamp' fieldextracted from 'published' field.

        :param item: item generated by the backend

        :returns: the timestamp field, UNIX format
        """
        return item['timestamp']

    def _init_client(self, from_archive=False):
        """Init client"""
        return FinosMeetingsClient(self.origin, SEPARATOR, SKIP_HEADER)


class FinosMeetingsClient(HttpClient):
    """FinosMeetings API client.

    :param uri: URI Pointer to CSV contents
    """

    def __init__(self, uri, archive=None, from_archive=False):
        if uri.startswith('file://'):
            self.file_path = uri.split('file://', 1)[1]
        else:
            self.file_path = tempfile.mkdtemp() + "/perceval-finos-meetings-backend-" + str(datetime_utcnow()) + ".csv"
            super().__init__(uri, archive=archive, from_archive=from_archive)
            response = self.session.get(uri)
            open(self.file_path, 'wb').write(response.content)

    def get_entries(self):
        """ Retrieve all entries from a CVS file"""
        self.session = None
        with open(self.file_path, newline='') as csv_content:
            reader = csv.reader(csv_content, delimiter=SEPARATOR)
            rows = []
            for row in reader:
                rows.append(row)
            return rows


class FinosMeetingsCommand(BackendCommand):
    """Class to run FinosMeetings backend from the command line."""

    BACKEND = FinosMeetings

    @staticmethod
    def setup_cmd_parser():
        """Returns the FinosMeetings argument parser."""

        parser = BackendCommandArgumentParser()

        # Required arguments
        parser.parser.add_argument('uri',
                                   help="URI pointer to FINOS meetings data")

        return parser
