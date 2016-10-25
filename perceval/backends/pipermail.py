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
# Note: some ot this code was based on parts of the MailingListStats project
#

import datetime
import json
import logging
import os

import bs4
import dateutil
import requests

from .mbox import MBox, MailingList
from ..backend import BackendCommand, metadata
from ..utils import (DEFAULT_DATETIME,
                     datetime_to_utc,
                     str_to_datetime,
                     urljoin)


logger = logging.getLogger(__name__)


PIPERMAIL_COMPRESSED_TYPES = ['.gz', '.bz2', '.zip',
                              '.tar', '.tar.gz', '.tar.bz2',
                              '.tgz', '.tbz']
PIPERMAIL_ACCEPTED_TYPES = ['.mbox', '.txt']
PIPERMAIL_TYPES = PIPERMAIL_COMPRESSED_TYPES + PIPERMAIL_ACCEPTED_TYPES

MOD_MBOX_THREAD_STR = "/thread"


class Pipermail(MBox):
    """Pipermail backend.

    This class allows the fetch the email messages stored on a Pipermail
    archiver. Initialize this class passing the URL where the archiver is
    and the directory path where the mbox files will be fetched and
    stored. The origin of the data will be set to the value of `url`.

    :param url: URL to the Pipermail archiver
    :param dirpath: directory path where the mboxes are stored
    :param tag: label used to mark the data
    :param cache: cache object to store raw data
    """
    version = '0.4.1'

    def __init__(self, url, dirpath, tag=None, cache=None):
        origin = url

        super().__init__(url, dirpath, tag=tag, cache=cache)
        self.url = url

    @metadata
    def fetch(self, from_date=DEFAULT_DATETIME):
        """Fetch the messages from the Pipermail archiver.

        The method fetches the mbox files from a remote Pipermail
        archiver and retrieves the messages stored on them.

        :param from_date: obtain messages since this date

        :returns: a generator of messages
        """
        logger.info("Looking for messages from '%s' since %s",
                    self.url, str(from_date))

        mailing_list = PipermailList(self.url, self.dirpath)
        mailing_list.fetch(from_date=from_date)

        messages = self._fetch_and_parse_messages(mailing_list, from_date)

        for message in messages:
            yield message

        logger.info("Fetch process completed")

    @classmethod
    def has_caching(cls):
        """Returns whether it supports caching items on the fetch process.

        :returns: this backend dooes not support items cache
        """
        return False

    @classmethod
    def has_resuming(cls):
        """Returns whether it supports to resume the fetch process.

        :returns: this backend supports items resuming
        """
        return True


