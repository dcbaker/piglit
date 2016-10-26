# -*- coding: utf-8 -*-

from __future__ import (
    absolute_import, division, print_function, unicode_literals
)

from framework import grouptools
from framework.test import (GleanTest, PiglitGLTest)
from tests.all import make_testlist as _make_testlist
from tests.all import profile as _profile

__all__ = [
    'make_testlist',
    'profile',
]

# See the note in all.py about this warning
# pylint: disable=bad-continuation

# This is required to get the filters from the other profile.
profile = _profile.copy()  # pylint: disable=invalid-name
profile.xml_list_path = 'tests/quick.profile.xml'

GleanTest.GLOBAL_PARAMS += ["--quick"]


def make_testlist():
    tests = _make_testlist()

    # Set the --quick flag on a few image_load_store_tests
    with tests.group_manager(
            PiglitGLTest,
            grouptools.join('spec', 'arb_shader_image_load_store')) as g:
        with tests.allow_reassignment:
            g(['arb_shader_image_load_store-coherency', '--quick'], 'coherency')
            g(['arb_shader_image_load_store-host-mem-barrier', '--quick'],
              'host-mem-barrier')
            g(['arb_shader_image_load_store-max-size', '--quick'], 'max-size')
            g(['arb_shader_image_load_store-semantics', '--quick'], 'semantics')
            g(['arb_shader_image_load_store-shader-mem-barrier', '--quick'],
              'shader-mem-barrier')

    # Set the --quick flag on the image_size test
    with tests.group_manager(
            PiglitGLTest,
            grouptools.join('spec', 'arb_shader_image_size')) as g:
        with tests.allow_reassignment:
            g(['arb_shader_image_size-builtin', '--quick'], 'builtin')

    # These take too long
    #
    # Put this in here to avoid having the filter run on the XML profile, which
    # has already been filtered.
    tests.filters.append(lambda n, _: '-explosion' not in n)

    return tests
