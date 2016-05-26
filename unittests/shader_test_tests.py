# Copyright (c) 2014 Intel Corporation

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

""" Provides tests for the shader_test module """

from __future__ import (
    absolute_import, division, print_function, unicode_literals
)
import os
import textwrap
try:
    from unittest import mock
except ImportError:
    import mock

import six
import nose.tools as nt

from framework import exceptions, results
import framework.test.shader_test as testm
from . import utils

# pylint: disable=invalid-name
# pylint: disable=attribute-defined-outside-init

class _Setup(object):
    """Setup and teardown for the module."""
    def __init__(self):
        self.__patchers = []
        self.__patchers.append(mock.patch.dict(
            'framework.test.base.options.OPTIONS.env',
            {'PIGLIT_PLATFORM': 'foo'}))

    def setup(self):
        for patcher in self.__patchers:
            patcher.start()

    def teardown(self):
        for patcher in self.__patchers:
            patcher.stop()


_setup = _Setup()
setup = _setup.setup
teardown = _setup.teardown


def test_initialize_shader_test():
    """test.shader_test.ShaderTest: class initializes"""
    testm.ShaderTest(['tests/spec/glsl-es-1.00/execution/sanity.shader_test'])


def test_initialize_multiple():
    """test.shader_test.ShaderTest: class initializes with multiple files"""
    testm.ShaderTest(['tests/spec/glsl-es-1.00/execution/sanity.shader_test',
                      'tests/spec/glsl-es-1.00/execution/sanity2.shader_test'])


def test_parse_gl_test_no_decimal():
    """test.shader_test.ShaderTest: raises if version lacks decminal"""
    data = ('[require]\n'
            'GL = 2\n')
    with utils.tempfile(data) as temp:
        with nt.assert_raises(exceptions.PiglitFatalError) as exc:
            testm.ShaderTest([temp])
            nt.assert_equal(exc.exception, "No GL version set",
                            msg="A GL version was passed without a decimal, "
                                "which should have raised an exception, but "
                                "did not")


def test_parse_gles2_test():
    """test.shader_test.ShaderTest: Identifies GLES2 tests successfully"""
    data = ('[require]\n'
            'GL ES >= 2.0\n'
            'GLSL ES >= 1.00\n')
    with utils.tempfile(data) as temp:
        test = testm.ShaderTest([temp])

    nt.assert_equal(
        os.path.basename(test.command[0]), "shader_runner_gles2",
        msg="This test should have run with shader_runner_gles2, "
            "but instead ran with " + os.path.basename(test.command[0]))


def test_parse_gles3_test():
    """test.shader_test.ShaderTest: Identifies GLES3 tests successfully"""
    data = ('[require]\n'
            'GL ES >= 3.0\n'
            'GLSL ES >= 3.00\n')
    with utils.tempfile(data) as temp:
        test = testm.ShaderTest([temp])

    nt.assert_equal(
        os.path.basename(test.command[0]), "shader_runner_gles3",
        msg="This test should have run with shader_runner_gles3, "
            "but instead ran with " + os.path.basename(test.command[0]))


def test_add_auto():
    """test.shader_test.ShaderTest: -auto is added to the command"""
    test = testm.ShaderTest(['tests/spec/glsl-es-1.00/execution/sanity.shader_test'])
    nt.assert_in('-auto', test.command)


def test_find_requirements_gl_requirements():
    """test.shader_test.ShaderTest: populates gl_requirements properly"""

    data = ('[require]\n'
            'GL = 2.0\n'
            'GL_ARB_ham_sandwhich\n')

    with utils.tempfile(data) as temp:
        test = testm.ShaderTest([temp])

    nt.eq_(test.gl_required, set(['GL_ARB_ham_sandwhich']))


def test_find_requirements_gl_version():
    """test.shader_test.ShaderTest: finds gl_version."""
    data = ('[require]\n'
            'GL = 2.0\n'
            'GL_ARB_ham_sandwhich\n')

    with mock.patch('framework.test.shader_test.open',
                    mock.mock_open(read_data=data), create=True):
        test = testm.ShaderTest(['null'])
    nt.eq_(test.gl_version, 2.0)


