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
#

import datetime
import json
import logging
import os
import re

import dateutil

from ..backend import Backend, BackendCommand, metadata
from ..errors import ParseError
from ..utils import (DEFAULT_DATETIME,
                     datetime_to_utc,
                     str_to_datetime)


logger = logging.getLogger(__name__)


class Supybot(Backend):
    """Supybot IRC log backend.

    This class fetches the messages stored by Supybot in log files.
    Initialize this class providing the directory where those IRC
    log files are stored.

    The log filenames expected by this backend should follow the
    pattern: #channel_YYYY-MM-DD.log (i.e #grimoirelab_2016-06-27.log).
    This is needed to determine the date when messages were sent.
    Other filenames might work too but the behaviour is unknown.

    The format of the messages must also follow a pattern. This
    patterns can be found in `SupybotParser` class documentation.

    :param uri: URI of the IRC archives; typically, the URL of their
        IRC channel
    :param dirpath: directory path where the archives are stored
    :param tag: label used to mark the data
    :param cache: cache object to store raw data
    """
    version = '0.4.1'

    def __init__(self, uri, dirpath, tag=None, cache=None):
        origin = uri

        super().__init__(origin, tag=tag, cache=cache)
        self.uri = uri
        self.dirpath = dirpath

    @metadata
    def fetch(self, from_date=DEFAULT_DATETIME):
        """Fetch the messages from the Supybot IRC logger.

        The method parsers and returns the messages saved on the
        IRC log files and stored by Supybot in `dirpath`.

        :param from_date: obtain messages since this date

        :returns: a generator of messages
        """
        logger.info("Fetching messages of '%s' from %s",
                    self.uri, str(from_date))

        from_date = datetime_to_utc(from_date)

        nmessages = 0
        archives = self.__retrieve_archives(from_date)

        for archive in archives:
            logger.debug("Parsing supybot archive %s", archive)

            for message in self.parse_supybot_log(archive):
                dt = str_to_datetime(message['timestamp'])

                if dt < from_date:
                    logger.debug("Message %s sent before %s; skipped",
                                 str(dt), str(from_date))
                    continue

                yield message
                nmessages += 1

        logger.info("Fetch process completed: %s messages fetched",
                    nmessages)

    def __retrieve_archives(self, from_date):
        """Retrieve the Supybot archives after the given date"""

        archives = []

        candidates = self.__list_supybot_archives()

        for candidate in candidates:
            dt = self.__parse_date_from_filepath(candidate)

            if dt.date() >= from_date.date():
                archives.append((dt, candidate))
            else:
                logger.debug("Archive %s stored before %s; skipped",
                             candidate, str(from_date))

        archives.sort(key=lambda x: x[0])

        return [archive[1] for archive in archives]

    def __list_supybot_archives(self):
        """List the filepath of the archives stored in dirpath"""

        archives = []

        for root, _, files in os.walk(self.dirpath):
            for filename in files:
                location = os.path.join(root, filename)
                archives.append(location)

        return archives

    def __parse_date_from_filepath(self, filepath):
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
        """Extracts the identifier from a Supybot item.

        This identifier will be the mix of two fields because IRC
        messages does not have any unique identifier. In this case,
        'timestamp' and 'nick' values are combined because it should
        not be possible to have two messages of the same user at the
        same time.
        """
        return item['timestamp'] + item['nick']

    @staticmethod
    def metadata_updated_on(item):
        """Extracts the update time from a Supybot item.

        The timestamp used is extracted from 'timestamp' field.
        This date is converted to UNIX timestamp format taking into
        account the timezone of the date.

        :param item: item generated by the backend

        :returns: a UNIX timestamp
        """
        ts = item['timestamp']
        ts = str_to_datetime(ts)

        return ts.timestamp()

    @staticmethod
    def metadata_category(item):
        """Extracts the category from a Supybot item.

        This backend only generates one type of item which is
        'message'.
        """
        return 'message'

    @staticmethod
    def parse_supybot_log(filepath):
        """Parse a Supybot IRC log file.

        The method parses the Supybot IRC log file and returns an iterator of
        dictionaries. Each one of this, contains a message from the file.

        :param filepath: path to the IRC log file

        :returns: a generator of parsed messages

        :raises ParseError: raised when the format of the Supybot log file
            is invalid
        :raises OSError: raised when an error occurs reading the
            given file
        """
        with open(filepath, 'r', errors='surrogateescape',
                  newline=os.linesep) as f:
            parser = SupybotParser(f)

            for message in parser.parse():
                yield message


class SupybotCommand(BackendCommand):
    """Class to run Supybot backend from the command line."""

    def __init__(self, *args):
        super().__init__(*args)

        self.uri = self.parsed_args.uri
        self.ircdir = self.parsed_args.ircdir
        self.outfile = self.parsed_args.outfile
        self.tag = self.parsed_args.tag
        self.from_date = str_to_datetime(self.parsed_args.from_date)

        cache = None

        self.backend = Supybot(self.uri, self.ircdir,
                               tag=self.tag, cache=cache)

    def run(self):
        """Fetch and print the IRC messages.

        This method runs the backend to fetch the IRC messages from
        the given Supybot log files. Messages are converted to JSON
        objects and printed to the defined output.
        """
        messages = self.backend.fetch(from_date=self.from_date)

        try:
            for message in messages:
                obj = json.dumps(message, indent=4, sort_keys=True)
                self.outfile.write(obj)
                self.outfile.write('\n')
        except OSError as e:
            raise RuntimeError(str(e))
        except Exception as e:
            raise RuntimeError(str(e))

    @classmethod
    def create_argument_parser(cls):
        """Returns the Supybot argument parser."""

        parser = super().create_argument_parser()

        # Required arguments
        parser.add_argument('uri',
                            help="URI of the IRC channel")
        parser.add_argument('ircdir',
                            help="Path to the IRC logs directory")

        return parser


