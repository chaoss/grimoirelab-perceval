# -*- coding: utf-8 -*-
#
# Copyright (C) 2015-2020 Bitergia
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
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
# Authors:
#     Santiago Dueñas <sduenas@bitergia.com>
#     Germán Poo-Caamaño <gpoo@gnome.org>
#     Stephan Barth <stephan.barth@gmail.com>
#     Valerio Cosentino <valcos@bitergia.com>
#     Jesus M. Gonzalez-Barahona <jgb@gsyc.es>
#     Harshal Mittal <harshalmittal4@gmail.com>
#

# Note: some of this code was taken from the MailingListStats project

import logging
import mailbox
import os
import tempfile

import gzip
import bz2
import zipfile

from grimoirelab_toolkit.datetime import (InvalidDateError,
                                          datetime_to_utc,
                                          str_to_datetime)

from ...backend import (Backend,
                        BackendCommand,
                        BackendCommandArgumentParser)
from ...utils import (DEFAULT_DATETIME,
                      DEFAULT_LAST_DATETIME,
                      check_compressed_file_type,
                      message_to_dict)

CATEGORY_MESSAGE = "message"

logger = logging.getLogger(__name__)


class MBox(Backend):
    """MBox backend.

    This class allows the fetch the email messages stored one or several
    mbox files. Initialize this class passing the directory path where
    the mbox files are stored. The origin of the data will be set to to
    the value of `uri`.

    :param uri: URI of the mboxes; typically, the URL of their
        mailing list
    :param dirpath: directory path where the mboxes are stored
    :param tag: label used to mark the data
    :param archive: archive to store/retrieve items
    :param ssl_verify: enable/disable SSL verification
    """
    version = '0.13.2'

    CATEGORIES = [CATEGORY_MESSAGE]

    DATE_FIELD = 'Date'
    MESSAGE_ID_FIELD = 'Message-ID'

    def __init__(self, uri, dirpath, tag=None, archive=None, ssl_verify=True):
        origin = uri

        super().__init__(origin, tag=tag, archive=archive, ssl_verify=ssl_verify)
        self.uri = uri
        self.dirpath = dirpath

    def fetch(self, category=CATEGORY_MESSAGE, from_date=DEFAULT_DATETIME, to_date=DEFAULT_LAST_DATETIME):
        """Fetch the messages from a set of mbox files.

        The method retrieves, from mbox files, the messages stored in
        these containers.

        :param category: the category of items to fetch
        :param from_date: obtain messages since this date
        :param to_date: obtain messages until this date

        :returns: a generator of messages
        """
        if not from_date:
            from_date = DEFAULT_DATETIME
        if not to_date:
            to_date = DEFAULT_LAST_DATETIME

        kwargs = {
            'from_date': from_date,
            'to_date': to_date
        }
        items = super().fetch(category, **kwargs)

        return items

    def fetch_items(self, category, **kwargs):
        """Fetch the messages

        :param category: the category of items to fetch
        :param kwargs: backend arguments

        :returns: a generator of items
        """
        from_date = kwargs['from_date']
        to_date = kwargs['to_date']

        logger.info("Looking for messages from '%s' on '%s' since %s until %s",
                    self.uri, self.dirpath, str(from_date), str(to_date))

        mailing_list = MailingList(self.uri, self.dirpath)

        messages = self._fetch_and_parse_messages(mailing_list, from_date, to_date)

        for message in messages:
            yield message

        logger.info("Fetch process completed")

    @classmethod
    def has_archiving(cls):
        """Returns whether it supports archiving items on the fetch process.

        :returns: this backend does not support items archive
        """
        return False

    @classmethod
    def has_resuming(cls):
        """Returns whether it supports to resume the fetch process.

        :returns: this backend supports items resuming
        """
        return True

    @staticmethod
    def metadata_id(item):
        """Extracts the identifier from a MBox item."""

        return item[MBox.MESSAGE_ID_FIELD]

    @staticmethod
    def metadata_updated_on(item):
        """Extracts the update time from a MBox item.

        The timestamp used is extracted from 'Date' field in its
        several forms. This date is converted to UNIX timestamp
        format.

        :param item: item generated by the backend

        :returns: a UNIX timestamp
        """
        ts = item[MBox.DATE_FIELD]
        ts = str_to_datetime(ts)

        return ts.timestamp()

    @staticmethod
    def metadata_category(item):
        """Extracts the category from a MBox item.

        This backend only generates one type of item which is
        'message'.
        """
        return CATEGORY_MESSAGE

    @staticmethod
    def parse_mbox(filepath):
        """Parse a mbox file.

        This method parses a mbox file and returns an iterator of dictionaries.
        Each one of this contains an email message.

        :param filepath: path of the mbox to parse

        :returns : generator of messages; each message is stored in a
            dictionary of type `requests.structures.CaseInsensitiveDict`
        """
        mbox = _MBox(filepath, create=False)

        for msg in mbox:
            message = message_to_dict(msg)
            yield message

    def _init_client(self, from_archive=False):
        pass

    def _fetch_and_parse_messages(self, mailing_list, from_date, to_date=DEFAULT_LAST_DATETIME):
        """Fetch and parse the messages from a mailing list"""

        from_date = datetime_to_utc(from_date)
        to_date = datetime_to_utc(to_date)

        nmsgs, imsgs, tmsgs = (0, 0, 0)

        for mbox in mailing_list.mboxes:
            tmp_path = None

            try:
                tmp_path = self._copy_mbox(mbox)

                for message in self.parse_mbox(tmp_path):
                    tmsgs += 1

                    if not self._validate_message(message):
                        imsgs += 1
                        continue

                    # Ignore those messages sent before from date and after to date
                    dt = str_to_datetime(message[MBox.DATE_FIELD])

                    if dt < from_date:
                        logger.debug("Message %s sent before %s; skipped",
                                     message['unixfrom'], str(from_date))
                        tmsgs -= 1
                        continue

                    if dt > to_date:
                        logger.debug("Message %s sent after %s; skipped",
                                     message['unixfrom'], str(to_date))
                        tmsgs -= 1
                        continue

                    # Convert 'CaseInsensitiveDict' to dict
                    message = self._casedict_to_dict(message)

                    nmsgs += 1
                    logger.debug("Message %s parsed", message['unixfrom'])

                    yield message
            except (OSError, EOFError) as e:
                logger.warning("Ignoring %s mbox due to: %s", mbox.filepath, str(e))
            except Exception as e:
                if tmp_path and os.path.exists(tmp_path):
                    os.remove(tmp_path)
                raise e
            finally:
                if tmp_path and os.path.exists(tmp_path):
                    os.remove(tmp_path)

        logger.info("Done. %s/%s messages fetched; %s ignored",
                    nmsgs, tmsgs, imsgs)

    def _copy_mbox(self, mbox):
        """Copy the contents of a mbox to a temporary file"""

        tmp_path = tempfile.mktemp(prefix='perceval_')

        with mbox.container as f_in:
            with open(tmp_path, mode='wb') as f_out:
                for line in f_in:
                    f_out.write(line)
        return tmp_path

    def _validate_message(self, message):
        """Check if the given message has the mandatory fields"""

        # This check is "case insensitive" because we're
        # using 'CaseInsensitiveDict' from requests.structures
        # module to store the contents of a message.
        if self.MESSAGE_ID_FIELD not in message:
            logger.warning("Field 'Message-ID' not found in message %s; ignoring",
                           message['unixfrom'])
            return False

        if not message[self.MESSAGE_ID_FIELD]:
            logger.warning("Field 'Message-ID' is empty in message %s; ignoring",
                           message['unixfrom'])
            return False

        if self.DATE_FIELD not in message:
            logger.warning("Field 'Date' not found in message %s; ignoring",
                           message['unixfrom'])
            return False

        if not message[self.DATE_FIELD]:
            logger.warning("Field 'Date' is empty in message %s; ignoring",
                           message['unixfrom'])
            return False

        try:
            str_to_datetime(message[self.DATE_FIELD])
        except InvalidDateError:
            logger.warning("Invalid date %s in message %s; ignoring",
                           message[self.DATE_FIELD], message['unixfrom'])
            return False

        return True

    def _casedict_to_dict(self, message):
        """Convert a message in CaseInsensitiveDict to dict.

        This method also converts well known problematic headers,
        such as Message-ID and Date to a common name.
        """
        message_id = message.pop(self.MESSAGE_ID_FIELD)
        date = message.pop(self.DATE_FIELD)

        msg = {k: v for k, v in message.items()}
        msg[self.MESSAGE_ID_FIELD] = message_id
        msg[self.DATE_FIELD] = date

        return msg


