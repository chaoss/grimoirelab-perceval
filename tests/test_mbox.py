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
#

import sys
import os.path
import shutil
import tempfile
import unittest

import bz2
import gzip

if not '..' in sys.path:
    sys.path.insert(0, '..')

from perceval.utils import check_compressed_file_type
from perceval.backends.mbox import MBox, MBoxArchive, MailingList


class TestBaseMBox(unittest.TestCase):
    """MBox base case class"""

    @classmethod
    def setUpClass(cls):
        cls.tmp_path = tempfile.mkdtemp(prefix='perceval_')

        cls.cfiles = {'bz2' : os.path.join(cls.tmp_path, 'bz2'),
                      'gz'  : os.path.join(cls.tmp_path, 'gz')}

        # Copy compressed files
        for ftype, fname in cls.cfiles.items():
            if ftype == 'bz2':
                mod = bz2
            else:
                mod = gzip

            with open('data/mbox_single.mbox', 'rb') as f_in:
                with mod.open(fname, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)

        # Copy a plain file
        cls.files = {'single'  : os.path.join(cls.tmp_path, 'mbox_single.mbox'),
                     'complex' : os.path.join(cls.tmp_path, 'mbox_complex.mbox')}

        shutil.copy('data/mbox_single.mbox', cls.tmp_path)
        shutil.copy('data/mbox_complex.mbox', cls.tmp_path)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp_path)


class TestMBoxArchive(TestBaseMBox):
    """Tests for MBoxArchive class"""

    def test_filepath(self):
        """Test filepath property"""

        mbox = MBoxArchive(self.cfiles['gz'])
        self.assertEqual(mbox.filepath, self.cfiles['gz'])

    def test_compressed(self):
        """Test compressed properties"""

        mbox = MBoxArchive(self.cfiles['bz2'])
        self.assertEqual(mbox.compressed_type, 'bz2')
        self.assertEqual(mbox.is_compressed(), True)

        mbox = MBoxArchive(self.cfiles['gz'])
        self.assertEqual(mbox.compressed_type, 'gz')
        self.assertEqual(mbox.is_compressed(), True)

    def test_not_compressed(self):
        """Check the properties of a non-compressed archive"""

        mbox = MBoxArchive(self.files['single'])
        self.assertEqual(mbox.compressed_type, None)
        self.assertEqual(mbox.is_compressed(), False)

    def test_container(self):
        """Check the type of the container of an archive"""

        mbox = MBoxArchive(self.cfiles['bz2'])
        container = mbox.container
        self.assertIsInstance(container, bz2.BZ2File)
        container.close()

        mbox = MBoxArchive(self.cfiles['gz'])
        container = mbox.container
        self.assertIsInstance(container, gzip.GzipFile)
        container.close()

        import _io
        mbox = MBoxArchive(self.files['single'])
        container = mbox.container
        self.assertIsInstance(container, _io.BufferedReader)
        container.close()


class TestMailingList(TestBaseMBox):
    """Tests for MailingList class"""

    def test_init(self):
        """Check attributes initialization"""

        mls = MailingList('test', self.tmp_path)

        self.assertEqual(mls.origin, 'test')
        self.assertEqual(mls.dirpath, self.tmp_path)

    def test_mboxes(self):
        """Check whether it gets a list of mboxes"""

        mls = MailingList('test', self.tmp_path)

        mboxes = mls.mboxes
        self.assertEqual(len(mboxes), 4)
        self.assertEqual(mboxes[0].filepath, self.cfiles['bz2'])
        self.assertEqual(mboxes[1].filepath, self.cfiles['gz'])
        self.assertEqual(mboxes[2].filepath, self.files['complex'])
        self.assertEqual(mboxes[3].filepath, self.files['single'])


