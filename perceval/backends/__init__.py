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

import importlib
import os

from ..backend import Backend, BackendCommand


def register_backends(dirpath):
    filenames = [fn for fn in os.listdir(dirpath)]

    # Find candidate modules and remove
    # the ".py" extension (fn[:-3])
    candidates = [fn[:-3] for fn in filenames \
                  if is_backend_module(fn, dirpath)]

    return import_backends(candidates)


def import_backends(modules):
    for module in modules:
        importlib.import_module('.' + module, __name__)

    bkls = filter_classes(Backend.__subclasses__(), modules)
    ckls = filter_classes(BackendCommand.__subclasses__(), modules)

    backends = {name: kls for name, kls in bkls}
    commands = {name: klass for name, klass in ckls}

    return backends, commands


def filter_classes(klasses, modules):
    prefix = __name__ + '.'

    for kls in klasses:
        name = kls.__module__.replace(prefix, '').lower()

        if name not in modules:
            continue

        yield name, kls


def is_backend_module(filename, dirpath):
    is_valid = filename.endswith('.py') \
        and not filename.startswith('__') \
        and not filename.endswith('__') \
        and os.path.isfile(os.path.join(dirpath, filename))
    return is_valid


PERCEVAL_BACKENDS, PERCEVAL_CMDS = \
    register_backends(os.path.dirname(__file__))
