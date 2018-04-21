# -*- coding: utf-8 -*- the Graal backend.
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
#     Valerio Cosentino <valcos@bitergia.com>
#

import warnings

import lizard

from perceval.backends.analyzers.analyzer import Analyzer


class Lizard(Analyzer):
    """A wrapper for Lizard, a code complexity analyzer, which is able
    to handle many imperative programming languages such as:
        C/C++ (works with C++14)
        Java
        C# (C Sharp)
        JavaScript
        Objective C
        Swift
        Python
        Ruby
        TTCN-3
        PHP
        Scala
        GDScript
    """

    def analyze(self, **kwargs):
        """Add code complexity information using Lizard.

        Current information includes cyclomatic complexity (ccn),
        avg lines of code and tokens, number of functions and tokens.
        Optionally, the following information can be included for every function:
        ccn, tokens, LOC, lines, name, args, start, end

        :param file_path: file path
        :param result: dict of the results of the analysis
        """
        result = {}
        file_path = kwargs['file_path']
        functions = kwargs['functions']

        with warnings.catch_warnings():
            warnings.simplefilter('ignore', DeprecationWarning)
            analysis = lizard.analyze_file(file_path)

        result['ccn'] = analysis.CCN
        result['avg_ccn'] = analysis.average_cyclomatic_complexity
        result['avg_loc'] = analysis.average_nloc
        result['avg_tokens'] = analysis.average_token_count
        result['funs'] = len(analysis.function_list)
        result['loc'] = analysis.nloc
        result['tokens'] = analysis.token_count

        if not functions:
            return result

        funs_data = []
        for fun in analysis.function_list:
            fun_data = {'ccn': fun.cyclomatic_complexity,
                        'tokens': fun.token_count,
                        'loc': fun.nloc,
                        'lines': fun.length,
                        'name': fun.name,
                        'args': fun.parameter_count,
                        'start': fun.start_line,
                        'end': fun.end_line}
            funs_data.append(fun_data)

        result['funs_data'] = funs_data
        return result
