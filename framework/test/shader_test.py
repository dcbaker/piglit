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
import io
import os
import re
try:
    import lxml.etree as et
except ImportError:
    import xml.etree.cElementTree as et

import six

from framework import exceptions
from framework import status
from .base import ReducedProcessMixin, TestIsSkip, REGISTRY
from .opengl import FastSkipMixin, FastSkip
from .piglit_test import PiglitBaseTest, PIGLIT_ROOT

__all__ = [
    'ShaderTest',
]


class Parser(object):
    """An object responsible for parsing a shader_test file."""

    _is_gl = re.compile(r'GL (<|<=|=|>=|>) \d\.\d')
    _match_gl_version = re.compile(
        r'^GL\s+(?P<es>ES)?\s*(?P<op>(<|<=|=|>=|>))\s*(?P<ver>\d\.\d)')
    _match_glsl_version = re.compile(
        r'^GLSL\s+(?P<es>ES)?\s*(?P<op>(<|<=|=|>=|>))\s*(?P<ver>\d\.\d+)')

    def __init__(self, filename):
        self.filename = filename
        self.gl_required = set()
        self._gl_version = None
        self._gles_version = None
        self._glsl_version = None
        self._glsl_es_version = None
        self.prog = None
        self.__op = None
        self.__sl_op = None

    def parse(self):
        # Iterate over the lines in shader file looking for the config section.
        # By using a generator this can be split into two for loops at minimal
        # cost. The first one looks for the start of the config block or raises
        # an exception. The second looks for the GL version or raises an
        # exception
        with io.open(self.filename, mode='r', encoding='utf-8') as shader_file:
            # The mock in python 3.3 doesn't support readlines(), so use
            # read().split() as a workaround
            lines = (l for l in shader_file.read().split('\n'))

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
                    "In file {}: Config block not found".format(self.filename))

        for line in lines:
            if line.startswith('GL_') and not line.startswith('GL_MAX'):
                self.gl_required.add(line.strip())
                continue

            # Find any GLES requirements.
            if not (self._gl_version or self._gles_version):
                m = self._match_gl_version.match(line)
                if m:
                    self.__op = m.group('op')
                    if m.group('es'):
                        self._gles_version = float(m.group('ver'))
                    else:
                        self._gl_version = float(m.group('ver'))
                    continue

            if not (self._glsl_version or self._glsl_es_version):
                # Find any GLSL requirements
                m = self._match_glsl_version.match(line)
                if m:
                    self.__sl_op = m.group('op')
                    if m.group('es'):
                        self._glsl_es_version = float(m.group('ver'))
                    else:
                        self._glsl_version = float(m.group('ver'))
                    continue

            if line.startswith('['):
                break

        # Select the correct binary to run the test, but be as conservative as
        # possible by always selecting the lowest version that meets the
        # criteria.
        if self._gles_version:
            if self.__op in ['<', '<='] or (
                    self.__op in ['=', '>='] and self._gles_version < 3):
                self.prog = 'shader_runner_gles2'
            else:
                self.prog = 'shader_runner_gles3'
        else:
            self.prog = 'shader_runner'

    # FIXME: All of these properties are a work-around for the fact that the
    # FastSkipMixin assumes that operations are always > or >=

    @property
    def gl_version(self):
        return self._gl_version if self.__op not in ['<', '<='] else None

    @property
    def gles_version(self):
        return self._gles_version if self.__op not in ['<', '<='] else None

    @property
    def glsl_version(self):
        return self._glsl_version if self.__sl_op not in ['<', '<='] else None

    @property
    def glsl_es_version(self):
        return self._glsl_es_version if self.__sl_op not in ['<', '<='] else None


