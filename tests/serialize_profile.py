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

"""Script to serialize a profile into xml."""

from __future__ import (
    absolute_import, division, print_function, unicode_literals
)
import argparse
import importlib
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def main():
    """Serialize a profile's tests into XML."""
    parser = argparse.ArgumentParser()
    parser.add_argument('file', help='Filename to serialize.')
    args = parser.parse_args()

    xmlfile = os.path.splitext(args.file)[0] + '.profile.xml'

    builder = importlib.import_module(
        os.path.basename(os.path.splitext(args.file)[0])).make_testlist
    xml = builder().to_xml(os.path.basename(os.path.splitext(args.file)[0]))

    with open(xmlfile, 'wb') as f:
        try:
            xml.write(f, encoding='utf-8', xml_declaration=True,
                      pretty_print=True)
        except TypeError:
            # This is the don't have lxml case, so no pretty printing.
            xml.write(f, encoding='utf-8', xml_declaration=True)


if __name__ == '__main__':
    main()
