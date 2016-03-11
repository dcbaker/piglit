# Copyright (c) 2015-2016 Intel Corporation

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

"""Tests for the dEQP integration in framework.

This tests the core framework shared code, and not the individual packages in
tests

"""

from __future__ import (
    absolute_import, division, print_function, unicode_literals
)
import sys
import textwrap

import nose.tools as nt

# There is a bug in mock < 1.2 or python 3.4 that we'd like to avoid, otherwise
# some tests will skip.
if sys.version_info[0:2] >= (3, 4):
    from unittest import mock
else:
    try:
        import mock
    except ImportError:
        from unittest import mock

from framework import profile, grouptools, exceptions
from framework.test import deqp
from . import utils

# pylint:disable=line-too-long,invalid-name,protected-access

doc_formatter = utils.DocFormatter({'separator': grouptools.SEPARATOR})


class _DEQPTestTest(deqp.DEQPBaseTest):
    deqp_bin = 'deqp.bin'
    extra_args = ['extra']


class _DEQPGroupTest(deqp.DEQPGroupTest):
    deqp_bin = 'deqp.bin'
    extra_args = ['extra']


@utils.set_piglit_conf(('deqp_test', 'test_env', 'from conf'))
@utils.set_env(_PIGLIT_TEST_ENV='from env')
def test_get_option_env():
    """deqp.get_option: if env is set it overrides piglit.conf"""
    nt.eq_(deqp.get_option('_PIGLIT_TEST_ENV', ('deqp_test', 'test_env')),
           'from env')


@utils.set_piglit_conf(('deqp_test', 'test_env', 'from conf'))
@utils.set_env(_PIGLIT_TEST_ENV=None)
def test_get_option_conf():
    """deqp.get_option: if env is not set a value is taken from piglit.conf"""
    nt.eq_(deqp.get_option('_PIGLIT_TEST_ENV', ('deqp_test', 'test_env')),
           'from conf')


@utils.set_env(_PIGLIT_TEST_ENV=None)
def test_get_option_default():
    """deqp.get_option: default value is returned when env and conf are unset
    """
    nt.eq_(deqp.get_option('_PIGLIT_TEST_ENV', ('deqp_test', 'test_env'),
                           'foobar'),
           'foobar')


@utils.set_env(_PIGLIT_TEST_ENV=None)
def test_get_option_conf_no_section():
    """deqp.get_option: if a no_section error is raised and env is unset None is return
    """
    nt.eq_(deqp.get_option('_PIGLIT_TEST_ENV', ('deqp_test', 'test_env')), None)


# The first argument ensures the sectio exists
@utils.set_piglit_conf(('deqp_test', 'test_env', 'from conf'),
                       ('deqp_test', 'not_exists', None))
@utils.set_env(_PIGLIT_TEST_ENV=None)
def test_get_option_conf_no_option():
    """deqp.get_option: if a no_option error is raised and env is unset None is return
    """
    nt.eq_(deqp.get_option('_PIGLIT_TEST_ENV', ('deqp_test', 'not_exists')),
           None)


class TestMakeProfile(object):
    """Test deqp.make_profile."""
    @classmethod
    def setup_class(cls):
        cls.profile = deqp.make_profile(['this.is.a.deqp.test'], _DEQPTestTest)

    def test_returns_profile(self):
        """deqp.make_profile: returns a TestProfile"""
        nt.assert_is_instance(self.profile, profile.TestProfile)

    @doc_formatter
    def test_grouptools(self):
        """deqp.make_profile: replaces '.' with '{separator}'"""
        nt.assert_in(grouptools.join('this', 'is', 'a', 'deqp', 'test'),
                     self.profile.test_list)


def test_iter_deqp_test_cases_test():
    """deqp.iter_deqp_test_cases: correctly detects a TEST: line"""
    with utils.tempfile('TEST: a.deqp.test') as tfile:
        gen = deqp.iter_deqp_test_cases(tfile)
        nt.eq_('a.deqp.test', next(gen))


def test_iter_deqp_test_cases_group():
    """deqp.iter_deqp_test_casesgen_caselist_txt: correctly detects a GROUP: line"""
    with utils.tempfile('GROUP: a group\nTEST: a.deqp.test') as tfile:
        gen = deqp.iter_deqp_test_cases(tfile)
        nt.eq_('a.deqp.test', next(gen))


