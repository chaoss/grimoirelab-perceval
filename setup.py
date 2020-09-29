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
#     Quan Zhou <quan@bitergia.com>
#

import codecs
import os.path
import sys
import unittest

from setuptools import setup
from setuptools.command.test import test as TestClass


here = os.path.abspath(os.path.dirname(__file__))
readme_md = os.path.join(here, 'README.md')

# Get the package description from the README.md file
with codecs.open(readme_md, encoding='utf-8') as f:
    long_description = f.read()


version = '0.1'


class TestCommand(TestClass):
    user_options = []
    __dir__ = os.path.dirname(os.path.realpath(__file__))

    def initialize_options(self):
        super().initialize_options()
        sys.path.insert(0, os.path.join(self.__dir__, 'tests'))

    def run_tests(self):
        test_suite = unittest.TestLoader().discover('.', pattern='test_*.py')
        result = unittest.TextTestRunner(buffer=True).run(test_suite)
        sys.exit(not result.wasSuccessful())


cmdclass = {'test': TestCommand}

setup(name="perceval-weblate",
      description="Bundle of Perceval backends for Weblate",
      long_description=long_description,
      long_description_content_type='text/markdown',
      url="https://github.com/Bitergia/grimoirelab-perceval-weblate",
      version=version,
      author="Bitergia",
      author_email="quan@bitergia.com",
      license="GPLv3",
      classifiers=[
          'Development Status :: 5 - Production/Stable',
          'Intended Audience :: Developers',
          'Topic :: Software Development',
          'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
          'Programming Language :: Python :: 3'
      ],
      keywords="development repositories analytics weblate",
      packages=[
          'perceval',
          'perceval.backends',
          'perceval.backends.weblate'
      ],
      namespace_packages=[
          'perceval',
          'perceval.backends'
      ],
      setup_requires=[
          'wheel',
          'pandoc'
      ],
      tests_require=[
          'httpretty==0.9.6'
      ],
      install_requires=[
          'requests>=2.7.0',
          'grimoirelab-toolkit>=0.1.12',
          'perceval>=0.17.1'
      ],
      cmdclass=cmdclass,
      zip_safe=False)
