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

from __future__ import (
    absolute_import, division, print_function, unicode_literals
)
import argparse
import ctypes
import itertools
import os
import os.path as path
import shutil
import sys
import time

import six
from six.moves import zip_longest  # pylint: disable=redefined-builtin

from framework import core, backends, exceptions, options
import framework.results
import framework.profile
from . import parsers

__all__ = ['run',
           'resume']


def grouper(iterable, size=2, fillvalue=None):
    """takes size elements at a time from an interable."""
    return zip_longest(fillvalue=fillvalue, *[iter(iterable)] * size)


def _get_profiles():
    """Get all of the profiles in test and return them."""
    possibilities = os.listdir(os.path.abspath(
        os.path.join(os.path.dirname(__file__), '..', '..', 'tests')))

    for filename in possibilities:
        name, ext = os.path.splitext(filename)
        if ext != '.py' or name.startswith('_'):
            continue

        yield name


def _default_backend():
    """ Logic to se the default backend to use

    There are two options, either the one set via the -b/--backend option, or
    the one in the config file. The default if that fails is to use json

    """
    backend = core.PIGLIT_CONFIG.safe_get('core', 'backend', 'json')
    if backend not in backends.BACKENDS.keys():
        raise exceptions.PiglitFatalError(
            'Backend is not valid\nvalid backends are: {}'.format(
                ' '.join(backends.BACKENDS.keys())))
    return backend


def _run_parser(input_):
    """ Parser for piglit run command """
    unparsed = parsers.parse_config(input_)[1]
    profiles = list(_get_profiles())

    # Set the parent of the config to add the -f/--config message
    parser = argparse.ArgumentParser(parents=[parsers.CONFIG])
    parser.add_argument("-n", "--name",
                        metavar="<test name>",
                        default=None,
                        help="Name of this test run")
    parser.add_argument("-d", "--dry-run",
                        action="store_false",
                        dest="execute",
                        help="Do not execute the tests")
    parser.add_argument('-b', '--backend',
                        default=_default_backend(),
                        choices=backends.BACKENDS.keys(),
                        help='select a results backend to use')
    parser.add_argument("-s", "--sync",
                        action="store_true",
                        help="Sync results to disk after every test")
    parser.add_argument("--junit_suffix",
                        type=str,
                        default="",
                        help="suffix string to append to each test name in junit")
    parser.add_argument('-o', '--overwrite',
                        dest='overwrite',
                        action='store_true',
                        help='If the results_path already exists, delete it')
    parser.add_argument("results_path",
                        type=path.realpath,
                        metavar="<Results Path>",
                        help="Path to results folder")
    log_parser = parser.add_mutually_exclusive_group()
    log_parser.add_argument('-v', '--verbose',
                            action='store_const',
                            const='verbose',
                            default='quiet',
                            dest='log_level',
                            help='DEPRECATED! Print more information during '
                                 'test runs. Use -l/--log-level instead')
    log_parser.add_argument("-l", "--log-level",
                            dest="log_level",
                            action="store",
                            choices=['quiet', 'verbose', 'dummy', 'http'],
                            default='quiet',
                            help="Set the logger verbosity level")

    grouped = itertools.groupby(unparsed, lambda x: x if x in profiles else None)
    main_args = parser.parse_args(next(grouped)[1])

    profile_args = []
    for p, a in grouped:
        if p is not None:
            profile_args.append((p, []))
        else:
            profile_args[-1][1].extend(list(a))

    return main_args, profile_args


def _create_metadata(args, name, profile_args):
    """Create and return a metadata dict for Backend.initialize()."""
    opts = dict(options.OPTIONS)
    opts['log_level'] = args.log_level
    metadata = {'options': opts}
    metadata['name'] = name
    metadata['system'] = core.collect_system_info()
    metadata['profiles'] = {p: a for p, a in profile_args}

    return metadata


