#!/usr/bin/env python3
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
#     Alvaro del Castillo <acs@bitergia.com>
#

import argparse
import json
import shutil
import sys
import tempfile
import unittest

import httpretty

if not '..' in sys.path:
    sys.path.insert(0, '..')

from perceval.cache import Cache
from perceval.errors import CacheError
from perceval.backends.jenkins import Jenkins, JenkinsCommand, JenkinsClient

JENKINS_SERVER_URL = 'http://example.com/ci'
JENKINS_JOBS_URL = JENKINS_SERVER_URL+'/view/All/api/json'
JENKINS_JOB_BUILDS_URL = JENKINS_SERVER_URL + '/job/job1/api/json?depth=2'
JENKINS_JOB_BUILDS_URL_1 = JENKINS_SERVER_URL + '/job/apex-build-brahmaputra/api/json?depth=2'
JENKINS_JOB_BUILDS_URL_2 = JENKINS_SERVER_URL + '/job/apex-build-master/api/json?depth=2'

def read_file(filename, mode='r'):
    with open(filename, mode) as f:
        content = f.read()
    return content

class TestJenkinsBackend(unittest.TestCase):
    """Jenkins backend tests"""

    def test_initialization(self):
        """Test whether attributes are initializated"""

        jenkins = Jenkins(JENKINS_SERVER_URL, job_url=JENKINS_JOB_BUILDS_URL, origin='test')

        self.assertEqual(jenkins.site, JENKINS_SERVER_URL)
        self.assertEqual(jenkins.origin, 'test')
        self.assertEqual(jenkins.job_url, JENKINS_JOB_BUILDS_URL)
        self.assertIsInstance(jenkins.client, JenkinsClient)

        # When origin is empty or None it will be set to
        # the value in url
        jenkins = Jenkins(JENKINS_SERVER_URL)
        self.assertEqual(jenkins.site, JENKINS_SERVER_URL)
        self.assertEqual(jenkins.origin, JENKINS_SERVER_URL)

        jenkins = Jenkins(JENKINS_SERVER_URL, origin='')
        self.assertEqual(jenkins.site, JENKINS_SERVER_URL)
        self.assertEqual(jenkins.origin, JENKINS_SERVER_URL)

    @httpretty.activate
    def test_fetch(self):
        """Test whether a list of builds is returned"""

        requests_http = []

        bodies_jobs = read_file('data/jenkins_jobs.json', mode='rb')
        bodies_builds_job = read_file('data/jenkins_job_builds.json')

        def request_callback(method, uri, headers):
            if uri.startswith(JENKINS_JOBS_URL):
                body = bodies_jobs
            elif uri.startswith(JENKINS_JOB_BUILDS_URL) or \
                 uri.startswith(JENKINS_JOB_BUILDS_URL_1) or \
                 uri.startswith(JENKINS_JOB_BUILDS_URL_2):
                body = bodies_builds_job
            else:
                body = ''

            requests_http.append(httpretty.last_request())

            return (200, headers, body)

        httpretty.register_uri(httpretty.GET,
                               JENKINS_JOBS_URL,
                               responses=[
                                    httpretty.Response(body=request_callback) \
                                    for _ in range(3)
                               ])
        httpretty.register_uri(httpretty.GET,
                               JENKINS_JOB_BUILDS_URL,
                               responses=[
                                    httpretty.Response(body=request_callback) \
                                    for _ in range(2)
                               ])
        httpretty.register_uri(httpretty.GET,
                               JENKINS_JOB_BUILDS_URL_1,
                               responses=[
                                    httpretty.Response(body=request_callback) \
                                    for _ in range(2)
                               ])
        httpretty.register_uri(httpretty.GET,
                               JENKINS_JOB_BUILDS_URL_2,
                               responses=[
                                    httpretty.Response(body=request_callback) \
                                    for _ in range(2)
                               ])

        # Test fetch builds from jobs list
        jenkins = Jenkins(JENKINS_SERVER_URL)
        builds = [build for build in jenkins.fetch()]

        self.assertEqual(len(builds), 64)

        with open("data/jenkins_build.json") as build_json:
            first_build = json.load(build_json)
            self.assertDictEqual(builds[0]['data'], first_build['data'])

        # Test fetch builds from a job
        jenkins = Jenkins(JENKINS_SERVER_URL, job_url=JENKINS_JOB_BUILDS_URL)
        builds = [build for build in jenkins.fetch()]

        self.assertEqual(len(builds), 32)

        with open("data/jenkins_build.json") as build_json:
            first_build = json.load(build_json)
            self.assertDictEqual(builds[0]['data'], first_build['data'])

    @httpretty.activate
    def test_fetch_empty(self):
        """Test whether it works when no builds are fetched"""

        body = '{"builds":[]}'
        httpretty.register_uri(httpretty.GET,
                               JENKINS_JOB_BUILDS_URL,
                               body=body, status=200)


        jenkins = Jenkins(JENKINS_SERVER_URL, job_url=JENKINS_JOB_BUILDS_URL)
        builds = [build for build in jenkins.fetch()]

        self.assertEqual(len(builds), 0)

