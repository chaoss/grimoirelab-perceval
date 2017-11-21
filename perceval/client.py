# -*- coding: utf-8 -*-
#
# Copyright (C) 2015-2017 Bitergia
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
# Foundation, 51 Franklin Street, Fifth Floor, Boston, MA 02110-1335, USA.
#
# Authors:
#     Valerio Cosentino <valcos@bitergia.com>
#

import logging
import time

import requests
from .errors import RateLimitError

logger = logging.getLogger(__name__)


class HttpClient:
    """Abstract class for HTTP clients.

    Base class to query data sources.

    Derivated classes have to implement `call`, `params`, `headers`
    `pagination`, `has_retry` and `has_sleep` methods. Otherwise, `NotImplementedError`
    exception will be raised.

    To track which version of the client was used during the fetching
    process, this class provides a `version` attribute that each client
    may override.

    :param has_rest: rest between calls
    :param has_retry: retry calls in case of data source failures
    :param has_pagination: client returns paginated items from the data source
    """
    version = '0.1'

    MIN_RATE_LIMIT = 10

    DEFAULT_SLEEP_TIME = 1
    MAX_RETRIES = 5

    RATE_LIMIT_HEADER = "X-RateLimit-Remaining"
    RATE_LIMIT_RESET_HEADER = "X-RateLimit-Reset"

    RETRY = "retry"
    STOP = "stop"

    def __init__(self, base_url, sleep_for_rate=False, min_rate_to_sleep=MIN_RATE_LIMIT,
                 max_retries=MAX_RETRIES, default_sleep_time=DEFAULT_SLEEP_TIME):
        self.base_url = base_url
        self.rate_limit = None
        self.rate_limit_reset_ts = None
        self.session = None
        self.sleep_for_rate = sleep_for_rate
        self.min_rate_to_sleep = min_rate_to_sleep

        self.max_retries = max_retries
        self.default_sleep_time = default_sleep_time

    @staticmethod
    def is_response(obj):
        return type(obj) == requests.Response

    def create_http_session(self, headers=None):
        self.session = requests.Session()

        if headers:
            self.session.headers.update(headers)

    def close_http_session(self):
        self.session.close()

    def init_api_token(self, path, params=None, headers=None, use_session=False, method=GET):
        response = self.send_request(path, params, headers, use_session, method)

        self.rate_limit = int(response.headers[self.RATE_LIMIT_HEADER])
        self.rate_limit_reset_ts = int(response.headers[self.RATE_LIMIT_RESET_HEADER])

    def fetch(self, url, params=None, headers=None):
        yield self._fetch(url, params, headers)

    def _fetch(self, url, params=None, headers=None):
        retries = 0

        response = None
        error = None

        while retries <= self.max_retries:
            retries += 1

            try:
                self.sleep_for_rate_limit()
                response = self.__send_request(url, params, headers)
                self.update_rate_limit(response)
                break
            except requests.exceptions.ConnectTimeout as e:
                error = e
                time.sleep(self.default_sleep_time * retries)
            except requests.exceptions.HTTPError as e:
                if e.response.status_code >= 500:
                    if self.STOP == self.handle_http_500_errors(e, retries, url, params, headers):
                        response = self.STOP
                        break
                    error = e
                if e.response.status_code >= 400:
                    if self.STOP == self.handle_http_400_errors(e, retries, url, params, headers):
                        response = self.STOP
                        break
                    error = e
                else:
                    error = e
                    break

        if error:
            raise error

        return response

    def handle_http_500_errors(self, error, retries=0, url=None, params=None, headers=None):
        time.sleep(self.default_sleep_time * retries)
        return self.RETRY

    def handle_http_400_errors(self, error, retries=0, url=None, params=None, headers=None):
        return self.STOP

    def sleep_for_rate_limit(self):
        if self.rate_limit is not None and self.rate_limit <= self.min_rate_to_sleep:
            seconds_to_reset = self.rate_limit_reset_ts - int(time.time()) + 1
            cause = "Rate limit exhausted."
            if self.sleep_for_rate:
                logger.info("%s Waiting %i secs for rate limit reset.", cause, seconds_to_reset)
                time.sleep(seconds_to_reset)
            else:
                raise RateLimitError(cause=cause, seconds_to_reset=seconds_to_reset)

    def update_rate_limit(self, response):
        if self.RATE_LIMIT_HEADER in response.headers:
            self.rate_limit = int(response.headers[self.RATE_LIMIT_HEADER])
            self.rate_limit_reset_ts = int(response.headers[self.RATE_LIMIT_RESET_HEADER])
            logger.debug("Rate limit: %s", self.rate_limit)
        else:
            self.rate_limit = None
            self.rate_limit_reset_ts = None

    def __send_request(self, url, params=None, headers=None):
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()

        return response
