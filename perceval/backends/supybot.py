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

import logging
import re

from perceval.errors import ParseError


logger = logging.getLogger(__name__)


class SupybotParser:
    """Supybot IRC parser.

    This class parses a Supybot IRC log stream, converting plain log
    lines (or messages) into dict items. Each dictionary will contain
    the date of the message, the type of message (comment or server
    message), the nick of the sender and its body.

    Each line on a log starts with a date in ISO format including its
    timezone and it is followed by two spaces and by a message.

    There are two types of valid messages in a Supybot log: comment
    messages and server messages. First one follows the next pattern:

        2016-06-27T12:00:00+0000  <nick> body of the message

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
    SERVER_PATTERN = r"^\*\*\*\s(?P<body>(?P<nick>(.*?)(!.*)?)\s.+)$"
    EMPTY_PATTERN = r"^\s*$"

    # Compiled patterns
    SUPYBOT_TIMESTAMP_REGEX = re.compile(TIMESTAMP_PATTERN, re.VERBOSE)
    SUPYBOT_COMMENT_REGEX = re.compile(COMMENT_PATTERN, re.VERBOSE)
    SUPYBOT_SERVER_REGEX = re.compile(SERVER_PATTERN, re.VERBOSE)
    SUPYBOT_EMPTY_REGEX = re.compile(EMPTY_PATTERN, re.VERBOSE)

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

        m = self.SUPYBOT_COMMENT_REGEX.match(line)

        if not m:
            m = self.SUPYBOT_SERVER_REGEX.match(line)

            if not m:
                msg = "invalid message on line %s" % (str(self.nline))
                raise ParseError(cause=msg)
            else:
                itype = self.TSERVER
        else:
            itype = self.TCOMMENT

        nick = m.group('nick')
        msg = m.group('body').strip()

        return itype, nick, msg

    def _build_item(self, ts, itype, nick, body):
        return {
                'timestamp' : ts,
                'type' : itype,
                'nick' : nick,
                'body' : body
               }
