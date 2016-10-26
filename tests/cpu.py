"""Profile that removes all CPU based tests.

This profile is the inverse of gpu.py.

It runs GLSLParserTests, asmparsertests, and ARB_vertex_program and
ARB_fragment_program tests only.

Using driver specific overrides these can be forced to run on arbitrary
hardware.

"""

from __future__ import (
    absolute_import, division, print_function, unicode_literals
)

from tests.quick import profile as _profile
from tests.quick import make_testlist as _make_testlist
from framework.test import GLSLParserTest

__all__ = [
    'make_testlist',
    'profile',
]


profile = _profile.copy()  # pylint: disable=invalid-name
profile.xml_list_path = 'tests/cpu.profile.xml'


def make_testlist():
    tests = _make_testlist()

    def filter_gpu(name, test):
        """Remove all tests that are run on the GPU."""
        return (isinstance(test, GLSLParserTest) or
                name.startswith('asmparsertest'))

    # Remove all parser tests, as they are compiler test
    tests.filters.append(filter_gpu)

    return tests
