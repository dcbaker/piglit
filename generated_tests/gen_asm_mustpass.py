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

import itertools
from mako.template import Template
import numpy as np
import arb_assembly as arb

def emit_test(path_base, suffix, template, inst, test_vectors, dest, sources):
    filename =  "{0}/{1}{2}.shader_test".format(path_base,
                                                inst.op_string.lower(),
                                                suffix)
    print(filename)
    f = open(filename, "w")
    f.write(Template(template).render(instruction =
                                      inst.getInstruction(dest, sources),
                                      test_vectors = test_vectors))
    f.close()
    return


def emit_set_tests(path_base, template, base_test_vectors,
                   fragment_program, saturate, nv):
    """Emit mustpass tests for "set" opcodes such as SGE."""

    sources = ["program.env[0]", "program.env[1]"]
    garbage = "program.env[2]"

    opcode_list = arb.set_opcodes(nv, False, filtered = True)
    for op in opcode_list:
        inst = op(saturate)
        program = arb.get_program_for_instruction(inst, "R0", sources,
                                                  garbage,
                                                  fragment_program, nv)

        test_vectors = []
        for [p0, p1, p2] in base_test_vectors:
            test_vectors.append([np.array(p0), np.array(p1)])

        arb.emit_test(path_base, template, inst.op_string.lower(),
                      m, program, test_vectors)

    return


def emit_abs_tests(path_base, template, base_test_vectors,
                   fragment_program, nv):
    """Emit mustpass tests for the ABS opcode.

    This set of tests is a little bit special because the base test vectors
    are modified in a way to guarantee that at least some of the operand
    values are negative."""

    sources = ["program.env[0]"]
    garbage = "program.env[1]"

    inst = arb.ABS_opcode(False)
    program = arb.get_program_for_instruction(inst, "R0", sources,
                                              garbage,
                                              fragment_program, nv)

    test_vectors = []
    for [p0, p1, p2] in base_test_vectors:
        test_vectors.append([np.array([p0[0], p0[1], -p0[0], -p0[1]])])

    arb.emit_test(path_base, template, inst.op_string.lower(),
                  m, program, test_vectors)

    return


def emit_dp4_tests(path_base, template, base_test_vectors,
                   fragment_program, saturate, nv):
    """Emit tests for the DP4 instruction

    The common usage of DP4 is to implement the any() function from GLSL.
    This takes a vector of logic values (i.e., 0.0 or 1.0 generated by either
    the SGE or SLT instruction) and returns zero if all the values were zero
    and non-zero otherwise.  This is done by taking the dot-product of the
    vector with itself.  Fragment programs may use the _SAT variant to
    automatically clamp the result to [0, 1].
    """
    sources = ["program.env[0]", "program.env[0]"]
    garbage = "program.env[1]"

    inst = arb.DP4_opcode(saturate)
    program = arb.get_program_for_instruction(inst, "R0", sources,
                                              garbage,
                                              fragment_program, nv)

    if not saturate:
        p = arb.get_program_for_instruction(arb.MIN_opcode(False),
                                            "R0",
                                            ["R0", "{1.0}.xxxx"],
                                            garbage,
                                            fragment_program,
                                            nv)
        program.append(p[1])

    test_vectors = []
    for i in range(len(base_test_vectors)):
        env = [np.array(base_test_vectors[i])]
        test_vectors.append(env)

    arb.emit_test(path_base, template, inst.op_string.lower() + "_mustpass",
                  m, program, test_vectors)
    return


