#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2015-2018 Bitergia
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
#     Santiago Dueñas <sduenas@bitergia.com>
#     Alvaro del Castillo <acs@bitergia.com>
#

import json
import os
import requests
import time
import unittest

import httpretty
import pkg_resources

pkg_resources.declare_namespace('perceval.backends')

from perceval.backend import BackendCommandArgumentParser
from perceval.backends.core.jenkins import (Jenkins,
                                            JenkinsCommand,
                                            JenkinsClient,
                                            SLEEP_TIME, DETAIL_DEPTH)
from base import TestCaseBackendArchive


JENKINS_SERVER_URL = 'http://example.com/ci'
JENKINS_JOBS_URL = JENKINS_SERVER_URL + '/api/json'
JENKINS_JOB_BUILDS_1 = 'apex-build-brahmaputra'
JENKINS_JOB_BUILDS_2 = 'apex-build-master'
JENKINS_JOB_BUILDS_500_ERROR = '500-error-job'
JENKINS_JOB_BUILDS_JSON_ERROR = 'invalid-json-job'
JENKINS_JOB_BUILDS_URL_1_DEPTH_1 = JENKINS_SERVER_URL + '/job/' + JENKINS_JOB_BUILDS_1 + '/api/json?depth=1'
JENKINS_JOB_BUILDS_URL_2_DEPTH_1 = JENKINS_SERVER_URL + '/job/' + JENKINS_JOB_BUILDS_2 + '/api/json?depth=1'
JENKINS_JOB_BUILDS_URL_500_ERROR_DEPTH_1 = JENKINS_SERVER_URL + '/job/' + JENKINS_JOB_BUILDS_500_ERROR + '/api/json?depth=1'
JENKINS_JOB_BUILDS_URL_JSON_ERROR_DEPTH_1 = JENKINS_SERVER_URL + '/job/' + JENKINS_JOB_BUILDS_JSON_ERROR + '/api/json?depth1'
JENKINS_JOB_BUILDS_URL_1_DEPTH_2 = JENKINS_SERVER_URL + '/job/' + JENKINS_JOB_BUILDS_1 + '/api/json?depth=2'
JENKINS_JOB_BUILDS_URL_2_DEPTH_2 = JENKINS_SERVER_URL + '/job/' + JENKINS_JOB_BUILDS_2 + '/api/json?depth=2'
JENKINS_JOB_BUILDS_URL_500_ERROR_DEPTH_2 = JENKINS_SERVER_URL + '/job/' + JENKINS_JOB_BUILDS_500_ERROR + '/api/json?depth=2'
JENKINS_JOB_BUILDS_URL_JSON_ERROR_DEPTH_2 = JENKINS_SERVER_URL + '/job/' + JENKINS_JOB_BUILDS_JSON_ERROR + '/api/json?depth2'


requests_http = []


def read_file(filename, mode='r'):
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), filename), mode) as f:
        content = f.read()
    return content