def _disable_windows_exception_messages():
    """Disable Windows error message boxes for this and all child processes."""
    if sys.platform == 'win32':
        # This disables messages boxes for uncaught exceptions, but it will not
        # disable the message boxes for assertion failures or abort().  Those
        # are created not by the system but by the CRT itself, and must be
        # disabled by the child processes themselves.
        SEM_FAILCRITICALERRORS     = 0x0001
        SEM_NOALIGNMENTFAULTEXCEPT = 0x0004
        SEM_NOGPFAULTERRORBOX      = 0x0002
        SEM_NOOPENFILEERRORBOX     = 0x8000
        uMode = ctypes.windll.kernel32.SetErrorMode(0)
        uMode |= SEM_FAILCRITICALERRORS \
              |  SEM_NOALIGNMENTFAULTEXCEPT \
              |  SEM_NOGPFAULTERRORBOX \
              |  SEM_NOOPENFILEERRORBOX
        ctypes.windll.kernel32.SetErrorMode(uMode)


def _results_handler(path):
    """Handler for core.check_dir."""
    if os.path.isdir(path):
        shutil.rmtree(path)
    else:
        os.unlink(path)


@exceptions.handler
def run(input_):
    """ Function for piglit run command

    This is a function because it allows it to be shared between piglit-run.py
    and piglit run

    """
    args, profile_args = _run_parser(input_)
    _disable_windows_exception_messages()

    # Pass arguments into Options
    options.OPTIONS.execute = args.execute
    options.OPTIONS.sync = args.sync

    # Change working directory to the root of the piglit directory
    piglit_dir = path.dirname(path.realpath(sys.argv[0]))
    os.chdir(piglit_dir)

    # If the results directory already exists and if overwrite was set, then
    # clear the directory. If it wasn't set, then raise fatal error.
    try:
        core.check_dir(args.results_path,
                       failifexists=args.overwrite,
                       handler=_results_handler)
    except exceptions.PiglitException:
        raise exceptions.PiglitFatalError(
            'Cannot overwrite existing folder without the -o/--overwrite '
            'option being set.')
    options.OPTIONS.result_dir = args.results_path

    testrun = framework.profile.Collection(profile_args)

    backend = backends.get_backend(args.backend)(
        args.results_path,
        junit_suffix=args.junit_suffix)
    backend.initialize(_create_metadata(
        args,
        args.name or path.basename(args.results_path),
        profile_args))

    timer = framework.results.TimeAttribute()
    timer.start = time.time()

    testrun.run(args.log_level, backend)
    timer.end = time.time()
    backend.finalize({'time_elapsed': timer})

    print('Thank you for running Piglit!\n'
          'Results have been written to ' + args.results_path)


@exceptions.handler
def resume(input_):
    parser = argparse.ArgumentParser()
    parser.add_argument("results_path",
                        type=path.realpath,
                        metavar="<Results Path>",
                        help="Path to results folder")
    parser.add_argument("-f", "--config",
                        dest="config_file",
                        type=argparse.FileType("r"),
                        help="Optionally specify a piglit config file to use. "
                             "Default is piglit.conf")
    parser.add_argument("-n", "--no-retry",
                        dest="no_retry",
                        action="store_true",
                        help="Do not retry incomplete tests")
    args = parser.parse_args(input_)
    _disable_windows_exception_messages()

    results = backends.load(args.results_path)
    options.OPTIONS.execute = results.options['execute']
    options.OPTIONS.sync = results.options['sync']

    core.get_config(args.config_file)

    results.options['env'] = core.collect_system_info()
    results.options['name'] = results.name

    # Resume only works with the JSON backend
    backend = backends.get_backend('json')(
        args.results_path,
        file_start_count=len(results.tests) + 1)
    # Specifically do not initialize again, everything initialize does is done.

    # Don't re-run tests that have already completed, incomplete status tests
    # have obviously not completed.
    for name, result in six.iteritems(results.tests):
        if args.no_retry or result.result != 'incomplete':
            options.OPTIONS.exclude_tests.add(name)

    options.OPTIONS.result_dir = args.results_path
    testrun = framework.profile.Collection(six.iteritems(results.profiles))

    # This is resumed, don't bother with time since it won't be accurate anyway
    testrun.run(results.options['log_level'], backend)

    backend.finalize()

    print("Thank you for running Piglit!\n"
          "Results have been written to {0}".format(args.results_path))