def test_find_requirements_gles_version():
    """test.shader_test.ShaderTest: finds gles_version."""
    data = ('[require]\n'
            'GL ES = 2.0\n'
            'GL_ARB_ham_sandwhich\n')

    with mock.patch('framework.test.shader_test.open',
                    mock.mock_open(read_data=data), create=True):
        test = testm.ShaderTest(['null'])
    nt.eq_(test.gles_version, 2.0)


def test_find_requirements_glsl_version():
    """test.shader_test.ShaderTest: finds glsl_version."""
    data = ('[require]\n'
            'GL = 2.0\n'
            'GLSL >= 1.0\n'
            'GL_ARB_ham_sandwhich\n')

    with mock.patch('framework.test.shader_test.open',
                    mock.mock_open(read_data=data), create=True):
        test = testm.ShaderTest(['null'])
    nt.eq_(test.glsl_version, 1.0)


def test_find_requirements_glsl_es_version():
    """test.shader_test.ShaderTest: finds glsl_es_version."""
    data = ('[require]\n'
            'GL ES = 2.0\n'
            'GLSL ES > 2.00\n'
            'GL_ARB_ham_sandwhich\n')

    with mock.patch('framework.test.shader_test.open',
                    mock.mock_open(read_data=data), create=True):
        test = testm.ShaderTest(['null'])
    nt.eq_(test.glsl_es_version, 2.0)


@utils.nose_generator
def test_ignore_shader_runner_directives():
    """test.shader_test.ShaderTest: Doesn't add shader_runner command to gl_required list"""
    should_ignore = [
        'GL_MAX_VERTEX_OUTPUT_COMPONENTS',
        'GL_MAX_FRAGMENT_UNIFORM_COMPONENTS',
        'GL_MAX_VERTEX_UNIFORM_COMPONENTS',
        'GL_MAX_VARYING_COMPONENTS',
    ]

    def test(config):
        with mock.patch('framework.test.shader_test.open',
                        mock.mock_open(read_data=config), create=True):
            test = testm.ShaderTest(['null'])
        nt.eq_(test.gl_required, {'GL_foobar'})

    for ignore in should_ignore:
        config = '\n'.join([
            '[require]',
            'GL >= 1.0',
            'GL_foobar',
            ignore,
        ])
        test.description = ('test.shader_test.ShaderTest: doesn\'t add '
                            'shader_runner command {} to gl_required'.format(
                                ignore))

        yield test, config


class TestOutputIterator(object):
    """Tests for the OutputIterator class."""
    _base = ['foo', 'bar', 'oi', 'oink']

    def setup(self):
        self._test = testm.OutputIterator('foo\nbar\noi\noink')

    def test_append(self):
        """test.shader_test.OutputIterator.append: works as expected"""
        self._test.append('sentinal')
        nt.assert_list_equal(self._base + ['sentinal'], list(self._test))

    def test_appendleft(self):
        """test.shader_test.OutputIterator.appendleft: works as expected"""
        self._test.appendleft('sentinal')
        nt.assert_list_equal(['sentinal'] + self._base, list(self._test))

    def test_pop(self):
        """test.shader_test.OutputIterator.pop: works as expected"""
        nt.eq_(self._test.pop(), self._base[-1])
        nt.assert_list_equal(self._base[:-1], list(self._test))

    def test_popleft(self):
        """test.shader_test.OutputIterator.popleft: works as expected"""
        nt.eq_(self._test.popleft(), self._base[0])
        nt.assert_list_equal(self._base[1:], list(self._test))

    def test_next(self):
        """test.shader_test.OutputIterator.__next__: works as expected"""
        nt.eq_(next(self._test), self._base[0])
        nt.eq_(next(self._test), self._base[1])

    def test_iter(self):
        """test.shader_test.OutputIterator.__iter__: works as expected"""
        fail = False
        for i, actual in enumerate(self._test):
            test = actual == self._base[i]
            if test:
                print('index {}: ok'.format(i))
            else:
                print('index {}: fail'.format(i))
                print('   expcted "{}", but got "{}"'.format(
                    self._base[i], actual))
                fail = True

        if fail:
            raise utils.TestFailure('One or more values were incorrect')

    def test_takewhile_values(self):
        """test.shader_test.OutputIterator.takewhile: returns expected values"""
        values = list(self._test.takewhile(lambda x: x != 'oi'))
        nt.assert_list_equal(values, ['foo', 'bar'])

    def test_takewhile_does_not_remove(self):
        """test.shader_test.OutputIterator.takewhile: does not remove failing value"""
        _ = list(self._test.takewhile(lambda x: x != 'oi'))
        nt.eq_(next(self._test), 'oi')

    def test_dropwhile_values(self):
        """test.shader_test.OutputIterator.dropwhile: returns expected values"""
        self._test.dropwhile(lambda x: x != 'oi')
        nt.assert_list_equal(list(self._test), ['oi', 'oink'])


