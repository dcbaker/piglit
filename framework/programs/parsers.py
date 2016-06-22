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

"""Shared parsers for use in multiple modules.

Much of this module is based on taking advantage of ArgumentParser's parent
argument and it's parse_known_args() method. The idea is that some parts of
parsers can be shared to reduce code duplication, either by parsing the
argumetns early and acting on them, or by inheriting from a parent object.

"""

from __future__ import (
    absolute_import, division, print_function, unicode_literals
)
import argparse
import os

from framework import core
from framework import exceptions


def parse_config(input_):
    """Convenience method for the CONFIG parser.

    This returns a two element tuple, the first element is a namespace with the
    known arguments in it (in this case the config_file), and the second is the
    remaining unparsed arguments. These remaining arguments should be passed to
    a new ArgumentParser instance.

    This will also call core.get_config on the config file. The parsed options
    are passed to ensure API compatibility

    """
    parsed, unparsed = CONFIG.parse_known_args(input_)

    # Read the config file
    # We want to read this before we finish parsing since some default options
    # are set in the config file.
    core.get_config(parsed.config_file)

    return parsed, unparsed


def _default_platform():
    """ Logic to determine the default platform to use

    This assumes that the platform can only be set on Linux, it probably works
    on BSD. This is only relevant if piglit is built with waffle support. When
    waffle support lands for Windows and if it ever happens for OSX, this will
    need to be extended.

    On Linux this will try in order,
    1) An option provided via the -p/--platform option (this is handled in
       argparse, not in this function)
    2) PIGLIT_PLATFORM from the environment
    3) [core]:platform from the config file
    4) mixed_glx_egl

    """
    if os.environ.get('PIGLIT_PLATFORM'):
        return os.environ.get('PIGLIT_PLATFORM')
    else:
        plat = core.PIGLIT_CONFIG.safe_get('core', 'platform', 'mixed_glx_egl')
        if plat not in core.PLATFORMS:
            raise exceptions.PiglitFatalError(
                'Platform is not valid\nvalid platforms are: {}'.format(
                    core.PLATFORMS))
        return plat


def _make_profile_parser():
    """Make the parser prototye for profiles to inherit from."""
    per_parser = argparse.ArgumentParser(add_help=False)
    per_parser.add_argument(
        "-t", "--include-tests",
        default=[],
        action="append",
        metavar="<regex>",
        dest="include_filter",
        help="Run only matching tests (can be used more than once)")
    per_parser.add_argument(
        "-x", "--exclude-tests",
        default=[],
        action="append",
        metavar="<regex>",
        dest="exclude_filter",
        help="Exclude matching tests (can be used more than once)")
    per_parser.add_argument(
        "--test-list",
        type=os.path.abspath,
        help="A file containing a list of tests to run")
    per_parser.add_argument(
        "--valgrind",
        action="store_true",
        help="Run tests in valgrind's memcheck")
    per_parser.add_argument(
        "--dmesg",
        action="store_true",
        help="Capture a difference in dmesg before and after each test. "
             "Implies -1/--no-concurrency")
    per_parser.add_argument(
        "--abort-on-monitored-error",
        action="store_true",
        dest="monitor",
        help="Enable monitoring according the rules defined in "
             "piglit.conf, and stop the execution when a monitored error "
             "is detected. Exit code 3. Implies -1/--no-concurrency")
    per_parser.add_argument(
        "-p", "--platform",
        choices=core.PLATFORMS,
        default=_default_platform(),
        help="Name of windows system passed to waffle")
    conc_parser = per_parser.add_mutually_exclusive_group()
    conc_parser.add_argument(
        '-c', '--all-concurrent',
        action="store_const",
        default="some",
        const="all",
        dest="concurrency",
        help="Run all tests concurrently")
    conc_parser.add_argument(
        "-1", "--no-concurrency",
        action="store_const",
        default="some",
        const="none",
        dest="concurrency",
        help="Disable concurrent test runs")

    return per_parser


PROFILE_PARSER = _make_profile_parser()

# parse the config file before any other options, this allows the config file
# to be used to set default values for the parser.
CONFIG = argparse.ArgumentParser(add_help=False)
CONFIG.add_argument("-f", "--config",
                    dest="config_file",
                    type=argparse.FileType("r"),
                    help="override piglit.conf search path")
