#!/usr/bin/env python3
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
#     Santiago Dueñas <sduenas@bitergia.com>
#     Stephan Barth <stephan.barth@gmail.com>
#     Valerio Cosentino <valcos@bitergia.com>
#     Miguel Ángel Fernández <mafesan@bitergia.com>
#     Harshal Mittal <harshalmittal4@gmail.com>
#

import bz2
import datetime
import gzip
import os
import shutil
import tempfile
import unittest
import unittest.mock
import zipfile

from perceval.backend import BackendCommandArgumentParser
from perceval.utils import DEFAULT_DATETIME
from perceval.backends.core.mbox import (logger,
                                         MBox,
                                         MBoxCommand,
                                         MBoxArchive,
                                         MailingList)


class TestBaseMBox(unittest.TestCase):
    """MBox base case class"""

    @classmethod
    def setUpClass(cls):
        cls.tmp_path = tempfile.mkdtemp(prefix='perceval_')

        cls.cfiles = {
            'bz2': os.path.join(cls.tmp_path, 'bz2'),
            'gz': os.path.join(cls.tmp_path, 'gz'),
            'zip': os.path.join(cls.tmp_path, 'zip')
        }

        # Copy compressed files
        for ftype, fname in cls.cfiles.items():
            if ftype == 'bz2':
                mod = bz2
            elif ftype == 'gz':
                mod = gzip
            else:
                mod = zipfile

            if mod == zipfile:
                with zipfile.ZipFile(fname, 'w') as f_out:
                    f_out.write(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                             'data/mbox/mbox_single.mbox'))
            else:
                with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                       'data/mbox/mbox_single.mbox'), 'rb') as f_in:
                    with mod.open(fname, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)

        # Copy a plain file
        cls.files = {
            'single': os.path.join(cls.tmp_path, 'mbox_single.mbox'),
            'complex': os.path.join(cls.tmp_path, 'mbox_complex.mbox'),
            'multipart': os.path.join(cls.tmp_path, 'mbox_multipart.mbox'),
            'unixfrom': os.path.join(cls.tmp_path, 'mbox_unixfrom_encoding.mbox'),
            'unknown': os.path.join(cls.tmp_path, 'mbox_unknown_encoding.mbox'),
            'iso8859': os.path.join(cls.tmp_path, 'mbox_iso8859_encoding.mbox')
        }

        shutil.copy(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data/mbox/mbox_single.mbox'),
                    cls.tmp_path)
        shutil.copy(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data/mbox/mbox_complex.mbox'),
                    cls.tmp_path)
        shutil.copy(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data/mbox/mbox_multipart.mbox'),
                    cls.tmp_path)
        shutil.copy(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data/mbox/mbox_unixfrom_encoding.mbox'),
                    cls.tmp_path)
        shutil.copy(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data/mbox/mbox_unknown_encoding.mbox'),
                    cls.tmp_path)
        shutil.copy(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data/mbox/mbox_iso8859_encoding.mbox'),
                    cls.tmp_path)

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

        mbox = MBoxArchive(self.cfiles['zip'])
        self.assertEqual(mbox.compressed_type, 'zip')
        self.assertEqual(mbox.is_compressed(), True)

    def test_not_compressed(self):
        """Check the properties of a non-compressed archive"""

        mbox = MBoxArchive(self.files['single'])
        self.assertEqual(mbox.compressed_type, None)
        self.assertEqual(mbox.is_compressed(), False)

    def test_container(self):
        """Check the type of the container of an archive"""

        import _io
        mbox = MBoxArchive(self.files['single'])
        container = mbox.container
        self.assertIsInstance(container, _io.BufferedReader)
        container.close()

    def test_container_bz2(self):
        """Check the type bz2 of the container of an archive"""

        mbox = MBoxArchive(self.cfiles['bz2'])
        container = mbox.container
        self.assertIsInstance(container, bz2.BZ2File)
        container.close()

    def test_container_gz(self):
        """Check the type gz of the container of an archive"""

        mbox = MBoxArchive(self.cfiles['gz'])
        container = mbox.container
        self.assertIsInstance(container, gzip.GzipFile)
        container.close()

    def test_container_zip(self):
        """Check the type zip of the container of an archive"""

        mbox = MBoxArchive(self.cfiles['zip'])
        container = mbox.container
        self.assertIsInstance(container, zipfile.ZipExtFile)
        container.close()

        with zipfile.ZipFile(self.cfiles['zip'], 'w') as f_out:
            f_out.write(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data/mbox/mbox_single.mbox'))
            f_out.write(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data/mbox/mbox_no_fields.mbox'))

        mbox = MBoxArchive(self.cfiles['zip'])
        with self.assertLogs(logger, level='ERROR') as cm:
            container = mbox.container
            container.close()
            self.assertEqual(cm.output[0], 'ERROR:perceval.backends.core.mbox:Zip %s contains more than one file, '
                                           'only the first uncompressed' % mbox.filepath)


class TestMailingList(TestBaseMBox):
    """Tests for MailingList class"""

    def test_init(self):
        """Check attributes initialization"""

        mls = MailingList('test', self.tmp_path)

        self.assertEqual(mls.uri, 'test')
        self.assertEqual(mls.dirpath, self.tmp_path)

    def test_mboxes(self):
        """Check whether it gets a list of mboxes sorted by name"""

        mls = MailingList('test', self.tmp_path)

        mboxes = mls.mboxes
        self.assertEqual(len(mboxes), 9)
        self.assertEqual(mboxes[0].filepath, self.cfiles['bz2'])
        self.assertEqual(mboxes[1].filepath, self.cfiles['gz'])
        self.assertEqual(mboxes[2].filepath, self.files['complex'])
        self.assertEqual(mboxes[3].filepath, self.files['iso8859'])
        self.assertEqual(mboxes[4].filepath, self.files['multipart'])
        self.assertEqual(mboxes[5].filepath, self.files['single'])
        self.assertEqual(mboxes[6].filepath, self.files['unixfrom'])
        self.assertEqual(mboxes[7].filepath, self.files['unknown'])
        self.assertEqual(mboxes[8].filepath, self.cfiles['zip'])

    @unittest.mock.patch('perceval.backends.core.mbox.check_compressed_file_type')
    def test_mboxes_error(self, mock_check_compressed_file_type):
        """Check whether OSError exceptions are properly handled"""

        mock_check_compressed_file_type.side_effect = OSError

        mls = MailingList('test', self.tmp_path)
        with self.assertLogs(logger, level='WARNING') as cm:
            _ = mls.mboxes
            self.assertEqual(cm.output[-1], 'WARNING:perceval.backends.core.mbox:'
                                            'Ignoring zip mbox due to: ')


class TestMBoxBackend(TestBaseMBox):
    """Tests for MBox backend"""

    def setUp(self):
        self.tmp_error_path = tempfile.mkdtemp(prefix='perceval_')
        shutil.copy(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data/mbox/mbox_no_fields.mbox'),
                    self.tmp_error_path)

    def tearDown(self):
        shutil.rmtree(self.tmp_error_path)

    def test_initialization(self):
        """Test whether attributes are initializated"""

        backend = MBox('http://example.com/', self.tmp_path, tag='test')

        self.assertEqual(backend.uri, 'http://example.com/')
        self.assertEqual(backend.dirpath, self.tmp_path)
        self.assertEqual(backend.origin, 'http://example.com/')
        self.assertEqual(backend.tag, 'test')
        self.assertTrue(backend.ssl_verify)

        # When origin is empty or None it will be set to
        # the value in uri
        backend = MBox('http://example.com/', self.tmp_path)
        self.assertEqual(backend.origin, 'http://example.com/')
        self.assertEqual(backend.tag, 'http://example.com/')

        backend = MBox('http://example.com/', self.tmp_path, tag='', ssl_verify=False)
        self.assertEqual(backend.origin, 'http://example.com/')
        self.assertEqual(backend.tag, 'http://example.com/')
        self.assertFalse(backend.ssl_verify)

    def test_has_archiving(self):
        """Test if it returns False when has_archiving is called"""

        self.assertEqual(MBox.has_archiving(), False)

    def test_has_resuming(self):
        """Test if it returns True when has_resuming is called"""

        self.assertEqual(MBox.has_resuming(), True)

    def test_fetch(self):
        """Test whether it parses a set of mbox files"""

        backend = MBox('http://example.com/', self.tmp_path)
        messages = [m for m in backend.fetch(from_date=None)]

        expected = [
            ('<4CF64D10.9020206@domain.com>', '86315b479b4debe320b59c881c1e375216cbf333', 1291210000.0),
            ('<4CF64D10.9020206@domain.com>', '86315b479b4debe320b59c881c1e375216cbf333', 1291210000.0),
            ('<BAY12-DAV6Dhd2stb2e0000c0ce@hotmail.com>', 'bd0185317b013beb21ad3ea04635de3db72496ad', 1095843820.0),
            ('<87iqzlofqu.fsf@avet.kvota.net>', '51535703010a3e63d5272202942c283394cdebca', 1205746505.0),
            ('<4fce8064d819e07fd80267aaecaf30ef@www.platvoet.de>', 'b25134a09996f33e94b2e191a2f9f379b11168ac', 1478544267.0),
            ('<019801ca633f$f4376140$dca623c0$@yang@example.com>', '302e314c07242bb4750351286862f49e758f3e17', 1257992964.0),
            ('<FB0C1D9DAED2D411BB990002A52C30EC03838593@example.com>', 'ddda42422c55d08d56c017a6f128fcd7447484ea', 1043881350.0),
            ('<4CF64D10.9020206@domain.com>', '86315b479b4debe320b59c881c1e375216cbf333', 1291210000.0),
            ('<20150115132225.GA22378@example.org>', 'ad3116ae93c0df50436f7c84bfc94000e990996c', 1421328145.0),
            ('<20020823171132.541DB44147@example.com>', '4e255acab6442424ecbf05cb0feb1eccb587f7de', 1030123489.0),
            ('<4CF64D10.9020206@domain.com>', '86315b479b4debe320b59c881c1e375216cbf333', 1291210000.0)
        ]

        self.assertEqual(len(messages), len(expected))

        for x in range(len(messages)):
            message = messages[x]
            self.assertEqual(message['data']['Message-ID'], expected[x][0])
            self.assertEqual(message['origin'], 'http://example.com/')
            self.assertEqual(message['uuid'], expected[x][1])
            self.assertEqual(message['updated_on'], expected[x][2])
            self.assertEqual(message['category'], 'message')
            self.assertEqual(message['tag'], 'http://example.com/')

    def test_search_fields(self):
        """Test whether the search_fields is properly set"""

        backend = MBox('http://example.com/', self.tmp_path)
        messages = [m for m in backend.fetch(from_date=None)]

        for message in messages:
            self.assertEqual(backend.metadata_id(message['data']), message['search_fields']['item_id'])

    def test_fetch_from_date(self):
        """Test whether a list of messages is returned since a given date"""

        from_date = datetime.datetime(2008, 1, 1)

        backend = MBox('http://example.com/', self.tmp_path)
        messages = [m for m in backend.fetch(from_date=from_date)]

        expected = [
            ('<4CF64D10.9020206@domain.com>', '86315b479b4debe320b59c881c1e375216cbf333', 1291210000.0),
            ('<4CF64D10.9020206@domain.com>', '86315b479b4debe320b59c881c1e375216cbf333', 1291210000.0),
            ('<87iqzlofqu.fsf@avet.kvota.net>', '51535703010a3e63d5272202942c283394cdebca', 1205746505.0),
            ('<4fce8064d819e07fd80267aaecaf30ef@www.platvoet.de>', 'b25134a09996f33e94b2e191a2f9f379b11168ac', 1478544267.0),
            ('<019801ca633f$f4376140$dca623c0$@yang@example.com>', '302e314c07242bb4750351286862f49e758f3e17', 1257992964.0),
            ('<4CF64D10.9020206@domain.com>', '86315b479b4debe320b59c881c1e375216cbf333', 1291210000.0),
            ('<20150115132225.GA22378@example.org>', 'ad3116ae93c0df50436f7c84bfc94000e990996c', 1421328145.0),
            ('<4CF64D10.9020206@domain.com>', '86315b479b4debe320b59c881c1e375216cbf333', 1291210000.0)
        ]

        self.assertEqual(len(messages), len(expected))

        for x in range(len(messages)):
            message = messages[x]
            self.assertEqual(message['data']['Message-ID'], expected[x][0])
            self.assertEqual(message['origin'], 'http://example.com/')
            self.assertEqual(message['uuid'], expected[x][1])
            self.assertEqual(message['updated_on'], expected[x][2])
            self.assertEqual(message['category'], 'message')
            self.assertEqual(message['tag'], 'http://example.com/')

    def test_fetch_to_date(self):
        """Test whether a list of messages is returned to a given date"""

        to_date = datetime.datetime(2008, 1, 1)

        backend = MBox('http://example.com/', self.tmp_path)
        messages = [m for m in backend.fetch(to_date=to_date)]

        expected = [
            ('<BAY12-DAV6Dhd2stb2e0000c0ce@hotmail.com>', 'bd0185317b013beb21ad3ea04635de3db72496ad', 1095843820.0),
            ('<FB0C1D9DAED2D411BB990002A52C30EC03838593@example.com>', 'ddda42422c55d08d56c017a6f128fcd7447484ea', 1043881350.0),
            ('<20020823171132.541DB44147@example.com>', '4e255acab6442424ecbf05cb0feb1eccb587f7de', 1030123489.0)
        ]

        self.assertEqual(len(messages), len(expected))

        for x in range(len(messages)):
            message = messages[x]
            self.assertEqual(message['data']['Message-ID'], expected[x][0])
            self.assertEqual(message['origin'], 'http://example.com/')
            self.assertEqual(message['uuid'], expected[x][1])
            self.assertEqual(message['updated_on'], expected[x][2])
            self.assertEqual(message['category'], 'message')
            self.assertEqual(message['tag'], 'http://example.com/')

    @unittest.mock.patch('perceval.backends.core.mbox.str_to_datetime')
    def test_fetch_exception(self, mock_str_to_datetime):
        """Test whether an exception is thrown when the the fetch_items method fails"""

        mock_str_to_datetime.side_effect = Exception

        backend = MBox('http://example.com/', self.tmp_path)

        with self.assertRaises(Exception):
            _ = [m for m in backend.fetch(from_date=None)]

    def test_ignore_messages(self):
        """Test if it ignores some messages without mandatory fields"""

        backend = MBox('http://example.com/', self.tmp_error_path)
        messages = [m for m in backend.fetch()]

        # There are only two valid message on the mbox
        self.assertEqual(len(messages), 2)

        expected = {
            'From': 'goran at domain.com ( Göran Lastname )',
            'Date': 'Wed, 01 Dec 2010 14:26:40 +0100',
            'Subject': '[List-name] Protocol Buffers anyone?',
            'Message-ID': '<4CF64D10.9020206@domain.com>',
            'unixfrom': 'goran at domain.com  Wed Dec  1 08:26:40 2010',
            'body': {
                'plain': "Hi!\n\nA message in English, with a signature "
                         "with a different encoding.\n\nregards, G?ran"
                         "\n",
            }
        }

        message = messages[0]['data']
        self.assertDictEqual(message, expected)

        # On the second message, the only change is that 'Message-id'
        # is replaced by 'Message-ID'
        message = messages[1]['data']
        self.assertDictEqual(message, expected)

    def test_ignore_file_errors(self):
        """Files with IO errors should be ignored"""

        tmp_path_ign = tempfile.mkdtemp(prefix='perceval_')

        def copy_mbox_side_effect(*args, **kwargs):
            """Copy a mbox archive or raise IO error for 'mbox_multipart.mbox' archive"""

            error_file = os.path.join(tmp_path_ign, 'mbox_multipart.mbox')
            mbox = args[0]

            if mbox.filepath == error_file:
                raise OSError('Mock error')

            tmp_path = tempfile.mktemp(prefix='perceval_')

            with mbox.container as f_in:
                with open(tmp_path, mode='wb') as f_out:
                    for line in f_in:
                        f_out.write(line)
            return tmp_path

        shutil.copy(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data/mbox/mbox_single.mbox'),
                    tmp_path_ign)
        shutil.copy(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data/mbox/mbox_multipart.mbox'),
                    tmp_path_ign)

        # Mock 'copy_mbox' method for forcing to raise an OSError
        # with file 'data/mbox/mbox_multipart.mbox' to check if
        # the code ignores this file
        with unittest.mock.patch('perceval.backends.core.mbox.MBox._copy_mbox') as mock_copy_mbox:
            mock_copy_mbox.side_effect = copy_mbox_side_effect

            backend = MBox('http://example.com/', tmp_path_ign)
            messages = [m for m in backend.fetch()]

            # Only one message is read
            self.assertEqual(len(messages), 1)
            self.assertEqual(messages[0]['data']['Message-ID'], '<4CF64D10.9020206@domain.com>')
            self.assertEqual(messages[0]['data']['Date'], 'Wed, 01 Dec 2010 14:26:40 +0100')

        shutil.rmtree(tmp_path_ign)

    def test_parse_mbox(self):
        """Test whether it parses a mbox file"""

        messages = MBox.parse_mbox(self.files['single'])
        result = [msg for msg in messages]

        self.assertEqual(len(result), 1)

        message = {k: v for k, v in result[0].items()}

        expected = {
            'From': 'goran at domain.com ( Göran Lastname )',
            'Date': 'Wed, 01 Dec 2010 14:26:40 +0100',
            'Subject': '[List-name] Protocol Buffers anyone?',
            'Message-ID': '<4CF64D10.9020206@domain.com>',
            'unixfrom': 'goran at domain.com  Wed Dec  1 08:26:40 2010',
            'body': {
                'plain': "Hi!\n\nA message in English, with a signature "
                         "with a different encoding.\n\nregards, G?ran"
                         "\n\n\n",
            }
        }

        self.assertDictEqual(message, expected)

    def test_parse_complex_mbox(self):
        """Test whether it parses a complex mbox file"""

        messages = MBox.parse_mbox(self.files['complex'])
        result = [msg for msg in messages]

        self.assertEqual(len(result), 2)

        m0 = {k: v for k, v in result[0].items()}
        self.assertEqual(len(m0.keys()), 34)
        self.assertEqual(m0['Message-ID'], '<BAY12-DAV6Dhd2stb2e0000c0ce@hotmail.com>')
        self.assertEqual(m0['Date'], 'Wed, 22 Sep 2004 02:03:40 -0700')
        self.assertEqual(m0['From'], '"Eugenia Loli-Queru" <eloli@hotmail.com>')
        self.assertEqual(m0['To'], '<language-bindings@gnome.org>, <desktop-devel-list@gnome.org>')
        self.assertEqual(m0['Cc'], None)
        self.assertEqual(m0['Subject'], 'Re: Revisiting the Gnome Bindings')
        self.assertEqual(m0['unixfrom'], 'eloli@hotmail.com  Wed Sep 22 05:05:28 2004')

        expected_body = {
            'plain': ">I don't think it's fair to blame the Foundation [...]\n"
                     ">of packaging since it's really not (just) a case [...]\n"
                     ">marketing.\n\n"
                     "No matter what is really to blame, it ultimately [...]\n\n"
                     "[...]\n\n"
                     "Rgds,\n"
                     "Eugenia\n"
        }
        self.assertDictEqual(m0['body'], expected_body)

        m1 = {k: v for k, v in result[1].items()}
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

    def test_parse_multipart_mbox(self):
        """Test if it parses a message with a multipart body"""

        messages = MBox.parse_mbox(self.files['multipart'])
        result = [msg for msg in messages]

        self.assertEqual(len(result), 2)

        # Multipart message
        plain_body = result[0]['body']['plain']
        html_body = result[0]['body']['html']
        self.assertEqual(plain_body, 'technology.esl Committers,\n\n'
                                     'This automatically generated message marks the successful completion of\n'
                                     'voting for Chuwei Huang to receive full Committer status on the\n'
                                     'technology.esl project. The next step is for the PMC to approve this vote,\n'
                                     'followed by the EMO processing the paperwork and provisioning the account.\n\n\n\n'
                                     'Vote summary: 4/0/0 with 0 not voting\n\n'
                                     '  +1  Thomas Guiu\n\n'
                                     '  +1  Jin Liu\n\n'
                                     '  +1  Yves YANG\n\n'
                                     '  +1  Bo Zhou\n\n\n\n'
                                     'If you have any questions, please do not hesitate to contact your project\n'
                                     'lead, PMC member, or the EMO <emo@example.org>\n\n\n\n\n\n')
        self.assertEqual(len(html_body), 3103)

        # Multipart message without defined encoding
        plain_body = result[1]['body']['plain']
        html_body = result[1]['body']['html']
        self.assertEqual(plain_body, 'I am fairly new to eclipse. I am evaluating the use of eclipse for a generic\n'
                                     'UI framework that is not necessarily related to code generation.\n'
                                     'Eclipse is very flexible and adding functionality seems straightforward. I\n'
                                     'can still use the project concept for what I need but there are things in\n'
                                     'the Workbench window that I don\'t want. For example the Open perspective\n'
                                     'icon, or some of the menus, like the Windows and project menu .\n\n'
                                     'I understand that by using retargetable actions I can have my view taking\n'
                                     'over most of the actions, but I could not figure out how to block the core\n'
                                     'plug-in to put their own actions. In the workbench plug-in (org.eclipse.ui)\n'
                                     'I could not find where menus are defined and where actionsviews for all\n'
                                     'generic toolbars are defined.\n\nHow do I do this?\nCan this be done?\n'
                                     'Is anybody using eclipse as a generic UI framework?\n\nI appreciate any help.\n\n'
                                     'Thanks,\n\nDaniel Nehren\n\n')
        self.assertEqual(len(html_body), 1557)

    def test_parse_unixfrom_decoding_error(self):
        """Check whether it parses a mbox thatn contains encoding errors on its from header"""

        messages = MBox.parse_mbox(self.files['unixfrom'])
        result = [msg for msg in messages]

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['unixfrom'],
                         "christian at “example.org”  Thu Jan 15 13:22:25 2015")

    def test_parse_unknown_encoding_mbox(self):
        """Check whether it parses a mbox that contains an unknown encoding"""

        messages = MBox.parse_mbox(self.files['unknown'])
        result = [msg for msg in messages]

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['From'],
                         '"\udcc3\udc94\udcc2\udcac\udcc2\udcb4\udcc3\udc8f" <yuancong@example.com>')

    def test_parse_iso8859_encoding_mbox(self):
        """Check whether no execption is raisen when parsing a mbox that contains a iso 8859 encoding"""

        messages = MBox.parse_mbox(self.files['iso8859'])
        _ = [msg for msg in messages]


