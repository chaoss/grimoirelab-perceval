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
#     Alvaro del Castillo <acs@bitergia.com>
#     Santiago Dueñas <sduenas@bitergia.com>
#     Luis Cañas Díaz <lcanas@bitergia.com>
#     Alberto Martín <alberto.martin@bitergia.com>
#     Stephan Barth <stephan.barth@gmail.com>
#     Valerio Cosentino <valcos@bitergia.com>
#     Jesus M. Gonzalez-Barahona <jgb@gsyc.es>
#     MalloZup <dmaiocchi@suse.com>
#     Venu Vardhan Reddy Tekula <venuvardhanreddytekula8@gmail.com>
#     animesh <animuz111@gmail.com>
#     Nitish Gupta <imnitish.ng@gmail.com>
#     Ashish Kumar Choubey <contactchoubey@gmail.com>

import argparse
import logging
import sys

import perceval
import perceval.backend
import perceval.backends.core

PERCEVAL_USAGE_MSG = \
    """%(prog)s [-g] <backend> [<args>] | --help | --version | --list"""

PERCEVAL_DESC_MSG = \
    """Send Sir Perceval on a quest to retrieve and gather data from software
repositories.

Repositories are reached using specific backends. The most common backends
are:

    askbot           Fetch questions and answers from Askbot site
    bugzilla         Fetch bugs from a Bugzilla server
    bugzillarest     Fetch bugs from a Bugzilla server (>=5.0) using its REST API
    confluence       Fetch contents from a Confluence server
    discourse        Fetch posts from Discourse site
    dockerhub        Fetch repository data from Docker Hub site
    gerrit           Fetch reviews from a Gerrit server
    git              Fetch commits from Git
    github           Fetch issues, pull requests and repository information from GitHub
    gitlab           Fetch issues, merge requests from GitLab
    gitter           Fetch messages from a Gitter room
    googlehits       Fetch hits from Google API
    groupsio         Fetch messages from Groups.io
    hyperkitty       Fetch messages from a HyperKitty archiver
    jenkins          Fetch builds from a Jenkins server
    jira             Fetch issues from JIRA issue tracker
    launchpad        Fetch issues from Launchpad issue tracker
    mattermost       Fetch posts from a Mattermost server
    mbox             Fetch messages from MBox files
    mediawiki        Fetch pages and revisions from a MediaWiki site
    meetup           Fetch events from a Meetup group
    nntp             Fetch articles from a NNTP news group
    pagure           Fetch issues from Pagure
    phabricator      Fetch tasks from a Phabricator site
    pipermail        Fetch messages from a Pipermail archiver
    postgresdb       Fetch contents from Postgres DB using SQL queries via DP API 2.0 standards
    redmine          Fetch issues from a Redmine server
    rocketchat       Fetch messages from a Rocket.Chat channel
    rss              Fetch entries from a RSS feed server
    slack            Fetch messages from a Slack channel
    stackexchange    Fetch questions from StackExchange sites
    supybot          Fetch messages from Supybot log files
    telegram         Fetch messages from the Telegram server
    twitter          Fetch tweets from the Twitter Search API

optional arguments:
  -h, --help            show this help message and exit
  -v, --version         show version
  -g, --debug           set debug mode on
  -l, --list            show available backends
"""

PERCEVAL_EPILOG_MSG = \
    """Run '%(prog)s <backend> --help' to get information about a specific backend."""

PERCEVAL_VERSION_MSG = \
    """%(prog)s """ + perceval.backends.core.__version__


# Logging formats
PERCEVAL_LOG_FORMAT = "[%(asctime)s] - %(message)s"
PERCEVAL_DEBUG_LOG_FORMAT = "[%(asctime)s - %(name)s - %(levelname)s] - %(message)s"


class ListBackends(argparse.Action):

    def __init__(self, option_strings, dest, **kwargs):
        self.backends = kwargs.get('backends', None)
        del kwargs['backends']
        super().__init__(option_strings, dest, nargs=0, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        backends = sorted(self.backends.keys())
        for backend in backends:
            sys.stdout.write(backend + '\n')
        parser.exit()


def main():
    _, PERCEVAL_CMDS = perceval.backend.find_backends(perceval.backends)

    args = parse_args(PERCEVAL_CMDS)

    if args.backend not in PERCEVAL_CMDS:
        raise RuntimeError("Unknown backend %s" % args.backend)
    configure_logging(args.debug)

    logging.info("Sir Perceval is on his quest.")
    klass = PERCEVAL_CMDS[args.backend]
    cmd = klass(*args.backend_args, debug=args.debug)
    cmd.run()

    logging.info("Sir Perceval completed his quest.")


def parse_args(perceval_cmds):
    """Parse command line arguments"""

    parser = argparse.ArgumentParser(usage=PERCEVAL_USAGE_MSG,
                                     description=PERCEVAL_DESC_MSG,
                                     epilog=PERCEVAL_EPILOG_MSG,
                                     formatter_class=argparse.RawDescriptionHelpFormatter,
                                     add_help=False)

    parser.add_argument('-h', '--help', action='help',
                        help=argparse.SUPPRESS)
    parser.add_argument('-v', '--version', action='version',
                        version=PERCEVAL_VERSION_MSG,
                        help=argparse.SUPPRESS)
    parser.add_argument('-g', '--debug', dest='debug',
                        action='store_true',
                        help=argparse.SUPPRESS)
    parser.add_argument('-l', '--list', backends=perceval_cmds, action=ListBackends,
                        help=argparse.SUPPRESS)

    parser.add_argument('backend', help=argparse.SUPPRESS)
    parser.add_argument('backend_args', nargs=argparse.REMAINDER,
                        help=argparse.SUPPRESS)

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)

    return parser.parse_args()


def configure_logging(debug=False):
    """Configure Perceval logging

    The function configures the log messages produced by Perceval.
    By default, log messages are sent to stderr. Set the parameter
    `debug` to activate the debug mode.

    :param debug: set the debug mode
    """
    if not debug:
        logging.basicConfig(level=logging.INFO,
                            format=PERCEVAL_LOG_FORMAT)
        logging.getLogger('requests').setLevel(logging.WARNING)
        logging.getLogger('urrlib3').setLevel(logging.WARNING)
    else:
        logging.basicConfig(level=logging.DEBUG,
                            format=PERCEVAL_DEBUG_LOG_FORMAT)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        s = "\n\nReceived Ctrl-C or other break signal. Exiting.\n"
        sys.stderr.write(s)
        sys.exit(0)
