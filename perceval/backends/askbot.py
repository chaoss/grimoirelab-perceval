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

import requests

from ..utils import urljoin


class AskbotClient:
    """Askbot client.

    This class implements a simple client to retrieve distinct
    kind of data from an Askbot site.

    :param base_url: URL of the Askbot site
    :param max_questions

    :raises HTTPError: when an error occurs doing the request
    """

    API_QUESTIONS = 'api/v1/questions/'
    HTML_QUESTION = 'question/'
    ORDER_API = 'activity-asc'
    ORDER_HTML = 'votes'

    def __init__(self, base_url):
        self.base_url = base_url

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
        """
        path = urljoin(self.HTML_QUESTION, question_id)
        params = {
                    'page': page,
                    'sort': self.ORDER_HTML
                 }
        response = self.__call(path, params)
        return response
