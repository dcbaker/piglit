# Copyright (C) 2012, 2014-2016 Intel Corporation
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the "Software"), to deal in the Software without
# restriction, including without limitation the rights to use,
# copy, modify, merge, publish, distribute, sublicense, and/or
# sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following
# conditions:
#
# This permission notice shall be included in all copies or
# substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY
# KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
# WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR
# PURPOSE AND NONINFRINGEMENT.  IN NO EVENT SHALL THE AUTHOR(S) BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN
# AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF
# OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.

""" This module enables running shader tests. """

from __future__ import (
    absolute_import, division, print_function, unicode_literals
)
import collections
import itertools
import os
import re
try:
    import simplejson as json
except ImportError:
    import json

import six

from framework import exceptions, results, grouptools, status
from .piglit_test import PiglitBaseTest
from .opengl import FastSkipMixin
from .base import MultiResultMixin

__all__ = [
    'ShaderTest',
]


def _make_test_name(path):
    if 'generated_tests' in path:
        name = grouptools.from_path(os.path.relpath(path, 'generated_tests'))
    else:
        name = grouptools.from_path(os.path.relpath(path, 'tests'))
    return os.path.splitext(name)[0].lower()


def _is_start(value):
    return value.startswith('START:')


def _not_start(value):
    return not value.startswith('START:')


class RunInterupted(exceptions.PiglitException):
    def __init__(self, *args, finished=None, todo=None, **kwargs):
        super().__init__(*args, **kwargs)

        assert finished is not None, 'Must set finished tests!'
        assert todo is not None, 'Must set todo tests!'
        self.finished = finished
        self.todo = todo


class OutputIterator(object):
    """A collections.deque-like object that also provides a next method.

    This class does not provide the entire collecitons.deque interface, only
    the append and pop methods (including the left variants), and a

    """
    def __init__(self, output):
        self.__queue = collections.deque(output.split('\n'))
        self.__empty = False

    @property
    def empty(self):
        return self.__empty

    def append(self, obj):
        self.__queue.append(obj)

    def appendleft(self, obj):
        self.__queue.appendleft(obj)

    def pop(self):
        return self.__queue.pop()

    def popleft(self):
        return self.__queue.popleft()

    def __next__(self):
        try:
            return self.popleft()
        except IndexError:
            self.__empty = True
            raise StopIteration

    def __iter__(self):
        while not self.__empty:
            yield next(self)

    def takewhile(self, pred):
        """Equivalent to itertools.takewhile, but maintains value that fails.

        This works almost just like itertools.takewhile, except that it puts
        the value that fails the predicate back on the deque instead of
        throwing it away.

        """
        for each in self:
            if pred(each):
                yield each
            else:
                self.appendleft(each)
                break

    def dropwhile(self, pred):
        """Equivalent to itertools.dropwhile, but maintains value that fails.

        Just like the takewhile method, but drops instead.

        """
        for each in self:
            if not pred(each):
                self.appendleft(each)
                break