@REGISTRY.register('ShaderParserTest')
class ShaderTest(FastSkipMixin, PiglitBaseTest):
    """ Parse a shader test file and return a PiglitTest instance

    This function parses a shader test to determine if it's a GL, GLES2 or
    GLES3 test, and then returns a PiglitTest setup properly.

    """

    def __init__(self, command, **kwargs):
        super(ShaderTest, self).__init__(command, **kwargs)

    @PiglitBaseTest.command.getter
    def command(self):
        """ Add -auto to the test command """
        return self._command + ['-auto']

    @classmethod
    def from_file(cls, filename):
        parser = Parser(filename)
        parser.parse()

        return cls(
            [parser.prog, parser.filename],
            run_concurrent=True,
            gl_required=parser.gl_required,
            gl_version=parser.gl_version,
            gles_version=parser.gles_version,
            glsl_version=parser.glsl_version,
            glsl_es_version=parser.glsl_es_version)

    @staticmethod
    def to_xml(filename=None, process_isolation=True, **kwargs):
        parser = Parser(filename)
        parser.parse()

        if parser.gl_version:
            kwargs['gl_version'] = six.text_type(parser.gl_version)
        if parser.gles_version:
            kwargs['gles_version'] = six.text_type(parser.gles_version)
        if parser.glsl_version:
            kwargs['glsl_version'] = six.text_type(parser.glsl_version)
        if parser.glsl_es_version:
            kwargs['glsl_es_version'] = six.text_type(parser.glsl_es_version)

        return ([('process_isolation', 'true' if process_isolation else 'false')],
                et.Element('ShaderTest',
                           command=' '.join([
                               parser.prog,
                               os.path.relpath(parser.filename, PIGLIT_ROOT),
                           ]),
                           run_concurrent='true',
                           gl_required=' '.join(parser.gl_required),
                           **kwargs))


