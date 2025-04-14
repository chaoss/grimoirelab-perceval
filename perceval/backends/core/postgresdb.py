# -*- coding: utf-8 -*-
#
# Copyright (C) 2015-2025 Bitergia
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
#     Ashish Kumar Choubey <contactchoubey@gmail.com>
#

import requests
import os 
import sys
import json
import logging
import psycopg2
import pandas as pd
import time
import random
from ...backend import (Backend, 
                        BackendCommand, 
                        BackendCommandArgumentParser,
                        OriginUniqueField)
from ...errors import BackendError
from ...client import HttpClient
from grimoirelab_toolkit.datetime import datetime_utcnow, str_to_datetime

'''
    This backend is for Postgres Database, feel free to add any number of categories
'''
CATEGORY_PROJECTS = "projects"
CATEGORY_EMPLOYEES = "employees"
CATEGORY_COMPONENTS = "components"

DETAIL_DEPTH = 1
SLEEP_TIME = 10

logger = logging.getLogger(__name__)

class PostgresDB(Backend):
    """
        PostgresDB backend for Perceval

        This class retrieves the builds from Postgres Reporting Database
        To initialize this class, the URL must be provided
        The 'url' will be set as the origin of the data

        :param url: The PostgresDB URL for the database connection.
        :param database: Postgres Reporting Database
        :param user: The username used for database authentication.
        :param password: The password used for database authentication.
        :param sslrootcert: Path to the SSL root certificate file for server validation.
        :param sslcert: Path to the client SSL certificate file for authentication.
        :param sslkey: Path to the SSL private key file for authentication.
        :param sslmode: SSL mode for the connection (e.g., 'require', 'disable', 'verify-full').
        :param from_archive: collect builds already retrieved from an archive
        :param ssl_verify: enable/disable SSL verification
        :param tab : lable used to mark the data
    """
    version = '1.0.0'
    ORIGIN_UNIQUE_FIELD = None
    CATEGORIES = [CATEGORY_COMPONENTS, CATEGORY_EMPLOYEES, CATEGORY_PROJECTS]

    def __init__(self, url, db, passw,
                 usr, 
                 sslrootcert=None,
                 sslcert=None,
                 sslkey=None,
                 api_token=None,
                 sleep_time=SLEEP_TIME, archive=None,
                 detail_depth=DETAIL_DEPTH, tag=None, 
                 blacklist_ids=None, ssl_verify=True, sslmode='disable'):
        
        if not url: 
            msg = "PostgresDB URL required"
            logger.error(msg)
            raise BackendError(cause=msg)
        
        origin = "POSTGRESDB"
        tag = "PostgresDB"
        super().__init__(origin, tag=tag, archive=archive, ssl_verify=ssl_verify)
        self.url = url
        self.database = db 
        self.password = open(passw, 'r').read()
        self.user = usr
        self.sslrootcert = sslrootcert
        self.sslcert = sslcert
        self.sslkey = sslcert
        self.sslmode = sslmode
        self.client = None

    def fetch(self, category=CATEGORY_PROJECTS):
        """
            Fetch the data from the URL
            This method retrieves from URL, the updated data

            :param category: the category of items to fetch

            :returns: a generator of each row of the source table
        """
        kwargs = {}
        items = super().fetch(category, **kwargs)

        return items

    def fetch_items(self, category, **kwargs):
        """
            Fetch contents
            Several categories can be added on requirement basis

            :param category: the category of items to fetch
            :param kwargs: backend arguments

            :returns a generator of items
        """
        logger.info("Looking for projects at url '%s'", self.url)
        if category == CATEGORY_PROJECTS:
            items = self.__get_projects()
            for item in items['projects']:
                yield item
        
        if category == CATEGORY_COMPONENTS:
            items = self.__get_components()
            for item in items['components']:
                yield item
        
        if category == CATEGORY_EMPLOYEES:
            items = self.__get_employees()
            for item in items['employees']:
                yield item
    
    def has_archiving(cls):
        """Returns whether it supports archiving items on the fetch process.

        :returns: this backend does not support items archive
        """
        return False

    @classmethod
    def has_resuming(cls):
        """Returns whether it supports to resume the fetch process.

        :returns: this backend supports items resuming
        """
        return False

    @staticmethod
    def metadata_id(item):
        """Extracts the identifier from different categories for generating UUID"""

        if "project_id" in item:
            return str(item['project_id'])
        
        if "component_id" in item:
            return str(item['component_id'])

        if "employee_id" in item:
            return str(item['employee_id'])
        
    @staticmethod
    def metadata_updated_on(item):
        """Extracts and coverts the update time from a PostgresDB item.

        The timestamp is extracted from timestamp field and converted
        to a UNIX timestamp.

        :param item: item generated by the backend

        :returns: a UNIX timestamp
        """
        if 'created_at' in item:
            return str_to_datetime(item['created_at']).timestamp()
        
        return time.time()
  
    @staticmethod
    def metadata_category(item):
        """
            Extracts the category from an item

            This backend only generates three types of items
            :param item: dict

            :return(str) : category 
        """

        if 'project_id' in item:
            return CATEGORY_PROJECTS
        
        if 'component_id' in item:
            return CATEGORY_COMPONENTS
        
        if 'employee_id' in item:
            return CATEGORY_EMPLOYEES

    def __get_projects(self):
        output = self.client.get_projects()
        return output
    
    def __get_components(self):
        output = self.client.get_components()
        return output
    
    def __get_employees(self):
        output = self.client.get_employees()
        return output

    def _init_client(self, from_archive=False):
        """Init client"""
        return PostgresDBClient(
            self.url, 
            self.database, 
            self.user,
            self.password, 
            self.archive, 
            self.sslrootcert, 
            self.sslcert, 
            self.sslkey, 
            self.sslmode, 
            from_archive, 
            self.ssl_verify
        )


