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
#     Alberto Martín <alberto.martin@bitergia.com>
#     Santiago Dueñas <sduenas@bitergia.com>
#     Stephan Barth <stephan.barth@gmail.com>
#     Valerio Cosentino <valcos@bitergia.com>
#     Jesus M. Gonzalez-Barahona <jgb@gsyc.es>
#     Harshal Mittal <harshalmittal4@gmail.com>
#     animesh <animuz111@gmail.com>
#

import json
import logging
import re

import bs4
import requests

from grimoirelab_toolkit.datetime import datetime_to_utc, str_to_datetime
from grimoirelab_toolkit.uris import urijoin

from ...backend import (Backend,
                        BackendCommand,
                        BackendCommandArgumentParser)
from ...client import HttpClient
from ...utils import DEFAULT_DATETIME

CATEGORY_QUESTION = 'question'

logger = logging.getLogger(__name__)


class Askbot(Backend):
    """Askbot backend.

    This class retrieves the questions posted on an Askbot site.
    To initialize this class the URL must be provided. The `url`
    will be set as the origin of the data.

    :param url: Askbot site URL
    :param tag: label used to mark the data
    :param archive: archive to store/retrieve items
    :param ssl_verify: enable/disable SSL verification
    """
    version = '1.0.0'

    CATEGORIES = [CATEGORY_QUESTION]
    EXTRA_SEARCH_FIELDS = {
        'tags': ['tags']
    }

    def __init__(self, url, tag=None, archive=None, ssl_verify=True):
        origin = url

        super().__init__(origin, tag=tag, archive=archive, ssl_verify=ssl_verify)
        self.url = url
        self.client = None
        self.ab_parser = AskbotParser()

    def fetch(self, category=CATEGORY_QUESTION, from_date=DEFAULT_DATETIME):
        """Fetch the questions/answers from the repository.

        The method retrieves, from an Askbot site, the questions and answers
        updated since the given date.

        :param category: the category of items to fetch
        :param from_date: obtain questions/answers updated since this date

        :returns: a generator of items
        """
        if not from_date:
            from_date = DEFAULT_DATETIME
        logger.info(f"Pulling Askbot data from {from_date}")
        kwargs = {'from_date': from_date}
        items = super().fetch(category, **kwargs)

        return items

    def fetch_items(self, category, **kwargs):
        """Fetch the questions

        :param category: the category of items to fetch
        :param kwargs: backend arguments

        :returns: a generator of items
        """

        from_date = datetime_to_utc(kwargs['from_date']).timestamp()

        questions_groups = self.client.get_api_questions(AskbotClient.API_QUESTIONS)
        for questions in questions_groups:

            for question in questions['questions']:
                updated_at = int(question['last_activity_at'])
                if updated_at > from_date:
                    html_question = self.__fetch_question(question)
                    if not html_question:
                        continue

                    logger.debug("Fetching HTML question %s", question['id'])
                    comments = self.__fetch_comments(question)
                    question_obj = self.__build_question(html_question, question, comments)
                    question.update(question_obj)
                    yield question

    @classmethod
    def has_resuming(cls):
        """Returns whether it supports to resume the fetch process.

        :returns: this backend supports items resuming
        """
        return True

    @classmethod
    def has_archiving(cls):
        """Returns whether it supports archiving items on the fetch process.

        :returns: this backend supports items archive
        """
        return True

    @staticmethod
    def metadata_category(item):
        """Extracts the category from an Askbot item.

        This backend only generates one type of item which is
        'question'.
        """
        return CATEGORY_QUESTION

    @staticmethod
    def metadata_id(item):
        """Extracts the identifier from an Askbot question item."""

        return str(item['id'])

    @staticmethod
    def metadata_updated_on(item):
        """Extracts the update time from an Askbot item.

        The timestamp is extracted from 'last_activity_at' field.
        This date is a UNIX timestamp but needs to be converted to
        a float value.

        :param item: item generated by the backend

        :returns: a UNIX timestamp
        """
        return float(item['last_activity_at'])

    def _init_client(self, from_archive=False):
        """Init client"""

        return AskbotClient(self.url, self.archive, from_archive, self.ssl_verify)

    def __fetch_question(self, question):
        """Fetch an Askbot HTML question body.

        The method fetches the HTML question retrieving the
        question body of the item question received

        :param question: item with the question itself

        :returns: a list of HTML page/s for the question
        """
        html_question_items = []

        npages = 1
        next_request = True

        while next_request:
            try:
                html_question = self.client.get_html_question(question['id'], npages)
                html_question_items.append(html_question)
                tpages = self.ab_parser.parse_number_of_html_pages(html_question)
                logger.info(f"{tpages} of questions found")
                if npages == tpages:
                    next_request = False

                npages = npages + 1
            except requests.exceptions.TooManyRedirects as e:
                logger.warning("%s, data not retrieved for question %s", e, question['id'])
                next_request = False

        return html_question_items

    def __fetch_comments(self, question):
        """Fetch all the comments of an Askbot question and answers.

        The method fetches the list of every comment existing in a question and
        its answers.

        :param question: item with the question itself

        :returns: a list of comments with the ids as hashes
        """
        comments = {}
        comments[question['id']] = json.loads(self.client.get_comments(question['id']))
        for object_id in question['answer_ids']:
            comments[object_id] = json.loads(self.client.get_comments(object_id))
        logger.debug(f"{len(comments)} comments found")
        return comments

    @staticmethod
    def __build_question(html_question, question, comments):
        """Build an Askbot HTML response.

        The method puts together all the information regarding a question

        :param html_question: array of HTML raw pages
        :param question: question object from the API
        :param comments: list of comments to add

        :returns: a dict item with the parsed question information
        """
        question_object = {}
        # Parse the user info from the soup container
        question_container = AskbotParser.parse_question_container(html_question[0])
        # Add the info to the question object
        question_object.update(question_container)
        # Add the comments of the question (if any)
        if comments[int(question['id'])]:
            question_object['comments'] = comments[int(question['id'])]

        answers = []

        for page in html_question:
            answers.extend(AskbotParser.parse_answers(page))

        if len(answers) != 0:
            question_object['answers'] = answers
            for answer in question_object['answers']:
                if comments[int(answer['id'])]:
                    answer['comments'] = comments[int(answer['id'])]

        return question_object


