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

from __future__ import (
    absolute_import, division, print_function, unicode_literals
)
import abc
import functools
import os
import re
import subprocess

import six
from six.moves import range

from framework import core, grouptools, exceptions, status
from framework.profile import TestProfile
from framework.test.base import Test, is_crash_returncode, TestRunError
from framework.log import LogManager
from framework.options import OPTIONS

__all__ = [
    'DEQPBaseTest',
    'DEQPGroupTest',
    'DEQPProfile',
    'get_option',
]


def get_option(env_varname, config_option, default=None):
    """Query the given environment variable and then piglit.conf for the option.

    Return the value of the default argument if opt is None.

    """
    opt = os.environ.get(env_varname, None)
    if opt is not None:
        return opt

    opt = core.PIGLIT_CONFIG.safe_get(config_option[0], config_option[1])

    return opt or default


_EXTRA_ARGS = get_option('PIGLIT_DEQP_EXTRA_ARGS',
                         ('deqp', 'extra_args'),
                         default='').split()

_RERUN = get_option('PIGLIT_DEQP_RERUN',
                    ('deqp', 'group_rerun'),
                    default='crash notrun incomplete timeout').split()


def _gen_caselist_txt(bin_, caselist, extra_args):
    """Generate a caselist.txt and return its path.

    Extra args should be a list of extra arguments to pass to deqp.

    """
    # dEQP is stupid (2014-12-07):
    #   1. To generate the caselist file, dEQP requires that the process's
    #      current directory must be that same as that of the executable.
    #      Otherwise, it fails to find its data files.
    #   2. dEQP creates the caselist file in the process's current directory
    #      and provides no option to change its location.
    #   3. dEQP creates a GL context when generating the caselist. Therefore,
    #      the caselist must be generated on the test target rather than the
    #      build host. In other words, when the build host and test target
    #      differ then we cannot pre-generate the caselist on the build host:
    #      we must *dynamically* generate it during the testrun.
    basedir = os.path.dirname(bin_)
    caselist_path = os.path.join(basedir, caselist)

    # TODO: need to catch some exceptions here...
    with open(os.devnull, 'w') as d:
        subprocess.check_call(
            [bin_, '--deqp-runmode=txt-caselist'] + extra_args, cwd=basedir,
            stdout=d, stderr=d)
    assert os.path.exists(caselist_path), \
        'Could not find {}'.format(caselist_path)
    return caselist_path


def _iterate_file(file_):
    """Lazily iterate a file line-by-line."""
    while True:
        line = file_.readline()
        if not line:
            raise StopIteration
        yield line


def _iter_test_groups(case_file):
    """Iterate over original dEQP testcase groups.

    This generator yields the name of each leaf group (that is, a group which
    contains only tests.)

    """
    slice_group = slice(len('GROUP: '), None)
    slice_test = slice(len('TEST: '), None)

    group = '.'
    tests = []
    with open(case_file, 'r') as caselist_file:
        iter_ = _iterate_file(caselist_file)
        # Wind passed the very base group, which would otherwise require
        # special handling.
        next(iter_)

        for i, line in enumerate(iter_):
            if line.startswith('GROUP:'):
                new = line[slice_group].strip()

                # This needs to handle the name of the new group being a
                # superset of the old group (ex: items to items_max)
                if new != group and tests:
                    yield group, tests
                    tests = []
                group = new
            elif line.startswith('TEST:'):
                tests.append(line[slice_test].strip())
            else:
                raise exceptions.PiglitFatalError(
                    'deqp: {}:{}: ill-formed line'.format(case_file, i))
        # Yield the final set of tests.
        yield group.strip(), tests


def _iter_test_single(case_file):
    """Iterate over original dEQP testcase names."""
    with open(case_file, 'r') as caselist_file:
        for i, line in enumerate(_iterate_file(caselist_file)):
            if line.startswith('GROUP:'):
                continue
            elif line.startswith('TEST:'):
                yield line[len('TEST:'):].strip()
            else:
                raise exceptions.PiglitFatalError(
                    'deqp: {}:{}: ill-formed line'.format(case_file, i))


def _iter_test_cases(case_file):
    """Wrapper that sets the iterator based on the mode."""
    if OPTIONS.deqp_mode == 'group':
        return _iter_test_groups(case_file)
    elif OPTIONS.deqp_mode == 'test':
        return _iter_test_single(case_file)


def _pop(kwargs, name, default=None):
    """A guard function for DEQPProfile."""
    try:
        return kwargs.pop(name)
    except KeyError:
        if default is not None:
            return default
        raise TypeError('Required keyword argument {} was not set'.format(name))


