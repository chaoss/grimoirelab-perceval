#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 Bitergia
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
#

import sys
import unittest

if not '..' in sys.path:
    sys.path.insert(0, '..')


from perceval.errors import ParseError
from perceval.backends.git import GitParser


class TestGitParser(unittest.TestCase):
    """Git parser tests"""

    def test_parser(self):
        """Test if it parsers a git log stream"""

        with open("data/git_log.txt", 'r') as f:
            parser = GitParser(f)
            commits = [commit for commit in parser.parse()]

        self.assertEqual(len(commits), 9)

        expected = {
                    'commit' : '456a68ee1407a77f3e804a30dff245bb6c6b872f',
                    'parent' : 'ce8e0b86a1e9877f42fe9453ede418519115f367',
                    'merge' : '51a3b654f252210572297f47597b31527c475fb8',
                    'refs' : 'HEAD -> refs/heads/master',
                    'Merge' : 'ce8e0b8 51a3b65',
                    'Author' : 'Zhongpeng Lin (林中鹏) <lin.zhp@example.com>',
                    'AuthorDate' : 'Tue Feb 11 22:10:39 2014 -0800',
                    'Commit' : 'Zhongpeng Lin (林中鹏) <lin.zhp@example.com>',
                    'CommitDate' : 'Tue Feb 11 22:10:39 2014 -0800',
                    'message' : "Merge branch 'lzp'\n\nConflicts:\n\taaa/otherthing",
                    'files' : [{'file' : "aaa/otherthing.renamed",
                                'added' : '1',
                                'removed' : '0',
                                'oldmode' : '100644',
                                'newmode' : '100644',
                                'mergemode' : '100644',
                                'oldindex' : 'e69de29',
                                'newindex' : '58a6c75',
                                'mergeindex' : '58a6c75',
                                'action' : 'MR'}]
                    }
        self.assertDictEqual(commits[0], expected)

        expected = {
                    'commit' : 'c0d66f92a95e31c77be08dc9d0f11a16715d1885',
                    'parent' : '7debcf8a2f57f86663809c58b5c07a398be7674c',
                    'Author' : 'Eduardo Morais <companheiro.vermelho@example.com>',
                    'AuthorDate' : 'Tue Aug 14 14:35:02 2012 -0300',
                    'Commit' : 'Eduardo Morais <companheiro.vermelho@example.com>',
                    'CommitDate': 'Tue Aug 14 14:35:02 2012 -0300',
                    'message' : 'Deleted and renamed file',
                    'files' : [{'file': 'bbb/bthing',
                                'added': '0',
                                'removed' : '0',
                                'oldmode' : '100644',
                                'newmode' : '000000',
                                'oldindex' : 'e69de29',
                                'newindex' : '0000000',
                                'action' : 'D'},
                                {'file': 'bbb/something',
                                 'newfile' : 'bbb/something.renamed',
                                 'added': '0',
                                 'removed' : '0',
                                 'oldmode' : '100644',
                                 'newmode' : '100644',
                                 'oldindex' : 'e69de29',
                                 'newindex' : 'e69de29',
                                 'action' : 'R100'}
                              ]
                    }
        self.assertDictEqual(commits[5], expected)

    def test_parse_incomplete_log(self):
        """Test if it parsers fails when the log is incompleted"""

        with self.assertRaisesRegex(ParseError, 'unexpected end of log stream'):
            with open("data/git_log_incompleted.txt", 'r') as f:
                parser = GitParser(f)
                _ = [commit for commit in parser.parse()]

    def test_commit_pattern(self):
        """Test commit pattern"""

        pattern = GitParser.GIT_COMMIT_REGEXP

        s = "commit bc57a9209f096a130dcc5ba7089a8663f758a703"
        m = pattern.match(s)
        self.assertEqual(m.group('commit'), "bc57a9209f096a130dcc5ba7089a8663f758a703")

        s = "commit ce8e0b86a1e9877f42fe9453ede418519115f367 589bb080f059834829a2a5955bebfd7c2baa110a"
        m = pattern.match(s)
        self.assertEqual(m.group('commit'), "ce8e0b86a1e9877f42fe9453ede418519115f367")
        self.assertEqual(m.group('parent'), "589bb080f059834829a2a5955bebfd7c2baa110a")

        s = "commit 51a3b654f252210572297f47597b31527c475fb8 589bb080f059834829a2a5955bebfd7c2baa110a (refs/heads/lzp)"
        m = pattern.match(s)
        self.assertEqual(m.group('commit'), "51a3b654f252210572297f47597b31527c475fb8")
        self.assertEqual(m.group('parent'), "589bb080f059834829a2a5955bebfd7c2baa110a")
        self.assertEqual(m.group('refs'), "refs/heads/lzp")

        s = "commit 456a68ee1407a77f3e804a30dff245bb6c6b872f ce8e0b86a1e9877f42fe9453ede418519115f367 51a3b654f252210572297f47597b31527c475fb8 (HEAD -> refs/heads/master)"
        m = pattern.match(s)
        self.assertEqual(m.group('commit'), "456a68ee1407a77f3e804a30dff245bb6c6b872f")
        self.assertEqual(m.group('parent'), "ce8e0b86a1e9877f42fe9453ede418519115f367")
        self.assertEqual(m.group('merge'), "51a3b654f252210572297f47597b31527c475fb8")
        self.assertEqual(m.group('refs'), "HEAD -> refs/heads/master")

    def test_header_pattern(self):
        """Test header pattern"""

        pattern = GitParser.GIT_HEADER_REGEXP

        s = "Merge: ce8e0b8 51a3b65"
        m = pattern.match(s)
        self.assertEqual(m.group('header'), "Merge")
        self.assertEqual(m.group('value'), "ce8e0b8 51a3b65")

        s = "Author:     Eduardo Morais <companheiro.vermelho@example.com>"
        m = pattern.match(s)
        self.assertEqual(m.group('header'), "Author")
        self.assertEqual(m.group('value'), "Eduardo Morais <companheiro.vermelho@example.com>")

        s = "CommitDate: Tue Feb 11 22:07:49 2014 -0800"
        m = pattern.match(s)
        self.assertEqual(m.group('header'), "CommitDate")
        self.assertEqual(m.group('value'), "Tue Feb 11 22:07:49 2014 -0800")

    def test_message_line_pattern(self):
        """Test message line pattern"""

        pattern = GitParser.GIT_MESSAGE_REGEXP

        s = "    \trename aaa/otherthing"
        m = pattern.match(s)
        self.assertEqual(m.group('msg'), "\trename aaa/otherthing")

        s = "    "
        m = pattern.match(s)
        self.assertEqual(m.group('msg'), "")

    def test_action_pattern(self):
        """Test action pattern"""

        pattern = GitParser.GIT_ACTION_REGEXP

        s = ":100644 000000 e69de29... 0000000... D\tbbb/bthing"
        m = pattern.match(s)
        self.assertEqual(m.group('oldmode'), "100644")
        self.assertEqual(m.group('newmode'), "000000")
        self.assertEqual(m.group('oldindex'), "e69de29")
        self.assertEqual(m.group('newindex'), "0000000")
        self.assertEqual(m.group('action'), "D")
        self.assertEqual(m.group('file'), "bbb/bthing")

        s = ":100644 100644 e69de29... e69de29... R100\taaa/otherthing\taaa/otherthing.renamed"
        m = pattern.match(s)
        self.assertEqual(m.group('oldmode'), "100644")
        self.assertEqual(m.group('newmode'), "100644")
        self.assertEqual(m.group('oldindex'), "e69de29")
        self.assertEqual(m.group('newindex'), "e69de29")
        self.assertEqual(m.group('action'), "R100")
        self.assertEqual(m.group('file'), "aaa/otherthing")
        self.assertEqual(m.group('newfile'), "aaa/otherthing.renamed")

    def test_stats_pattern(self):
        """Test stats pattern"""

        pattern = GitParser.GIT_STATS_REGEXP

        s = "8\t7\tperceval/backends/gerrit.py"
        m = pattern.match(s)
        self.assertEqual(m.group('added'), "8")
        self.assertEqual(m.group('removed'), "7")
        self.assertEqual(m.group('file'), "perceval/backends/gerrit.py")

        s = "0\t0\t{aaa => bbb}/something"
        m = pattern.match(s)
        self.assertEqual(m.group('added'), "0")
        self.assertEqual(m.group('removed'), "0")
        self.assertEqual(m.group('file'), "{aaa => bbb}/something")

        s = "1\t0\tbbb/{something => something.renamed}"
        m = pattern.match(s)
        self.assertEqual(m.group('added'), "1")
        self.assertEqual(m.group('removed'), "0")
        self.assertEqual(m.group('file'), "bbb/{something => something.renamed}")

    def test_empty_line(self):
        """Test empty line pattern"""

        pattern = GitParser.GIT_NEXT_STATE_REGEXP

        s = ""
        m = pattern.match(s)
        self.assertIsNotNone(m)


if __name__ == "__main__":
    unittest.main()