class AskbotClient(HttpClient):
    """Askbot client.

    This class implements a simple client to retrieve distinct
    kind of data from an Askbot site.

    :param base_url: URL of the Askbot site
    :param archive: an archive to store/read fetched data
    :param from_archive: it tells whether to write/read the archive
    :param ssl_verify: enable/disable SSL verification

    :raises HTTPError: when an error occurs doing the request
    """

    API_QUESTIONS = 'api/v1/questions/'

    # API resources
    RHTML_QUESTION = 'question/'
    RCOMMENTS = 's/post_comments'
    RCOMMENTS_OLD = 'post_comments'

    # API header
    HREQUEST_WITH = 'X-Requested-With'

    # Resource parameters
    PPAGE = 'page'
    PSORT = 'sort'
    PPOST_ID = 'post_id'
    PPOST_TYPE = 'post_type'
    PAVATAR_SIZE = 'avatar_size'

    # Predefined values
    VORDER_API = 'activity-asc'
    VORDER_HTML = 'votes'
    VANSWER = 'answer'
    VAVATAR_SIZE = 0
    VHTTP_REQUEST = 'XMLHttpRequest'

    def __init__(self, base_url, archive=None, from_archive=False, ssl_verify=True):
        super().__init__(base_url, archive=archive, from_archive=from_archive, ssl_verify=ssl_verify)
        self._use_new_urls = True

    def get_api_questions(self, path):
        """Retrieve a question page using the API.

        :param page: page to retrieve
        """
        npages = 1
        next_request = True
        logger.debug("Retrieving question pages")
        path = urijoin(self.base_url, path)
        while next_request:

            try:
                params = {
                    self.PPAGE: npages,
                    self.PSORT: self.VORDER_API
                }

                response = self.fetch(path, payload=params)

                whole_page = response.text

                raw_questions = json.loads(whole_page)
                tpages = raw_questions['pages']

                logger.debug("Fetching questions from '%s': page %s/%s",
                             self.base_url, npages, tpages)

                if npages == tpages:
                    next_request = False

                npages = npages + 1
                yield raw_questions

            except requests.exceptions.TooManyRedirects as e:
                logger.warning("%s, data not retrieved for resource %s", e, path)
                next_request = False

    def get_html_question(self, question_id, page=1):
        """Retrieve a raw HTML question and all it's information.

        :param question_id: question identifier
        :param page: page to retrieve
        """
        path = urijoin(self.base_url, self.RHTML_QUESTION, question_id)
        logger.debug(f"Raw html retrieved: {path}")
        params = {
            self.PPAGE: page,
            self.PSORT: self.VORDER_HTML
        }

        response = self.fetch(path, payload=params)
        return response.text

    def get_comments(self, post_id):
        """Retrieve a list of comments by a given id.

        :param object_id: object identifiere
        """
        path = urijoin(self.base_url, self.RCOMMENTS if self._use_new_urls else self.RCOMMENTS_OLD)
        params = {
            self.PPOST_ID: post_id,
            self.PPOST_TYPE: self.VANSWER,
            self.PAVATAR_SIZE: self.VAVATAR_SIZE
        }
        headers = {self.HREQUEST_WITH: self.VHTTP_REQUEST}

        try:
            response = self.fetch(path, payload=params, headers=headers)
            raw = response.text
        except requests.exceptions.HTTPError as ex:
            if ex.response.status_code == 404:
                logger.debug("Comments URL did not work. Using old URL schema.")
                self._use_new_urls = False
                path = urijoin(self.base_url, self.RCOMMENTS_OLD)
                response = self.fetch(path, payload=params, headers=headers)
                raw = response.text
            elif ex.response.status_code == 500:
                logger.warning("Comments not retrieved due to %s", ex)
                raw = '[]'
            else:
                raise ex

        return raw