class _MBox(mailbox.mbox):
    """Wrapper of `mailbox.mbox` to catch unhandled errors"""

    def get_message(self, key):
        """Return a Message representation or raise a KeyError."""

        start, stop = self._lookup(key)
        self._file.seek(start)
        from_line = self._file.readline().replace(mailbox.linesep, b'')
        string = self._file.read(stop - self._file.tell())
        msg = self._message_factory(string.replace(mailbox.linesep, b'\n'))

        try:
            msg.set_from(from_line[5:].decode('ascii'))
            return msg
        except UnicodeDecodeError:
            pass

        try:
            msg.set_from(from_line[5:].decode('utf-8'))
        except UnicodeDecodeError:
            msg.set_from(from_line[5:].decode('iso-8859-1'))

        return msg


class MBoxCommand(BackendCommand):
    """Class to run MBox backend from the command line."""

    BACKEND = MBox

    @classmethod
    def setup_cmd_parser(cls):
        """Returns the MBox argument parser."""

        parser = BackendCommandArgumentParser(cls.BACKEND,
                                              from_date=True,
                                              to_date=True,
                                              ssl_verify=True)

        # Required arguments
        parser.parser.add_argument('uri',
                                   help="URI of the mboxes, usually the URL to their mailing list")
        parser.parser.add_argument('dirpath',
                                   help="Path to the mbox directory")

        return parser


