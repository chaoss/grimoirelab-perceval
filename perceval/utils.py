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

import dateutil.parser

import xml.etree.ElementTree

from .errors import InvalidDateError, ParseError


DEFAULT_DATETIME = datetime.datetime(1970, 1, 1, 0, 0, 0)


def str_to_datetime(ts):
    """Format a string to a datetime object.

    This functions supports several date formats like YYYY-MM-DD,
    MM-DD-YYYY and YY-MM-DD.

    :param ts: string to convert

    :returns: a datetime object

    :raises IvalidDateError: when the given string cannot be converted into
        a valid date
    """
    if not ts:
        raise InvalidDateError(date=str(ts))

    try:
        return dateutil.parser.parse(ts).replace(tzinfo=None)
    except Exception:
        raise InvalidDateError(date=str(ts))


def urljoin(*args):
    """Joins given arguments into a URL.

    Trailing and leading slashes are stripped for each argument.

    This code is based on a Rune Kaagaard's answer on StackOverflow.
    See http://stackoverflow.com/questions/1793261 for more into. The
    code was licensed as cc by-sa 3.0.

    :params *args: list of arguments to join

    :returns: a URL string
    """
    return '/'.join(map(lambda x: str(x).strip('/'), args))


def xml_to_dict(raw_xml):
    """Convert a XML stream into a dictionary.

    This function transforms a xml stream into a dictionary. The
    attributes are stored as single elements while child nodes are
    stored into lists. The text node is stored using the special
    key '__text__'.

    This code is based on Winston Ewert's solution to this problem.
    See http://codereview.stackexchange.com/questions/10400/convert-elementtree-to-dict
    for more info. The code was licensed as cc by-sa 3.0.

    :param raw_xml: XML stream

    :returns: a dict with the XML data

    :raises ParseError: raised when an error occurs parsing the given
        XML stream
    """
    def node_to_dict(node):
        d = {}
        d.update(node.items())

        text = getattr(node, 'text', None)

        if text is not None:
            d['__text__'] = text

        childs = {}
        for child in node:
            childs.setdefault(child.tag, []).append(node_to_dict(child))

        d.update(childs.items())

        return d

    try:
        tree = xml.etree.ElementTree.fromstring(raw_xml)
    except xml.etree.ElementTree.ParseError as e:
        cause = "XML stream %s" % (str(e))
        raise ParseError(cause=cause)

    d = node_to_dict(tree)

    return d
