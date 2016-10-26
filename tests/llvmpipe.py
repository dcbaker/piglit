# -*- coding: utf-8 -*-

from __future__ import (
    absolute_import, division, print_function, unicode_literals
)
import platform

from framework.grouptools import join
from tests.quick import profile as _profile
from tests.quick import make_testlist as _make_testlist

__all__ = [
    'make_testlist',
    'profile',
]

profile = _profile.copy()  # pylint: disable=invalid-name
profile.xml_list_path = 'tests/llvmpipe.profile.xml'


def make_testlist():
    tests = _make_testlist()

    # These take too long or too much memory
    tests.filters.append(
        lambda n, _: n.startswith(join('glean', 'pointAtten')))
    tests.filters.append(
        lambda n, _: n.startswith(join('glean', 'texCombine')))
    tests.filters.append(lambda n, _: n.startswith(
        join('spec', '!OpenGL 1.0', 'gl-1.0-blend-func')))
    tests.filters.append(lambda n, _: n.startswith(
        join('spec', '!OpenGL 1.1', 'streaming-texture-leak')))
    tests.filters.append(lambda n, _: n.startswith(
        join('spec', '!OpenGL 1.1', 'max-texture-size')))

    if platform.system() != 'Windows':
        tests.filters.append(lambda n, _: n.startswith(
            join('glx', 'glx-multithread-shader-compile')))

    return tests