@nt.raises(exceptions.PiglitFatalError)
def test_iter_deqp_test_cases_bad():
    """deqp.iter_deqp_test_casesgen_caselist_txt: PiglitFatalException is raised if line is not TEST: or GROUP:
    """
    with utils.tempfile('this will fail') as tfile:
        gen = deqp.iter_deqp_test_cases(tfile)
        nt.eq_('a.deqp.test', next(gen))


@utils.no_error
def test_DEQPBaseTest_initialize():
    """deqp.DEQPBaseTest: can be initialized (with abstract methods overwritten)
    """
    _DEQPTestTest('a.deqp.test')


def test_DEQPBaseTest_command():
    """deqp.DEQPBaseTest.command: cls.extra_args are added to self.command"""
    test = _DEQPTestTest('a.deqp.test')
    nt.eq_(test.command[-1], 'extra')


class TestDEQPBaseTestInterpretResult(object):
    """Tests for DEQPBaseTest.interpret_result.

    This specifically tests the part that searches stdout.

    """
    def __init__(self):
        self.test = None

    def setup(self):
        self.test = _DEQPTestTest('a.deqp.test')

    def test_crash(self):
        """deqp.DEQPBaseTest.interpret_result: if returncode is < 0 stauts is crash"""
        self.test.result.returncode = -9
        self.test.interpret_result()
        nt.eq_(self.test.result.result, 'crash')

    def test_returncode_fail(self):
        """deqp.DEQPBaseTest.interpret_result: if returncode is > 0 result is fail"""
        self.test.result.returncode = 1
        self.test.interpret_result()
        nt.eq_(self.test.result.result, 'fail')

    def test_fallthrough(self):
        """deqp.DEQPBaseTest.interpret_result: if no case is hit set to fail"""
        self.test.result.returncode = 0
        self.test.result.out = ''
        self.test.interpret_result()
        nt.eq_(self.test.result.result, 'fail')

    def test_windows_returncode_3(self):
        """deqp.DEQPBaseTest.interpret_result: on windows returncode 3 is crash"""
        self.test.result.returncode = 3
        with mock.patch('framework.test.base.sys.platform', 'win32'):
            self.test.interpret_result()
        nt.eq_(self.test.result.result, 'crash')


class TestDEQPBaseTestIntepretResultStatus(object):
    """Tests for DEQPBaseTest.__find_map."""
    def __init__(self):
        self.inst = None

    __OUT = textwrap.dedent("""\
        dEQP Core 2014.x (0xcafebabe) starting..
          target implementation = 'DRM'

        Test case 'dEQP-GLES2.functional.shaders.conversions.vector_to_vector.vec3_to_ivec3_fragment'..
        Vertex shader compile time = 0.129000 ms
        Fragment shader compile time = 0.264000 ms
        Link time = 0.814000 ms
        Test case duration in microseconds = 487155 us
          {stat} ({stat})

        DONE!

        Test run totals:
          Passed:        {pass_}/1 (100.0%)
          Failed:        {fail}/1 (0.0%)
          Not supported: {supp}/1 (0.0%)
          Warnings:      {warn}/1 (0.0%)
        Test run was ABORTED!
    """)

    def __gen_stdout(self, status):
        assert status in ['Fail', 'NotSupported', 'Pass', 'QualityWarning',
                          'InternalError', 'Crash', 'ResourceError']

        return self.__OUT.format(
            stat=status,
            pass_=1 if status == 'Pass' else 0,
            fail=1 if status in ['Crash', 'Fail', 'ResourceError'] else 0,
            supp=1 if status == 'InternalError' else 0,
            warn=1 if status == 'QualityWarning' else 0,
        )

    def setup(self):
        self.inst = _DEQPTestTest('a.deqp.test')
        self.inst.result.returncode = 0

    def test_fail(self):
        """test.deqp.DEQPBaseTest.interpret_result: when Fail in result the result is 'fail'"""
        self.inst.result.out = self.__gen_stdout('Fail')
        self.inst.interpret_result()
        nt.eq_(self.inst.result.result, 'fail')

    def test_pass(self):
        """test.deqp.DEQPBaseTest.interpret_result: when Pass in result the result is 'Pass'"""
        self.inst.result.out = self.__gen_stdout('Pass')
        self.inst.interpret_result()
        nt.eq_(self.inst.result.result, 'pass')

    def test_warn(self):
        """test.deqp.DEQPBaseTest.interpret_result: when QualityWarning in result the result is 'warn'"""
        self.inst.result.out = self.__gen_stdout('QualityWarning')
        self.inst.interpret_result()
        nt.eq_(self.inst.result.result, 'warn')

    def test_error(self):
        """test.deqp.DEQPBaseTest.interpret_result: when InternalError in result the result is 'fail'"""
        self.inst.result.out = self.__gen_stdout('InternalError')
        self.inst.interpret_result()
        nt.eq_(self.inst.result.result, 'fail')

    def test_crash(self):
        """test.deqp.DEQPBaseTest.interpret_result: when InternalError in result the result is 'crash'"""
        self.inst.result.out = self.__gen_stdout('Crash')
        self.inst.interpret_result()
        nt.eq_(self.inst.result.result, 'crash')

    def test_skip(self):
        """test.deqp.DEQPBaseTest.interpret_result: when NotSupported in result the result is 'skip'"""
        self.inst.result.out = self.__gen_stdout('NotSupported')
        self.inst.interpret_result()
        nt.eq_(self.inst.result.result, 'skip')

    def test_resourceerror(self):
        """test.deqp.DEQPBaseTest.interpret_result: when ResourceError in result the result is 'crash'"""
        self.inst.result.out = self.__gen_stdout('ResourceError')
        self.inst.interpret_result()
        nt.eq_(self.inst.result.result, 'crash')


