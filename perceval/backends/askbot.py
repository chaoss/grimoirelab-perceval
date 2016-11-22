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
#     Alberto Martín <alberto.martin@bitergia.com>
#


import bs4
import json
import logging
import re
import requests

from ..backend import Backend, metadata, BackendCommand
from ..utils import urljoin, DEFAULT_DATETIME, str_to_datetime, datetime_to_utc

logger = logging.getLogger(__name__)


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
        contains the information related with the user who generated the question
        and the date (if any). The second one contains the date of the updated,
        and the user who updated it (if not the same who generated the question).

        :param html_question: raw HTML question element

        :returns: an object with the parsed information
        """
        container_info = {}
        bs_question = bs4.BeautifulSoup(html_question, "html.parser")
        question = bs_question.select("div.js-question")
        container = question[0].select("div.post-update-info")
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

        return container_info

    @staticmethod
    def parse_question_comments(html_question):
        """Parse the comments of a given HTML question.

        The method parses the comments available for each question.

        :param html_question: raw HTML question element

        :returns: a list with the desired comments
        """
        bs_question = bs4.BeautifulSoup(html_question, "html.parser")
        question = bs_question.select("div.js-question")
        comments = question[0].select("div.comment")
        question_comments = AskbotParser.parse_comments(comments)
        return question_comments

    @staticmethod
    def parse_answers(html_question):
        """Parse the answers of a given HTML question.

        The method parses the answers related with a given HTML question,
        as well as all the comments related to the answer.

        :param html_question: raw HTML question element

        :returns: a list with the answers
        """
        def parse_answer_comments(bs_answer):
            """Parse the comments of a given HTML answer.

            The method parses the comments available for each answer.

            :param bs_answer: beautiful soup answer element

            :returns: a list with the desired comments
            """
            comments = bs_answer.select("div.comment")
            answer_comments = AskbotParser.parse_comments(comments)
            return answer_comments

        def parse_answer_container(update_info):
            """Parse the answer info container of a given HTML question.

            The method parses the information available in the answer information
            container. The container can have up to 2 elements: the first one
            contains the information related with the user who generated the question
            and the date (if any). The second one contains the date of the updated,
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
        for bs_answer in bs_answers:
            answer_id = bs_answer.attrs["data-post-id"]
            votes_element = bs_answer.select("div.vote-number")[0].text
            # Select all the comments in the answer
            comments = parse_answer_comments(bs_answer)
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
                      'summary': body
                      }
            if comments:
                answer['comments'] = comments
            # Update the object with the information in the answer container
            answer.update(answer_container)
            answer_list.append(answer)
        return answer_list

    @staticmethod
    def parse_comments(comments):
        """Parse the HTML comments information of a given list of them.

        The method parses the information available inside each comment.

        :param comments: beautiful soup list of comments

        :returns: a list with the parsed comments
        """
        def parse_comment_author(comment):
            """Parse the author information from an HTML comment.

            The method parses the user information available inside a comment.

            :param comment: beautiful soup comment

            :returns: an object with the user information
            """
            username = comment.select("a.author")[0].text
            href = comment.select("a.author")[0].attrs["href"]
            user_id = re.search('\d+', href).group(0)
            return {'id': user_id, 'username': username}

        comments_list = []
        for comment in comments:
            added_at = comment.select("abbr.timeago")[0].attrs["title"]
            element = {'added_at': str(str_to_datetime(added_at).timestamp()),
                       'author': parse_comment_author(comment),
                       'id': comment.attrs["data-comment-id"],
                       'summary': comment.select("div.comment-body")[0].get_text(strip=True),
                       'score': comment.select("div.upvote")[0].text
                       }
            comments_list.append(element)
        return comments_list

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
            user_info['id'] = re.search('\d+', href).group(0)
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
            return user_info
        elif update_info.select("p.tip"):
            user_info = "This post is a wiki"
            return user_info
        else:
            return


