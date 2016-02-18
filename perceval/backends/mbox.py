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
from ..utils import check_compressed_file_type


logger = logging.getLogger(__name__)


def get_update_time(item):
    """Extracts the update time from a message item"""

    date = item['Date'] if 'Date' in item else item['date']
    return date


class MBox(Backend):
    """MBox backend.

    This class allows the fetch the email messages stored one or several
    mbox files. Initialize this class passing the directory path where
    the mbox files are stored.

    :param origin: origin of the mboxes; typically, the URL of their
        mailing list
    :param dirpath: directory path where the mboxes are stored
    :param cache: cache object to store raw data
    """
    version = '0.1.0'

    def __init__(self, origin, dirpath, cache=None):
        super().__init__(origin, cache=cache)
        self.dirpath = dirpath

    @metadata(get_update_time)
    def fetch(self):
        """Fetch the commits from a set of mbox files.

        The method retrieves, from mbox files, the messages stored in
        these containers.

        :returns: a generator of messages
        """
        logger.info("Looking for messages from '%s' on '%s'",
                    self.origin, self.dirpath)

        mailing_list = MailingList(self.origin, self.dirpath)

        nmsgs, imsgs, tmsgs = (0, 0, 0)

        for mbox in mailing_list.mboxes:
            try:
                tmp_path = self._copy_mbox(mbox)

                for message in self.parse_mbox(tmp_path):
                    tmsgs += 1

                    if not self._validate_message(message):
                        imsgs += 1
                        continue

                    nmsgs += 1
                    logger.debug("Message from %s parsed", message['unixfrom'])

                    # Convert 'CaseInsensitiveDict' to dict
                    message = {k : v for k, v in message.items()}

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


        logger.info("Fetch process completed: %s/%s messages fetched; %s ignored",
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
        if 'Message-ID' not in message:
            logger.warning("Field 'Message-ID' not found in message %s; ignoring",
                           message['unixfrom'])
            return False
        elif 'Date' not in message:
            logger.warning("Field 'Date' not found in message %s; ignoring",
                           message['unixfrom'])
            return False
        else:
            return True

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

        self.origin = self.parsed_args.origin
        self.mboxes = self.parsed_args.mboxes
        self.outfile = self.parsed_args.outfile

        cache = None

        self.backend = MBox(self.origin, self.mboxes,
                            cache=cache)

    def run(self):
        """Fetch and print the email messages.

        This method runs the backend to fetch the email messages from
        the given directory. Messages are converted to JSON objects
        and printed to the defined output.
        """
        messages = self.backend.fetch()

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
        parser.add_argument('origin',
                            help='Origin of the mboxes, usually the URL to their mailing list')
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

    :param origin: origin of the mailing lists, usually its URL address
    :param dirpath: path to the mboxes archives
    """
    def __init__(self, origin, dirpath):
        self.origin = origin
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
