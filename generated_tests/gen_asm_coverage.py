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
import math
import numpy as np
import random
import re
from mako.template import Template
import arb_assembly as arb

def emit_common_tests(path_base, template, base_test_vectors,
                      fragment_program, saturate, nv):
    sources = ["program.env[0]", "program.env[1]", "program.env[2]"]

    garbage = "program.env[{0}]".format(3 + 2 * len(masks_and_swizzles))

    opcode_list = arb.common_opcodes(nv, fragment_program, filtered = True)
    for op in opcode_list:
        inst = op(saturate)

        programs = []
        for (mask, swiz0, swiz1, swiz2) in masks_and_swizzles:
            swizzled_sources = [sources[0] + swiz0,
                                sources[1] + swiz1,
                                sources[2] + swiz2]
            dest = "R0" + mask

            p = arb.get_program_for_instruction(inst, dest, swizzled_sources,
                                                garbage,
                                                fragment_program, nv)
            programs.append(p)

        test_vectors = []
        for [p0, p1, p2] in base_test_vectors:
            env = []

            if op == arb.LIT_opcode:
                # The spec says that the exponent (the w component) is clamped
                # to "[-(128-epsilon), 128-epsilon], but it never defines a
                # value for epsilon.  Because if this exponents larger than
                # 127ish can never produce predictable values.  Avoid
                # generating them altogether.
                env.append(np.array([p0[0], p0[1], 0.,
                                     p0[3] * (128. - (1./256.))]))
            else:
                env.append(np.array(p0))

            if inst.numSources >= 2:
                env.append(np.array(p1))

            if inst.numSources >= 3:
                env.append(np.array(p2))

            test_vectors.append(env)

        arb.emit_test_from_multiple_programs(path_base, template,
                                             inst.op_string.lower(),
                                             nv, programs, test_vectors,
                                             fragment_program, False)
    return


def emit_exp_and_log_tests(path_base, template, base_test_vectors,
                           fragment_program, saturate, nv):
    opcode_list = arb.exp_and_log_opcodes(nv, fragment_program,
                                          filtered = True)
    for op in opcode_list:
        inst = op(saturate)

        if op == arb.RCC_opcode:
            print("Note: Numpy may generate several 'divide by zero' warnings.  These are\n      normal and can be ignored.")

        # Of the instructions handled by this loop, all but FLR and FRC
        # require a single scalar operand.
        if not op.has_scalar_sources():
            sources = ["program.env[0]"]
        else:
            # POW is the only instruction that uses the second operand.  The
            # others will just ignore it.
            sources = ["program.env[0].x", "program.env[0].y"]

        garbage = "program.env[1]"

        programs = []
        for (mask, swiz0, swiz1, swiz2) in masks_and_swizzles:
            dest = "R0" + mask

            # The swizzles aren't actually used because several of the opcodes
            # are really twitchy about their inputs (see RCP, RSQ, LG2, LOG,
            # EX2, EXP, and POW handling below).
            p = arb.get_program_for_instruction(inst, dest, sources, garbage,
                                                fragment_program, nv)
            programs.append(p)


        test_vectors = []
        for [p0, p1, p2] in base_test_vectors:
            # Testing FLR and FRC on operands that are always in [0, 1) is
            # just silly.  It's also a little silly for EX2, EXP, and POW.
            # Expand the range of the values so that these instructions do
            # something useful.
            p = np.trunc(1000.0 * np.array(p0)) / 255.

            # Fix some operands values to prevent cases of "undefined results"
            # in the opcode definitions.
            #
            # NOTE: Do *NOT* include RCC_opcode in the list of exclusions!
            if op == arb.RCP_opcode or op == arb.RSQ_opcode:
                while abs(p[0]) < 1e-6:
                    p[0] = random.random()
            elif op == arb.LG2_opcode or op == arb.LOG_opcode:
                while p[0] < 1e-11:
                    p[0] = random.random()

            # Smashing these (unused) components to zero causes the generated
            # test file to be a little bit smaller.
            if op == arb.POW_opcode:
                p[1] = p1[0] * 10.0
                p[2] = 0.
                p[3] = 0.
            elif op != arb.FLR_opcode and op != arb.FRC_opcode:
                p[1] = 0.
                p[2] = 0.
                p[3] = 0.

            test_vectors.append([p])

        arb.emit_test_from_multiple_programs(path_base, template,
                                             inst.op_string.lower(),
                                             nv, programs, test_vectors,
                                             fragment_program, False)
    return