class SupybotParser:
    """Supybot IRC parser.

    This class parses a Supybot IRC log stream, converting plain log
    lines (or messages) into dict items. Each dictionary will contain
    the date of the message, the type of message (comment or server
    message), the nick of the sender and its body.

    Each line on a log starts with a date in ISO format including its
    timezone and it is followed by two spaces and by a message.

    There are two types of valid messages in a Supybot log: comment
    messages and server messages. First one follows any of these two
    patterns:

        2016-06-27T12:00:00+0000  <nick> body of the message
        2016-06-27T12:00:00+0000  * nick waves hello

    While a valid server message has the next pattern:

        2016-06-27T12:00:00+0000  *** nick is known as new_nick

    An exception is raised when any of the lines does not follow any
    of the above formats.

    :param stream: an iterator which produces Supybot log lines
    """
    TIMESTAMP_PATTERN = r"""^(?P<ts>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[\+\-]\d{4})\s\s
                        (?P<msg>.+)$
                        """
    COMMENT_PATTERN = r"^<(?P<nick>(.*?)(!.*)?)>\s(?P<body>.+)$"
    COMMENT_ACTION_PATTERN = r"^\*\s(?P<body>(?P<nick>(.*?)(!.*)?)\s.+)$"
    SERVER_PATTERN = r"^\*\*\*\s(?P<body>(?P<nick>(.*?)(!.*)?)\s.+)$"
    BOT_PATTERN = r"^-(?P<nick>(.*?)(!.*)?)-\s(?P<body>.+)$"
    EMPTY_PATTERN = r"^\s*$"
    EMPTY_COMMENT_PATTERN = r"^<(.*?)(!.*)?>\s*$"

    # Compiled patterns
    SUPYBOT_TIMESTAMP_REGEX = re.compile(TIMESTAMP_PATTERN, re.VERBOSE)
    SUPYBOT_COMMENT_REGEX = re.compile(COMMENT_PATTERN, re.VERBOSE)
    SUPYBOT_COMMENT_ACTION_REGEX = re.compile(COMMENT_ACTION_PATTERN, re.VERBOSE)
    SUPYBOT_SERVER_REGEX = re.compile(SERVER_PATTERN, re.VERBOSE)
    SUPYBOT_BOT_REGEX = re.compile(BOT_PATTERN, re.VERBOSE)
    SUPYBOT_EMPTY_REGEX = re.compile(EMPTY_PATTERN, re.VERBOSE)
    SUPYBOT_EMPTY_COMMENT_REGEX = re.compile(EMPTY_COMMENT_PATTERN, re.VERBOSE)

    # Item types
    TCOMMENT = 'comment'
    TSERVER = 'server'

    def __init__(self, stream):
        self.stream = stream
        self.nline = 0

    def parse(self):
        """Parse a Supybot IRC stream.

        Returns an iterator of dicts. Each dicts contains information
        about the date, type, nick and body of a single log entry.

        :returns: iterator of parsed lines

        :raises ParseError: when an invalid line is found parsing the given
            stream
        """
        for line in self.stream:
            line = line.rstrip('\n')
            self.nline += 1

            if self.SUPYBOT_EMPTY_REGEX.match(line):
                continue

            ts, msg = self._parse_supybot_timestamp(line)

            if self.SUPYBOT_EMPTY_COMMENT_REGEX.match(msg):
                continue

            itype, nick, body = self._parse_supybot_msg(msg)
            item = self._build_item(ts, itype, nick, body)

            yield item

    def _parse_supybot_timestamp(self, line):
        """Parse timestamp section"""

        m = self.SUPYBOT_TIMESTAMP_REGEX.match(line)

        if not m:
            msg = "date expected on line %s" % (str(self.nline))
            raise ParseError(cause=msg)

        ts = m.group('ts')
        msg = m.group('msg')

        return ts, msg

    def _parse_supybot_msg(self, line):
        """Parse message section"""

        patterns = [(self.SUPYBOT_COMMENT_REGEX, self.TCOMMENT),
                    (self.SUPYBOT_COMMENT_ACTION_REGEX, self.TCOMMENT),
                    (self.SUPYBOT_SERVER_REGEX, self.TSERVER),
                    (self.SUPYBOT_BOT_REGEX, self.TCOMMENT)]

        for p in patterns:
            m = p[0].match(line)
            if not m:
                continue
            return p[1], m.group('nick'), m.group('body').strip()

        msg = "invalid message on line %s" % (str(self.nline))
        raise ParseError(cause=msg)

    def _build_item(self, ts, itype, nick, body):
        return {
                'timestamp' : ts,
                'type' : itype,
                'nick' : nick,
                'body' : body
               }