class AskbotParser:
    """Askbot HTML parser.

    This class parses a plain HTML document, converting questions, answers,
    comments and user information into dict items.
    """

    @staticmethod
    def parse_question_container(html_question):
        """Parse the question info container of a given HTML question.

        The method parses the information available in the question information
        container. The container can have up to 2 elements: the first one
        contains the information related to the user who generated the question
        and the date (if any). The second one contains the date of the update
        and the user who updated it (if not the same who generated the question).

        :param html_question: raw HTML question element

        :returns: an object with the parsed information
        """
        container_info = {}
        bs_question = bs4.BeautifulSoup(html_question, "html.parser")
        question = AskbotParser._find_question_container(bs_question)
        container = question.select("div.post-update-info")
        created = container[0]
        container_info['author'] = AskbotParser.parse_user_info(created)
        try:
            container[1]
        except IndexError:
            pass
        else:
            updated = container[1]
            if AskbotParser.parse_user_info(updated):
                container_info['updated_by'] = AskbotParser.parse_user_info(updated)
        logger.debug("Container info parsed")
        return container_info

    @staticmethod
    def parse_answers(html_question):
        """Parse the answers of a given HTML question.

        The method parses the answers related with a given HTML question,
        as well as all the comments related to the answer.

        :param html_question: raw HTML question element

        :returns: a list with the answers
        """

        def parse_answer_container(update_info):
            """Parse the answer info container of a given HTML question.

            The method parses the information available in the answer information
            container. The container can have up to 2 elements: the first one
            contains the information related to the user who generated the question
            and the date (if any). The second one contains the date of the update
            and the user who updated it (if not the same who generated the question).

            :param update_info: beautiful soup update_info container element

            :returns: an object with the parsed information
            """
            container_info = {}
            created = update_info[0]
            answered_at = created.abbr.attrs["title"]
            # Convert date to UNIX timestamp
            container_info['added_at'] = str(str_to_datetime(answered_at).timestamp())
            container_info['answered_by'] = AskbotParser.parse_user_info(created)
            try:
                update_info[1]
            except IndexError:
                pass
            else:
                updated = update_info[1]
                updated_at = updated.abbr.attrs["title"]
                # Convert date to UNIX timestamp
                container_info['updated_at'] = str(str_to_datetime(updated_at).timestamp())
                if AskbotParser.parse_user_info(updated):
                    container_info['updated_by'] = AskbotParser.parse_user_info(updated)
            return container_info

        answer_list = []
        # Select all the answers
        bs_question = bs4.BeautifulSoup(html_question, "html.parser")
        bs_answers = bs_question.select("div.answer")
        logger.debug(f"{str(len(bs_answers))} answers found")
        for bs_answer in bs_answers:
            answer_id = bs_answer.attrs["data-post-id"]
            votes_element = bs_answer.select("div.vote-number")[0].text
            accepted_answer = bs_answer.select("div.answer-img-accept")[0].get('title').endswith("correct")
            # Select the body of the answer
            body = bs_answer.select("div.post-body")
            # Get the user information container and parse it
            update_info = body[0].select("div.post-update-info")
            answer_container = parse_answer_container(update_info)
            # Remove the update-info-container div to be able to get the body
            body[0].div.extract().select("div.post-update-info-container")
            # Override the body with a clean one
            body = body[0].get_text(strip=True)
            # Generate the answer object
            answer = {'id': answer_id,
                      'score': votes_element,
                      'summary': body,
                      'accepted': accepted_answer
                      }
            # Update the object with the information in the answer container
            answer.update(answer_container)
            answer_list.append(answer)
        logger.debug("Answers parsed")
        return answer_list

    @staticmethod
    def parse_number_of_html_pages(html_question):
        """Parse number of answer pages to paginate over them.

        :param html_question: raw HTML question element

        :returns: an integer with the number of pages
        """
        bs_question = bs4.BeautifulSoup(html_question, "html.parser")
        try:
            bs_question.select('div.paginator')[0]
        except IndexError:
            return 1
        else:
            return int(bs_question.select('div.paginator')[0].attrs['data-num-pages'])

    @staticmethod
    def parse_user_info(update_info):
        """Parse the user information of a given HTML container.

        The method parses all the available user information in the container.
        If the class "user-info" exists, the method will get all the available
        information in the container. If not, if a class "tip" exists, it will be
        a wiki post with no user associated. Else, it can be an empty container.

        :param update_info: beautiful soup answer container element

        :returns: an object with the parsed information
        """
        user_info = {}
        if update_info.select("div.user-info"):
            # Get all the <a> elements in the container. First <a> contains the user
            # information, second one (if exists), the website of the user.
            elements = update_info.select("div.user-info")[0].find_all("a")
            href = elements[0].attrs["href"]
            user_info['id'] = re.search(r'\d+', href).group(0)
            user_info['username'] = elements[0].text
            user_info['reputation'] = update_info.select('span.reputation-score')[0].text
            user_info['badges'] = update_info.select("span.badges")[0].attrs["title"]
            try:
                elements[1]
            except IndexError:
                pass
            else:
                user_info['website'] = elements[1].attrs["href"]
            if update_info.select("img.flag"):
                flag = update_info.select("img.flag")[0].attrs["alt"]
                user_info['country'] = re.sub("flag of ", "", flag)
        logger.debug("User info parsed")
        return user_info

    @staticmethod
    def _find_question_container(bs_question):
        questions = bs_question.find_all("div",
                                         attrs={'class': re.compile(".*question")})
        for question in questions:
            if 'post' in question.attrs['class']:
                return question


class AskbotCommand(BackendCommand):
    """Class to run Askbot backend from the command line."""

    BACKEND = Askbot

    @classmethod
    def setup_cmd_parser(cls):
        """Returns the Askbot argument parser."""

        parser = BackendCommandArgumentParser(cls.BACKEND,
                                              from_date=True,
                                              archive=True,
                                              ssl_verify=True)

        # Required arguments
        parser.parser.add_argument('url',
                                   help="URL of the Askbot server")

        return parser