def configure_http_server(depth=1):
    bodies_jobs = read_file('data/jenkins/jenkins_jobs.json', mode='rb')
    bodies_builds_job = read_file('data/jenkins/jenkins_job_builds.json')

    def request_callback(method, uri, headers):
        status = 200

        if depth == 2:
            if uri.startswith(JENKINS_JOBS_URL):
                body = bodies_jobs
            elif (uri.startswith(JENKINS_JOB_BUILDS_URL_1_DEPTH_2) or
                  uri.startswith(JENKINS_JOB_BUILDS_URL_2_DEPTH_2)):
                body = bodies_builds_job
            elif uri.startswith(JENKINS_JOB_BUILDS_URL_500_ERROR_DEPTH_2):
                status = 500
                body = '500 Internal Server Error'
            else:
                body = '{'
        else:
            if uri.startswith(JENKINS_JOBS_URL):
                body = bodies_jobs
            elif (uri.startswith(JENKINS_JOB_BUILDS_URL_1_DEPTH_1) or
                  uri.startswith(JENKINS_JOB_BUILDS_URL_2_DEPTH_1)):
                body = bodies_builds_job
            elif uri.startswith(JENKINS_JOB_BUILDS_URL_500_ERROR_DEPTH_1):
                status = 500
                body = '500 Internal Server Error'
            else:
                body = '{'

        requests_http.append(httpretty.last_request())

        return (status, headers, body)

    httpretty.register_uri(httpretty.GET,
                           JENKINS_JOBS_URL,
                           responses=[
                               httpretty.Response(body=request_callback)
                               for _ in range(3)
                           ])
    httpretty.register_uri(httpretty.GET,
                           JENKINS_JOB_BUILDS_URL_1_DEPTH_1,
                           responses=[
                               httpretty.Response(body=request_callback)
                               for _ in range(2)
                           ])
    httpretty.register_uri(httpretty.GET,
                           JENKINS_JOB_BUILDS_URL_2_DEPTH_1,
                           responses=[
                               httpretty.Response(body=request_callback)
                               for _ in range(2)
                           ])
    httpretty.register_uri(httpretty.GET,
                           JENKINS_JOB_BUILDS_URL_500_ERROR_DEPTH_1,
                           responses=[
                               httpretty.Response(body=request_callback)
                           ])
    httpretty.register_uri(httpretty.GET,
                           JENKINS_JOB_BUILDS_URL_JSON_ERROR_DEPTH_1,
                           responses=[
                               httpretty.Response(body=request_callback)
                           ])

    httpretty.register_uri(httpretty.GET,
                           JENKINS_JOBS_URL,
                           responses=[
                               httpretty.Response(body=request_callback)
                               for _ in range(3)
                           ])
    httpretty.register_uri(httpretty.GET,
                           JENKINS_JOB_BUILDS_URL_1_DEPTH_2,
                           responses=[
                               httpretty.Response(body=request_callback)
                               for _ in range(2)
                           ])
    httpretty.register_uri(httpretty.GET,
                           JENKINS_JOB_BUILDS_URL_2_DEPTH_2,
                           responses=[
                               httpretty.Response(body=request_callback)
                               for _ in range(2)
                           ])
    httpretty.register_uri(httpretty.GET,
                           JENKINS_JOB_BUILDS_URL_500_ERROR_DEPTH_2,
                           responses=[
                               httpretty.Response(body=request_callback)
                           ])
    httpretty.register_uri(httpretty.GET,
                           JENKINS_JOB_BUILDS_URL_JSON_ERROR_DEPTH_2,
                           responses=[
                               httpretty.Response(body=request_callback)
                           ])


