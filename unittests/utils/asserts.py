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

"""Various assert methods to massage core-like objects for nose's rich asserts.

Nose provides a number of rich assert methods (which are actually wrappers
around the underlying unittest asserts) which are very useful since they can
compare specific details of types and provide detail comparisons. The problem
is that they assert that they are passed a specific type rather than a
type-like object.

"""

from __future__ import (
    absolute_import, division, print_function, unicode_literals
)

import nose.tools as nt


def list_eq(first, second):
    """Assert two list-like objects are the same."""
    nt.assert_list_equal(list(first), list(second))


def dict_eq(first, second):
    """Assert two dict-like objects are the same."""
    nt.assert_dict_equal(dict(first), dict(second))
