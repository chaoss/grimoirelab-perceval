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

"""Common functions for introspection.

This module provides a set of functions that come in handy for
instrospection on a higher level than the provided by other libraries
such as `inspect`.
"""

import inspect


__all__ = [
    "inspect_signature_parameters",
    "find_signature_parameters"
]


def inspect_signature_parameters(callable_, excluded=None):
    """Get the parameters of a callable.

    Returns a list with the signature parameters of `callable_`.
    Parameters contained in `excluded` tuple will not be included
    in the result.

    :param callable_: callable object
    :param excluded: tuple with default parameters to exclude

    :result: list of parameters
    """
    if not excluded:
        excluded = ()

    signature = inspect.signature(callable_)
    params = [
        v for p, v in signature.parameters.items()
        if p not in excluded
    ]
    return params


def find_signature_parameters(callable_, candidates,
                              excluded=('self', 'cls')):
    """Find on a set of candidates the parameters needed to execute a callable.

    Returns a dictionary with the `candidates` found on `callable_`.
    When any of the required parameters of a callable is not found,
    it raises a `AttributeError` exception. A signature parameter
    whitout a default value is considered as required.

    :param callable_: callable object
    :param candidates: dict with the possible parameters to use
        with the callable
    :param excluded: tuple with default parameters to exclude

    :result: dict of parameters ready to use with the callable

    :raises AttributeError: when any of the required parameters for
        executing a callable is not found in `candidates`
    """
    signature_params = inspect_signature_parameters(callable_,
                                                    excluded=excluded)
    exec_params = {}

    for param in signature_params:
        name = param.name

        if name in candidates:
            exec_params[name] = candidates[name]
        elif param.default == inspect.Parameter.empty:
            msg = "required argument %s not found" % name
            raise AttributeError(msg, name)
        else:
            continue

    return exec_params
