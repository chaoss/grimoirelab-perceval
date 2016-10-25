# -*- coding: utf-8 -*-
#
# Copyright (C) 2015-2016 Bitergia
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
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
#
# Authors:
#     Santiago Dueñas <sduenas@bitergia.com>
#     Germán Poo-Caamaño <gpoo@gnome.org>
#
# Note: some ot this code was taken from the MailingListStats project
#

import email
import json
import logging
import mailbox
import os
import tempfile

import gzip
import bz2

import requests.structures

from ..backend import Backend, BackendCommand, metadata
from ..errors import ParseError
from ..utils import (DEFAULT_DATETIME,
                     check_compressed_file_type,
                     datetime_to_utc,
                     str_to_datetime)


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
    :param cache: cache object to store raw data
    """
    version = '0.7.0'

    DATE_FIELD = 'Date'
    MESSAGE_ID_FIELD = 'Message-ID'

    def __init__(self, uri, dirpath, tag=None, cache=None):
        origin = uri

        super().__init__(origin, tag=tag, cache=cache)
        self.uri = uri
        self.dirpath = dirpath

    @metadata
    def fetch(self, from_date=DEFAULT_DATETIME):
        """Fetch the messages from a set of mbox files.

        The method retrieves, from mbox files, the messages stored in
        these containers.

        :param from_date: obtain messages since this date

        :returns: a generator of messages
        """
        logger.info("Looking for messages from '%s' on '%s' since %s",
                    self.uri, self.dirpath, str(from_date))

        mailing_list = MailingList(self.uri, self.dirpath)

        messages = self._fetch_and_parse_messages(mailing_list, from_date)

        for message in messages:
            yield message

        logger.info("Fetch process completed")

    def _fetch_and_parse_messages(self, mailing_list, from_date):
        """Fetch and parse the messages from a mailing list"""

        from_date = datetime_to_utc(from_date)

        nmsgs, imsgs, tmsgs = (0, 0, 0)

        for mbox in mailing_list.mboxes:
            try:
                tmp_path = self._copy_mbox(mbox)

                for message in self.parse_mbox(tmp_path):
                    tmsgs += 1

                    if not self._validate_message(message):
                        imsgs += 1
                        continue

                    # Ignore those messages sent before the given date
                    dt = str_to_datetime(message[MBox.DATE_FIELD])

                    if dt < from_date:
                        logger.debug("Message %s sent before %s; skipped",
                                     message['unixfrom'], str(from_date))
                        tmsgs -= 1
                        continue

                    # Convert 'CaseInsensitiveDict' to dict
                    message = self._casedict_to_dict(message)

                    nmsgs += 1
                    logger.debug("Message %s parsed", message['unixfrom'])

                    yield message
            except OSError as e:
                logger.warning("Ignoring %s mbox due to: %s", mbox.filepath, str(e))
            except Exception as e:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
                raise e
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)

        logger.info("Done. %s/%s messages fetched; %s ignored",
                    nmsgs, tmsgs, imsgs)

    def _copy_mbox(self, mbox):
        """Copy the contents of a mbox to a temporary file"""

        tmp_path = tempfile.mktemp(prefix='perceval_')

        with mbox.container as f_in:
            with open(tmp_path, mode='wb') as f_out:
                for l in f_in:
                    f_out.write(l)
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
        elif not message[self.MESSAGE_ID_FIELD]:
            logger.warning("Field 'Message-ID' is empty in message %s; ignoring",
                           message['unixfrom'])
            return False
        elif self.DATE_FIELD not in message:
            logger.warning("Field 'Date' not found in message %s; ignoring",
                           message['unixfrom'])
            return False
        elif not message[self.DATE_FIELD]:
            logger.warning("Field 'Date' is empty in message %s; ignoring",
                           message['unixfrom'])
            return False
        else:
            return True

    def _casedict_to_dict(self, message):
        """Convert a message in CaseInsensitiveDict to dict.

        This method also converts well known problematic headers,
        such as Message-ID and Date to a common name.
        """
        message_id = message.pop(self.MESSAGE_ID_FIELD)
        date = message.pop(self.DATE_FIELD)

        msg = {k : v for k, v in message.items()}
        msg[self.MESSAGE_ID_FIELD] = message_id
        msg[self.DATE_FIELD] = date

        return msg

    @classmethod
    def has_caching(cls):
        """Returns whether it supports caching items on the fetch process.

        :returns: this backend does not support items cache
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
        return 'message'

    @staticmethod
    def parse_mbox(filepath):
        """Parse a mbox file.

        This method parses a mbox file and returns an iterator of dictionaries.
        Each one of this contains an email message.

        :param filepath: path of the mbox to parse

        :returns : generator of messages; each message is stored in a
            dictionary of type `requests.structures.CaseInsensitiveDict`
        """
        def parse_headers(msg):
            headers = {}

            for header, value in msg.items():
                hv = []

                for text, charset in email.header.decode_header(value):
                    if type(text) == bytes:
                        charset = charset if charset else 'utf-8'
                        try:
                            text = text.decode(charset, errors='surrogateescape')
                        except (UnicodeError, LookupError):
                            # Try again with a 7bit encoding
                            text = text.decode('ascii', errors='surrogateescape')
                    hv.append(text)

                v = ' '.join(hv)
                headers[header] = v if v else None

            return headers

        def parse_payload(msg):
            body = {}

            if not msg.is_multipart():
                payload = decode_payload(msg)
                subtype = msg.get_content_subtype()
                body[subtype] = [payload]
            else:
                # Include all the attached texts if it is multipart
                # Ignores binary parts by default
                for part in email.iterators.typed_subpart_iterator(msg):
                    payload = decode_payload(part)
                    subtype = part.get_content_subtype()
                    body.setdefault(subtype, []).append(payload)

            return {k : '\n'.join(v) for k, v in body.items()}

        def decode_payload(msg_or_part):
            charset = msg_or_part.get_content_charset('utf-8')
            payload = msg_or_part.get_payload(decode=True)

            try:
                payload = payload.decode(charset, errors='surrogateescape')
            except (UnicodeError, LookupError):
                # Try again with a 7bit encoding
                payload = payload.decode('ascii', errors='surrogateescape')
            return payload

        mbox = mailbox.mbox(filepath, create=False)

        for msg in mbox:
            message = requests.structures.CaseInsensitiveDict()
            message['unixfrom'] = msg.get_from()

            try:
                for k, v in parse_headers(msg).items():
                    message[k] = v
                message['body'] = parse_payload(msg)
            except UnicodeError as e:
                raise ParseError(str(e))

            yield message


