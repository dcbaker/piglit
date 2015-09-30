#!/usr/bin/env python
# coding=utf-8
#
# Copyright © 2014 The Piglit Project
# Copyright © 2015 Intel Corporation
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice (including the next
# paragraph) shall be included in all copies or substantial portions of the
# Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.  IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.

"""Generate tests for tessellation input stages.

Currently test for VS -> TCS and TCS -> TES are generated.

"""

from __future__ import print_function, absolute_import, division
import os
import sys

from six.moves import range  # pylint: disable=redefined-builtin
import numpy as np

from modules.utils import safe_makedirs, lazy_property
from templates import template_dir


_TEMPLATES = template_dir(os.path.basename(os.path.splitext(__file__)[0]))


class TcsTest(object):
    """Test passing variables from the vertex shader to the tessellation
    control shader.

    For every varying type create one tests that passes a scalar of that type
    and one test that passes a two element array. Copy an uniform value to the
    varying in the vertex shader and compare the varying to the same uniform in
    the tessellation control shader. If the values are equal draw the screen
    green, red otherwise.

    Draw four tessellated quads. Each should cover one quarter of the screen.

    """
    TEMPLATE = _TEMPLATES.get_template('tcs.shader_test.mako')

    def __init__(self, type_name, array, name):
        """Creates a test.

        type_name -- varying type to test (e.g.: vec4, mat3x2, int, ...)
        array -- number of array elements to test, None for no array
        name -- name of the variable to test

        """
        self.var_name = name or 'var'

        if self.var_name == 'gl_Position':
            self.var_type = 'vec4'
            self.var_array = None
        elif self.var_name == 'gl_PointSize':
            self.var_type = 'float'
            self.var_array = None
        elif self.var_name == 'gl_ClipDistance':
            self.var_type = 'float'
            self.var_array = 8
        else:
            self.var_type = type_name
            self.var_array = array

        if self.built_in:
            self.interface_name = 'gl_PerVertex'
            self.interface_vs_instance = ''
            self.interface_tcs_instance = 'gl_in'
        else:
            self.interface_name = 'v2tc_interface'
            self.interface_vs_instance = ''
            self.interface_tcs_instance = 'v2tc'

        if self.var_array:
            self.var_type_full = self.var_type + '[{0}]'.format(self.var_array)
        else:
            self.var_type_full = self.var_type

    @property
    def built_in(self):
        return self.var_name.startswith('gl_')

    @property
    def vs_var_ref(self):
        return '.' + self.var_name if self.interface_vs_instance else self.var_name

    @property
    def tcs_var_ref(self):
        return '.' + self.var_name if self.interface_tcs_instance else self.var_name

    def components(self):
        """Returns the number of scalar components of the used data type."""
        n = 1

        if self.var_type.startswith('mat'):
            if 'x' in self.var_type:
                n *= int(self.var_type[-1])
                n *= int(self.var_type[-3])
            else:
                n *= int(self.var_type[-1])
                n *= int(self.var_type[-1])
        elif 'vec' in self.var_type:
            n *= int(self.var_type[-1])

        return n

    @lazy_property
    def test_data(self):
        """Returns random but deterministic data as a list of strings.

        n strings are returned containing c random values, each.
        Where n is the number of vertices times the array length and
        c is the number of components in the tested scalar data type.
        """
        np.random.seed(17)

        if self.var_array:
            n = self.var_array * 12
        else:
            n = 12

        if self.var_type.startswith('i'):
            rand = lambda: np.random.randint(-0x80000000, 0x7fffffff)
        elif self.var_type.startswith('u'):
            rand = lambda: np.random.randint(0, 0xffffffff)
        else:
            rand = lambda: (np.int_(np.random.choice((-1, 1))) *
                            np.random.randint(0, 2**23-1) *
                            np.float_(2.0)**(np.random.randint(-126, 127)))

        c = self.components()

        ret = []
        for _ in range(n):
            ret.append(" ".join(str(rand()) for _ in range(c)))

        return ret

    def filename(self):
        """Returns the file name (including path) for the test."""
        if self.built_in:
            name = self.var_name
        elif self.var_array:
            name = self.var_type + '_{0}'.format(self.var_array)
        else:
            name = self.var_type
        return os.path.join('spec',
                            'arb_tessellation_shader',
                            'execution',
                            'tcs-input',
                            'tcs-input-{0}.shader_test'.format(name))

    def generate(self):
        """Generates and writes the test to disc."""
        filename = self.filename()
        dirname = os.path.dirname(filename)
        safe_makedirs(dirname)
        with open(filename, 'w') as f:
            f.write(self.TEMPLATE.render_unicode(
                params=self, generator_command=" ".join(sys.argv)))


class TesTest(object):
    """Test passing variables from the tessellation control shader to the
    tessellation evaluation shader.

    For every combination of varying type as scalar and as two element array
    and per-vertex or per-patch varying create a test that that passes said
    variable between the tessellation shader stages.  Copy a uniform value to
    the varying in the tessellation control shader and compare the varying to
    the same uniform in the tessellation evaluation shader. If the values are
    equal draw the screen green, red otherwise.

    Draw four tessellated quads. Each should cover one quarter of the screen.

    """
    TEMPLATE = _TEMPLATES.get_template('tes.shader_test.mako')

    def __init__(self, type_name, array, patch_in, name):
        """Creates a test.

        type_name -- varying type to test (e.g.: vec4, mat3x2, int, ...)
        array -- number of array elements to test, None for no array
        patch_in -- true for per-patch varying, false for per-vertex varying
        name -- name of the variable to test

        """
        self.var_name = name or 'var'
        self.use_block = 0 if patch_in else 1

        if self.var_name == 'gl_Position':
            self.var_type = 'vec4'
            self.var_array = None
            self.patch_in = False
        elif self.var_name == 'gl_PointSize':
            self.var_type = 'float'
            self.var_array = None
            self.patch_in = False
        elif self.var_name == 'gl_ClipDistance':
            self.var_type = 'float'
            self.var_array = 8
            self.patch_in = False
        else:
            self.var_type = type_name
            self.var_array = array
            self.patch_in = patch_in

        if self.built_in:
            self.interface_name = 'gl_PerVertex'
            self.interface_tcs_instance = 'gl_out'
            self.interface_tes_instance = 'gl_in'
        else:
            self.interface_name = 'tc2te_interface'
            self.interface_tcs_instance = '' if self.patch_in else 'tc2te'
            self.interface_tes_instance = '' if self.patch_in else 'tc2te'

        if self.var_array:
            self.var_type_full = self.var_type + '[{0}]'.format(self.var_array)
        else:
            self.var_type_full = self.var_type

        if self.patch_in:
            self.interface_prefix = 'patch '
            self.interface_postfix = ''
        else:
            self.interface_prefix = ''
            self.interface_postfix = '[]'

    @property
    def built_in(self):
        return self.var_name.startswith('gl_')

    @property
    def tcs_var_ref(self):
        return '[gl_InvocationID].' + self.var_name if self.interface_tcs_instance else self.var_name

    @property
    def tes_var_ref(self):
        return '[i].' + self.var_name if self.interface_tes_instance else self.var_name

    @property
    def tcs_reference_index(self):
        return 'gl_PrimitiveID' if self.patch_in else 'gl_PrimitiveID * vertices_in + gl_InvocationID'

    @property
    def tes_reference_index(self):
        return 'gl_PrimitiveID' if self.patch_in else 'gl_PrimitiveID * vertices_in + i'

    @property
    def reference_size(self):
        return 4 if self.patch_in else 12

    def components(self):
        """Returns the number of scalar components of the used data type."""
        n = 1

        if self.var_type.startswith('mat'):
            if 'x' in self.var_type:
                n *= int(self.var_type[-1])
                n *= int(self.var_type[-3])
            else:
                n *= int(self.var_type[-1])
                n *= int(self.var_type[-1])
        elif 'vec' in self.var_type:
            n *= int(self.var_type[-1])

        return n

    @lazy_property
    def test_data(self):
        """Returns random but deterministic data as a list of strings.

        n strings are returned containing c random values, each.
        Where n is the number of vertices times the array length and
        c is the number of components in the tested scalar data type.
        """
        np.random.seed(17)

        if self.var_array:
            n = self.var_array * self.reference_size
        else:
            n = self.reference_size

        if self.var_type.startswith('i'):
            rand = lambda: np.random.randint(-0x80000000, 0x7fffffff)
        elif self.var_type.startswith('u'):
            rand = lambda: np.random.randint(0, 0xffffffff)
        else:
            rand = lambda: (np.int_(np.random.choice((-1, 1))) *
                            np.random.randint(0, 2**23-1) *
                            np.float_(2.0)**(np.random.randint(-126, 127)))

        c = self.components()

        ret = []
        for _ in range(n):
            ret.append(" ".join(str(rand()) for _ in range(c)))

        return ret

    def filename(self):
        """Returns the file name (including path) for the test."""
        if self.built_in:
            name = self.var_name
        elif self.var_array:
            name = self.var_type + '_{0}'.format(self.var_array)
        else:
            name = self.var_type
        if self.patch_in:
            name = 'patch-' + name
        return os.path.join('spec',
                            'arb_tessellation_shader',
                            'execution',
                            'tes-input',
                            'tes-input-{0}.shader_test'.format(name))

    def generate(self):
        """Generates and writes the test to disc."""
        filename = self.filename()
        dirname = os.path.dirname(filename)
        safe_makedirs(dirname)
        with open(filename, 'w') as f:
            f.write(self.TEMPLATE.render_unicode(
                params=self, generator_command=" ".join(sys.argv)))


def all_tests():
    """Generator yield test instances."""
    for type_name in ['float', 'vec2', 'vec3', 'vec4',
                      'mat2', 'mat3', 'mat4',
                      'mat2x3', 'mat2x4', 'mat3x2',
                      'mat3x4', 'mat4x2', 'mat4x3',
                      'int', 'ivec2', 'ivec3', 'ivec4',
                      'uint', 'uvec2', 'uvec3', 'uvec4']:
        for array in [None, 2]:
            for patch_in in [True, False]:
                yield TesTest(type_name, array, patch_in, name=None)
            yield TcsTest(type_name, array, name=None)
    for var in ['gl_Position', 'gl_PointSize', 'gl_ClipDistance']:
        yield TesTest(type_name=None, array=None, patch_in=False, name=var)
        yield TcsTest(type_name=None, array=None, name=var)


def main():
    for test in all_tests():
        test.generate()
        print(test.filename())


if __name__ == '__main__':
    main()