@REGISTRY.register('MultiShaderTest')
class MultiShaderTest(ReducedProcessMixin, PiglitBaseTest):
    """A Shader class that can run more than one test at a time.

    This class can call shader_runner with multiple shader_files at a time, and
    interpret the results, as well as handle pre-mature exit through crashes or
    from breaking import assupmtions in the utils about skipping.

    Arguments:
    filenames -- a list of absolute paths to shader test files
    """

    @classmethod
    def from_file(cls, filenames):
        assert filenames
        prog = None
        files = []
        subtests = []
        skips = []

        # Walk each subtest, and either add it to the list of tests to run, or
        # determine it is skip, and set the result of that test in the subtests
        # dictionary to skip without adding it ot the liest of tests to run
        for each in filenames:
            parser = Parser(each)
            parser.parse()
            subtest = os.path.basename(os.path.splitext(each)[0]).lower()

            if prog is not None:
                # This allows mixing GLES2 and GLES3 shader test files
                # together. Since GLES2 profiles can be promoted to GLES3, this
                # is fine.
                if parser.prog != prog:
                    # Pylint can't figure out that prog is not None.
                    if 'gles' in parser.prog and 'gles' in prog:  # pylint: disable=unsupported-membership-test
                        prog = max(parser.prog, prog)
                    else:
                        # The only way we can get here is if one is GLES and
                        # one is not, since there is only one desktop runner
                        # thus it will never fail the is parser.prog != prog
                        # check
                        raise exceptions.PiglitInternalError(
                            'GLES and GL shaders in the same command!\n'
                            'Cannot pick a shader_runner binary!')
            else:
                prog = parser.prog

            try:
                skipper = FastSkip(gl_required=parser.gl_required,
                                   gl_version=parser.gl_version,
                                   gles_version=parser.gles_version,
                                   glsl_version=parser.glsl_version,
                                   glsl_es_version=parser.glsl_es_version)
                skipper.test()
            except TestIsSkip:
                skips.append(subtest)
                continue
            files.append(parser.filename)
            subtests.append(subtest)

        assert len(subtests) + len(skips) == len(filenames), \
            'not all tests accounted for'

        inst = cls(
            [prog] + files,
            subtests=subtests,
            run_concurrent=True)

        for name in skips:
            inst.result.subtests[name] = status.SKIP

        return inst

    @classmethod
    def from_xml(cls, element):
        files = []
        subtests = []
        skips = []

        for each in element:
            skipper = FastSkip(
                gl_required=set(each.attrib.get('gl_required', '').split()),
                gl_version=float(each.attrib.get('gl_version', '0')) or None,
                glsl_version=float(each.attrib.get('glsl_version', '0')) or None,
                gles_version=float(each.attrib.get('gles_version', '0')) or None,
                glsl_es_version=float(each.attrib.get('glsl_es_version', '0')) or None)
            try:
                skipper.test()
            except TestIsSkip:
                skips.append(each.attrib['subtest'])
                continue
            files.append(each.attrib['filename'])
            subtests.append(each.attrib['subtest'])

        inst = cls(
            command=[element.attrib['prog']] + files,
            subtests=subtests,
            run_concurrent=True)

        for name in skips:
            inst.result.subtests[name] = status.SKIP

        return inst

    @staticmethod
    def to_xml(filenames=None, **kwargs):
        if 'run_concurrent' in kwargs:
            kwargs['run_concurrent'] = 'true' if kwargs['run_concurrent'] else 'false'
        root = et.Element('MultiShaderTest', **kwargs)
        prog = None

        # Walk each subtest, and either add it to the list of tests to run, or
        # determine it is skip, and set the result of that test in the subtests
        # dictionary to skip without adding it ot the liest of tests to run
        for each in filenames:
            parser = Parser(each)
            parser.parse()
            subtest = os.path.basename(os.path.splitext(each)[0]).lower()

            if prog is not None:
                # This allows mixing GLES2 and GLES3 shader test files
                # together. Since GLES2 profiles can be promoted to GLES3, this
                # is fine.
                if parser.prog != prog:
                    # Pylint can't figure out that prog is not None.
                    if 'gles' in parser.prog and 'gles' in prog:  # pylint: disable=unsupported-membership-test
                        prog = max(parser.prog, prog)
                    else:
                        # The only way we can get here is if one is GLES and
                        # one is not, since there is only one desktop runner
                        # thus it will never fail the is parser.prog != prog
                        # check
                        raise exceptions.PiglitInternalError(
                            'GLES and GL shaders in the same command!\n'
                            'Cannot pick a shader_runner binary!')
            else:
                prog = parser.prog

            sub = et.SubElement(root, 'file',
                                filename=os.path.relpath(each, PIGLIT_ROOT),
                                subtest=subtest)
            if parser.gl_required:
                sub.attrib['gl_required'] = ' '.join(parser.gl_required)
            if parser.gl_version:
                sub.attrib['gl_version'] = six.text_type(parser.gl_version)
            if parser.gles_version:
                sub.attrib['gles_version'] = six.text_type(parser.gles_version)
            if parser.glsl_version:
                sub.attrib['glsl_version'] = six.text_type(parser.glsl_version)
            if parser.glsl_es_version:
                sub.attrib['glsl_es_version'] = six.text_type(parser.glsl_es_version)

        root.attrib['prog'] = prog
        return ([('process_isolation', 'false')], root)

    @PiglitBaseTest.command.getter  # pylint: disable=no-member
    def command(self):
        """Add -auto to the test command."""
        return self._command + ['-auto', '-report-subtests']

    def _is_subtest(self, line):
        return line.startswith('PIGLIT TEST:')

    def _resume(self, current):
        command = [self.command[0]]
        command.extend(self.command[current + 1:])
        return command

    def _stop_status(self):
        # If the lower level framework skips then return a status for that
        # subtest as skip, and resume.
        if self.result.out.endswith('PIGLIT: {"result": "skip" }\n'):
            return status.SKIP
        if self.result.returncode > 0:
            return status.FAIL
        return status.CRASH

    def _is_cherry(self):
        # Due to the way that piglt is architected if a particular feature
        # isn't supported it causes the test to exit with status 0. There is no
        # straightforward way to fix this, so we work around it by looking for
        # the message that feature provides and marking the test as not
        # "cherry" when it is found at the *end* of stdout. (We don't want to
        # match other places or we'll end up in an infinite loop)
        return (
            self.result.returncode == 0 and not
            self.result.out.endswith(
                'not supported on this implementation\n') and not
            self.result.out.endswith(
                'PIGLIT: {"result": "skip" }\n'))
