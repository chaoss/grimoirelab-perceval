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
#     Stephan Barth <stephan.barth@gmail.com>
#     Valerio Cosentino <valcos@bitergia.com>
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


class ArchiveError(BaseError):
    """Generic error for archive objects"""

    message = "%(cause)s"


class ArchiveManagerError(BaseError):
    """Generic error for archive manager"""

    message = "%(cause)s"


class BackendError(BaseError):
    """Generic error for backends"""

    message = "%(cause)s"


class HttpClientError(BaseError):
    """Generic error for HTTP Cient"""

    message = "%(cause)s"


class RepositoryError(BaseError):
    """Generic error for repositories"""

    message = "%(cause)s"


class RateLimitError(BaseError):
    """Exception raised when the rate limit is exceeded"""

    message = "%(cause)s; %(seconds_to_reset)s seconds to rate reset"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._seconds_to_reset = kwargs['seconds_to_reset']

    @property
    def seconds_to_reset(self):
        return self._seconds_to_reset


class ParseError(BaseError):
    """Exception raised a parsing errors occurs"""

    message = "%(cause)s"


class BackendCommandArgumentParserError(BaseError):
    """Generic error for BackendCommandArgumentParser"""

    message = "%(cause)s"
