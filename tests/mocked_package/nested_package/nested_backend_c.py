#!/usr/bin/env python3
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
#     Valerio Cosentino <valcos@bitergia.com>
#

from perceval.backend import (Backend,
                              BackendCommand)


class BackendC(Backend):
    """Mocked backend class used for testing"""

    def __init__(self, origin, tag=None, archive=None):
        super().__init__(origin, tag=tag, archive=archive)


class BackendCommandC(BackendCommand):
    """Mocked backend command class used for testing"""

    BACKEND = BackendC

    def __init__(self, *args):
        super().__init__(*args)
