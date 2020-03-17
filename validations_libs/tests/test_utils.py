#   Copyright 2020 Red Hat, Inc.
#
#   Licensed under the Apache License, Version 2.0 (the "License"); you may
#   not use this file except in compliance with the License. You may obtain
#   a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#   WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#   License for the specific language governing permissions and limitations
#   under the License.
#

from unittest import mock
from unittest import TestCase

from validations_libs import utils
from validations_libs.tests import fakes


class TestUtils(TestCase):

    def setUp(self):
        super(TestUtils, self).setUp()

    def test_get_validations_data(self):
        res = utils.get_validations_data(fakes.VALIDATIONS_LIST[0])
        self.assertEqual(res, fakes.VALIDATIONS_DATA)

    def test_get_validations_stats(self):
        res = utils.get_validations_stats(fakes.VALIDATIONS_LOGS_CONTENTS_LIST)
        self.assertEqual(res, fakes.VALIDATIONS_STATS)

    @mock.patch('validations_libs.utils.parse_all_validations_on_disk',
                return_value=fakes.VALIDATIONS_LIST)
    def test_get_validations_details(self, mock_parse):
        res = utils.get_validations_details('my_val1')
        self.assertEqual(res, fakes.VALIDATIONS_LIST[0])