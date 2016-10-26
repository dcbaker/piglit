# -*- coding: utf-8 -*-

# quick.tests minus compiler tests.

from __future__ import (
    absolute_import, division, print_function, unicode_literals
)

from tests.quick import profile as _profile
from tests.quick import make_testlist as _make_testlist
from framework.test.glsl_parser_test import GLSLParserTest
from framework.test.piglit_test import ASMParserTest

__all__ = [
    'make_testlist',
    'profile',
]

profile = _profile.copy()  # pylint: disable=invalid-name
profile.xml_list_path = 'tests/gpu.profile.xml'


def make_testlist():
    tests = _make_testlist()

    # Remove all parser tests, as they are compiler test
    tests.filters.append(
        lambda p, t: not isinstance(t, (GLSLParserTest, ASMParserTest)))

    return tests
