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
import mailbox
import os
import tempfile

import gzip
import bz2

from ..backend import Backend, BackendCommand, metadata
from ..utils import check_compressed_file_type


def get_update_time(item):
    """Extracts the update time from a message item"""
    return item['Date']


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
        mailing_list = MailingList(self.origin, self.dirpath)

        for mbox in mailing_list.mboxes:
            try:
                tmp_path = tempfile.mktemp(prefix='perceval_')

                with mbox.container as f_in:
                    with open(tmp_path, mode='wb') as f_out:
                        for l in f_in:
                            f_out.write(l)

                for message in self.parse_mbox(tmp_path):
                    yield message
                os.remove(tmp_path)
            except Exception as e:
                os.remove(tmp_path)
                raise e

    @staticmethod
    def parse_mbox(filepath):
        """Parse a mbox file.

        This method parses a mbox file and returns an iterator of dictionaries.
        Each one of this contains an email message.

        :param filepath: path of the mbox to parse
        """
        mbox = mailbox.mbox(filepath, create=False)

        for msg in mbox:
            message = {}
            message['unixfrom'] = msg.get_from()

            # Parse headers
            for header, value in msg.items():
                hv = []
                for text, charset in email.header.decode_header(value):
                    if type(text) == bytes:
                        charset = charset if charset else 'utf-8'
                        text = text.decode(charset)
                    hv.append(text)
                v = ' '.join(hv)
                message[header] = v if v else None

            # Parse message body
            body = {}

            if not msg.is_multipart():
                subtype = msg.get_content_subtype()
                charset = msg.get_content_charset()
                charset = charset if charset else 'utf-8'
                body[subtype] = [msg.get_payload(decode=True).decode(charset)]
            else:
                # Include all the attached texts if it is multipart
                # Ignores binary parts by default
                for part in email.iterators.typed_subpart_iterator(msg):
                    charset = part.get_content_charset('utf-8')
                    payload = part.get_payload(decode=True)
                    payload = payload.decode(charset)
                    subtype = part.get_content_subtype()
                    body.setdefault(subtype, []).append(payload)

            message['body'] = {k : '\n'.join(v) for k, v in body.items()}

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
            archives.append(MBoxArchive(self.dirpath))
        else:
            for root, _, files in os.walk(self.dirpath):
                for filename in sorted(files):
                    location = os.path.join(root, filename)
                    archives.append(MBoxArchive(location))
        return archives
