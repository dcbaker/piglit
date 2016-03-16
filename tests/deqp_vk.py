# Copyright 2014-2016 Intel Corporation
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

"""Piglit integrations for the official Khronos Vulkan CTS.

upstream: https://github.com/KhronosGroup/Vulkan-CTS

"""

from __future__ import (
    absolute_import, division, print_function, unicode_literals
)
import re

from framework.test import deqp

__all__ = ['profile']

# Path to the deqp-gles3 executable.
_DEQP_VK_BIN = deqp.get_option('PIGLIT_DEQP_VK_BIN',
                               ('deqp-vk', 'bin'))

_EXTRA_ARGS = deqp.get_option('PIGLIT_DEQP_VK_EXTRA_ARGS',
                              ('deqp-vk', 'extra_args'),
                              default='').split()

_DEQP_ASSERT = re.compile(
    r'deqp-vk: external/vulkancts/.*: Assertion `.*\' failed.')


class _Mixin(object):
    """Mixin class that provides shared methods for dEQP-VK."""
    deqp_bin = _DEQP_VK_BIN
    @property
    def extra_args(self):
        return super(_Mixin, self).extra_args + \
            [x for x in _EXTRA_ARGS if not x.startswith('--deqp-case')]


class DEQPVKTest(_Mixin, deqp.DEQPBaseTest):
    """Test representation for Khronos Vulkan CTS."""
    timeout = 60

    def interpret_result(self):
        if 'Failed to compile shader at vkGlslToSpirV' in self.result.out:
            self.result.result = 'skip'
            self.result.out += \
                '\n\nMarked as skip because GLSLang failed to compile shaders'
        elif _DEQP_ASSERT.search(self.result.err):
            self.result.result = 'skip'
            self.result.out += \
                '\n\nMarked as skip because of a internal dEQP assertion'
        else:
            super(DEQPVKTest, self).interpret_result()


class DEQPVKGroupTest(_Mixin, deqp.DEQPGroupTest):
    """Test representation for Khronos Vulkacn CTS in group mode."""
    def interpret_result(self):
        # If there are either of the know result problems add all subcases to
        # the rerun list.
        if 'Failed to compile shader at vkGlslToSpirV' in self.result.out:
            self.rerun.extend(self._individual_cases)
        elif _DEQP_ASSERT.search(self.result.err):
            self.rerun.extend(self._individual_cases)
        else:
            super(DEQPVKGroupTest, self).interpret_result()


profile = deqp.DEQPProfile(  # pylint: disable=invalid-name
    single_class=DEQPVKTest,
    multi_class=DEQPVKGroupTest,
    bin_=_DEQP_VK_BIN,
    filename='dEQP-VK-cases.txt',
    extra_args=_EXTRA_ARGS)
