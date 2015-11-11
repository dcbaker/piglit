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

"""Profile that generates random UBO tests.

This profile is very special, as is it's Test class. Basically the test_list
attribute is a generator, which when iterated over will create a new test. If
the test fails, then it will add the test to the results output.

"""

from __future__ import absolute_import, division, print_function
import tempfile
import random
import os

from framework.profile import FuzzerProfile
from framework.test.shader_test import ShaderTest
from .fuzzers.random_ubo import gen

__all__ = ['profile']

# XXX: It might make sense in the future to make these sharable
_EXTENSIONS = [
    'GL_ARB_uniform_buffer_object',
    'GL_ARB_gpu_shader_fp64',
    'GL_ARB_arrays_of_arrays',
]
_VERSIONS = [130, 140, 150, 400, 430]


class FuzzerShaderTest(ShaderTest):
    # TODO: it's actually probably possible to get the requirements out of the
    # generator, and not have to parse this at all

    # On Unix a NamedTemporaryFile can be opened multiple times, but that isn't
    # true on NT
    def __init__(self, contents):
        with tempfile.NamedTemporaryFile() as f:
            f.write(contents)
            f.seek(0)
            super(FuzzerShaderTest, self).__init__(f.name)

        self.result.test = contents
        self.__contents = contents

    @ShaderTest.command.getter
    def command(self):
        """Generate a tempoarary file for the tet command."""
        super_ = super(FuzzerShaderTest, self).command
        temp = tempfile.NamedTemporaryFile(delete=False)
        temp.write(self.__contents)
        temp.seek(0)
        super_[1] = temp.name
        return super_

    def _run_command(self):
        try:
            super(FuzzerShaderTest, self)._run_command()
        finally:
            os.unlink(self.command[1])


def make_args():
    return (random.choice(_VERSIONS),
            random.sample(_EXTENSIONS, random.randint(0, len(_EXTENSIONS))))


profile = FuzzerProfile(gen, make_args, FuzzerShaderTest)
