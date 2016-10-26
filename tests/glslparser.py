"""A profile that runs only GLSLParserTest instances."""

from __future__ import (
    absolute_import, division, print_function, unicode_literals
)

from framework.test import GLSLParserTest
from tests.quick import profile as _profile
from tests.quick import make_testlist as _make_testlist

__all__ = [
    'make_testlist',
    'profile',
]

profile = _profile.copy()  # pylint: disable=invalid-name
profile.xml_list_path = 'tests/glslparser.profile.xml'


def make_testlist():
    tests = _make_testlist()
    tests.filters.append(lambda _, t: isinstance(t, GLSLParserTest))
    return tests
