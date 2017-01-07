# encoding=utf-8
# Copyright © 2017 Intel Corporation

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""Tests for the framework.backend.abstract module."""

from __future__ import (
    absolute_import, division, print_function, unicode_literals
)

try:
    from unittest import mock
except ImportError:
    import mock
import pytest
import six

from framework import results
from framework import grouptools
from framework.backends import abstract


# pylint: disable=invalid-name,no-self-use,protected-access


class Test_ExpectedStatus(object):

    @pytest.fixture(scope='class')
    def func(self):
        return abstract._ExpectedStatus()

    class TestResult(object):

        @pytest.yield_fixture(scope='module', autouse=True)
        def mock_config(self):
            """Mock the expected-failures and expected-crashes values."""
            vals = {
                'expected-crashes': {'foo': None},
                'expected-failures': {'bar': None}
            }

            def _items(name):
                return six.iteritems(vals[name])

            with mock.patch('framework.backends.abstract.PIGLIT_CONFIG.items',
                            _items):
                yield

        @pytest.mark.parametrize('input_, expected', [
            ('pass', 'pass'),
            ('fail', 'fail'),
            ('crash', 'crash'),
            ('warn', 'warn'),
            ('skip', 'skip'),
            ('timeout', 'timeout'),
            ('dmesg-fail', 'dmesg-fail'),
            ('dmesg-warn', 'dmesg-warn'),
        ])
        def test_not_expected(self, input_, expected, func):
            result = results.TestResult(input_)
            func('oof', result)
            assert result.result == expected

        @pytest.mark.parametrize('input_, expected', [
            ('pass', 'fail'),
            ('fail', 'expected-fail'),
            ('crash', 'fail'),
            ('warn', 'expected-fail'),
            ('skip', 'skip'),
            ('dmesg-fail', 'expected-fail'),
            ('dmesg-warn', 'expected-fail'),
            ('timeout', 'fail'),
        ])
        def test_expected_failure(self, input_, expected, func):
            result = results.TestResult(input_)
            func('bar', result)
            assert result.result == expected

        @pytest.mark.parametrize('input_, expected', [
            ('pass', 'fail'),
            ('fail', 'fail'),
            ('crash', 'expected-crash'),
            ('warn', 'fail'),
            ('skip', 'skip'),
            ('dmesg-fail', 'fail'),
            ('dmesg-warn', 'fail'),
            ('timeout', 'expected-crash'),
        ])
        def test_expected_crash(self, input_, expected, func):
            result = results.TestResult(input_)
            func('foo', result)
            assert result.result == expected

    class TestSubtest(object):

        @pytest.yield_fixture(scope='module', autouse=True)
        def mock_config(self):
            """Mock the expected-failures and expected-crashes values."""
            vals = {
                'expected-crashes': {grouptools.join('group', 'foo'): None},
                'expected-failures': {grouptools.join('group', 'bar'): None}
            }

            def _items(name):
                return six.iteritems(vals[name])

            with mock.patch('framework.backends.abstract.PIGLIT_CONFIG.items',
                            _items):
                yield

        @pytest.mark.parametrize('input_, expected', [
            ('pass', 'pass'),
            ('fail', 'fail'),
            ('crash', 'crash'),
            ('warn', 'warn'),
            ('skip', 'skip'),
            ('timeout', 'timeout'),
            ('dmesg-fail', 'dmesg-fail'),
            ('dmesg-warn', 'dmesg-warn'),
        ])
        def test_not_expected(self, input_, expected, func):
            result = results.TestResult()
            result.subtests['oink'] = input_
            func('group', result)
            assert result.subtests['oink'] == expected

        @pytest.mark.parametrize('input_, expected', [
            ('pass', 'fail'),
            ('fail', 'expected-fail'),
            ('crash', 'fail'),
            ('warn', 'expected-fail'),
            ('skip', 'skip'),
            ('dmesg-fail', 'expected-fail'),
            ('dmesg-warn', 'expected-fail'),
            ('timeout', 'fail'),
        ])
        def test_expected_failure(self, input_, expected, func):
            result = results.TestResult()
            result.subtests['bar'] = input_
            func('group', result)
            assert result.subtests['bar'] == expected

        @pytest.mark.parametrize('input_, expected', [
            ('pass', 'fail'),
            ('fail', 'fail'),
            ('crash', 'expected-crash'),
            ('warn', 'fail'),
            ('skip', 'skip'),
            ('dmesg-fail', 'fail'),
            ('dmesg-warn', 'fail'),
            ('timeout', 'expected-crash'),
        ])
        def test_expected_crash(self, input_, expected, func):
            result = results.TestResult()
            result.subtests['foo'] = input_
            func('group', result)
            assert result.subtests['foo'] == expected

    class TestJUnitEscaped(object):

        @pytest.yield_fixture(scope='module', autouse=True)
        def mock_config(self):
            """Mock the expected-failures and expected-crashes values."""
            vals = {
                'expected-crashes': {'foo.bar': None},
                'expected-failures': {},
            }

            def _items(name):
                return six.iteritems(vals[name])

            with mock.patch('framework.backends.abstract.PIGLIT_CONFIG.items',
                            _items):
                yield

        @pytest.yield_fixture(scope='module', autouse=True)
        def mock_escaped(self):
            with mock.patch('framework.backends.abstract.PIGLIT_CONFIG.safe_get',
                            lambda *_: True):
                yield

        def test_not_expected(self, func):
            result = results.TestResult('crash')
            func(grouptools.join('foo', 'bar'), result)
            assert result.result == 'expected-crash'