class PipermailCommand(BackendCommand):
    """Class to run Pipermail backend from the command line."""

    def __init__(self, *args):
        super().__init__(*args)

        self.url = self.parsed_args.url
        self.outfile = self.parsed_args.outfile
        self.tag = self.parsed_args.tag
        self.from_date = str_to_datetime(self.parsed_args.from_date)

        if not self.parsed_args.mboxes_path:
            base_path = os.path.expanduser('~/.perceval/mailinglists/')
            self.mboxes_path = os.path.join(base_path, self.url)
        else:
            self.mboxes_path = self.parsed_args.mboxes_path

        cache = None

        self.backend = Pipermail(self.url, self.mboxes_path,
                                 tag=self.tag, cache=cache)

    def run(self):
        """Fetch and print the email messages.

        This method runs the backend to fetch the email messages from
        the given archiver. Messages are converted to JSON objects
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
        """Returns the Pipermail argument parser."""

        parser = super().create_argument_parser()

        # Optional arguments
        parser.add_argument('--mboxes-path', dest='mboxes_path',
                            help='Path where mbox files will be stored')

        # Required arguments
        parser.add_argument('url',
                            help='URL of the archiver')

        return parser


class PipermailList(MailingList):
    """Manage mailing list archives stored by Pipermail archiver.

    This class gives access to remote and local mboxes archives
    from a mailing list stored by Pipermail. This class also allows
    to keep them in sync.

    :param url: URL to the Pipermail archiver for this list
    :param dirpath: path to the local mboxes archives
    """
    def __init__(self, url, dirpath):
        super().__init__(url, dirpath)
        self.url = url

    def fetch(self, from_date=DEFAULT_DATETIME):
        """Fetch the mbox files from the remote archiver.

        Stores the archives in the path given during the initialization
        of this object. Those archives which a not valid extension will
        be ignored.

        Pipermail archives usually have on their file names the date of
        the archives stored following the schema year-month. When `from_date`
        property is called, it will return the mboxes which their year
        and month are equal or after that date.

        :param from_date: fetch archives that store messages
            equal or after the given date; only year and month values
            are compared

        :returns: a list of tuples, storing the links and paths of the
            fetched archives
        """
        logger.info("Downloading mboxes from '%s' to since %s",
                    self.url, str(from_date))
        logger.debug("Storing mboxes in '%s'", self.dirpath)

        from_date = datetime_to_utc(from_date)

        r = requests.get(self.url)
        r.raise_for_status()

        links = self._parse_archive_links(r.text)

        fetched = []

        if not os.path.exists(self.dirpath):
            os.makedirs(self.dirpath)

        for l in links:
            filename = os.path.basename(l)

            mbox_dt = self._parse_date_from_filepath(filename)

            if (from_date.year == mbox_dt.year and \
                from_date.month == mbox_dt.month) or \
                from_date < mbox_dt:

                filepath = os.path.join(self.dirpath, filename)
                success = self._download_archive(l, filepath)

                if success:
                    fetched.append((l, filepath))

        logger.info("%s/%s MBoxes downloaded", len(fetched), len(links))

        return fetched

    @property
    def mboxes(self):
        """Get the mboxes managed by this mailing list.

        Returns the archives sorted by date in ascending order.

        :returns: a list of `.MBoxArchive` objects
        """
        archives = []

        for mbox in super().mboxes:
            dt = self._parse_date_from_filepath(mbox.filepath)
            archives.append((dt, mbox))

        archives.sort(key=lambda x: x[0])

        return [a[1] for a in archives]

    def _parse_archive_links(self, raw_html):
        bs = bs4.BeautifulSoup(raw_html)

        candidates = [a['href'] for a in bs.find_all('a', href=True)]
        links = []

        for candidate in candidates:
            # Links from Apache's 'mod_mbox' plugin contain
            # trailing "/thread" substrings. Remove them to get
            # the links where mbox files are stored.
            if candidate.endswith(MOD_MBOX_THREAD_STR):
                candidate = candidate[:-len(MOD_MBOX_THREAD_STR)]

            # Ignore links with not recognized extension
            ext1 = os.path.splitext(candidate)[-1]
            ext2 = os.path.splitext(candidate.rstrip(ext1))[-1]

            if ext1 in PIPERMAIL_TYPES or ext2 in PIPERMAIL_TYPES:
                links.append(urljoin(self.url, candidate))
            else:
                logger.debug("Ignoring %s archive because its extension was not recognized",
                             candidate)

        logger.debug("%s archives found", len(links))

        return links

    def _parse_date_from_filepath(self, filepath):
        default_dt = datetime.datetime(2100, 1, 1,
                                       tzinfo=dateutil.tz.tzutc())

        try:
            name = os.path.basename(filepath)
            dt = dateutil.parser.parse(name, default=default_dt,
                                       fuzzy=True)
        except (AttributeError, TypeError, ValueError) as e:
            dt = default_dt
            logger.debug("Date of file %s not detected due to %s",
                         filepath, str(e))
            logger.debug("Date set to default: %s", str(dt))

        return dt

    def _download_archive(self, url, filepath):
        r = requests.get(url, stream=True)
        r.raise_for_status()

        try:
            with open(filepath, 'wb') as fd:
                fd.write(r.raw.read())
        except OSError as e:
            logger.warning("Ignoring %s archive due to: %s", url, str(e))
            return False

        logger.debug("%s archive downloaded and stored in %s", url, filepath)

        return True
