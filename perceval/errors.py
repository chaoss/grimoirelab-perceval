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

class BaseError(Exception):
    """Base class for Perceval exceptions.

    Derived classes can overwrite the error message declaring ``message``
    property.
    """
    message = 'Perceval base error'

    def __init__(self, **kwargs):
        super().__init__()
        self.msg = self.message % kwargs

    def __str__(self):
        return self.msg


class BackendError(BaseError):
    """Generic error for backends"""

    message = "%(cause)s"


class CacheError(BaseError):
    """Generic error for cache objects"""

    message = "%(cause)s"


class InvalidDateError(BaseError):
    """Exception raised when a date is invalid"""

    message = "%(date)s is not a valid date"


class RepositoryError(BaseError):
    """Generic error for repositories"""

    message = "%(cause)s"


class ParseError(BaseError):
    """Exception raised a parsing errors occurs"""

    message = "%(cause)s"