class TestJenkinsBackendCache(unittest.TestCase):
    """Jenkins backend tests using a cache"""

    def setUp(self):
        self.tmp_path = tempfile.mkdtemp(prefix='perceval_')

    def tearDown(self):
        shutil.rmtree(self.tmp_path)

    @httpretty.activate
    def test_fetch_from_cache(self):
        """Test whether the cache works"""

        # Init the httpretty server contents
        bodies_builds_job = read_file('data/jenkins_job_builds.json')

        def request_callback(method, uri, headers):
            if uri.startswith(JENKINS_JOB_BUILDS_URL):
                body = bodies_builds_job
            else:
                body = ''
            return (200, headers, body)

        httpretty.register_uri(httpretty.GET,
                               JENKINS_JOB_BUILDS_URL,
                               responses=[
                                    httpretty.Response(body=request_callback) \
                                    for _ in range(2)
                               ])

        # First, we fetch the builds from the server, storing them
        # in a cache
        cache = Cache(self.tmp_path)
        jenkins = Jenkins(JENKINS_SERVER_URL, job_url=JENKINS_JOB_BUILDS_URL,  cache=cache)

        builds = [build for build in jenkins.fetch()]

        # Now, we get the builds from the cache.
        # The contents should be the same and there won't be
        # any new request to the server
        cached_builds = [build for build in jenkins.fetch_from_cache()]
        self.assertEqual(len(cached_builds), len(builds))

        with open("data/jenkins_build.json") as build_json:
            first_build = json.load(build_json)
            self.assertDictEqual(cached_builds[0]['data'], first_build['data'])


    def test_fetch_from_empty_cache(self):
        """Test if there are not any builds returned when the cache is empty"""

        cache = Cache(self.tmp_path)
        jenkins = Jenkins(JENKINS_SERVER_URL, job_url=JENKINS_JOB_BUILDS_URL,  cache=cache)
        cached_builds = [build for build in jenkins.fetch_from_cache()]
        self.assertEqual(len(cached_builds), 0)

    def test_fetch_from_non_set_cache(self):
        """Test if a error is raised when the cache was not set"""

        jenkins = Jenkins(JENKINS_SERVER_URL, job_url=JENKINS_JOB_BUILDS_URL)

        with self.assertRaises(CacheError):
            _ = [build for build in jenkins.fetch_from_cache()]


class TestJenkinsCommand(unittest.TestCase):

    @httpretty.activate
    def test_parsing_on_init(self):
        """Test if the class is initialized"""

        args = ['--job-url', JENKINS_JOB_BUILDS_URL,
                '--origin', 'test',
                '--site', JENKINS_SERVER_URL]

        cmd = JenkinsCommand(*args)
        self.assertIsInstance(cmd.parsed_args, argparse.Namespace)
        self.assertEqual(cmd.parsed_args.job_url, JENKINS_JOB_BUILDS_URL)
        self.assertEqual(cmd.parsed_args.site, JENKINS_SERVER_URL)
        self.assertEqual(cmd.parsed_args.origin, 'test')
        self.assertIsInstance(cmd.backend, Jenkins)

    def test_argument_parser(self):
        """Test if it returns a argument parser object"""

        parser = JenkinsCommand.create_argument_parser()
        self.assertIsInstance(parser, argparse.ArgumentParser)


class TestJenkinsClient(unittest.TestCase):
    """Jenkins API client tests

    These tests not check the body of the response, only if the call
    was well formed and if a response was obtained. Due to this, take
    into account that the body returned on each request might not
    match with the parameters from the request.
    """
    @httpretty.activate
    def test_init(self):
        """Test initialization"""
        client = JenkinsClient(JENKINS_SERVER_URL)

    @httpretty.activate
    def test_get_jobs(self):
        """Test get_jobs API call"""

        # Set up a mock HTTP server
        body = read_file('data/jenkins_jobs.json')
        httpretty.register_uri(httpretty.GET,
                               JENKINS_JOBS_URL,
                               body=body, status=200)

        client = JenkinsClient(JENKINS_SERVER_URL)
        response = client.get_jobs()

        self.assertEqual(response, body)

    @httpretty.activate
    def test_get_builds(self):
        """Test get_builds API call"""

        # Set up a mock HTTP server
        body = read_file('data/jenkins_jobs.json')
        httpretty.register_uri(httpretty.GET,
                               JENKINS_JOB_BUILDS_URL,
                               body=body, status=200)

        client = JenkinsClient(JENKINS_SERVER_URL)
        response = client.get_builds(JENKINS_JOB_BUILDS_URL)

        self.assertEqual(response, body)


if __name__ == "__main__":
    unittest.main(warnings='ignore')