class DEQPProfile(TestProfile):
    """A profile specifically for dEQP tests.

    This profile provides much of the necessary setup bits for dEQP
    integration, including generating a valid test list.

    All arguments not listed will be passed to the parent class.

    Keyword Arguments:
    single_class -- the class to use for 'test at a time' mode. Required.
    multi_class -- the class to use for 'group at a time' mode. Required.
    filter_ -- A function that filters that test cases. By default this is a
               no-op function.
    bin_ -- the dEQP binary to use. Required.
    extra_args -- the extra arguments to pass to the dEQP binary for each test.
                  Default: [].
    filename -- the name of the txt file containing all of the test and group
                information that dEQP generates. Required.

    """

    def __init__(self, *args, **kwargs):
        # PYTHON3: This could all be done with explict keyword arguments
        # instead of this...madness
        pop = functools.partial(_pop, kwargs)

        single_class = pop('single_class')
        multi_class = pop('multi_class')
        bin_ = pop('bin_')
        filename = pop('filename')
        extra_args = pop('extra_args', default=[])
        filter_ = pop('filter_', default=lambda x: x)

        super(DEQPProfile, self).__init__(*args, **kwargs)
        self._rerun = multi_class.rerun
        self._rerun_class = single_class

        iter_ = _iter_test_cases(filter_(
            _gen_caselist_txt(bin_, filename, extra_args)))

        if OPTIONS.deqp_mode == 'group':
            for testname, rerun in iter_:
                # deqp uses '.' as the testgroup separator.
                piglit_name = testname.replace('.', grouptools.SEPARATOR)
                self.test_list[piglit_name] = multi_class(testname, rerun)
        elif OPTIONS.deqp_mode == 'test':
            for testname in iter_:
                # deqp uses '.' as the testgroup separator.
                piglit_name = testname.replace('.', grouptools.SEPARATOR)
                self.test_list[piglit_name] = single_class(testname)

    def run(self, logger, backend):
        """Run all tests.

        Adds the option to rerun tests if requested.

        """
        super(DEQPProfile, self).run(logger, backend)

        if OPTIONS.deqp_group_rerun and self._rerun:
            print('\nRerunning tests in single mode with statuses: "{}". '
                  '(run with --deqp-no-group-rerun to disable)\n'.format(
                      ', '.join(_RERUN)))

            log = LogManager(logger, len(self._rerun))
            self._run(log, backend,
                      # TODO: replace this dict with a profile.TestDict
                      test_list={k.replace('.', grouptools.SEPARATOR).lower():
                                 self._rerun_class(k) for k in self._rerun})

            log.get().summary()

    def _test(self, pair, log, backend):
        """Function to call test.execute from map.

        if in Group mode and group-rerun is enabled,then pass None to write if
        the test isn't pass or skip, this will cause it to delete the result
        file rather than loading it, which will be replaced when the re-run
        happens.

        """
        name, test = pair
        if (OPTIONS.deqp_mode == 'group' and
                OPTIONS.deqp_group_rerun and
                isinstance(test, DEQPGroupTest)):
            with backend.write_test(name) as w:
                test.execute(name, log.get(), self.dmesg)
                w(None if test.result.result in _RERUN else test.result)
        else:
            super(DEQPProfile, self)._test(pair, log, backend)


