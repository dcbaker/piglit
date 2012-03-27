# coding=utf-8
#
# Copyright © 2011 Intel Corporation
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice (including the next
# paragraph) shall be included in all copies or substantial portions of the
# Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.  IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.

import copy
import itertools
from mako.template import Template
import numpy as np
import re
import arb_assembly as arb

def emit_test(path_base, template, name, nv, programs, test_vectors):
    """Generate a complete test from a program, set of inputs, and a template

    Position data for a square tile for each value in 'test_vectors' is
    generated.

    Each program in 'programs' is used to generate the expected output for
    each input in 'test_vectors'.

    All of this data, along with the programs, is passed to the Mako template.
    The resulting test is stored in path_base/name.shader_test."""

    filename =  "{0}/{1}.shader_test".format(path_base, name)

    print(filename)

    m = arb.machine(nv)

    tiles_per_row = int(np.ceil(np.sqrt(len(test_vectors))))
    if tiles_per_row < 16:
        tiles_per_row = 16

    w = 2. / tiles_per_row
    h = w

    x = np.linspace(-1, 1, 1 + tiles_per_row)
    locations = list(itertools.product(x[:tiles_per_row], repeat = 2))

    # Run the program for each set of inputs.  Record the value in R0 at the
    # end of program execution.  This will be the "expected" value for the
    # test template.
    test_vectors_with_results = []
    for i in range(len(test_vectors)):
        data = copy.deepcopy(test_vectors[i])

        m.reset(nv)
        m.address[0] = [True, np.array([int(data[0][0]), 0, 0, 0],
                                       dtype = np.int32)]
        m.env[0:len(data)] = data

        results = []
        for p in programs:
            m.execute_program(p)

            r0 = m.getOperand("R0")
            results.append(r0)

        [y, x] = locations[i]
        test_vectors_with_results.append([data, results, x, y, w, h])

    program_text = []
    for p in programs:
        program_text.append(arb.get_program_text(p))

    f = open(filename, "w")
    f.write(Template(template).render(programs = program_text,
                                      test_vectors = test_vectors_with_results))
    f.close()
    return


def emit_indirect_addressing_tests(path_base, suffix, template, sources,
                                   base_test_vectors, nv):
    # The set of test vectors will be the same for every instruction because
    # all of the inputs are stored in the array of constant inputs.  Each
    # instruction will fetch the correct number of operands from the array.
    test_vectors = []
    for [p0, p1, p2] in base_test_vectors:
        env = [np.array([3.0, 1.0, 0.0, 0.0]),
               np.array(p0),
               np.array(p1),
               np.array(p2),
               np.array([p0[0], p1[1], p2[2], p0[3]])]
        test_vectors.append(env)


    garbage = "program.env[{0}]".format(5 + 2 * len(all_sources))

    opcode_list = arb.common_opcodes(nv, False, filtered = True)
    for op in opcode_list:
        inst = op(False)


        programs = []
        for s in all_sources:
            sources = [s[0], s[1], "c[1]"]
            p = arb.get_program_for_instruction(inst, "R0", sources,
                                                garbage, False, nv)
            programs.append(p)


        arb.emit_test_from_multiple_programs(path_base, template,
                                             inst.op_string.lower() + suffix,
                                             nv, programs, test_vectors,
                                             False, False)
    return


arb_path_base = "spec/arb_vertex_program"
f = open("{0}/indirect.template".format(arb_path_base))
arb_template = f.read()
f.close()

nv_path_base = "spec/nv_vertex_program"
f = open("{0}/indirect.template".format(nv_path_base))
nv_template = f.read()
f.close()

nv11_path_base = "spec/nv_vertex_program1_1"
f = open("{0}/indirect.template".format(nv11_path_base))
nv11_template = f.read()
f.close()

base_test_vectors = arb.generate_random_test_vectors(8 * 8)

array_sources = ["c[1]", "c[A0.x]", "c[A0.x+1]"]

# Generate all combinations of two operands.  Remove the "c[1], c[1]" case
# because that is already handled by the non-ARL tests.
all_sources = list(itertools.product(array_sources, array_sources))[1:]

emit_indirect_addressing_tests(arb_path_base, "_indirect",
                               arb_template, all_sources, base_test_vectors,
                               0.0)
emit_indirect_addressing_tests(nv_path_base, "_indirect",
                               nv_template, all_sources, base_test_vectors,
                               1.0)
emit_indirect_addressing_tests(nv11_path_base, "_indirect",
                               nv11_template, all_sources, base_test_vectors,
                               1.1)

# It seems like there should be a better way to do this, but I'm not sure what
# it is.  We want the list of every possible addressing mode paired with
# "c[A0.x-1]", and we only want ("c[A0.x-1]", "c[A0.x-1]") to appear once in
# the list.
all_sources = list(itertools.product(["c[A0.x-1]"], array_sources))
all_sources += list(itertools.product(array_sources, ["c[A0.x-1]"]))
all_sources += [("c[A0.x-1]", "c[A0.x-1]")]

emit_indirect_addressing_tests(arb_path_base, "_indirect_negative_offset",
                               arb_template, all_sources, base_test_vectors,
                               0.0)
emit_indirect_addressing_tests(nv_path_base, "_indirect_negative_offset",
                               nv_template, all_sources, base_test_vectors,
                               1.0)
emit_indirect_addressing_tests(nv11_path_base, "_indirect_negative_offset",
                               nv11_template, all_sources, base_test_vectors,
                               1.1)
