#
# Minimal tests to check whether the installation is working
#

from __future__ import (
    absolute_import, division, print_function, unicode_literals
)

from framework import grouptools
from framework.profile import XMLProfile, TestDict
from framework.test import PiglitGLTest

__all__ = [
    'make_testlist',
    'profile',
]


def make_testlist():
    tests = TestDict()
    with tests.group_manager(
            PiglitGLTest,
            grouptools.join('spec', '!OpenGL 1.0')) as g:
        g(['gl-1.0-readpixsanity'], run_concurrent=True)

    return tests


profile = XMLProfile('tests/sanity.profile.xml')
