# -*- coding: utf-8 -*-
#
# Copyright (C) 2015-2018 Bitergia
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
#     Santiago Dueñas <sduenas@bitergia.com>
#

import datetime
import logging
import os

import dateutil.parser
import dateutil.relativedelta
import dateutil.tz

from grimoirelab_toolkit.datetime import datetime_to_utc, datetime_utcnow
from grimoirelab_toolkit.uris import urijoin

from .mbox import MBox, MailingList, CATEGORY_MESSAGE
from ...backend import (BackendCommand,
                        BackendCommandArgumentParser)
from ...client import HttpClient
from ...utils import (DEFAULT_DATETIME,
                      months_range)

logger = logging.getLogger(__name__)


class HyperKitty(MBox):
    """HyperKitty backend.

    This class allows the fetch the email messages stored on a HyperKitty
    archiver. Initialize this class passing the URL where the mailing list
    archiver is and the directory path where the mbox files will be fetched
    and stored. The origin of the data will be set to the value of `url`.

    :param url: URL to the HyperKitty mailing list archiver
    :param dirpath: directory path where the mboxes are stored
    :param tag: label used to mark the data
    :param archive: archive to store/retrieve items
    """
    version = '0.4.2'

    CATEGORIES = [CATEGORY_MESSAGE]

    def __init__(self, url, dirpath, tag=None, archive=None):
        super().__init__(url, dirpath, tag=tag, archive=archive)
        self.url = url

    def fetch(self, category=CATEGORY_MESSAGE, from_date=DEFAULT_DATETIME):
        """Fetch the messages from the HyperKitty mailing list archiver.

        The method fetches the mbox files from a remote HyperKitty
        mailing list archiver and retrieves the messages stored on them.

        Take into account that HyperKitty does not provide yet any kind
        of info to know which is the first message on the mailing list.
        For this reason, using a value in `from_date` previous to the
        date where the first message was sent will make to download
        empty mbox files.

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

        mailing_list = HyperKittyList(self.url, self.dirpath)
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


class HyperKittyList(MailingList):
    """Manage mailing list archives stored by HyperKitty archiver.

    This class gives access to remote and local mboxes archives
    from a mailing list stored by HyperKitty. This class also allows
    to keep them in sync.

    Notice that this class only works with HyperKitty version 1.0.4
    or greater. Previous versions do not export messages in MBox
    format.

    :param url: URL to the HyperKitty archiver for this list
    :param dirpath: path to the local mboxes archives
    """
    def __init__(self, url, dirpath):
        super().__init__(url, dirpath)
        self.client = HttpClient(url)

    def fetch(self, from_date=DEFAULT_DATETIME):
        """Fetch the mbox files from the remote archiver.

        This method stores the archives in the path given during the
        initialization of this object.

        HyperKitty archives are accessed month by month and stored following
        the schema year-month. Archives are fetched from the given month
        till the current month.

        :param from_date: fetch archives that store messages
            equal or after the given date; only year and month values
            are compared

        :returns: a list of tuples, storing the links and paths of the
            fetched archives
        """
        logger.info("Downloading mboxes from '%s' to since %s",
                    self.client.base_url, str(from_date))
        logger.debug("Storing mboxes in '%s'", self.dirpath)

        self.client.fetch(self.client.base_url)

        from_date = datetime_to_utc(from_date)
        to_end = datetime_utcnow()
        to_end += dateutil.relativedelta.relativedelta(months=1)

        months = months_range(from_date, to_end)

        fetched = []

        if not os.path.exists(self.dirpath):
            os.makedirs(self.dirpath)

        tmbox = 0

        for dts in months:
            tmbox += 1
            start, end = dts[0], dts[1]
            filename = start.strftime("%Y-%m.mbox.gz")
            filepath = os.path.join(self.dirpath, filename)

            url = urijoin(self.client.base_url, 'export', filename)

            params = {
                'start': start.strftime("%Y-%m-%d"),
                'end': end.strftime("%Y-%m-%d")
            }

            success = self._download_archive(url, params, filepath)

            if success:
                fetched.append((url, filepath))

        logger.info("%s/%s MBoxes downloaded", len(fetched), tmbox)

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

    def _download_archive(self, url, params, filepath):
        r = self.client.fetch(url, payload=params, stream=True)

        try:
            with open(filepath, 'wb') as fd:
                fd.write(r.raw.read())
        except OSError as e:
            logger.warning("Ignoring %s archive due to: %s", url, str(e))
            return False

        logger.debug("%s archive downloaded and stored in %s", url, filepath)

        return True


class HyperKittyCommand(BackendCommand):
    """Class to run HyperKitty backend from the command line."""

    BACKEND = HyperKitty

    def _pre_init(self):
        """Initialize mailing lists directory path"""

        if not self.parsed_args.mboxes_path:
            base_path = os.path.expanduser('~/.perceval/mailinglists/')
            dirpath = os.path.join(base_path, self.parsed_args.url)
        else:
            dirpath = self.parsed_args.mboxes_path

        setattr(self.parsed_args, 'dirpath', dirpath)

    @staticmethod
    def setup_cmd_parser():
        """Returns the HyperKitty argument parser."""

        parser = BackendCommandArgumentParser(from_date=True)

        # Optional arguments
        group = parser.parser.add_argument_group('HyperKitty arguments')
        group.add_argument('--mboxes-path', dest='mboxes_path',
                           help="Path where mbox files will be stored")

        # Required arguments
        parser.parser.add_argument('url',
                                   help="URL of the mailing list archiver")

        return parser