class TestJenkinsBackend(unittest.TestCase):
    """Jenkins backend tests"""

    def test_initialization(self):
        """Test whether attributes are initializated"""

        jenkins = Jenkins(JENKINS_SERVER_URL, tag='test', sleep_time=60, detail_depth=2)

        self.assertEqual(jenkins.url, JENKINS_SERVER_URL)
        self.assertEqual(jenkins.origin, JENKINS_SERVER_URL)
        self.assertEqual(jenkins.sleep_time, 60)
        self.assertEqual(jenkins.detail_depth, 2)
        self.assertEqual(jenkins.tag, 'test')
        self.assertIsNone(jenkins.client)

        # When tag is empty or None it will be set to
        # the value in url
        jenkins = Jenkins(JENKINS_SERVER_URL)
        self.assertEqual(jenkins.url, JENKINS_SERVER_URL)
        self.assertEqual(jenkins.origin, JENKINS_SERVER_URL)
        self.assertEqual(jenkins.tag, JENKINS_SERVER_URL)
        self.assertEqual(jenkins.sleep_time, SLEEP_TIME)
        self.assertEqual(jenkins.detail_depth, DETAIL_DEPTH)

        jenkins = Jenkins(JENKINS_SERVER_URL, tag='')
        self.assertEqual(jenkins.url, JENKINS_SERVER_URL)
        self.assertEqual(jenkins.origin, JENKINS_SERVER_URL)
        self.assertEqual(jenkins.tag, JENKINS_SERVER_URL)

    def test_has_archiving(self):
        """Test if it returns True when has_archiving is called"""

        self.assertEqual(Jenkins.has_archiving(), True)

    def test_has_resuming(self):
        """Test if it returns False when has_resuming is called"""

        self.assertEqual(Jenkins.has_resuming(), False)

    @httpretty.activate
    def test_fetch_depth_1(self):
        """Test whether a list of builds is returned"""

        configure_http_server()

        # Test fetch builds from jobs list
        jenkins = Jenkins(JENKINS_SERVER_URL)
        builds = [build for build in jenkins.fetch()]
        self.assertEqual(len(builds), 64)

        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "data/jenkins/jenkins_build.json")) \
                as build_json:
            first_build = json.load(build_json)
            self.assertDictEqual(builds[0]['data'], first_build['data'])

        # Test metadata
        expected = [('69fb6b0fe503c59d075d497e2ff37535ccac94b6', 1458874078.582),
                    ('1145170a61c10d1bfc60c3c93c2d800587467b4a', 1458854340.139),
                    ('2d3688b4cac6ad22d4c20223216facfcbc8abb5f', 1458842674.184),
                    ('77a4b72563a212d0950fc48e81471bd03409ec39', 1458831639.674),
                    ('c1110cd988722c124d60f4f234ad1d00ea168286', 1458764722.848),
                    ('88bbd95bf4e07792531760f6ac17711f8e3ade90', 1458740779.456),
                    ('fa6857e34c5fabd929cad0dd736971a676ed2804', 1458687074.485),
                    ('b8d84ea6a2c67c4fccd5cf4473af45909c174731', 1458662464.685),
                    ('c4f3c8c773e8e26eb87b7f5e014768b7977f82e3', 1458596193.695)]

        for x in range(len(expected)):
            build = builds[x]
            self.assertEqual(build['origin'], 'http://example.com/ci')
            self.assertEqual(build['uuid'], expected[x][0])
            self.assertEqual(build['updated_on'], expected[x][1])
            self.assertEqual(build['category'], 'build')
            self.assertEqual(build['tag'], 'http://example.com/ci')

        # Check request params
        expected = {
            'depth': ['1']
        }

        req = httpretty.last_request()

        self.assertEqual(req.method, 'GET')
        self.assertRegex(req.path, '/ci/job')
        self.assertDictEqual(req.querystring, expected)

    @httpretty.activate
    def test_fetch_depth_2(self):
        """Test whether a list of builds is returned"""

        configure_http_server(depth=2)

        # Test fetch builds from jobs list
        jenkins = Jenkins(JENKINS_SERVER_URL, detail_depth=2)
        builds = [build for build in jenkins.fetch()]
        self.assertEqual(len(builds), 64)

        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "data/jenkins/jenkins_build.json")) \
                as build_json:
            first_build = json.load(build_json)
            self.assertDictEqual(builds[0]['data'], first_build['data'])

        # Test metadata
        expected = [('69fb6b0fe503c59d075d497e2ff37535ccac94b6', 1458874078.582),
                    ('1145170a61c10d1bfc60c3c93c2d800587467b4a', 1458854340.139),
                    ('2d3688b4cac6ad22d4c20223216facfcbc8abb5f', 1458842674.184),
                    ('77a4b72563a212d0950fc48e81471bd03409ec39', 1458831639.674),
                    ('c1110cd988722c124d60f4f234ad1d00ea168286', 1458764722.848),
                    ('88bbd95bf4e07792531760f6ac17711f8e3ade90', 1458740779.456),
                    ('fa6857e34c5fabd929cad0dd736971a676ed2804', 1458687074.485),
                    ('b8d84ea6a2c67c4fccd5cf4473af45909c174731', 1458662464.685),
                    ('c4f3c8c773e8e26eb87b7f5e014768b7977f82e3', 1458596193.695)]

        for x in range(len(expected)):
            build = builds[x]
            self.assertEqual(build['origin'], 'http://example.com/ci')
            self.assertEqual(build['uuid'], expected[x][0])
            self.assertEqual(build['updated_on'], expected[x][1])
            self.assertEqual(build['category'], 'build')
            self.assertEqual(build['tag'], 'http://example.com/ci')

        # Check request params
        expected = {
            'depth': ['2']
        }

        req = httpretty.last_request()

        self.assertEqual(req.method, 'GET')
        self.assertRegex(req.path, '/ci/job')
        self.assertDictEqual(req.querystring, expected)

    @httpretty.activate
    def test_fetch_empty(self):
        """Test whether it works when no jobs are fetched"""

        body = '{"jobs":[]}'
        httpretty.register_uri(httpretty.GET,
                               JENKINS_JOBS_URL,
                               body=body, status=200)

        jenkins = Jenkins(JENKINS_SERVER_URL)
        builds = [build for build in jenkins.fetch()]

        self.assertEqual(len(builds), 0)

    @httpretty.activate
    def test_fetch_blacklist(self):
        """Test whether jobs in balcklist are not retrieved"""

        blacklist = [JENKINS_JOB_BUILDS_1]

        configure_http_server()

        jenkins = Jenkins(JENKINS_SERVER_URL, blacklist_jobs=blacklist)
        nrequests = len(requests_http)
        builds = [build for build in jenkins.fetch()]

        # No HTTP calls at all must be done for JENKINS_JOB_BUILDS_1
        # Just the first call for all jobs and one for each job,
        # including those jobs that raise errors
        self.assertEqual(len(requests_http) - nrequests, 4)

        # Builds just from JENKINS_JOB_BUILDS_2
        self.assertEqual(len(builds), 32)