class TestMBoxBackend(TestBaseMBox):
    """Tests for MBox backend"""

    def test_fetch(self):
        """Test whether it parses a set of mbox files"""

        backend = MBox('http://example.com/', self.tmp_path)
        messages = [m for m in backend.fetch()]

        expected = [('<4CF64D10.9020206@domain.com>', 'Wed, 01 Dec 2010 14:26:40 +0100'),
                    ('<4CF64D10.9020206@domain.com>', 'Wed, 01 Dec 2010 14:26:40 +0100'),
                    ('<BAY12-DAV6Dhd2stb2e0000c0ce@hotmail.com>', 'Wed, 22 Sep 2004 02:03:40 -0700'),
                    ('<87iqzlofqu.fsf@avet.kvota.net>', 'Mon, 17 Mar 2008 10:35:05 +0100'),
                    ('<4CF64D10.9020206@domain.com>', 'Wed, 01 Dec 2010 14:26:40 +0100')]

        self.assertEqual(len(messages), len(expected))

        for x in range(len(messages)):
            message = messages[x]
            self.assertEqual(message['Message-ID'], expected[x][0])
            self.assertEqual(message['__metadata__']['origin'], 'http://example.com/')
            self.assertEqual(message['__metadata__']['updated_on'], expected[x][1])

    def test_parse_mbox(self):
        """Test whether it parses a mbox file"""

        messages = MBox.parse_mbox(self.files['single'])
        result = [msg for msg in messages]

        self.assertEqual(len(result), 1)

        expected = {
                    'From' : 'goran at domain.com ( Göran Lastname )',
                    'Date' : 'Wed, 01 Dec 2010 14:26:40 +0100',
                    'Subject' : '[List-name] Protocol Buffers anyone?',
                    'Message-ID' : '<4CF64D10.9020206@domain.com>',
                    'unixfrom' : 'goran at domain.com  Wed Dec  1 08:26:40 2010',
                    'body': {
                             'plain' : "Hi!\n\nA message in English, with a signature "
                                       "with a different encoding.\n\nregards, G?ran"
                                       "\n\n\n",
                            }
                    }
        self.assertDictEqual(result[0], expected)

    def test_parse_complex_mbox(self):
        """Test whether it parses a complex mbox file"""

        messages = MBox.parse_mbox(self.files['complex'])
        result = [msg for msg in messages]

        self.assertEqual(len(result), 2)

        m0 = result[0]
        self.assertEqual(len(m0.keys()), 34)
        self.assertEqual(m0['Message-ID'], '<BAY12-DAV6Dhd2stb2e0000c0ce@hotmail.com>')
        self.assertEqual(m0['Date'], 'Wed, 22 Sep 2004 02:03:40 -0700')
        self.assertEqual(m0['From'], '"Eugenia Loli-Queru" <eloli@hotmail.com>')
        self.assertEqual(m0['To'], '<language-bindings@gnome.org>, <desktop-devel-list@gnome.org>')
        self.assertEqual(m0['Cc'], None)
        self.assertEqual(m0['Subject'], 'Re: Revisiting the Gnome Bindings')
        self.assertEqual(m0['unixfrom'], 'eloli@hotmail.com  Wed Sep 22 05:05:28 2004')

        expected_body = {
                         'plain' : ">I don't think it's fair to blame the Foundation [...]\n"
                                   ">of packaging since it's really not (just) a case [...]\n"
                                   ">marketing.\n\n"
                                   "No matter what is really to blame, it ultimately [...]\n\n"
                                   "[...]\n\n"
                                   "Rgds,\n"
                                   "Eugenia\n"
                        }
        self.assertDictEqual(m0['body'], expected_body)

        m1 = result[1]
        self.assertEqual(len(m1.keys()), 35)
        self.assertEqual(m1['Message-ID'], '<87iqzlofqu.fsf@avet.kvota.net>')
        self.assertEqual(m1['Date'], 'Mon, 17 Mar 2008 10:35:05 +0100')
        self.assertEqual(m1['From'], 'danilo@gnome.org (Danilo  Šegan )')
        self.assertEqual(m1['To'], 'Simos Xenitellis <simos.lists@googlemail.com>')
        self.assertEqual(m1['Cc'], 'desktop-devel-list@gnome.org, '
                                   '"Nikolay V. Shmyrev" <nshmyrev@yandex.ru>,\n\t'
        	                       'Brian Nitz <Brian.Nitz@sun.com>, '
                                   'Bastien Nocera <hadess@hadess.net>')
        self.assertEqual(m1['Subject'], 'Re: Low memory hacks')
        self.assertEqual(m1['unixfrom'], 'danilo@adsl-236-193.eunet.yu  Mon Mar 17 09:35:25 2008')


if __name__ == "__main__":
    unittest.main()
