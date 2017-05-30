# -*- coding: utf-8 -*-
#
# Copyright (C) 2015-2017 Bitergia
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
#

"""Functions for handling datetime types.

Parsing dates from strings, setting timezones or converting
datatime objects are complex and prone error tasks. This module
offers a toolkit to make easier to deal with those problems.
"""

import datetime
import logging
import re

import dateutil.parser
import dateutil.rrule
import dateutil.tz


__all__ = [
    "InvalidDateError", "datetime_utcnow", "datetime_to_utc",
    "str_to_datetime", "unixtime_to_datetime"
]

logger = logging.getLogger(__name__)


class InvalidDateError(Exception):
    """Exception raised when a date is invalid"""

    message = "%(date)s is not a valid date"

    def __init__(self, **kwargs):
        super().__init__()
        self.msg = self.message % kwargs

    def __str__(self):
        return self.msg


def datetime_utcnow():
    """Handy function which returns the current date and time in UTC."""

    return datetime.datetime.utcnow()


def datetime_to_utc(ts):
    """Convert a timestamp to UTC+0 timezone.

    Returns the given datetime object converted to a date with
    UTC+0 timezone. For naive datetimes, it will be assumed that
    they are in UTC+0.

    :param dt: timestamp to convert

    :returns: a datetime object

    :raises InvalidDateError: when the given parameter is not an
        instance of datetime
    """
    if not isinstance(ts, datetime.datetime):
        msg = '<%s> object' % type(ts)
        raise InvalidDateError(date=msg)

    if not ts.tzinfo:
        ts = ts.replace(tzinfo=dateutil.tz.tzutc())

    return ts.astimezone(dateutil.tz.tzutc())


def str_to_datetime(ts):
    """Format a string to a datetime object.

    This functions supports several date formats like YYYY-MM-DD,
    MM-DD-YYYY, YY-MM-DD, YYYY-MM-DD HH:mm:SS +HH:MM, among others.
    When the timezone is not provided, UTC+0 will be set as default
    (using `dateutil.tz.tzutc` object).

    :param ts: string to convert

    :returns: a datetime object

    :raises IvalidDateError: when the given string cannot be converted
        on a valid date
    """
    def parse_datetime(ts):
        dt = dateutil.parser.parse(ts)
        if not dt.tzinfo:
            dt = dt.replace(tzinfo=dateutil.tz.tzutc())
        return dt

    if not ts:
        raise InvalidDateError(date=str(ts))

    try:
        # Try to remove additional information after
        # timezone section because it cannot be parsed,
        # like in 'Wed, 26 Oct 2005 15:20:32 -0100 (GMT+1)'
        # or in 'Thu, 14 Aug 2008 02:07:59 +0200 CEST'.
        m = re.search(r"^.+?\s+[\+\-]\d{4}(\s+.+)$", ts)
        if m:
            ts = ts[:m.start(1)]

        try:
            dt = parse_datetime(ts)
        except ValueError as e:
            # Try to remove the timezone, usually it causes
            # problems. If it doesn't work, raise an exception
            m = re.search(r"^(.+?)\s+[\+\-]\d+$", ts)

            if not m:
                raise e

            dt = parse_datetime(m.group(1))

            logger.warning("Date %s str does not have a valid timezone", ts)
            logger.warning("Date converted removing timezone info")

        return dt
    except ValueError as e:
        raise InvalidDateError(date=str(ts))


def unixtime_to_datetime(ut):
    """Convert a unixtime timestamp to a datetime object.

    The function converts a timestamp in Unix format to a
    datetime object. UTC timezone will also be set.

    :param ut: Unix timestamp to convert

    :returns: a datetime object

    :raises InvalidDateError: when the given timestamp cannot be
        converted into a valid date
    """
    try:
        dt = datetime.datetime.utcfromtimestamp(ut)
        dt = dt.replace(tzinfo=dateutil.tz.tzutc())
        return dt
    except Exception:
        raise InvalidDateError(date=str(ut))