class MBoxArchive(object):
    """Class to access a mbox archive.

    MBOX archives can be stored into plain or compressed files
    (gzip, bz2 or zip).

    :param filepath: path to the mbox file
    """
    def __init__(self, filepath):
        self._filepath = filepath
        self._compressed = check_compressed_file_type(filepath)

    @property
    def filepath(self):
        return self._filepath

    @property
    def container(self):
        if not self.is_compressed():
            return open(self.filepath, mode='rb')

        if self.compressed_type == 'bz2':
            return bz2.open(self.filepath, mode='rb')
        elif self.compressed_type == 'gz':
            return gzip.open(self.filepath, mode='rb')
        elif self.compressed_type == "zip":
            _zip = zipfile.ZipFile(self.filepath)
            if len(_zip.infolist()) > 1:
                logger.error("Zip %s contains more than one file, only the first uncompressed", self.filepath)
            return _zip.open(_zip.infolist()[0].filename)

    @property
    def compressed_type(self):
        return self._compressed

    def is_compressed(self):
        return self._compressed is not None


class MailingList(object):
    """Manage mailing lists archives.

    This class gives access to the local mboxes archives that a
    mailing list manages.

    :param uri: URI of the mailing lists, usually its URL address
    :param dirpath: path to the mboxes archives
    """
    def __init__(self, uri, dirpath):
        self.uri = uri
        self.dirpath = dirpath

    @property
    def mboxes(self):
        """Get the mboxes managed by this mailing list.

        Returns the archives sorted by name.

        :returns: a list of `.MBoxArchive` objects
        """
        archives = []

        if os.path.isfile(self.dirpath):
            try:
                archives.append(MBoxArchive(self.dirpath))
            except OSError as e:
                logger.warning("Ignoring %s mbox due to: %s", self.dirpath, str(e))
        else:
            for root, _, files in os.walk(self.dirpath):
                for filename in sorted(files):
                    try:
                        location = os.path.join(root, filename)
                        archives.append(MBoxArchive(location))
                    except OSError as e:
                        logger.warning("Ignoring %s mbox due to: %s", filename, str(e))
        return archives