class PostgresDBClient():
    """
    PostgresDBClient to establish a connection with the database and execute queries.

    :param url: The PostgresDB URL for the database connection.
    :param database: Postgres Reporting Database
    :param user: The username used for database authentication.
    :param password: The password used for database authentication.
    :param sslrootcert: Path to the SSL root certificate file for server validation.
    :param sslcert: Path to the client SSL certificate file for authentication.
    :param sslkey: Path to the SSL private key file for authentication.
    :param sslmode: SSL mode for the connection (e.g., 'require', 'disable', 'verify-full').
    :param from_archive: collect builds already retrieved from an archive
    :param ssl_verify: enable/disable SSL verification
    """
    def __init__(self, url, database, user, password, archive, sslrootcert=None, sslcert=None, sslkey=None, 
                 sslmode=None, from_archive=False, ssl_verify=False):
        #connection object
        self.conn = psycopg2.connect(host=url, database=database, password=password, user=user,
                                     sslrootcert=sslrootcert, sslcert=sslcert, sslkey=sslkey, sslmode=sslmode)
        return 
    
    def query_exec(self, query):
        """
            Execute query on DB server
            
            :param query : Valid SQL Query
            :returns : JSON data suitable for parsing
        """
        curr = self.conn.cursor()
        curr.execute(query)
        df = pd.DataFrame(data=curr.fetchall(), columns=[desc[0] for desc in curr.description])
        return json.loads(df.to_json(orient='records', date_format='iso'))
    
    def get_projects(self):
        """
            Retrieve data from project table

            :returns : JSON
        """
        query = """select * from reporting.project"""
        output = self.query_exec(query)
        return {'projects' : output}
    
    def get_employees(self):
        """
            Retrieve employees data for your organization

            :returns : JSON
        """

        query = """select * from reporting.employees"""
        output = self.query_exec(query)
        return {'employees' : output}

    def get_components(self):
        """
            Retrieve data for all components

            :returns : JSON
        """

        query = """select * from reporting.component"""
        output = self.query_exec(query)
        return {'components' : output}

    
class PostgresDBCommand(BackendCommand):
    """Class to run PostgresDB backend from the command line"""
    BACKEND = PostgresDB

    @classmethod
    def setup_cmd_parser(cls):
        """Returns the PostgresDB argument parser."""
        parser = BackendCommandArgumentParser(
            cls.BACKEND,
            token_auth=True,
            archive=True,
            blacklist=False,
            ssl_verify=True
        )

        # PostgresDB options
        group = parser.parser.add_argument_group('PostgresDB arguments')

        # Required arguments
        parser.parser.add_argument(
            '--url',
            help="URL of the PostgresDB server",
            default='<host-url-endpoint>',
            required=False
        )
        #Optional arguments
        parser.parser.add_argument(
            '--db',
            help="Database name on the PostgresDB server", 
            default='<db-name>',
            required=False
        )
        parser.parser.add_argument(
            '--usr',
            help="user name of the PostgresDB server",
            default='<username>',
            required=False
        )
        parser.parser.add_argument(
            '--passw',
            help="location of password file for accessing the PostgresDB server",
            default='<password-file-full-address>',
            required=False
        )

        return parser