class TestDEQPGroupTest_interpret_result(object):
    __out = textwrap.dedent("""
        dEQP Core unknown (0xcafebabe) starting..
          target implementation = 'X11 GLX'

        Test case 'dEQP-GLES3.functional.fragment_out.random.0'..
        Vertex shader compile time = 4.134000 ms
        Fragment shader compile time = 0.345000 ms
        Link time = 2.442000 ms
        Test case duration in microseconds = 10164 us
          Fail (After program setup: glGetError() returned GL_INVALID_FRAMEBUFFER_OPERATION at es3fFragmentOutputTests.cpp:706)

        Test case 'dEQP-GLES3.functional.fragment_out.random.1'..
        Vertex shader compile time = 0.352000 ms
        Fragment shader compile time = 0.276000 ms
        Link time = 2.625000 ms
        Test case duration in microseconds = 3894 us
          Pass (After program setup: glGetError() returned GL_INVALID_FRAMEBUFFER_OPERATION at es3fFragmentOutputTests.cpp:706)

        DONE!

        Test run totals:
          Passed:        2/2 (100.0%)
          Failed:        0/2 (0.0%)
          Not supported: 0/2 (0.0%)
          Warnings:      0/2 (0.0%)
    """)

    @classmethod
    def setup_class(cls):
        cls.test = _DEQPGroupTest('foo')
        cls.test.result.returncode = 0
        cls.test.result.out = cls.__out
        cls.test.interpret_result()

    def test_name(self):
        """test.deqp.DEQPGroupTest: set's name properly"""
        nt.assert_set_equal({'0', '1'}, set(self.test.result.subtests.keys()))

    def test_status(self):
        """test.deqp.DEQPGroupTest: set's status properly"""
        nt.assert_dict_equal(
            {'0': 'fail', '1': 'pass'},
            dict(self.test.result.subtests))