class TestMBoxCommand(unittest.TestCase):
    """MBoxCommand unit tests"""

    def test_backend_class(self):
        """Test if the backend class is MBox"""

        self.assertIs(MBoxCommand.BACKEND, MBox)

    def test_setup_cmd_parser(self):
        """Test if it parser object is correctly initialized"""

        parser = MBoxCommand.setup_cmd_parser()
        self.assertIsInstance(parser, BackendCommandArgumentParser)
        self.assertEqual(parser._backend, MBox)

        args = ['http://example.com/', '/tmp/perceval/',
                '--tag', 'test',
                '--from-date', '1970-01-01']

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.uri, 'http://example.com/')
        self.assertEqual(parsed_args.dirpath, '/tmp/perceval/')
        self.assertEqual(parsed_args.tag, 'test')
        self.assertEqual(parsed_args.from_date, DEFAULT_DATETIME)
        self.assertTrue(parsed_args.ssl_verify)

        args = ['http://example.com/', '/tmp/perceval/',
                '--tag', 'test',
                '--from-date', '1970-01-01',
                '--no-ssl-verify']

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.uri, 'http://example.com/')
        self.assertEqual(parsed_args.dirpath, '/tmp/perceval/')
        self.assertEqual(parsed_args.tag, 'test')
        self.assertEqual(parsed_args.from_date, DEFAULT_DATETIME)
        self.assertFalse(parsed_args.ssl_verify)


if __name__ == "__main__":
    unittest.main()