class Askbot(Backend):
    """Askbot backend.

    This class retrieves the questions posted in an Askbot site.
    To initialize this class the URL must be provided. The `url`
    will be set as the origin of the data.

    :param url: Askbot site URL
    :param tag: label used to mark the data
    """
    version = '0.1.0'

    def __init__(self, url, tag=None):
        origin = url

        super().__init__(origin, tag=tag)
        self.url = url
        self.client = AskbotClient(url)
        self.ab_parser = AskbotParser()

    @metadata
    def fetch(self, from_date=DEFAULT_DATETIME):
        """Fetch the questions/answers from the repository.

        The method retrieves, from an Askbot site, the questions and answers
        updated since the given date.

        :param from_date: obtain questions/answers updated since this date

        :returns: a generator of items
        """

        if not from_date:
            from_date = DEFAULT_DATETIME

        from_date = datetime_to_utc(from_date).timestamp()

        npages = 1
        next_request = True

        while next_request:
            whole_page = self.client.get_api_questions(npages)
            raw_questions = json.loads(whole_page)
            questions = raw_questions['questions']
            tpages = raw_questions['pages']

            logger.debug("Fetching questions from '%s': page %s/%s",
                         self.url, npages, tpages)

            for question in questions:
                updated_at = int(question['last_activity_at'])
                if updated_at > from_date:
                    html_question = self.__fetch_question(question)
                    logger.debug("Fetching HTML question %s", question['id'])
                    question_obj = self.__build_question(html_question)
                    question.update(question_obj)
                    yield question

            if npages == tpages:
                next_request = False

            npages = npages + 1

    def __fetch_question(self, question):
        """Fetch an Askbot HTML question body.

        The method fetchs the HTML question retrieving the
        question body of the item question received

        :param question: item with the question itself

        :returns: a list of HTML page/s for the question
        """

        html_question_items = []

        npages = 1
        next_request = True

        while next_request:
            html_question = self.client.get_html_question(question['id'], npages)
            html_question_items.append(html_question)
            tpages = self.ab_parser.parse_number_of_html_pages(html_question)

            if npages == tpages:
                next_request = False

            npages = npages + 1

        return html_question_items

    @classmethod
    def has_resuming(cls):
        """Returns whether it supports to resume the fetch process.

        :returns: this backend supports items resuming
        """
        return True

    @classmethod
    def has_caching(cls):
        """Returns whether it supports caching items on the fetch process.

        :returns: this backend does not support items cache
        """
        return False

    @staticmethod
    def metadata_category(item):
        """Extracts the category from an Askbot item.

        This backend only generates one type of item which is
        'question'.
        """
        return 'question'

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

    @staticmethod
    def __build_question(html_question):
        """Build an Askbot HTML response.

        The method puts together all the information regarding a question

        :param html_question: array of HTML raw pages

        :returns: a dict item with the parsed question information
        """
        question_object = {}
        # Parse the user info from the soup container
        question_container = AskbotParser.parse_question_container(html_question[0])
        # Add the info to the question object
        question_object.update(question_container)
        # Add the comments of the question (if any)
        if AskbotParser.parse_question_comments(html_question[0]):
            question_object['comments'] = AskbotParser.parse_question_comments(html_question[0])

        answers = []

        for page in html_question:
            answers.extend(AskbotParser.parse_answers(page))

        if len(answers) != 0:
            question_object['answers'] = answers

        return question_object


class AskbotClient:
    """Askbot client.

    This class implements a simple client to retrieve distinct
    kind of data from an Askbot site.

    :param base_url: URL of the Askbot site

    :raises HTTPError: when an error occurs doing the request
    """

    API_QUESTIONS = 'api/v1/questions/'
    HTML_QUESTION = 'question/'
    ORDER_API = 'activity-asc'
    ORDER_HTML = 'votes'

    def __init__(self, base_url):
        self.base_url = base_url

    def get_api_questions(self, page=1):
        """Retrieve a question page using the API.

        :param page: page to retrieve
        """
        path = self.API_QUESTIONS
        params = {
                    'page': page,
                    'sort': self.ORDER_API
                 }
        response = self.__call(path, params)
        return response

    def get_html_question(self, question_id, page=1):
        """Retrieve a raw HTML question and all it's information.

        :param question_id: question identifier
        :param page: page to retrieve
        """
        path = urljoin(self.HTML_QUESTION, question_id)
        params = {
                    'page': page,
                    'sort': self.ORDER_HTML
                 }
        response = self.__call(path, params)
        return response

    def __call(self, path, params=None):
        """Retrieve all the questions.

        :param path: path of the url
        :param params: dict with the HTTP parameters needed to run
            the given command
        """

        url = urljoin(self.base_url, path)

        req = requests.get(url, params=params)
        req.raise_for_status()

        return req.text


class AskbotCommand(BackendCommand):
    """Class to run Askbot backend from the command line."""

    def __init__(self, *args):
        super().__init__(*args)

        self.url = self.parsed_args.url
        self.from_date = str_to_datetime(self.parsed_args.from_date)
        self.tag = self.parsed_args.tag
        self.outfile = self.parsed_args.outfile

        self.backend = Askbot(self.url, tag=self.tag)

    def run(self):
        """Fetch and print the questions.

        This method runs the backend to fetch the questions from the given
        site. Questions are converted to JSON objects and printed to the
        defined output.
        """
        questions = self.backend.fetch(from_date=self.from_date)

        try:
            for question in questions:
                obj = json.dumps(question, indent=4, sort_keys=True)
                self.outfile.write(obj)
                self.outfile.write('\n')
        except IOError as e:
            raise RuntimeError(str(e))
        except Exception as e:
            raise RuntimeError(str(e))

    @classmethod
    def create_argument_parser(cls):
        """Returns the Askbot argument parser."""

        parser = super().create_argument_parser()

        # Required arguments
        parser.add_argument('url',
                            help="URL of the Askbot server")

        return parser