class ShaderTest(MultiResultMixin, FastSkipMixin, PiglitBaseTest):
    """ Parse a shader test file and return a PiglitTest instance

    This function parses a shader test to determine if it's a GL, GLES2 or
    GLES3 test, and then returns a PiglitTest setup properly.

    """
    _is_gl = re.compile(r'GL (<|<=|=|>=|>) \d\.\d')
    _match_gl_version = re.compile(
        r'^GL\s+(?P<es>ES)?\s*(?P<op>(<|<=|=|>=|>))\s*(?P<ver>\d\.\d)')
    _match_glsl_version = re.compile(
        r'^GLSL\s+(?P<es>ES)?\s*(?P<op>(<|<=|=|>=|>))\s*(?P<ver>\d\.\d+)')

    def __init__(self, files):
        self.gl_required = set()

        first_filename = files[0]

        # Iterate over the lines in shader file looking for the config section.
        # By using a generator this can be split into two for loops at minimal
        # cost. The first one looks for the start of the config block or raises
        # an exception. The second looks for the GL version or raises an
        # exception
        with open(first_filename, 'r') as shader_file:
            # The mock in python 3.3 doesn't support readlines(), so use
            # read().split() as a workaround
            if six.PY3:
                lines = (l for l in shader_file.read().split('\n'))
            elif six.PY2:
                lines = (l.decode('utf-8') for l in
                         shader_file.read().split(b'\n'))

            # Find the config section
            for line in lines:
                # We need to find the first line of the configuration file, as
                # soon as we do then we can move on to geting the
                # configuration. The first line needs to be parsed by the next
                # block.
                if line.startswith('[require]'):
                    break
            else:
                raise exceptions.PiglitFatalError(
                    "In file {}: Config block not found".format(first_filename))

            lines = list(lines)

        prog = self.__find_gl(lines, first_filename)

        super(ShaderTest, self).__init__([prog] + files, run_concurrent=True)

        # Ensure that -auto and -fbo aren't added on the command line, or
        # remove them if they are.
        if self._command[-1] in ['-auto', '-fbo']:
            del self._command[-1]
        if self._command[-1] in ['-auto', '-fbo']:
            del self._command[:-1]
        elif self._command[-2] in ['-auto', '-fbo']:
            del self._command[:-2]

        # This needs to be run after super or gl_required will be reset
        # TODO: how to handle this for multiple files?
        #self.__find_requirements(lines)

    def __find_gl(self, lines, filename):
        """Find the OpenGL API to use."""
        for line in lines:
            line = line.strip()
            if line.startswith('GL ES'):
                if line.endswith('3.0'):
                    prog = 'shader_runner_gles3'
                elif line.endswith('2.0'):
                    prog = 'shader_runner_gles2'
                # If we don't set gles2 or gles3 continue the loop,
                # probably htting the exception in the for/else
                else:
                    raise exceptions.PiglitFatalError(
                        "In File {}: No GL ES version set".format(filename))
                break
            elif line.startswith('[') or self._is_gl.match(line):
                # In the event that we reach the end of the config black
                # and an API hasn't been found, it's an old test and uses
                # "GL"
                prog = 'shader_runner'
                break
        else:
            raise exceptions.PiglitFatalError(
                "In file {}: No GL version set".format(filename))

        return prog

    def __find_requirements(self, lines):
        """Find any requirements in the test and record them."""
        for line in lines:
            if line.startswith('GL_') and not line.startswith('GL_MAX'):
                self.gl_required.add(line.strip())
                continue

            if not (self.gl_version or self.gles_version):
                # Find any gles requirements
                m = self._match_gl_version.match(line)
                if m:
                    if m.group('op') not in ['<', '<=']:
                        if m.group('es'):
                            self.gles_version = float(m.group('ver'))
                        else:
                            self.gl_version = float(m.group('ver'))
                        continue

            if not (self.glsl_version or self.glsl_es_version):
                # Find any GLSL requirements
                m = self._match_glsl_version.match(line)
                if m:
                    if m.group('op') not in ['<', '<=']:
                        if m.group('es'):
                            self.glsl_es_version = float(m.group('ver'))
                        else:
                            self.glsl_version = float(m.group('ver'))
                        continue

            if line.startswith('['):
                break

    def interpret_result(self, result):
        resultlist = []
        out = OutputIterator(result.out)
        err = OutputIterator(result.err)

        # Fast forward until we get to the enumerated list of shader tests
        # (hopefully anyway), and then read that in.
        out.dropwhile(lambda x: not x.startswith('PIGLIT:'))
        command, testlist = json.loads(next(out)[7:])

        # In the event what we got wasn't 'enumerate shader tests', then
        # hopefully it's a ['result', 'skip'], which means something went wrong
        # in waffle. Mark the
        if command != 'enumerate shader tests':
            assert command == 'result', \
                'Expected shader test list but got {}'.format(command)

            iresult = results.TestResult(name=_make_test_name(self._command[1]))
            iresult.out = result.out
            iresult.err = result.err
            iresult.returncode = 0
            iresult.result = testlist
            resultlist.append(iresult)

            raise RunInterupted(finished=resultlist, todo=self._command[2:])

        # While there is still a testlist, read through the output generating a
        # result for each result in the output.
        while testlist:
            try:
                name = next(out)[len('START: '):]
                ename = next(err)[len('START: '):]
            except StopIteration:
                break

            assert name == ename, \
                'names dont match!\nout "{}"\nerr "{}"'.format(name, ename)
            assert name == testlist[0], \
                'Unexpected order of tests. expected "{}", but got "{}"'.format(
                    testlist[0], name)

            iresult = results.TestResult(name=_make_test_name(name))
            iresult.out = '\n'.join(out.takewhile(_not_start))
            iresult.err = '\n'.join(err.takewhile(_not_start))
            iresult.returncode = 0
            resultlist.append(iresult)

            del testlist[0]

        # TODO: what do we do for a > 0 returncode?
        # TODO: windows....
        # If the returncode is < 0 then assume that the last test was the one
        # that crashed, and set it's returncode as such.
        if result.returncode < 0:
            resultlist[-1].returncode = result.returncode

        # If the testlist isn't empty that means that the run was interupted,
        # raise a special kind of exception that will be cuaght in the custom
        # run method.
        if testlist:
            raise RunInterupted(
                finished=[super(ShaderTest, self).interpret_result(r)
                          for r in resultlist],
                todo=testlist[len(resultlist):])

        return [super(ShaderTest, self).interpret_result(r) for r in resultlist]

    def run(self, result):
        expected = len(self._command[1:])
        assert len(self._command) > 1, 'No files specified!'

        resultlist = []

        def keep_trying(result, resultlist):
            """Keep trying to run the test until all the tests finish."""
            try:
                resultlist.extend(super(ShaderTest, self).run(result))
            except RunInterupted as e:
                # If the run was interupted, extend the resultlist with the
                # tests that did work, then mark the test that stoped the run
                # as crash, and remove it from the list of tests to run, then
                # try again.
                resultlist.extend(e.finished)

                if e.todo:
                    result = results.TestResult()
                    self._command = [self._command[0]] + e.todo
                    assert len(self._command) > 1, 'No files specified!'
                    return keep_trying(result, resultlist)

            return resultlist

        def _run(result, resultlist):
            keep_trying(result, resultlist)

            if len(resultlist) != expected:
                command = self._command[1:]
                self._command = [self._command[0]] + command[len(resultlist):]
                assert len(self._command) > 1, 'No files specified!'
                return _run(result, resultlist)
            return resultlist

        return _run(result, resultlist)

    @PiglitBaseTest.command.getter  # pylint: disable=no-member
    def command(self):
        """ Add -auto to the test command """
        return self._command + ['-auto']