def emit_mad_tests(path_base, template, base_test_vectors, fragment_program, nv):
    """The common usage of MAD in the complex test it to implement

        color = (pass) ? green : red;

    This is performed by

        MUL    r2, r1.x, {0.0, 1.0, 0.0, 1.0};
        MAD    result.color, r1.y, {1.0, 0.0, 0.0, 1.0}, r2;

    In this case, r1.y = 1 - r1.x, and r1.x is either 0.0 or 1.0.  After the
    first instruction, r2 will be either zero or green.  After the second
    instruction r2 will be either red or green.

    The other common usage of MAD in the test suite is to compress the range
    of values on [0, 1] to [0.25, 0.75].

    Since there are two main uses, two different sets of tests are generated.
    The first is written to mad_mustpass.shader_test, and the second is
    written to mad_mustpass2.shader_test."""

    zero  = np.array([0., 0., 0., 0.])
    one   = np.array([1., 1., 1., 1.])
    green = np.array([0., 1., 0., 1.])
    red   = np.array([1., 0., 0., 1.])

    test_vectors = [[one,  red, zero],
                    [zero, red, green]]

    sources = ["program.env[0]", "program.env[1]", "program.env[2]"]
    garbage = "program.env[3]"

    inst = arb.MAD_opcode(False)
    program = arb.get_program_for_instruction(inst, "R0", sources,
                                              garbage,
                                              fragment_program, nv)

    arb.emit_test(path_base, template, "mad_mustpass", m, program, test_vectors)

    # Generate the "compression" tests
    sources = ["program.env[0]", "program.env[1].x", "program.env[1].y"]
    garbage = "program.env[2]"

    program = arb.get_program_for_instruction(inst, "R0", sources,
                                              garbage,
                                              fragment_program, nv)

    test_vectors = []
    for [p0, p1, p2] in base_test_vectors:
        test_vectors.append([np.array(p0), np.array([0.5, 0.25, 0.0, 0.0])])

    arb.emit_test(path_base, template, "mad_mustpass2", m, program, test_vectors)
    return


def emit_max_tests(path_base, template, base_test_vectors, fragment_program, nv):
    """Emit mustpass tests for the MAX opcode.

    This set of tests is a little bit special because the base test vectors
    are modified in a way to guarantee that at least some of the operand
    values are negative."""

    sources = ["program.env[0]", "-program.env[0]"]
    garbage = "program.env[1]"

    inst = arb.MAX_opcode(False)
    program = arb.get_program_for_instruction(inst, "R0", sources,
                                              garbage,
                                              fragment_program, nv)

    test_vectors = []
    for [p0, p1, p2] in base_test_vectors:
        test_vectors.append([np.array([p0[0], p0[1], -p0[0], -p0[1]])])

    arb.emit_test(path_base, template, inst.op_string.lower() + "_mustpass",
                  m, program, test_vectors)

    return


def emit_min_tests(path_base, template, nv):
    """Emit mustpass tests for the MIN opcode.

    The MIN opcode is used in vertex shader tests the clamp values on the
    range [0, int(4 * num_subtests)] to be either 0 or 1.  This test simulates
    this by trying a large range of integer values on the range [0, big].
    """

    if nv != 0.0:
        # This is a bit of a hack.  Expect that c[1] gets properly set to
        # {junk, 0, 1, 0} and use the 1 from its Z component.
        sources = ["program.env[0]", "program.env[1].z"]
    else:
        sources = ["program.env[0]", "{1.0}.x"]

    garbage = "program.env[1]"

    inst = arb.MIN_opcode(False)
    program = arb.get_program_for_instruction(inst, "R0", sources,
                                              garbage, False, nv)

    test_vectors = []
    for i in range(16 * 16):
        test_vectors.append([np.array([float(i * 4 + 0),
                                       float(i * 4 + 1),
                                       float(i * 4 + 2),
                                       float(i * 4 + 3)])])

    arb.emit_test(path_base, template, inst.op_string.lower() + "_mustpass",
                  m, program, test_vectors)
    return


