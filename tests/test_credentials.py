#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (C) GrimoireLab Contributors
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

import sys
import types
import unittest
import unittest.mock

from perceval.credentials import (build_credential_manager,
                                  normalize_credentials)


LIST_FIELDS = ('api_token',)


class TestBuildCredentialManager(unittest.TestCase):
    """Unit tests for build_credential_manager"""

    @unittest.mock.patch('grimoirelab_toolkit.credential_manager.bw_manager.BitwardenManager')
    def test_bitwarden(self, mock_bw):
        """Test whether a Bitwarden manager is built"""

        manager = build_credential_manager('bitwarden',
                                           bw_client_id='cid',
                                           bw_client_secret='csecret',
                                           bw_master_password='mpass',
                                           vault_url='http://vault')

        self.assertEqual(manager, mock_bw.return_value)
        mock_bw.assert_called_once_with('cid', 'csecret', 'mpass')

    def test_hashicorp(self):
        """Test whether a HashiCorp Vault manager is built"""

        # hvac is an optional dependency, so the module is replaced
        hc_module = types.ModuleType('grimoirelab_toolkit.credential_manager.hc_manager')
        hc_module.HashicorpManager = unittest.mock.MagicMock()

        with unittest.mock.patch.dict(sys.modules,
                                      {hc_module.__name__: hc_module}):
            manager = build_credential_manager('hashicorp',
                                               vault_url='http://vault',
                                               vault_token='token',
                                               vault_certificate='/ca.crt')

        self.assertEqual(manager, hc_module.HashicorpManager.return_value)
        hc_module.HashicorpManager.assert_called_once_with('http://vault', 'token', '/ca.crt')

    def test_bitwarden_missing_parameters(self):
        """Test whether it fails when Bitwarden parameters are missing"""

        with self.assertRaisesRegex(ValueError, 'Bitwarden requires'):
            build_credential_manager('bitwarden',
                                     bw_client_id='cid',
                                     bw_client_secret='csecret')

    def test_hashicorp_missing_parameters(self):
        """Test whether it fails when HashiCorp Vault parameters are missing"""

        with self.assertRaisesRegex(ValueError, 'HashiCorp Vault requires'):
            build_credential_manager('hashicorp', vault_url='http://vault')

    def test_unsupported_manager(self):
        """Test whether it fails with an unknown type of manager"""

        with self.assertRaisesRegex(ValueError, "Unsupported secrets manager: 'keepass'"):
            build_credential_manager('keepass')


class TestNormalizeCredentials(unittest.TestCase):
    """Unit tests for normalize_credentials"""

    def test_single_values(self):
        """Test whether single values are not modified"""

        credentials = {
            'user': 'alice',
            'password': 'pass,with\ncommas',
            'api_token': 'tok1'
        }

        result = normalize_credentials(credentials)
        self.assertDictEqual(result, credentials)

    def test_single_value_from_list(self):
        """Test whether a list with one element is converted to that element"""

        result = normalize_credentials({'api_token': ['tok1']})
        self.assertDictEqual(result, {'api_token': 'tok1'})

    def test_multiple_values_for_single_value_field(self):
        """Test whether it fails when a single value field has several values"""

        with self.assertRaisesRegex(ValueError, "'api_token' must have a single value"):
            normalize_credentials({'api_token': ['tok1', 'tok2']})

    def test_list_from_string(self):
        """Test whether a string is converted to a list"""

        credentials = {
            'user': 'alice',
            'api_token': ' tok1,tok2\ntok3,\n'
        }

        result = normalize_credentials(credentials, list_fields=LIST_FIELDS)
        self.assertDictEqual(result, {
            'user': 'alice',
            'api_token': ['tok1', 'tok2', 'tok3']
        })

    def test_list_from_single_value(self):
        """Test whether a single value is converted to a list of one element"""

        result = normalize_credentials({'api_token': 'tok1'}, list_fields=LIST_FIELDS)
        self.assertDictEqual(result, {'api_token': ['tok1']})

    def test_list_from_list(self):
        """Test whether a list is kept as a list"""

        result = normalize_credentials({'api_token': ['tok1', ' tok2 ', '']},
                                       list_fields=LIST_FIELDS)
        self.assertDictEqual(result, {'api_token': ['tok1', 'tok2']})

    def test_input_not_modified(self):
        """Test whether the given credentials are not modified"""

        credentials = {'api_token': 'tok1,tok2'}

        normalize_credentials(credentials, list_fields=LIST_FIELDS)
        self.assertDictEqual(credentials, {'api_token': 'tok1,tok2'})

    def test_single_value_not_stripped(self):
        """Test whether spaces around a single value are kept"""

        result = normalize_credentials({'password': ' my pass '})
        self.assertDictEqual(result, {'password': ' my pass '})

    def test_empty_list_field(self):
        """Test whether it fails when a list field is empty"""

        for value in ['', '   ', ' , ', []]:
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "'api_token' is empty"):
                    normalize_credentials({'api_token': value}, list_fields=LIST_FIELDS)

    def test_empty_single_value_field(self):
        """Test whether it fails when a single value field is empty"""

        for value in ['', '   ', [], ['', ' ']]:
            with self.subTest(value=value):
                with self.assertRaises(ValueError) as ctx:
                    normalize_credentials({'api_token': value})

                self.assertIn("'api_token' is empty", str(ctx.exception))
                self.assertNotIn("multiple", str(ctx.exception))

    def test_numbers_converted_to_strings(self):
        """Test whether numbers are converted to strings"""

        result = normalize_credentials({'api_token': 12345}, list_fields=LIST_FIELDS)
        self.assertDictEqual(result, {'api_token': ['12345']})

        result = normalize_credentials({'api_token': 12345})
        self.assertDictEqual(result, {'api_token': '12345'})

        result = normalize_credentials({'user_id': 42})
        self.assertDictEqual(result, {'user_id': '42'})

        result = normalize_credentials({'user_id': [42]})
        self.assertDictEqual(result, {'user_id': '42'})

    def test_numbers_in_list_converted_to_strings(self):
        """Test whether numbers in a list are converted to strings"""

        result = normalize_credentials({'api_token': ['a', 1]}, list_fields=LIST_FIELDS)
        self.assertDictEqual(result, {'api_token': ['a', '1']})

    def test_invalid_values(self):
        """Test whether it fails when a value is not a string or a number"""

        for value in [True, {'k': 'v'}, [None]]:
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "'api_token' has an invalid value"):
                    normalize_credentials({'api_token': value}, list_fields=LIST_FIELDS)

                with self.assertRaisesRegex(ValueError, "'api_token' has an invalid value"):
                    normalize_credentials({'api_token': value})


if __name__ == "__main__":
    unittest.main(warnings='ignore')
