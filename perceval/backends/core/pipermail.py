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

# Note: some of this code was based on parts of the MailingListStats project

import datetime
import logging
import os

import bs4
import dateutil
import requests

from grimoirelab_toolkit.datetime import datetime_to_utc
from grimoirelab_toolkit.uris import urijoin

from .mbox import MBox, MailingList, CATEGORY_MESSAGE
from ...backend import (BackendCommand,
                        BackendCommandArgumentParser)
from ...utils import DEFAULT_DATETIME

PIPERMAIL_COMPRESSED_TYPES = ['.gz', '.bz2', '.zip',
                              '.tar', '.tar.gz', '.tar.bz2',
                              '.tgz', '.tbz']
PIPERMAIL_ACCEPTED_TYPES = ['.mbox', '.txt']
PIPERMAIL_TYPES = PIPERMAIL_COMPRESSED_TYPES + PIPERMAIL_ACCEPTED_TYPES

MOD_MBOX_THREAD_STR = "/thread"

logger = logging.getLogger(__name__)


class Pipermail(MBox):
    """Pipermail backend.

    This class allows the fetch the email messages stored on a Pipermail
    archiver. Initialize this class passing the URL where the archiver is
    and the directory path where the mbox files will be fetched and
    stored. The origin of the data will be set to the value of `url`.

    :param url: URL to the Pipermail archiver
    :param dirpath: directory path where the mboxes are stored
    :param tag: label used to mark the data
    :param archive: archive to store/retrieve items
    :param ssl_verify: enable/disable SSL verification
    """
    version = '0.11.1'

    CATEGORIES = [CATEGORY_MESSAGE]

    def __init__(self, url, dirpath, tag=None, archive=None, ssl_verify=True):
        super().__init__(url, dirpath, tag=tag, archive=archive, ssl_verify=ssl_verify)
        self.url = url

    def fetch(self, category=CATEGORY_MESSAGE, from_date=DEFAULT_DATETIME):
        """Fetch the messages from the Pipermail archiver.

        The method fetches the mbox files from a remote Pipermail
        archiver and retrieves the messages stored on them.

        :param category: the category of items to fetch
        :param from_date: obtain messages since this date

        :returns: a generator of messages
        """
        items = super().fetch(category, from_date)

        return items

    def fetch_items(self, category, **kwargs):
        """Fetch the messages

        :param category: the category of items to fetch
        :param kwargs: backend arguments

        :returns: a generator of items
        """
        from_date = kwargs['from_date']

        logger.info("Looking for messages from '%s' since %s",
                    self.url, str(from_date))

        mailing_list = PipermailList(self.url, self.dirpath, self.ssl_verify)
        mailing_list.fetch(from_date=from_date)

        messages = self._fetch_and_parse_messages(mailing_list, from_date)

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


class PipermailCommand(BackendCommand):
    """Class to run Pipermail backend from the command line."""

    BACKEND = Pipermail

    def _pre_init(self):
        """Initialize mailing lists directory path"""

        if not self.parsed_args.mboxes_path:
            base_path = os.path.expanduser('~/.perceval/mailinglists/')
            dirpath = os.path.join(base_path, self.parsed_args.url)
        else:
            dirpath = self.parsed_args.mboxes_path

        setattr(self.parsed_args, 'dirpath', dirpath)

    @classmethod
    def setup_cmd_parser(cls):
        """Returns the Pipermail argument parser."""

        parser = BackendCommandArgumentParser(cls.BACKEND,
                                              from_date=True,
                                              ssl_verify=True)

        # Optional arguments
        group = parser.parser.add_argument_group('Pipermail arguments')
        group.add_argument('--mboxes-path', dest='mboxes_path',
                           help="Path where mbox files will be stored")

        # Required arguments
        parser.parser.add_argument('url',
                                   help="URL of the archiver")

        return parser


class PipermailList(MailingList):
    """Manage mailing list archives stored by Pipermail archiver.

    This class gives access to remote and local mboxes archives
    from a mailing list stored by Pipermail. This class also allows
    to keep them in sync.

    :param url: URL to the Pipermail archiver for this list
    :param dirpath: path to the local mboxes archives
    :param ssl_verify: enable/disable SSL verification
    """
    def __init__(self, url, dirpath, ssl_verify=True):
        super().__init__(url, dirpath)
        self.url = url
        self.ssl_verify = ssl_verify

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

        r = requests.get(self.url, verify=self.ssl_verify)
        r.raise_for_status()

        links = self._parse_archive_links(r.text)

        fetched = []

        if not os.path.exists(self.dirpath):
            os.makedirs(self.dirpath)

        for link in links:
            filename = os.path.basename(link)

            mbox_dt = self._parse_date_from_filepath(filename)

            if ((from_date.year == mbox_dt.year and
                from_date.month == mbox_dt.month) or
                from_date < mbox_dt):

                filepath = os.path.join(self.dirpath, filename)
                success = self._download_archive(link, filepath)

                if success:
                    fetched.append((link, filepath))

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
        bs = bs4.BeautifulSoup(raw_html, 'html.parser')

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
                links.append(urijoin(self.url, candidate))
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
        try:
            r = requests.get(url, stream=True, verify=self.ssl_verify)
            r.raise_for_status()
            self._write_archive(r, filepath)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                logger.warning("Ignoring %s archive due to: %s", url, str(e))
                return False
            else:
                raise e
        except OSError as e:
            logger.warning("Ignoring %s archive due to: %s", url, str(e))
            return False

        logger.debug("%s archive downloaded and stored in %s", url, filepath)

        return True

    @staticmethod
    def _write_archive(r, filepath):
        with open(filepath, 'wb') as fd:
            fd.write(r.raw.read())