@six.add_metaclass(abc.ABCMeta)
class DEQPBaseTest(Test):
    # This a very hot path, a small speed optimization can be had by shortening
    # this match to just one character
    _RESULT_MAP = {
        "P": status.PASS,    # Pass
        "F": status.FAIL,    # Fail
        "Q": status.WARN,    # QualityWarnings
        "I": status.FAIL,    # InternalError
        "C": status.CRASH,   # Crash
        "N": status.SKIP,    # NotSupported
        "R": status.CRASH,   # ResourceError
    }

    @abc.abstractproperty
    def deqp_bin(self):
        """The path to the exectuable."""

    @abc.abstractproperty
    def extra_args(self):
        """Extra arguments to be passed to the each test instance.

        Needs to return a list, since self.command uses the '+' operator, which
        only works to join two lists together.

        """
        return _EXTRA_ARGS

    def __init__(self, case_name):
        command = [self.deqp_bin, '--deqp-case=' + case_name]

        super(DEQPBaseTest, self).__init__(command)

        # dEQP's working directory must be the same as that of the executable,
        # otherwise it cannot find its data files (2014-12-07).
        # This must be called after super or super will overwrite it
        self.cwd = os.path.dirname(self.deqp_bin)

    @Test.command.getter
    def command(self):
        """Return the command plus any extra arguments."""
        command = super(DEQPBaseTest, self).command
        return command + self.extra_args

    def interpret_result(self):
        if is_crash_returncode(self.result.returncode):
            self.result.result = 'crash'
        elif self.result.returncode != 0:
            self.result.result = 'fail'
        else:
            # Strip the first 3 lines, which are useless
            cur = ''
            lines = (l for l in self.result.out.rstrip().split('\n')[3:-8])
            for l in lines:
                # If there is an info block fast forward through it by calling
                # next on the generator until it is passed.
                if l.startswith('INFO'):
                    while not (cur.startswith('INFO') and cur.endswith('----')):
                        cur = next(lines)
                    l = cur

                if l.startswith('  '):
                    self.result.result = self._RESULT_MAP[l[2]]

        # We failed to parse the test output. Fallback to 'fail'.
        if self.result.result == 'notrun':
            self.result.result = 'fail'

    def _run_command(self):
        """Rerun the command if X11 connection failure happens."""
        for _ in range(5):
            super(DEQPBaseTest, self)._run_command()
            if "FATAL ERROR: Failed to open display" not in self.result.err:
                return

        raise TestRunError('Failed to connect to X server 5 times', 'fail')


class DEQPGroupTest(DEQPBaseTest):
    timeout = 300  # 5 minutes
    rerun = []
    __name_slicer = slice(len("Test case '"), -len("'.."))
    __finder = re.compile(r'^  (Warnings|Not supported|Failed|Passed):\s+\d/(?P<total>\d+).*')

    def __init__(self, case_name, individual_cases, **kwargs):
        super(DEQPGroupTest, self).__init__(case_name + '.*', **kwargs)
        self._individual_cases = individual_cases

    def interpret_result(self):
        """Group based result interpretation.

        This method is used to find names of subtests and their results and put
        them together.

        It provides a block keyword argument, this should be a callable taking
        the the line being processed as output. It may process the line, and
        can raise an Exception descending from PiglitException to mark
        conditions.

        """
        # This function is ugly and complicated. But it can be pretty easily
        # understood as an extension of DEQPBaseTest.inrepret_result. In this
        # case though there are multiple results, each being treated as a
        # subtest. This function must not only find the result of each subtest,
        # but the name as well.

        # If the returncode is non-0 don't bother, call it crash and move on,
        # since there will almost certinaly be an exception raised.
        if self.result.returncode != 0:
            self.result.result = 'crash'
        else:
            # Strip the first 3 lines, and the last 8 lines, which aren't
            # useful for this pass
            lines = self.result.out.rstrip().split('\n')[3:]
            cur = ''
            total = None
            for each in reversed(lines):
                m = self.__finder.match(each)
                if m:
                    total = int(m.group('total'))
                    break
            assert total is not None, 'Could not calculate total test count'

            lines = (l for l in lines[:-8])

            # Walk over standard out line by line, looking for 'Test case' (to
            # get the name of the test) and then for a result. Track each line,
            # which is used to both know when to stop walking and for error
            # reporting.
            while len(self.result.subtests) < total:
                for l in lines:
                    if l.startswith('Test case'):
                        name = l[self.__name_slicer].rsplit('.', 1)[1].lower()
                        break
                else:
                    raise exceptions.PiglitInternalError(
                        'Expected "Test case", but didn\'t find it in:\n'
                        '{}\ncurrent line: {}'.format(self.result.out, l))

                for l in lines:
                    # If there is an info block fast forward through it by
                    # calling next on the generator until it is passed.
                    if l.startswith('INFO'):
                        cur = ''
                        while not (cur.startswith('INFO') and cur.endswith('----')):
                            cur = next(lines)

                    elif l.startswith('  '):
                        try:
                            self.result.subtests[name] = self._RESULT_MAP[l[2]]
                        except KeyError:
                            raise exceptions.PiglitInternalError(
                                'Unknown status {}'.format(l[2:].split()[0]))
                        break
                else:
                    raise exceptions.PiglitInternalError(
                        'Expected "  (Pass,Fail,...)", '
                        'but didn\'t find it in:\n'
                        '{}\ncurrent line: {}'.format(self.result.out, l))

        # If group_rerun (the default) and the status is crash rerun
        if OPTIONS.deqp_group_rerun and self.result.result in _RERUN:
            self.rerun.extend(self._individual_cases)
        # We failed to parse the test output. Fallback to 'fail'.
        elif self.result.result == 'notrun':
            self.result.result = 'fail'