class TestJenkinsBackendArchive(TestCaseBackendArchive):
    """Jenkins backend tests using an archive"""

    def setUp(self):
        super().setUp()
        self.backend_write_archive = Jenkins(JENKINS_SERVER_URL, archive=self.archive)
        self.backend_read_archive = Jenkins(JENKINS_SERVER_URL, archive=self.archive)

    @httpretty.activate
    def test_fetch_from_archive(self):
        """Test whether a list of builds is returned from an archive"""

        configure_http_server()
        self._test_fetch_from_archive()

    @httpretty.activate
    def test_fetch_empty_from_archive(self):
        """Test whether it works when no jobs are fetched from archive"""

        body = '{"jobs":[]}'
        httpretty.register_uri(httpretty.GET,
                               JENKINS_JOBS_URL,
                               body=body, status=200)

        self._test_fetch_from_archive()

    @httpretty.activate
    def test_fetch_blacklist_from_archive(self):
        """Test whether jobs in balcklist are not retrieved from archive"""

        blacklist = [JENKINS_JOB_BUILDS_1]

        configure_http_server()
        self._test_fetch_from_archive()


class TestJenkinsCommand(unittest.TestCase):
    """JenkinsCommand unit tests"""

    def test_backend_class(self):
        """Test if the backend class is Jenkins"""

        self.assertIs(JenkinsCommand.BACKEND, Jenkins)

    def test_setup_cmd_parser(self):
        """Test if it parser object is correctly initialized"""

        parser = JenkinsCommand.setup_cmd_parser()
        self.assertIsInstance(parser, BackendCommandArgumentParser)

        args = ['--tag', 'test', '--no-archive', '--sleep-time', '60',
                '--detail-depth', '2',
                '--blacklist-jobs', '1', '2', '3', '4', '--',
                JENKINS_SERVER_URL]

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.url, JENKINS_SERVER_URL)
        self.assertEqual(parsed_args.tag, 'test')
        self.assertEqual(parsed_args.detail_depth, 2)
        self.assertEqual(parsed_args.sleep_time, 60)
        self.assertEqual(parsed_args.no_archive, True)
        self.assertListEqual(parsed_args.blacklist_jobs, ['1', '2', '3', '4'])


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

        target_sleep_time = 0.1

        client = JenkinsClient(JENKINS_SERVER_URL, sleep_time=target_sleep_time)

        self.assertEqual(client.base_url, JENKINS_SERVER_URL)
        self.assertEqual(client.blacklist_jobs, None)
        self.assertEqual(client.sleep_time, target_sleep_time)

    @httpretty.activate
    def test_http_retry_requests(self):
        """Test whether failed requests are properly handled"""

        httpretty.register_uri(httpretty.GET,
                               JENKINS_JOBS_URL,
                               body="", status=408)

        client = JenkinsClient(JENKINS_SERVER_URL, sleep_time=0.1)

        before = float(time.time())
        expected = before + (client.sleep_time * JenkinsClient.MAX_RETRIES)

        with self.assertRaises(requests.exceptions.RetryError):
            _ = client.get_jobs()

        after = float(time.time())
        self.assertTrue(expected <= after)

    @httpretty.activate
    def test_get_jobs(self):
        """Test get_jobs API call"""

        # Set up a mock HTTP server
        body = read_file('data/jenkins/jenkins_jobs.json')
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
        body = read_file('data/jenkins/jenkins_job_builds.json')
        httpretty.register_uri(httpretty.GET,
                               JENKINS_JOB_BUILDS_URL_1_DEPTH_1,
                               body=body, status=200)

        client = JenkinsClient(JENKINS_SERVER_URL)
        response = client.get_builds(JENKINS_JOB_BUILDS_1)

        self.assertEqual(response, body)

    @httpretty.activate
    def test_connection_error(self):
        """Test that HTTP connection error is correctly handled"""

        # Set up a mock HTTP server
        body = read_file('data/jenkins/jenkins_job_builds.json')
        httpretty.register_uri(httpretty.GET,
                               JENKINS_JOB_BUILDS_URL_1_DEPTH_1,
                               body=body, status=408)

        client = JenkinsClient(JENKINS_SERVER_URL, sleep_time=0.1)

        start = float(time.time())
        expected = start + (sum([i * client.sleep_time for i in range(client.MAX_RETRIES)]))

        with self.assertRaises(requests.exceptions.RequestException):
            _ = client.get_builds(JENKINS_JOB_BUILDS_1)

        end = float(time.time())
        self.assertGreater(end, expected)


if __name__ == "__main__":
    unittest.main(warnings='ignore')
