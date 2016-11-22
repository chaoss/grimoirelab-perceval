# -*- coding: utf-8 -*-
#
# Copyright (C) 2016 Bitergia
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
#     Alvaro del Castillo <acs@bitergia.com>
#

import functools
import json
import logging
import os.path

import requests

from ...backend import Backend, BackendCommand, metadata
from ...cache import Cache
from ...errors import CacheError, ParseError
from ...utils import (DEFAULT_DATETIME,
                      str_to_datetime,
                      urljoin)


logger = logging.getLogger(__name__)

KITSUNE_URL = "https://support.mozilla.org"
DEFAULT_OFFSET = 0


def kitsune_metadata(func):
    """Kitsune metadata decorator.

    This decorator takes items overrides `metadata` decorator to add extra
    information related to Kitsune (offset of the question).
    """
    @functools.wraps(func)
    def decorator(self, *args, **kwargs):
        for item in func(self, *args, **kwargs):
            item['offset'] = item['data'].pop('offset')
            yield item
    return decorator


class Kitsune(Backend):
    """Kitsune backend for Perceval.

    This class retrieves the questions and answers from a
    Kitsune URL. To initialize this class a URL may be provided.
    If not, https://support.mozilla.org will be used. The origin
    of the data will be set to this URL.

    Questions and answers are returned from older to newer.

    :param url: Kitsune URL
    :param tag: label used to mark the data
    :param cache: cache object to store raw data
    """
    version = '0.4.0'

    def __init__(self, url=None, tag=None, cache=None):
        if not url:
            url = KITSUNE_URL
        origin = url

        super().__init__(origin, tag=tag, cache=cache)
        self.url = url
        self.client = KitsuneClient(url)

    @kitsune_metadata
    @metadata
    def fetch(self, offset=DEFAULT_OFFSET):
        """Fetch questions from the Kitsune url.

        :offset: obtain questions after offset
        :returns: a generator of questions
        """
        logger.info("Looking for questions at url '%s' using offset %s",
                    self.url, str(offset))

        self._purge_cache_queue()
        # Add to the cache the offset so it can be used to recover from cache
        self._push_cache_queue(offset)

        nquestions = 0  # number of questions processed
        tquestions = 0  # number of questions from API data
        equestions = 0  # number of questions dropped by errors

        # Always get complete pages so the first item is always
        # the first one in the page
        page = int(offset / KitsuneClient.ITEMS_PER_PAGE)
        page_offset = page * KitsuneClient.ITEMS_PER_PAGE
        # drop questions from page before the offset
        drop_questions = offset - page_offset
        current_offset = offset

        questions_page = self.client.get_questions(offset)

        while True:
            try:
                raw_questions = next(questions_page)
            except StopIteration:
                break
            except requests.exceptions.HTTPError as e:
                # Continue with the next page if it is a 500 error
                if e.response.status_code == 500:
                    logger.exception(e)
                    logger.error("Problem getting Kitsune questions. " +
                                 "Loosing %i questions. Going to the next page.",
                                 KitsuneClient.ITEMS_PER_PAGE)
                    equestions += KitsuneClient.ITEMS_PER_PAGE
                    current_offset += KitsuneClient.ITEMS_PER_PAGE
                    questions_page = self.client.get_questions(current_offset)
                    continue
                else:
                    # If it is another error just propagate the exception
                    raise e

            self._push_cache_queue(raw_questions)

            try:
                questions_data = json.loads(raw_questions)
                tquestions = questions_data['count']
                questions = questions_data['results']
            except (ValueError, KeyError) as ex:
                logger.error(ex)
                cause = ("Bad JSON format for mozilla_questions: %s" % (raw_questions))
                raise ParseError(cause=cause)

            for question in questions:
                if drop_questions > 0:
                    # Remove extra questions due to page base retrieval
                    drop_questions -= 1
                    continue
                question['offset'] = current_offset
                current_offset += 1
                question['answers_data'] = []
                for raw_answers in self.client.get_question_answers(question['id']):
                    self._push_cache_queue(raw_answers)
                    answers = json.loads(raw_answers)['results']
                    question['answers_data'] += answers
                yield question
                nquestions += 1
                self._push_cache_queue('{}') # Mark with empty dict end of question

            logger.debug("Questions: %i/%i", nquestions + offset, tquestions)

            self._flush_cache_queue()

        logger.info("Total number of questions: %i (%i total)", nquestions, tquestions)
        logger.info("Questions with errors dropped: %i", equestions)


    @kitsune_metadata
    @metadata
    def fetch_from_cache(self):
        """Fetch the questions from the cache.

        It only works with a cache created from one execution.

        :returns: a generator of questions

        :raises CacheError: raised when an error occurs accessing the
            cache
        """

        def get_drop_questions(offset):
            page = int(offset / KitsuneClient.ITEMS_PER_PAGE)
            page_offset = page * KitsuneClient.ITEMS_PER_PAGE
            drop_questions = offset - page_offset
            return drop_questions

        def get_answers(cache_answers):
            answers_data = []

            for answers_raw in cache_answers:
                answers = json.loads(answers_raw)
                if not answers:
                    # empty dict is the mark for end of question answers
                    break
                else:
                    answers = answers['results']
                    answers_data += answers

            return answers_data


        if not self.cache:
            raise CacheError(cause="cache instance was not provided")

        cache_items = self.cache.retrieve()

        nquestions = 0

        logger.info("Retrieving cached questions: '%s'", self.url)

        for items_raw in cache_items:
            if type(items_raw) is int:
                # offset from a new execution results in the cache
                offset = items_raw
                questions_raw = next(cache_items)
                drop_questions = get_drop_questions(offset)
            else:
                questions_raw = items_raw
            if not json.loads(questions_raw):
                # Last item is the empty dict
                questions_raw = next(cache_items)
            questions = json.loads(questions_raw)['results']
            for question in questions:
                if drop_questions > 0:
                    # Remove extra questions due to page base retrieval
                    drop_questions -= 1
                    continue
                question['offset'] = offset
                offset += 1
                question['answers_data'] = get_answers(cache_items)
                yield question
                nquestions += 1

        logger.info("Retrieval process completed: %s questions retrieved from cache",
                    nquestions)

    @classmethod
    def has_caching(cls):
        """Returns whether it supports caching items on the fetch process.

        :returns: this backend supports items cache
        """
        return True

    @classmethod
    def has_resuming(cls):
        """Returns whether it supports to resume the fetch process.

        :returns: this backend supports items resuming
        """
        return True

    @staticmethod
    def metadata_id(item):
        """Extracts the identifier from a Kitsune item."""

        return str(item['id'])

    @staticmethod
    def metadata_updated_on(item):
        """Extracts the update time from a Kitsune item.

        The timestamp is extracted from 'timestamp' field.
        This date is a UNIX timestamp but needs to be converted to
        a float value.

        :param item: item generated by the backend

        :returns: a UNIX timestamp
        """
        return float(str_to_datetime(item['updated']).timestamp())

    @staticmethod
    def metadata_category(item):
        """Extracts the category from a Kitsune item.

        This backend only generates one type of item which is
        'question'.
        """
        return 'question'