class MBoxCommand(BackendCommand):
    """Class to run MBox backend from the command line."""

    def __init__(self, *args):
        super().__init__(*args)

        self.uri = self.parsed_args.uri
        self.mboxes = self.parsed_args.mboxes
        self.outfile = self.parsed_args.outfile
        self.tag = self.parsed_args.tag
        self.from_date = str_to_datetime(self.parsed_args.from_date)

        cache = None

        self.backend = MBox(self.uri, self.mboxes,
                            tag=self.tag, cache=cache)

    def run(self):
        """Fetch and print the email messages.

        This method runs the backend to fetch the email messages from
        the given directory. Messages are converted to JSON objects
        and printed to the defined output.
        """
        messages = self.backend.fetch(from_date=self.from_date)

        try:
            for message in messages:
                obj = json.dumps(message, indent=4, sort_keys=True)
                self.outfile.write(obj)
                self.outfile.write('\n')
        except IOError as e:
            raise RuntimeError(str(e))
        except Exception as e:
            raise RuntimeError(str(e))

    @classmethod
    def create_argument_parser(cls):
        """Returns the MBox argument parser."""

        parser = super().create_argument_parser()

        # Required arguments
        parser.add_argument('uri',
                            help='URI of the mboxes, usually the URL to their mailing list')
        parser.add_argument('mboxes',
                            help="Path to the mbox directory")

        return parser


class MBoxArchive(object):
    """Class to access a mbox archive.

    MBOX archives can be stored into plain or compressed files
    (gzip and bz2).

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
