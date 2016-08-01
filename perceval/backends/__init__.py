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

from .bugzilla import Bugzilla, BugzillaCommand
from .bugzillarest import BugzillaREST, BugzillaRESTCommand
from .confluence import Confluence, ConfluenceCommand
from .discourse import Discourse, DiscourseCommand
from .gerrit import Gerrit, GerritCommand
from .git import Git, GitCommand
from .github import GitHub, GitHubCommand
from .gmane import Gmane, GmaneCommand
from .jenkins import Jenkins, JenkinsCommand
from .jira import Jira, JiraCommand
from .kitsune import Kitsune, KitsuneCommand
from .mbox import MBox, MBoxCommand
from .mediawiki import MediaWiki, MediaWikiCommand
from .phabricator import Phabricator, PhabricatorCommand
from .pipermail import Pipermail, PipermailCommand
from .redmine import Redmine, RedmineCommand
from .remo import ReMo, ReMoCommand
from .stackexchange import StackExchange, StackExchangeCommand
from .supybot import Supybot, SupybotCommand
from .telegram import Telegram, TelegramCommand


PERCEVAL_BACKENDS = {
                     'bugzilla'      : Bugzilla,
                     'bugzillarest'  : BugzillaREST,
                     'confluence'    : Confluence,
                     'discourse'     : Discourse,
                     'gerrit'        : Gerrit,
                     'git'           : Git,
                     'github'        : GitHub,
                     'gmane'         : Gmane,
                     'jenkins'       : Jenkins,
                     'jira'          : Jira,
                     'kitsune'       : Kitsune,
                     'mbox'          : MBox,
                     'mediawiki'     : MediaWiki,
                     'phabricator'   : Phabricator,
                     'pipermail'     : Pipermail,
                     'redmine'       : Redmine,
                     'remo'          : ReMo,
                     'stackexchange' : StackExchange,
                     'supybot'       : Supybot,
                     'telegram'      : Telegram
                    }
PERCEVAL_CMDS = {
                 'bugzilla'      : BugzillaCommand,
                 'bugzillarest'  : BugzillaRESTCommand,
                 'confluence'    : ConfluenceCommand,
                 'discourse'     : DiscourseCommand,
                 'gerrit'        : GerritCommand,
                 'git'           : GitCommand,
                 'github'        : GitHubCommand,
                 'gmane'         : GmaneCommand,
                 'jenkins'       : JenkinsCommand,
                 'jira'          : JiraCommand,
                 'kitsune'       : KitsuneCommand,
                 'mbox'          : MBoxCommand,
                 'mediawiki'     : MediaWikiCommand,
                 'phabricator'   : PhabricatorCommand,
                 'pipermail'     : PipermailCommand,
                 'redmine'       : RedmineCommand,
                 'remo'          : ReMoCommand,
                 'stackexchange' : StackExchangeCommand,
                 'supybot'       : SupybotCommand,
                 'telegram'      : TelegramCommand
                }