class KitsuneClient:
    """Kitsune API client.

    This class implements a simple client to retrieve questions and answers from
    a Kitsune site.

    :param url: URL of Kitsune (sample https://support.mozilla.org)

    :raises HTTPError: when an error occurs doing the request
    """
    FIRST_PAGE = 1  # Initial page in Kitsune
    ITEMS_PER_PAGE = 20 # Items per page in Kitsune API

    def __init__(self, url):
        self.url = url
        self.api_url = urljoin(self.url, '/api/2/')

    def call(self, api_url, params):
        """Run an API command.
        :param api_url: api url to run on the server
        :param params: dict with the HTTP parameters needed to run
            the given command
        """
        logger.debug("Kitsune client calls API: %s params: %s",
                     api_url, str(params))

        req = requests.get(api_url, params=params)
        req.raise_for_status()

        return req.text

    def get_questions(self, offset=None):
        """Retrieve questions from older to newer updated starting offset"""

        page = KitsuneClient.FIRST_PAGE

        if offset:
            page += int(offset / KitsuneClient.ITEMS_PER_PAGE)

        next_uri = None # URI for the next questions query

        while True:
            api_questions_url = urljoin(self.api_url, '/question') + '/'

            params = {
                "page":page,
                "ordering":"updated"
            }

            questions = self.call(api_questions_url, params)
            yield questions

            questions_json = json.loads(questions)
            next_uri = questions_json['next']
            if not next_uri:
                break
            page += 1

    def get_question_answers(self, question_id):
        """Retrieve all answers for a question from older to newer (updated)"""

        page = KitsuneClient.FIRST_PAGE

        while True:
            api_answers_url = urljoin(self.api_url, '/answer') + '/'
            params = {
                "page": page,
                "question":question_id,
                "ordering":"updated"
            }
            answers_raw = self.call(api_answers_url, params)
            yield answers_raw

            answers = json.loads(answers_raw)
            if not answers['next']:
                break
            page = page+1


class KitsuneCommand(BackendCommand):
    """Class to run Kitsune backend from the command line."""

    def __init__(self, *args):
        super().__init__(*args)
        self.url = self.parsed_args.url
        self.tag = self.parsed_args.tag
        self.outfile = self.parsed_args.outfile
        self.offset = self.parsed_args.offset

        if not self.parsed_args.no_cache:
            if not self.parsed_args.cache_path:
                base_path = os.path.expanduser('~/.perceval/cache/')
            else:
                base_path = self.parsed_args.cache_path

            cache_path = os.path.join(base_path, self.url)

            cache = Cache(cache_path)

            if self.parsed_args.clean_cache:
                cache.clean()
            else:
                cache.backup()
        else:
            cache = None

        self.backend = Kitsune(self.url, tag=self.tag, cache=cache)

    def run(self):
        """Fetch and print the Events.

        This method runs the backend to fetch the questions of a given url.
        Events are converted to JSON objects and printed to the
        defined output.
        """
        if self.parsed_args.fetch_cache:
            questions = self.backend.fetch_from_cache()
        else:
            questions = self.backend.fetch(offset=self.offset)

        try:
            for question in questions:
                obj = json.dumps(question, indent=4, sort_keys=True)
                self.outfile.write(obj)
                self.outfile.write('\n')
        except requests.exceptions.HTTPError as e:
            raise requests.exceptions.HTTPError(str(e.response.json()))
        except IOError as e:
            raise RuntimeError(str(e))
        except Exception as e:
            if self.backend.cache:
                self.backend.cache.recover()
            raise RuntimeError(str(e))

    @classmethod
    def create_argument_parser(cls):
        """Returns the Kitsune argument parser."""

        parser = super().create_argument_parser()

        # Remove --from-date argument from parent parser
        # because it is not needed by this backend
        action = parser._option_string_actions['--from-date']
        parser._handle_conflict_resolve(None, [('--from-date', action)])

        # Kitsune options
        group = parser.add_argument_group('Kitsune arguments')

        group.add_argument('--offset', dest='offset',
                            type=int, default=DEFAULT_OFFSET,
                            help='Offset from which to start fetching questions')

        group.add_argument("url", default="https://support.mozilla.org", nargs='?',
                           help="Kitsune URL (default: https://support.mozilla.org)")

        return parser
