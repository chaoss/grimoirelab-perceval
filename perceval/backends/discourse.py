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
#   J. Manrique López de la Fuente <jsmanrique@bitergia.com>
#

import json
import logging
import os.path

import requests
import time

from ..backend import Backend, BackendCommand, metadata
from ..cache import Cache
from ..errors import CacheError
from ..utils import str_to_datetime, DEFAULT_DATETIME, urljoin

MAX_topics = 100  # Maximum number of posts per query

logger = logging.getLogger(__name__)


def get_update_time(item):
    """Extracts the update time from a Discourse item"""
    return item['updated_at']


class Discourse(Backend):
    """Discourse backend for Perceval.

    This class retrieves the posts stored in any of the
    Discourse urls. To initialize this class the
    url must be provided.

    :param url: Discourse url
    :param token: Discourse access_token for the API
    :param cache: cache object to store raw data
    """
    version = '0.1.0'

    def __init__(self, url, token=None,
                 max_topics=None, cache=None):

        super().__init__(url, cache=cache)
        self.url = url
        self.max_topics = max_topics
        self.client = DiscourseClient(url, token, max_topics)

    @metadata(get_update_time)
    def fetch(self, from_date=DEFAULT_DATETIME):
        """Fetch the posts from the url.

        The method retrieves, from a Discourse url, the
        posts updated since the given date.

        :param from_date: obtain topics updated since this date

        :returns: a generator of posts
        """
        if not from_date:
            from_date = DEFAULT_DATETIME

        logger.info("Looking for topics at url '%s', updated from '%s'",
                    self.url, str(from_date))

        task_init = time.time()
        i = 0
        self._purge_cache_queue()

        """whole_pages = self.client.get_topics(from_date)"""
        whole_pages = self.client.get_posts(from_date)

        for whole_page in whole_pages:
            self._push_cache_queue(whole_page)
            self._flush_cache_queue()
            post = self.parse_post(whole_page)
            yield post
            i = i + 1
        logger.info("%i posts parsed in %.2fs from '%s'" % (i, time.time()-task_init, self.url))

    @metadata(get_update_time)
    def fetch_from_cache(self):
        """Fetch the posts from the cache.

        :returns: a generator of topics

        :raises CacheError: raised when an error occurs accessing the
            cache
        """
        if not self.cache:
            raise CacheError(cause="cache instance was not provided")

        cache_items = self.cache.retrieve()

        for items in cache_items:
            posts = self.parse_posts(items)
            for post in posts:
                yield post

    @staticmethod
    def parse_post(raw_page):
        """Parse a Discourse API topic raw response.

        The method parses the API response retrieving the
        posts from the received topic

        :param raw_page: topic page from where to parse the posts

        :returns: a generator of posts
        """
        post = json.loads(raw_page)

        return post


class DiscourseClient:
    """Discourse API client.

    This class implements a simple client to retrieve topics from
    any Discourse url.

    :param url: URL of the Discourse site
    :param token: Discourse access_token for the API
    :param max_topics: max number of topics per query

    :raises HTTPError: when an error occurs doing the request
    """

    def __init__(self, url, token, max_topics):
        self.url = url
        self.token = token
        self.max_topics = max_topics

    def __build_base_url(self, item_type, item_id):
        id_json = str(item_id) + '.json'
        base_api_url = urljoin(self.url, item_type, id_json)
        return base_api_url

    def __build_payload(self, page):
        payload = {'page': page,
                   'api_key': self.token}
        return payload

    def get_posts(self, from_date):
        """Retrieve all the posts updated since a given date.

        :param from_date: obtain topics updated since this date
        """

        logger.info('Getting posts')
        posts = []
        topics_id_list = self.get_topics_id_list(from_date)

        for topic_id in topics_id_list:
            req = requests.get(self.__build_base_url('t', topic_id),
                                params=self.__build_payload(None))
            req.raise_for_status()
            data = req.json()
            i = 0
            for post_id in reversed(data['post_stream']['stream']):
                req_post = requests.get(self.__build_base_url('posts', post_id),
                                    params=self.__build_payload(None))
                req_post.raise_for_status()
                data_post = req_post.json()
                if str_to_datetime(data_post['updated_at']) >= from_date:
                    posts.append(req_post.text)
                    i = i + 1
                else:
                    break
            logger.info('%i posts updated for topic %s' % (i, topic_id))

        logger.info('Done! %i posts updated', len(posts))
        return posts

    def get_topics_id_list(self, from_date):
        """Retrieve all the topics ids updated since a given date.

        :param from_date: obtain topics updated since this date
        """
        logger.info('Getting topics ids')
        topics_ids = []
        req = requests.get(self.url+'/latest.json', self.__build_payload(None))
        req.raise_for_status()
        data = req.json()
        for topic in data['topic_list']['topics']:
            if str_to_datetime(topic['last_posted_at']) >= from_date:
                topics_ids.append(topic['id'])
                logger.info("Id for topic '%s': %s" % (topic['title'],topic['id']))

        page = 0

        while 'more_topics_url' in data['topic_list']:
            page = page + 1
            req = requests.get(self.url+'/latest.json', self.__build_payload(page))
            req.raise_for_status()
            data = req.json()
            for topic in data['topic_list']['topics']:
                if str_to_datetime(topic['last_posted_at']) >= from_date:
                    topics_ids.append(topic['id'])
                    logger.info("Id for topic '%s': %s" % (topic['title'], topic['id']))

        logger.info("Topics to be requested: %s" % len(topics_ids))
        return topics_ids


class DiscourseCommand(BackendCommand):
    """Class to run Discourse backend from the command line."""

    def __init__(self, *args):
        super().__init__(*args)
        self.url = self.parsed_args.url
        self.token = self.parsed_args.token
        self.max_topics = self.parsed_args.max_topics
        self.from_date = str_to_datetime(self.parsed_args.from_date)
        self.outfile = self.parsed_args.outfile

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

        self.backend = Discourse(
            self.url, self.token, self.max_topics, cache=cache)

    def run(self):
        """Fetch and print the Posts.

        This method runs the backend to fetch the posts
        of a given Discourse url.
        Posts are converted to JSON objects and printed to the
        defined output.
        """
        if self.parsed_args.fetch_cache:
            posts = self.backend.fetch_from_cache()
        else:
            posts = self.backend.fetch(from_date=self.from_date)

        try:
            for post in posts:
                obj = json.dumps(post, indent=4, sort_keys=True)
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
        """Returns the Discourse argument parser."""

        parser = super().create_argument_parser()

        # StackExchange options
        group = parser.add_argument_group('Discourse arguments')

        group.add_argument("--token",
                           help="Discourse API key")
        group.add_argument('--max-topics', dest='max_topics',
                           type=int, default=MAX_topics,
                           help="Max number of topics to be requested")
        # Required arguments
        parser.add_argument("url", help="Discourse site's url")

        return parser
