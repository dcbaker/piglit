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

""" Module providing tests for the core module """


from __future__ import print_function, absolute_import

from framework import results, status
import framework.tests.utils as utils


@utils.nose_generator
def test_generate_initialize():
    """ Generator that creates tests to initialize all of the classes in core

    In a compiled language the compiler provides this kind of checking, but in
    an interpreted language like python you don't have a compiler test. The
    unit tests generated by this function serve as a similar test, does this
    even work?

    """
    @utils.no_error
    def check(target):
        target()

    for target in [results.TestrunResult, results.TestResult]:
        check.description = \
            "results.{}: class initializes".format(target.__name__)
        yield check, target


def test_testresult_load_to_status():
    """results.TestResult: an initial status value is converted to a Status object"""
    result = results.TestResult.load({'result': 'pass'})
    assert isinstance(result['result'], status.Status), \
        "Result key not converted to a status object"
