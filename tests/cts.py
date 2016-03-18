# Copyright (c) 2015 Intel Corporation

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

"""Piglit integration for Khronos CTS tests.

By default this will run GLES2, GLES3, GLES31, and GLESEXT test cases. Those
desiring to run only a subset of them should consider using the -t or -x
options to include or exclude tests.

For example:
./piglit run cts -c foo -t ES3- would run only ES3 tests (note the dash to
exclude ES31 tests)

This integration requires some configuration in piglit.conf, or the use of
environment variables.

In piglit.conf one should set the following:
[cts]:bin -- Path to the glcts binary
[cts]:extra_args -- any extra arguments to be passed to cts (optional)

Alternatively (or in addition, since environment variables have precedence),
one could set:
PIGLIT_CTS_BIN -- environment equivalent of [cts]:bin
PIGLIT_CTS_EXTRA_ARGS -- environment equivalent of [cts]:extra_args

"""

from __future__ import (
    absolute_import, division, print_function, unicode_literals
)
import functools

from framework.test import deqp
from framework import profile

__all__ = ['profile']

_CTS_BIN = deqp.get_option('PIGLIT_CTS_BIN', ('cts', 'bin'))

_EXTRA_ARGS = deqp.get_option('PIGLIT_CTS_EXTRA_ARGS', ('cts', 'extra_args'),
                              default='').split()


class _Mixin(object):
    deqp_bin = _CTS_BIN

    @property
    def extra_args(self):
        return super(_Mixin, self).extra_args + \
            [x for x in _EXTRA_ARGS if not x.startswith('--deqp-case')]


class DEQPCTSTest(_Mixin, deqp.DEQPBaseTest):
    """Class for running GLES CTS in test at a time mode."""
    pass


class DEQPCTSGroupTest(_Mixin, deqp.DEQPGroupTest):
    """Class for running GLES CTS in group at a time mode."""
    pass


def _make_profile():
    """Make a single profile for the GLES CTS.

    The GLES CTS is wierd. It's 4 distinct test suites, that need to be run as
    one. The profile mechanism for dEQP integration doesn't really support
    this, so instead what is done is that 4 profiles are created, then merged.

    This can easily be trimmed using the standard test filters from the command
    line.

    """
    partial = functools.partial(deqp.DEQPProfile,
                                single_class=DEQPCTSTest,
                                multi_class=DEQPCTSGroupTest,
                                bin_=_CTS_BIN,
                                extra_args=_EXTRA_ARGS)
    profile_ = partial(filename='ES2-CTS-cases.txt')
    profile_.update(partial(filename='ES3-CTS-cases.txt'))
    profile_.update(partial(filename='ES31-CTS-cases.txt'))
    profile_.update(partial(filename='ESEXT-CTS-cases.txt'))

    return profile_


profile = _make_profile()  # pylint: disable=invalid-name
