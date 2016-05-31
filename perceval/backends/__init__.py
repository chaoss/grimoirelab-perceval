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

from .bugzilla import Bugzilla, BugzillaCommand
from .gerrit import Gerrit, GerritCommand
from .git import Git, GitCommand
from .github import GitHub, GitHubCommand
from .jenkins import Jenkins, JenkinsCommand
from .jira import Jira, JiraCommand
from .mbox import MBox, MBoxCommand
from .pipermail import Pipermail, PipermailCommand
from .stackexchange import StackExchange, StackExchangeCommand


PERCEVAL_BACKENDS = {
                     'bugzilla'      : Bugzilla,
                     'git'           : Git,
                     'gerrit'        : Gerrit,
                     'github'        : GitHub,
                     'jenkins'       : Jenkins,
                     'jira'          : Jira,
                     'mbox'          : MBox,
                     'pipermail'     : Pipermail,
                     'stackexchange' : StackExchange
                    }
PERCEVAL_CMDS = {
                 'bugzilla'      : BugzillaCommand,
                 'git'           : GitCommand,
                 'gerrit'        : GerritCommand,
                 'github'        : GitHubCommand,
                 'jenkins'       : JenkinsCommand,
                 'jira'          : JiraCommand,
                 'mbox'          : MBoxCommand,
                 'pipermail'     : PipermailCommand,
                 'stackexchange' : StackExchangeCommand
                }