def test_DEQPGroupTest_interpret_result_cts():
    """test.deqp.DEQPGroupTest.interpret_result: Handles CTS shader dumps."""
    # The following is just something that looks kind of like a CTS shader, the
    # point is that the layout doesn't trip up the intepret_result method
    out = textwrap.dedent("""\
        dEQP Core GL-CTS-2.0 (0x0052484b) starting..
          target implementation = 'intel-gbm'

        Test case 'A.Test.case.1'..
        INFO:a test-------------------------------- BEGIN ---------------------------------
        INFO:a test

        [VERTEX SHADER]

        #version foobar
        #ifdef something
        in something
        INFO:mo stuff:

        [FRAGMENT SHADER]

        #version 300 es
        precision highp int;

        struct S {
            vec4 foo;
            vec2 fo[2];
        };
        layout(std140) uniform UB0 {
            S     x;
            S     y[2];
        } ub0;
        INFO:even more stuff:

        [VERTEX SHADER]

        #version 300 es
        bool something () {
            if (thing) { do! }
        INFO:and even more stuff:

        [FRAGMENT SHADER]

        #version 300 es
        precision highp int;

        INFO:a test:OK
        INFO:a test:--------------------------------- END ----------------------------------
          Pass (Pass)

        Test case 'A.Test.case.2'..
        INFO:a test-------------------------------- BEGIN ---------------------------------
        INFO:a test

        [VERTEX SHADER]

        #version foobar
        #ifdef something
        in something
        INFO:mo stuff:

        [FRAGMENT SHADER]

        #version 300 es
        precision highp int;

        struct S {
            vec4 boo;
            vec2 bo[2];
        };
        layout(std140) uniform UB0 {
            S     x;
            S     y[2];
        } ub0;
        INFO:even more stuff:

        [VERTEX SHADER]

        #version 300 es
        bool something () {
            if (thing) { do! }
        INFO:and even more stuff:

        [FRAGMENT SHADER]

        #version 300 es
        precision highp int;

        INFO:a test:OK
        INFO:a test:--------------------------------- END ----------------------------------
          Pass (Pass)

        DONE!

        Test run totals:
          Passed:        2/2 (100.00%)
          Failed:        0/2 (0.00%)
          Not supported: 0/2 (0.00%)
          Warnings:      0/2 (0.00%)
    """)

    test = _DEQPGroupTest('foo')
    test.result.returncode = 0
    test.result.out = out
    test.interpret_result()
    nt.eq_(test.result.subtests['1'], 'pass')
    nt.eq_(test.result.subtests['2'], 'pass')


def test_DEQPGroupTest_interpret_result_nonzero():
    """test.deqp.DEQPGroupTest.interpret_results: if returncode is nonzero test is crash"""
    test = _DEQPGroupTest('foo')
    test.result.returncode = -6
    test.interpret_result()
    nt.eq_(test.result.result, 'crash')


@utils.skip(not (sys.version_info[0:2] >= (3, 4) or
                 float(mock.__version__[:3]) >= 1.2),
            'Test requires that mock.mock_open provides readline method.')
def test_iter_deqp_test_groups():
    """deqp._test_deqp_test_groups: Returns expected values"""
    text = textwrap.dedent("""\
        GROUP: dEQP-GLES2.info
        TEST: dEQP-GLES2.info.vendor
        TEST: dEQP-GLES2.info.renderer
        TEST: dEQP-GLES2.info.version
        TEST: dEQP-GLES2.info.shading_language_version
        TEST: dEQP-GLES2.info.extensions
        TEST: dEQP-GLES2.info.render_target
        GROUP: dEQP-GLES2.capability
        GROUP: dEQP-GLES2.capability.limits
        TEST: dEQP-GLES2.capability.limits.vertex_attribs
        TEST: dEQP-GLES2.capability.limits.varying_vectors
        TEST: dEQP-GLES2.capability.limits.vertex_uniform_vectors
        TEST: dEQP-GLES2.capability.limits.fragment_uniform_vectors
        TEST: dEQP-GLES2.capability.limits.texture_image_units
        TEST: dEQP-GLES2.capability.limits.vertex_texture_image_units
        TEST: dEQP-GLES2.capability.limits.combined_texture_image_units
        TEST: dEQP-GLES2.capability.limits.texture_2d_size
        TEST: dEQP-GLES2.capability.limits.texture_cube_size
        TEST: dEQP-GLES2.capability.limits.renderbuffer_size
        GROUP: dEQP-GLES2.capability.limits_lower
        TEST: dEQP-GLES2.capability.limits_lower.minimum_size
        GROUP: dEQP-GLES2.capability.extensions
        GROUP: dEQP-GLES2.capability.extensions.uncompressed_texture_formats
        TEST: dEQP-GLES2.capability.extensions.uncompressed_texture_formats.foo
    """)

    expected = [
        'dEQP-GLES2.info',
        'dEQP-GLES2.capability.limits',
        'dEQP-GLES2.capability.limits_lower',
        'dEQP-GLES2.capability.extensions.uncompressed_texture_formats',
    ]

    with mock.patch('framework.test.deqp.open', create=True,
                    new=mock.mock_open(read_data=text)):
        actual = list(deqp._iter_deqp_test_groups(None))

    nt.assert_list_equal(actual, expected)
