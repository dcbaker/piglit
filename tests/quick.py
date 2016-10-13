# -*- coding: utf-8 -*-

from __future__ import (
    absolute_import, division, print_function, unicode_literals
)

from framework import grouptools
from framework.test import (GleanTest, PiglitGLTest)
from tests.all import profile as _profile

__all__ = ['profile']

# See the note in all.py about this warning
# pylint: disable=bad-continuation

profile = _profile.copy()  # pylint: disable=invalid-name

GleanTest.GLOBAL_PARAMS += ["--quick"]

# Set the --quick flag on a few image_load_store_tests
with profile.group_manager(
        PiglitGLTest,
        grouptools.join('spec', 'arb_shader_image_load_store')) as g:
    with profile.allow_reassignment:
        g(['arb_shader_image_load_store-coherency', '--quick'], 'coherency')
        g(['arb_shader_image_load_store-host-mem-barrier', '--quick'],
          'host-mem-barrier')
        g(['arb_shader_image_load_store-max-size', '--quick'], 'max-size')
        g(['arb_shader_image_load_store-semantics', '--quick'], 'semantics')
        g(['arb_shader_image_load_store-shader-mem-barrier', '--quick'],
          'shader-mem-barrier')

# Set the --quick flag on the image_size test
with profile.group_manager(
        PiglitGLTest,
        grouptools.join('spec', 'arb_shader_image_size')) as g:
    with profile.allow_reassignment:
        g(['arb_shader_image_size-builtin', '--quick'], 'builtin')

# These take too long
profile.filter_tests(lambda n, _: '-explosion' not in n)