def emit_mul_tests(path_base, template, base_test_vectors, fragment_program, nv):
    """Emit mustpass tests for the MUL opcode.

    Other tests use MUL as a logical-and instruction.  In this usage, MUL is
    applied to a series of logic-level values (i.e., either 1.0 for true or
    0.0 for false).  This generates a test tries multiplication with all
    possible combinations of logic levels.  This is 16*16 = 256 total test
    vectors.
    """
    sources = ["program.env[0]", "program.env[1]"]
    garbage = "program.env[2]"

    inst = arb.MUL_opcode(False)
    program = arb.get_program_for_instruction(inst, "R0", sources,
                                              garbage,
                                              fragment_program, nv)

    test_vectors = []
    for i in range(len(base_test_vectors)):
        env = [np.array(base_test_vectors[i]), None]

        for j in range(len(base_test_vectors)):
            env[1] = np.array(base_test_vectors[j])
            test_vectors.append(env)

    arb.emit_test(path_base, template, inst.op_string.lower() + "_mustpass",
                  m, program, test_vectors)
    return


def emit_sub_tests(path_base, template, base_test_vectors,
                   fragment_program, nv):
    # The SUB instruction isn't added until VP1.1.
    if nv == 1.0:
        sources = ["program.env[0]", "-program.env[1]"]
        inst = arb.ADD_opcode(False)
    else:
        sources = ["program.env[0]", "program.env[1]"]
        inst = arb.SUB_opcode(False)

    garbage = "program.env[2]"

    program = arb.get_program_for_instruction(inst, "R0", sources,
                                              garbage,
                                              fragment_program, nv)

    test_vectors = []
    for i in range(len(base_test_vectors)):
        env = [np.array([1., 1., 1., 1.]),
               np.array(base_test_vectors[i])]
        test_vectors.append(env)

    arb.emit_test(path_base, template, inst.op_string.lower() + "_mustpass",
                  m, program, test_vectors)
    return


base_test_vectors = arb.generate_random_test_vectors(16 * 16)
logic_levels = list(itertools.product([0, 1], repeat = 4))

m = arb.machine()

# In the more complex tests, ABS, SLT, and SUB are used on arbitrary values.
# In addition, MAD, MUL, MOV, and SUB are used on "logic level" values (i.e.,
# vectors containing only the values 0.0 or 1.0.  Note that SUB appears in
# both lists, but only the later usage is tested here.  Testing the former
# usage in a meaningful way without using other instructions is difficult (if
# not impossible).

#             Test location               Saturate?  NV version (0 means ARB)
versions = [["spec/arb_vertex_program",   False,     0.0],
            ["spec/arb_fragment_program", False,     0.0],
            ["spec/arb_fragment_program", True,      0.0],
            ["spec/nv_vertex_program",    False,     1.0],
            ["spec/nv_vertex_program1_1", False,     1.1]
            ]

for (path_base, saturate, nv) in versions:
    f = open("{0}/simple.template".format(path_base))
    mad_template = f.read()
    f.close()

    f = open("{0}/mustpass.template".format(path_base))
    template = f.read()
    f.close()

    fragment = "fragment" in path_base
    emit_set_tests(path_base, template, base_test_vectors,
                   fragment, saturate, nv)

    if nv < 1.1:
        emit_dp4_tests(path_base, template, logic_levels,
                       fragment, saturate, nv)

    if not saturate:
        # NV_vertex_program lacks the ABS instruction.  It is added by
        # NV_vertex_program1_1.  Some program templates for NV_vertex_program
        # will use MAX with negative operands in place of ABS.
        if nv != 1.0:
            emit_abs_tests(path_base, template, base_test_vectors, fragment, nv)
        else:
            emit_max_tests(path_base, template, base_test_vectors, fragment, nv)

        # Even though there is no SUB instruction in NV_vertex_program, the
        # test generator creates an equivalent test that adds a negative
        # operand.  This matches the usage in the other test templates.
        emit_sub_tests(path_base, template, logic_levels, fragment, nv)

        if not fragment and nv < 1.1:
            emit_min_tests(path_base, template, nv)

        # Only emit these tests for ARB_vertex_program and NV_vertex_program.
        # There's no utility in emitting the same tests for
        # NV_vertex_program1_1 or later.
        if nv < 1.1:
            emit_mad_tests(path_base, mad_template, base_test_vectors,
                           fragment, nv)
            emit_mul_tests(path_base, template, logic_levels, fragment, nv)