class Test_interpret_result(object):
    """Tests for ShaderTest.interpret_result."""
    # TODO: test for stdout content
    # TODO: test for stderr content
    @classmethod
    def setup_class(cls):
        """Make a ShaderTest instance to use."""
        data = textwrap.dedent("""\
            [require]
            GL >= 2.0
        """)

        with utils.tempfile(data) as temp:
            cls._test = testm.ShaderTest([temp])

    def _run(self, out='', err='', returncode=0, command=None):
        """Helper method that calls interpret_result."""
        assert isinstance(out, six.text_type), 'out is not a unicode'
        assert isinstance(err, six.text_type), 'err is not a unicode'
        assert isinstance(returncode, int), 'int is not a int'

        result = results.TestResult()
        result.out = out
        result.err = err
        result.command = command or 'shader_runner foo.shader_test'
        result.returncode = returncode
        result.command = 'bin/shader_test sentinal.shader_test'

        try:
            return self._test.interpret_result(result), None
        except testm.RunInterupted as e:
            return e.finished, e.todo

    @staticmethod
    def _assert(testresult, out=None, err=None, result=None, returncode=0):
        """Assert that things are correct."""
        fail = False
        for probe, name in [(out, 'out'), (err, 'out'), (result, 'result'),
                            (returncode, 'returncode')]:
            if probe is not None:
                actual = getattr(testresult, name)
                if probe == actual:
                    print('{:15}: ok'.format(name))
                else:
                    print('{:15}: fail'.format(name))
                    print('   expcted "{}", but got "{}"'.format(probe, actual))
                    fail = True

        return fail

    @staticmethod
    def _assert_todo(actual, expected):
        if actual == expected:
            print('{:15}: ok'.format('todo list'))
            return False
        else:
            print('{:15}: fail'.format('todo list'))
            print('   expcted "{}", but got "{}"'.format(expected, actual))
            return True

    def test_one_valid(self):
        """test.shader_test.interpret_result: handles a single result"""
        out = textwrap.dedent("""\
            PIGLIT: ["enumerate shader tests", ["tests/spec/glsl-es-1.00/execution/sanity.shader_test"]]
            START: tests/spec/glsl-es-1.00/execution/sanity.shader_test
            PIGLIT: ["time start", 1464041636]
            PIGLIT: ["result", "pass"]
            PIGLIT: ["time end", 1464041636]""")

        err = textwrap.dedent("""\
            START: tests/spec/glsl-es-1.00/execution/sanity.shader_test""")

        fail = False

        resultlist, todo = self._run(out, err)
        fail &= self._assert(resultlist[0], result='pass', out='', err='')
        fail &= self._assert_todo(todo, None)

        if fail:
            raise utils.TestFailure

    def test_multiple_valid(self):
        """test.shader_test.interpret_result: handles multiple results"""
        out = textwrap.dedent("""\
			PIGLIT: ["enumerate shader tests", ["tests/spec/glsl-es-1.00/execution/glsl-no-vertex-attribs.shader_test", "tests/spec/glsl-es-1.00/execution/sanity.shader_test"]]
			START: tests/spec/glsl-es-1.00/execution/glsl-no-vertex-attribs.shader_test
			PIGLIT: ["time start", 1464049110]
			PIGLIT: ["result", "pass"]
			PIGLIT: ["time end", 1464049110]
			START: tests/spec/glsl-es-1.00/execution/sanity.shader_test
			PIGLIT: ["time start", 1464049110]
			PIGLIT: ["result", "pass"]
			PIGLIT: ["time end", 1464049110]""")

        err = textwrap.dedent("""\
			START: tests/spec/glsl-es-1.00/execution/glsl-no-vertex-attribs.shader_test
			START: tests/spec/glsl-es-1.00/execution/sanity.shader_test""")

        fail = False

        resultlist, todo = self._run(out, err)
        fail &= self._assert(resultlist[0], result='pass', out='', err='')
        fail &= self._assert(resultlist[1], result='pass', out='', err='')
        fail &= self._assert_todo(todo, None)

        if fail:
            raise utils.TestFailure

    def test_skip_first(self):
        """test.shader_test.interpret_result: handles skip as the first status"""
        out = textwrap.dedent('PIGLIT: ["result", "skip"]')
        err = textwrap.dedent("""\
            piglit: error: waffle_context_create failed due to WAFFLE_ERROR_UNKNOWN: glXCreateContextAttribsARB failed
            piglit: error: Failed to create waffle_context for OpenGL 4.2 Core Context
            piglit: info: Falling back to GL 4.2 compatibility context
            piglit: error: waffle_context_create failed due to WAFFLE_ERROR_UNKNOWN: glXCreateContextAttribsARB failed
            piglit: error: Failed to create waffle_context for OpenGL 4.2 Compatibility Context
            piglit: info: Failed to create any GL context""")
        command = "bin/shader_runner foo.shader_test bar.shader_test -auto"

        fail = False
        resultlist, todo = self._run(out, command=command)
        fail &= self._assert(resultlist[0], out=out, err=err, result='skip')
        fail &= self._assert_todo(todo, ['bar.shader_test'])

        if fail:
            raise utils.TestFailure

    def test_skip_end(self):
        """test.shader_test.interpret_result: handles skip in the end of runs"""
        out = textwrap.dedent("""\
			PIGLIT: ["enumerate shader tests", ["tests/spec/glsl-es-1.00/execution/glsl-no-vertex-attribs.shader_test", "tests/spec/glsl-es-1.00/execution/sanity.shader_test"]]
			START: tests/spec/glsl-es-1.00/execution/glsl-no-vertex-attribs.shader_test
			PIGLIT: ["time start", 1464049110]
			PIGLIT: ["result", "pass"]
			PIGLIT: ["time end", 1464049110]
			START: tests/spec/glsl-es-1.00/execution/sanity.shader_test
			PIGLIT: ["time start", 1464049110]
			PIGLIT: ["result", "skip"]""")

        err = textwrap.dedent("""\
			START: tests/spec/glsl-es-1.00/execution/glsl-no-vertex-attribs.shader_test
			START: tests/spec/glsl-es-1.00/execution/sanity.shader_test""")

        fail = False

        resultlist, todo = self._run(out, err)
        fail &= self._assert(resultlist[0], result='pass', out='', err='')
        fail &= self._assert(resultlist[1], result='skip', out='', err='')
        fail &= self._assert_todo(todo, None)

        if fail:
            raise utils.TestFailure

    def test_skip_middle(self):
        """test.shader_test.interpret_result: handles skip in the middle of runs"""
        out = textwrap.dedent("""\
			PIGLIT: ["enumerate shader tests", ["tests/spec/glsl-es-1.00/execution/glsl-no-vertex-attribs.shader_test", "tests/spec/glsl-es-1.00/execution/sanity.shader_test", "tests/spec/glsl-es-1.00/execution/extra.shader_test"]]
			START: tests/spec/glsl-es-1.00/execution/glsl-no-vertex-attribs.shader_test
			PIGLIT: ["time start", 1464049110]
			PIGLIT: ["result", "pass"]
			PIGLIT: ["time end", 1464049110]
			START: tests/spec/glsl-es-1.00/execution/sanity.shader_test
			PIGLIT: ["time start", 1464049110]
			PIGLIT: ["result", "skip"]""")

        err = textwrap.dedent("""\
			START: tests/spec/glsl-es-1.00/execution/glsl-no-vertex-attribs.shader_test
			START: tests/spec/glsl-es-1.00/execution/sanity.shader_test""")

        fail = False

        resultlist, todo = self._run(out, err)
        fail &= self._assert(resultlist[0], result='pass', out='', err='')
        fail &= self._assert(resultlist[1], result='skip', out='', err='')
        fail &= self._assert_todo(
            todo, ["tests/spec/glsl-es-1.00/execution/extra.shader_test"])

        if fail:
            raise utils.TestFailure

    def test_crash_last(self):
        """test.shader_test.interpret_result: handles crashes of last test"""
        out = textwrap.dedent("""\
			PIGLIT: ["enumerate shader tests", ["tests/spec/glsl-es-1.00/execution/glsl-no-vertex-attribs.shader_test", "tests/spec/glsl-es-1.00/execution/sanity.shader_test"]]
			START: tests/spec/glsl-es-1.00/execution/glsl-no-vertex-attribs.shader_test
			PIGLIT: ["time start", 1464049110]
			PIGLIT: ["result", "pass"]
			PIGLIT: ["time end", 1464049110]
			START: tests/spec/glsl-es-1.00/execution/sanity.shader_test
			PIGLIT: ["time start", 1464049110]""")

        err = textwrap.dedent("""\
			START: tests/spec/glsl-es-1.00/execution/glsl-no-vertex-attribs.shader_test
			START: tests/spec/glsl-es-1.00/execution/sanity.shader_test""")

        fail = False

        resultlist, todo = self._run(out, err, returncode=-5)
        fail &= self._assert(resultlist[0], result='pass', out='', err='',
                             returncode=0)
        fail &= self._assert(resultlist[1], result='crash', out='', err='',
                             returncode=-5)
        fail &= self._assert_todo(todo, None)

        if fail:
            raise utils.TestFailure

    def test_crash_middle(self):
        """test.shader_test.interpret_result: handles crashes before last test
        """
        out = textwrap.dedent("""\
			PIGLIT: ["enumerate shader tests", ["tests/spec/glsl-es-1.00/execution/glsl-no-vertex-attribs.shader_test", "tests/spec/glsl-es-1.00/execution/sanity.shader_test", "tests/spec/glsl-es-1.00/execution/another.shader_test"]]
			START: tests/spec/glsl-es-1.00/execution/glsl-no-vertex-attribs.shader_test
			PIGLIT: ["time start", 1464049110]
			PIGLIT: ["result", "pass"]
			PIGLIT: ["time end", 1464049110]
			START: tests/spec/glsl-es-1.00/execution/sanity.shader_test
			PIGLIT: ["time start", 1464049110]""")

        err = textwrap.dedent("""\
			START: tests/spec/glsl-es-1.00/execution/glsl-no-vertex-attribs.shader_test
			START: tests/spec/glsl-es-1.00/execution/sanity.shader_test""")
        fail = False

        resultlist, todo = self._run(out, err, returncode=-5)
        fail &= self._assert(resultlist[0], result='pass', out='', err='',
                             returncode=0)
        fail &= self._assert(resultlist[1], result='crash', out='', err='',
                             returncode=-5)
        fail &= self._assert_todo(
            todo, ["tests/spec/glsl-es-1.00/execution/another.shader_test"])

        if fail:
            raise utils.TestFailure


# TODO: write tests for the run method
