# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 Bitergia
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

import argparse


class Backend:

    def __init__(self):
        pass

    @classmethod
    def get_argument_parser(cls):
        parser = argparse.ArgumentParser()

        # Options
        group = parser.add_argument_group('general arguments')
        group.add_argument('-u', '--backend-user', dest='backend_user',
                           help='Backend user')
        group.add_argument('-p', '--backend-password', dest='backend_password',
                           help='Backend password')
        group.add_argument('-t', '--backend-token', dest='backend_token',
                           help='Backend authentication token')

        return parser
