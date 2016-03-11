# Copyright (c) 2015-2016 Intel Corporation
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""Piglit integrations for dEQP GLES31 tests."""

from __future__ import (
    absolute_import, division, print_function, unicode_literals
)

from framework.test import deqp

__all__ = ['profile']

# Path to the deqp-gles3 executable.
_DEQP_GLES31_BIN = deqp.get_option('PIGLIT_DEQP_GLES31_BIN',
                                   ('deqp-gles31', 'bin'))

_EXTRA_ARGS = deqp.get_option('PIGLIT_DEQP_GLES31_EXTRA_ARGS',
                              ('deqp-gles31', 'extra_args'),
                              default='').split()


class _Mixin(object):
    """Mixin class that provides shared methods for dEQP-GLES31."""
    deqp_bin = _DEQP_GLES31_BIN

    @property
    def extra_args(self):
        return super(DEQPGLES31Test, self).extra_args + \
            [x for x in _EXTRA_ARGS if not x.startswith('--deqp-case')]


class DEQPGLES31Test(_Mixin, deqp.DEQPBaseTest):
    """Class for running dEQP GLES31 in group at a time mode."""
    pass


class DEQPGLES31GroupTest(_Mixin, deqp.DEQPGroupTest):
    """Class for running dEQP GLES31 in group at a time mode."""
    pass


profile = deqp.make_profile(  # pylint: disable=invalid-name
    deqp.iter_deqp_test_cases(
        deqp.gen_caselist_txt(_DEQP_GLES31_BIN, 'dEQP-GLES31-cases.txt',
                              _EXTRA_ARGS)),
    single_class=DEQPGLES31Test, multi_class=DEQPGLES31GroupTest)
