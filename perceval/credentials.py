# -*- coding: utf-8 -*-
#
# Copyright (C) GrimoireLab Contributors
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

import re


CREDENTIAL_FIELDS = ['user', 'password', 'api_token', 'email',
                     'access_token', 'user_id']
"""Fields Perceval looks up in a secret of a credential manager."""

LIST_SEPARATORS = re.compile(r'[,\n]')


def normalize_credentials(credentials, list_fields=()):
    """Convert the values of the credentials to single values or lists.

    Fields in `list_fields` (e.g. a pool of API tokens) are
    converted into lists. Values for these fields can be lists
    or strings with the elements separated by commas or new lines.

    Any other field must have a single value. A list with only
    one element is converted to that element.

    Numbers are converted to strings. Empty values and values
    of any other type are rejected, so a misconfigured secret
    is reported instead of being passed to the backend.

    :param credentials: dict with the credentials
    :param list_fields: names of the fields that take a list of values

    :returns: a new dict with the normalized credentials

    :raises ValueError: when a value is empty or invalid, or when
        a field that only accepts a single value has several values
    """
    normalized = {}

    for name, value in credentials.items():
        values = value if isinstance(value, list) else [value]

        # 'bool' is a subclass of 'int', but it isn't a valid credential
        if any(isinstance(v, bool) or not isinstance(v, (str, int, float)) for v in values):
            raise ValueError(f"'{name}' has an invalid value")

        values = [str(v) for v in values]

        if name in list_fields:
            values = [t.strip() for v in values for t in LIST_SEPARATORS.split(v)]

        # Blank values are ignored
        values = [v for v in values if v.strip()]

        if not values:
            raise ValueError(f"'{name}' is empty")

        if name in list_fields:
            normalized[name] = values
        elif len(values) == 1:
            normalized[name] = values[0]
        else:
            raise ValueError(f"'{name}' must have a single value; multiple values were found")

    return normalized
