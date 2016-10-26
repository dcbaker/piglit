#!/usr/bin/env python
# encoding=utf-8
# Copyright © 2016 Intel Corporation

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

"""Script to find all declarative test files.

This script finds shader_test, glslparsertest, or asmparsertest files and
writes the list to a files. It is used in CMake to know when to trigger a
rebuild of the profile.xml files.  It doesn't check the generated tests because
it is already possible rely on CMake's targets to trigger a rebuild of the
profiles if any of those change.
"""

# XXX: what if a file changes, should we take a crc32 sum instead of the name?

from __future__ import (
    absolute_import, division, print_function, unicode_literals
)
import argparse
import os

LOC = os.path.dirname(__file__)


def main():
    """parses args and calls the right mode."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'mode',
        choices=['gl', 'cl'],
        help="Choose either OpenGL or OpenCL mode.")
    args = parser.parse_args()

    if args.mode == 'gl':
        opengl()
    elif args.mode == 'cl':
        opencl()


def opengl():
    # Store all tests in a list and sort them before writing, which makes it
    # less likely to cause spurious rebuilds of the profile.xml files, some of
    # which take a long time to build.
    tests = []

    for dirpath, _, filenames in os.walk(LOC):
        if dirpath.startswith('utils'):
            continue

        for filename in filenames:
            ext = os.path.splitext(filename)[1]

            # This will mark a few files that are .frag and .vert that aren't
            # actually glslparser tests, they're shaders included in C files.
            # that's fine
            if ext in ['.vert', '.tesc', '.tese', '.geom', '.frag', '.comp',
                       '.shader_test']:
                tests.append(os.path.join(dirpath, filename))

            # We really only want to find asmparsertests, if only they had a
            # unique name and not .txt
            elif ext == '.txt.' and not filename.startswith('CMake'):
                tests.append(os.path.join(dirpath, filename))

    with open(os.path.join(LOC, 'opengl-declarative-files.list'), 'w') as f:
        for test in sorted(tests):
            f.write(test)
            f.write('\n')


def opencl():
    # Store all tests in a list and sort them before writing, which makes it
    # less likely to cause spurious rebuilds of the profile.xml files, some of
    # which take a long time to build.
    tests = []

    for dirpath, _, filenames in os.walk(LOC):
        if dirpath.startswith('utils'):
            continue

        for filename in filenames:
            ext = os.path.splitext(filename)[1]

            # This will mark a few files that are .frag and .vert that aren't
            # actually glslparser tests, they're shaders included in C files.
            # that's fine
            if ext in ['.cl', '.program_test']:
                tests.append(os.path.join(dirpath, filename))

    with open(os.path.join(LOC, 'opencl-declarative-files.list'), 'w') as f:
        for test in sorted(tests):
            f.write(test)
            f.write('\n')


if __name__ == '__main__':
    main()