def emit_trig_tests(path_base, template, base_test_vectors, saturate):
    """Generate tests for SIN, COS, and SCS opcodes

    SIN, COS, and SCS have slightly different behavior.  SIN and COS operate
    on arbitrary values while SCS expects values on the range [-PI, PI].
    Values outside that range may or may not produce valid results.  Generate
    two sets of test.  The first set tests all three opcodes with values in
    [-PI, PI].  The second set tests only SIN and COS with values on the range
    [-10*PI, 10*PI]."""

    nv = 0.0
    fragment_program = True
    zero = "{0.}.x"

    sources = ["program.env[0].x"]
    garbage = "program.env[1]"
    tiles = 25
    bias = (2. * math.pi) / (2. * tiles)

    for op in [arb.COS_opcode, arb.SCS_opcode, arb.SIN_opcode]:
        inst = op(saturate)
        dest = "R0{0}".format(op.destination_mask())

        program = arb.get_program_for_instruction(inst, "R0", sources, garbage,
                                                  fragment_program, nv)

        test_vectors = []
        for offset in np.linspace(.0, bias, tiles):
            for angle in np.linspace(-math.pi, math.pi - bias, tiles):
                test_vectors.append([np.array([angle + offset, 0., 0., 0.])])

        arb.emit_test(path_base, template, inst.op_string.lower(),
                      nv, program, test_vectors)


    for op in [arb.COS_opcode, arb.SIN_opcode]:
        inst = op(saturate)
        dest = "R0"

        program = arb.get_program_for_instruction(inst, "R0", sources, garbage,
                                                  fragment_program, nv)

        test_vectors = []
        for offset in np.linspace(.0, bias, tiles):
            for angle in np.linspace(-10. * math.pi, (10. * math.pi) - bias,
                                      tiles):
                test_vectors.append([np.array([angle + offset, 0., 0., 0.])])

        arb.emit_test(path_base, template,
                      inst.op_string.lower() + "_expanded_domain",
                      nv, program, test_vectors)

    return


base_test_vectors = arb.generate_random_test_vectors(16 * 16)

# Generate a set of swizzles that will allow the resulting full program to fit
# within the instruction count limits.  These are the limits defined by the
# extension specifications.  They do *NOT* allow for programs that compile but
# use too many native instructions to fail.  Specifically, ARB_vertex_program
# says:
#
#     "Programs that satisfy the program resource limits described above, but
#     whose native resource usage exceeds one or more native resource limits,
#     are guaranteed to load but may execute suboptimally."
#
# The limits are:
#
#     ARB_vertex_program          >= 128
#     ARB_fragment_program        >= 72
#     NV_vertex_program           128
#     NV_vertex_program1_1        128
#     NV_fragment_program_option  >= 1024
#
# The templates have the following worst-case counts for each program target:
#
#                                 1st step  Remaining  Final   Max. n
#                                           n-1 steps
#     ARB_vertex_program          2 + 4     2 + 5      5       17
#     ARB_fragment_program        2 + 4     2 + 5      3       10
#     NV_vertex_program           4 + 4     4 + 5      5       13
#     NV_vertex_program1_1        4 + 4     4 + 5      5       13
#     NV_fragment_program_option  TBD       TBD        TBD     146?

all_swizzles = []
for s in itertools.product("xyzw", repeat = 4):
    all_swizzles.append('.' + ''.join(s))

all_masks = [".xyzw",	# 1111
             ".xyz",	# 1110
             ".xyw",	# 1101
             ".xy",	# 1100
             ".xzw",	# 1011
             ".xz",	# 1010
             ".xw",	# 1001
             ".x",	# 1000
             ".yzw",	# 0111
             ".yz",	# 0110
             ".yw",	# 0101
             ".y",	# 0100
             ".zw",	# 0011
             ".z",	# 0010
             ".w"]	# 0001

#             Test location               Max         Saturate?  NV version
#                                         iterations             (0 means ARB)
versions = [["spec/arb_vertex_program",   17,         False,     0.0],
            ["spec/arb_fragment_program", 10,         False,     0.0],
            ["spec/arb_fragment_program", 10,         True,      0.0],
            ["spec/nv_vertex_program",    13,         False,     1.0],
            ["spec/nv_vertex_program1_1", 13,         False,     1.1]]

for (path_base, iterations, saturate, nv) in versions:
    f = open("{0}/binary_result.template".format(path_base))
    template = f.read()
    f.close()

    fragment_program = "fragment" in path_base

    # Always test the empty mask and empty swizzles first
    masks_and_swizzles = [["", "", "", ""]]
    for i in range(1, iterations):
        masks_and_swizzles.append([all_masks[(i * 3) % len(all_masks)],
                                   all_swizzles[(i * 7)  % len(all_swizzles)],
                                   all_swizzles[(i * 11) % len(all_swizzles)],
                                   all_swizzles[(i * 13) % len(all_swizzles)]])

    emit_common_tests(path_base, template, base_test_vectors,
                      fragment_program, saturate, nv)
    emit_exp_and_log_tests(path_base, template, base_test_vectors,
                           fragment_program, saturate, nv)

    if fragment_program:
        f = open("{0}/trig.template".format(path_base))
        template = f.read()
        f.close()

        emit_trig_tests(path_base, template, base_test_vectors, saturate)
