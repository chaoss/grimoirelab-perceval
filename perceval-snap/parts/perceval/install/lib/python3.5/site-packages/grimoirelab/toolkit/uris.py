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

"""Functions for handling URIs."""


__all__ = ["urijoin"]


def urijoin(*args):
    """Joins given arguments into a URI.

    Trailing and leading slashes are stripped for each argument.

    This code is based on a Rune Kaagaard's answer on Stack Overflow.
    See http://stackoverflow.com/questions/1793261 for more into. The
    code was licensed as cc by-sa 3.0.

    :params *args: list of arguments to join

    :returns: a URI string
    """
    return '/'.join(map(lambda x: str(x).strip('/'), args))
