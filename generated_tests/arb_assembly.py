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
import math
import numpy as np
import random
import re

class machine:
    """Virtual machine for the execution of programs

    This is not a complete virtual machine.  It only handles getting and
    setting storage.  Temporary and address registers must have values set
    before they can be read.

    Temporary registers have name R0 through R11.  The address register has
    the name A0.  Program environment variables can be accessed using either
    'program.env[]' or 'c[]'.  The later is for compatibility with the NV
    extensions.  Program local variables can only be accessed using
    'program.local[]'.

    There is currently no support for either built-in variables, textures, or
    user-defined constants.
    """

    def __init__(self, nv = False):
        self.component_map = {"x": 0, "y": 1, "z": 2, "w": 3}
        self.reset(nv)
        return


    def reset(self, nv):
        """Reset the state of the virtual machine

        In NV mode, temporary registers and address registers are
        preinitialized to zero."""

        preinitialized_to_zero = nv

        self.registers = []
        for i in range(12):
            self.registers.append([preinitialized_to_zero,
                                   np.array([0., 0., 0., 0.])])

        self.address = [[preinitialized_to_zero,
                         np.array([0, 0, 0, 0], dtype = np.int32)]]

        self.env = []
        for i in range(96):
            self.env.append(np.array([0., 0., 0., 0.]))

        self.local = []
        for i in range(96):
            self.local.append(np.array([0., 0., 0., 0.]))

        self.attrib = []
        for i in range(16):
            self.attrib.append(np.array([0., 0., 0., 1.]))

        return


    def swizzleResult(self, vec, swiz):
        """Apply a swizzle to an array of four values."""

        if swiz == None:
            return vec
        if len(swiz) == 1:
            c = self.component_map[swiz]
            return np.array([vec[c], vec[c], vec[c], vec[c]])
        elif len(swiz) == 4:
            v = [0, 0, 0, 0]
            for i in range(4):
                c = self.component_map[swiz[i]]
                v[i] = vec[c]

            return np.array(v)
        else:
            raise Exception("Invalid swizzle string {0}".format(m.group(2)))

        return


    def calculateAddress(self, index):
        """Calculate the true array index for a given index expression

        If the expression contains an indirection via an address register, the
        current value of the address register will be read.  This may lead to
        an exception of the address register has not been initialized."""

        m = re.match("(\d+)|A(\d+).x\s*(([+-])\s*(\d+))?", index)

        if m.group(1) != None:
            return int(m.group(1))

        v = self.getOperand("A{0}.x".format(m.group(2)))
        if m.group(5) != None:
            if m.group(4) == "+":
                return int(v[0]) + int(m.group(5))
            else:
                return int(v[0]) - int(m.group(5))
        else:
            return int(v[0])

        return None


    def getOperand(self, operand):
        """Get the value of an operand

        Optional swizzles and negations are applied to the data retrieved."""

        if operand[0] == '-':
            scale = -1.
            operand = operand[1:]
        else:
            scale = 1.

        if operand[0] == '{':
            m = re.match("[{]\s*(\d+\.\d*)\s*(,\s*(\d+\.\d*)\s*,\s*(\d+\.\d*)\s*,\s*(\d+\.\d*))?\s*[}](\.[xyzw]+)?", operand)

            if m == None:
                raise Exception("Invalid immediate value {0}".format(operand))

            if m.group(2) != None:
                value = np.array([float(m.group(1)),
                                  float(m.group(3)),
                                  float(m.group(4)),
                                  float(m.group(5))])
            else:
                value = np.array([float(m.group(1)),
                                  float(m.group(1)),
                                  float(m.group(1)),
                                  float(m.group(1))])

            if m.group(6) != None:
                return scale * self.swizzleResult(value, m.group(6)[1:])

            return scale * value
        elif operand[0] == 'R':
            m = re.match("R(\d+)(\.[xyzw]+)?", operand)

            index = int(m.group(1))
            if index >= len(self.registers):
                raise Exception("Invalid temporary register {0}".format(operand))

            [initialized, value] = self.registers[index]
            if not initialized:
                raise Exception("Register {0} not initialized".format(operand))

            if m.group(2) != None:
                return scale * self.swizzleResult(value, m.group(2)[1:])

            return scale * value
        elif operand[0] == 'A':
            m = re.match("A(\d+)(\.[xyzw]+)?", operand)

            index = int(m.group(1))
            if index >= len(self.address):
                raise Exception("Invalid address register {0}".format(operand))

            if m.group(2) == None:
                    raise Exception("Missing address swizzle")

            if m.group(2) != ".x":
                    raise Exception("Invalid address swizzle string {0}".format(m.group(2)))

            [initialized, value] = self.address[index]
            if not initialized:
                raise Exception("Register {0} not initialized".format(operand))

            if scale != 1.:
                raise Exception("Cannot negate an address register")

            return value
        elif operand[0:13] == "program.local":
            m = re.match("program.local[[]([^]]+)](\.[xyzw]+)?", operand)

            index = self.calculateAddress(m.group(1))
            if index >= len(self.local):
                raise Exception("Invalid local parameter index {0}".format(operand))

            value = self.local[index]

            if m.group(2) != None:
                return scale * self.swizzleResult(value, m.group(2)[1:])

            return scale * value
        elif operand[0:11] == "program.env" or operand[0] == 'c':
            m = re.match("(program.env|c)[[]([^]]+)](\.[xyzw]+)?", operand)

            index = self.calculateAddress(m.group(2))
            if index >= len(self.local):
                raise Exception("Invalid environment parameter index {0}".format(operand))

            value = self.env[index]

            if m.group(3) != None:
                return scale * self.swizzleResult(value, m.group(3)[1:])

            return scale * value
        elif operand[0:13] == "vertex.attrib" or operand[0] == 'v' or operand[0:17] == "fragment.texcoord":
            m = re.match("(vertex\.attrib|v|fragment\.texcoord)[[]([0-9]+)](\.[xyzw]+)?", operand)

            index = self.calculateAddress(m.group(2))
            if index >= len(self.attrib):
                raise Exception("Invalid attribute index {0}".format(m.group(2)))

            value = self.attrib[index]

            if m.group(3) != None:
                return scale * self.swizzleResult(value, m.group(3)[1:])

            return scale * value

        raise Exception("Invalid operand name {0}".format(operand))
        return


    def setOperand(self, operand, value, saturate = False):
        """Write a value to a specified address or temporary register.

        The write mask specified in 'operand' is applied.  Conditional write
        masks (from NV_fragment_program_option) are not supported.  If the
        'saturate' flag is set, the values will be clamped to [0,1] before
        writing.

        The new contents of the destination operand are returned.
        """

        if saturate:
            value = value.clip(0.0, 1.0)

        if operand[0] == 'R':
            m = re.match("R(\d+)(\.x?y?z?w?)?", operand)

            index = int(m.group(1))
            if index >= len(self.registers):
                raise Exception("Invalid temporary register {0}".format(operand))

            [initialized, oldValue] = self.registers[index]

            if m.group(2) != None:
                # Strip off the leading '.'
                mask = m.group(2)[1:]
            else:
                mask = "xyzw"

            if len(mask) == 0:
                raise Exception("Invalid write mask")

            for c in mask:
                i = self.component_map[c]
                try:
                    oldValue[i] = value[i]
                except:
                    raise Exception("Cannot set index {0} value for {1} (was {2}), source is {3}".format(i, operand, oldValue, value))

            self.registers[index] = [True, oldValue]
        elif operand[0] == 'A':
            m = re.match("A(\d+)(\.x?y?z?w?)?", operand)

            index = int(m.group(1))
            if index >= len(self.address):
                raise Exception("Invalid address register {0}".format(operand))

            [initialized, oldValue] = self.address[index]

            if m.group(2) != None:
                # Strip off the leading '.'
                mask = m.group(2)[1:]
            else:
                mask = "x"

            if len(mask) == 0:
                raise Exception("Invalid write mask")
            elif mask != "x":
                raise Exception("Invalid write mask {0}".format(mask))

            for c in mask:
                i = self.component_map[c]
                oldValue[i] = value[i]

            self.address[index] = [True, oldValue]
        else:
            raise Exception("Invalid destination operand {0}".format(operand))

        return [oldValue[0], oldValue[1], oldValue[2], oldValue[3]]


    def execute_program(self, program):
        for (instruction, destination, sources) in program:
            try:
                instruction.evaluate(self, destination, sources)
            except Exception as e:
                print("At: {0} in\n{1}".format(instruction.getInstruction(destination,
                                                                  sources),
                                               get_program_text(program)))
                raise e

        return

class opcode:
    def __init__(self, name, numSources, saturate):
        if saturate:
            self.op_string = "{0}_SAT".format(name)
        else:
            self.op_string = name

        self.saturate = saturate
        self.numSources = numSources
        return

    @staticmethod
    def has_scalar_sources():
        raise Exception("Calling has_scalar_sources on base class")

    @staticmethod
    def destination_mask():
        return ""

    def evaluate(self, m, dest, sources):
        return None

    def getInstruction(self, dest, sources):
        return None


# Instruction that takes a single scalar argument
class s_opcode(opcode):
    def __init__(self, name, saturate):
        opcode.__init__(self, name, 1, saturate)

    @staticmethod
    def has_scalar_sources():
        return True

    def getInstruction(self, dest, sources):
        return "{opcode}\t{dest}, {s0};".format(opcode = self.op_string,
                                                dest = dest,
                                                s0 = sources[0])

# Instruction that takes two scalar arguments
class ss_opcode(opcode):
    def __init__(self, name, saturate):
        opcode.__init__(self, name, 2, saturate)

    @staticmethod
    def has_scalar_sources():
        return True

    def getInstruction(self, dest, sources):
        return "{opcode}\t{dest}, {s0}, {s1};".format(opcode = self.op_string,
                                                      dest = dest,
                                                      s0 = sources[0],
                                                      s1 = sources[1])

# Instruction that takes a single vector argument
class v_opcode(opcode):
    def __init__(self, name, saturate):
        opcode.__init__(self, name, 1, saturate)

    @staticmethod
    def has_scalar_sources():
        return False

    def getInstruction(self, dest, sources):
        return "{opcode}\t{dest}, {s0};".format(opcode = self.op_string,
                                                dest = dest,
                                                s0 = sources[0])

# Instruction that takes two vector arguments
class vv_opcode(opcode):
    def __init__(self, name, saturate):
        opcode.__init__(self, name, 2, saturate)

    @staticmethod
    def has_scalar_sources():
        return False

    def getInstruction(self, dest, sources):
        return "{opcode}\t{dest}, {s0}, {s1};".format(opcode = self.op_string,
                                                      dest = dest,
                                                      s0 = sources[0],
                                                      s1 = sources[1])

# Instruction that takes three vector arguments
class vvv_opcode(opcode):
    def __init__(self, name, saturate):
        opcode.__init__(self, name, 3, saturate)
        return

    @staticmethod
    def has_scalar_sources():
        return False

    def getInstruction(self, dest, sources):
        return "{opcode}\t{dest}, {s0}, {s1}, {s2};".format(opcode = self.op_string,
                                                            dest = dest,
                                                            s0 = sources[0],
                                                            s1 = sources[1],
                                                            s2 = sources[2])

class ADD_opcode(vv_opcode):
    def __init__(self, saturate):
        vv_opcode.__init__(self, "ADD", saturate)

    def evaluate(self, m, dest, sources):
        v0 = m.getOperand(sources[0])
        v1 = m.getOperand(sources[1])
        return m.setOperand(dest, v0 + v1, self.saturate)

class ABS_opcode(v_opcode):
    def __init__(self, saturate):
        v_opcode.__init__(self, "ABS", saturate)

    def evaluate(self, m, dest, sources):
        v0 = m.getOperand(sources[0])
        return m.setOperand(dest, abs(v0), self.saturate)

class CMP_opcode(vvv_opcode):
    def __init__(self, saturate):
        vvv_opcode.__init__(self, "CMP", saturate)

    def evaluate(self, m, dest, sources):
        v0 = m.getOperand(sources[0])
        v1 = m.getOperand(sources[1])
        v2 = m.getOperand(sources[2])

        result = np.array(v2)
        if v0[0] < 0.:
            result[0] = v1[0]

        if v0[1] < 0.:
            result[1] = v1[1]

        if v0[2] < 0.:
            result[2] = v1[2]

        if v0[3] < 0.:
            result[3] = v1[3]

        return m.setOperand(dest, result, self.saturate)

class COS_opcode(s_opcode):
    def __init__(self, saturate):
        s_opcode.__init__(self, "COS", saturate)

    def evaluate(self, m, dest, sources):
        v0 = m.getOperand(sources[0])
        r = math.cos(v0[0])
        return m.setOperand(dest, np.array([r, r, r, r]), self.saturate)

class DP3_opcode(vv_opcode):
    def __init__(self, saturate):
        vv_opcode.__init__(self, "DP3", saturate)

    def evaluate(self, m, dest, sources):
        v0 = m.getOperand(sources[0])
        v1 = m.getOperand(sources[1])

        v0[3] = 0.;
        result = np.dot(v0, v1)
        return m.setOperand(dest, np.array([result, result, result, result]),
                            self.saturate)

class DP4_opcode(vv_opcode):
    def __init__(self, saturate):
        vv_opcode.__init__(self, "DP4", saturate)

    def evaluate(self, m, dest, sources):
        v0 = m.getOperand(sources[0])
        v1 = m.getOperand(sources[1])
        result = np.dot(v0, v1)
        return m.setOperand(dest, np.array([result, result, result, result]),
                            self.saturate)

class DPH_opcode(vv_opcode):
    def __init__(self, saturate):
        vv_opcode.__init__(self, "DPH", saturate)

    def evaluate(self, m, dest, sources):
        v0 = m.getOperand(sources[0])
        v1 = m.getOperand(sources[1])

        v0[3] = 1.;
        result = np.dot(v0, v1)
        return m.setOperand(dest, np.array([result, result, result, result]),
                            self.saturate)

class DST_opcode(vv_opcode):
    def __init__(self, saturate):
        vv_opcode.__init__(self, "DST", saturate)

    def evaluate(self, m, dest, sources):
        v0 = m.getOperand(sources[0])
        v1 = m.getOperand(sources[1])

        result = np.array([1.0, v0[1] * v1[1], v0[2], v1[3]])
        return m.setOperand(dest, result, self.saturate)

class EX2_opcode(s_opcode):
    def __init__(self, saturate):
        s_opcode.__init__(self, "EX2", saturate)

    def evaluate(self, m, dest, sources):
        v0 = m.getOperand(sources[0])
        return m.setOperand(dest, np.exp2(v0), self.saturate)

class EXP_opcode(s_opcode):
    def __init__(self, saturate):
        s_opcode.__init__(self, "EXP", saturate)

    def evaluate(self, m, dest, sources):
        v0 = m.getOperand(sources[0])
        s = v0[0]
        result = np.array([float(1 << int(np.floor(s))),
                           s - np.floor(s),
                           np.exp2(s),
                           1.0])
        return m.setOperand(dest, result, self.saturate)

class FLR_opcode(v_opcode):
    def __init__(self, saturate):
        v_opcode.__init__(self, "FLR", saturate)

    def evaluate(self, m, dest, sources):
        v0 = m.getOperand(sources[0])
        return m.setOperand(dest, np.floor(v0), self.saturate)

class FRC_opcode(v_opcode):
    def __init__(self, saturate):
        v_opcode.__init__(self, "FRC", saturate)

    def evaluate(self, m, dest, sources):
        v0 = m.getOperand(sources[0])
        return m.setOperand(dest, v0 - np.floor(v0), self.saturate)

class LG2_opcode(s_opcode):
    def __init__(self, saturate):
        s_opcode.__init__(self, "LG2", saturate)

    def evaluate(self, m, dest, sources):
        v0 = m.getOperand(sources[0])
        r = np.log2(v0[0])
        return m.setOperand(dest, np.array([r, r, r, r]),
                            self.saturate)

class LIT_opcode(v_opcode):
    def __init__(self, saturate):
        v_opcode.__init__(self, "LIT", saturate)
        return

    def evaluate(self, m, dest, sources):
        # The ARB_vertex_program spec says LIT does:
        #
        #      tmp = VectorLoad(op0);
        #      if (tmp.x < 0) tmp.x = 0;
        #      if (tmp.y < 0) tmp.y = 0;
        #      if (tmp.w < -(128.0-epsilon)) tmp.w = -(128.0-epsilon);
        #      else if (tmp.w > 128-epsilon) tmp.w = 128-epsilon;
        #      result.x = 1.0;
        #      result.y = tmp.x;
        #      result.z = (tmp.x > 0) ? RoughApproxPower(tmp.y, tmp.w) : 0.0;
        #      result.w = 1.0;

        v = np.array(m.getOperand(sources[0]))
        if (v[1] < 0.0):
            v[1] = 0.0

        epsilon = 1e-5
        if (v[3] < -(128.0 - epsilon)):
            v[3] = -(128.0 - epsilon)
        elif (v[3] > (128.0 - epsilon)):
            v[3] = (128.0 - epsilon)

        if (v[0] <= 0.):
            v[0] = 0.
            r = 0.
        elif v[1] == 0. and v[3] == 0.:
            # The ARB_vertex_program spec also says:
            #
            #     Also, since 0^0 is defined to be 1, RoughApproxPower(0.0,
            #     0.0) will produce 1.0.
            r = 1.
        else:
            r = np.power(v[1], v[3])

        return m.setOperand(dest, np.array([1., v[0], r, 1.]), self.saturate)

class LOG_opcode(s_opcode):
    def __init__(self, saturate):
        s_opcode.__init__(self, "LOG", saturate)

    def evaluate(self, m, dest, sources):
        v0 = m.getOperand(sources[0])
        s = v0[0]
        r = np.log2(s)
        result = np.array([np.floor(r),
                           s / np.exp2(np.floor(r)),
                           r,
                           1.])

        return m.setOperand(dest, result, self.saturate)

class LRP_opcode(vvv_opcode):
    def __init__(self, saturate):
        vvv_opcode.__init__(self, "LRP", saturate)

    def evaluate(self, m, dest, sources):
        v0 = m.getOperand(sources[0])
        v1 = m.getOperand(sources[1])
        v2 = m.getOperand(sources[2])
        result = v0 * v1 + (1. - v0) * v2
        return m.setOperand(dest, result, self.saturate)

class MAD_opcode(vvv_opcode):
    def __init__(self, saturate):
        vvv_opcode.__init__(self, "MAD", saturate)

    def evaluate(self, m, dest, sources):
        v0 = m.getOperand(sources[0])
        v1 = m.getOperand(sources[1])
        v2 = m.getOperand(sources[2])
        return m.setOperand(dest, (v0 * v1) + v2, self.saturate)

class MAX_opcode(vv_opcode):
    def __init__(self, saturate):
        vv_opcode.__init__(self, "MAX", saturate)

    def evaluate(self, m, dest, sources):
        v0 = m.getOperand(sources[0])
        v1 = m.getOperand(sources[1])

        result = np.array([max(v0[0], v1[0]),
                           max(v0[1], v1[1]),
                           max(v0[2], v1[2]),
                           max(v0[3], v1[3])])
        return m.setOperand(dest, result, self.saturate)

class MIN_opcode(vv_opcode):
    def __init__(self, saturate):
        vv_opcode.__init__(self, "MIN", saturate)

    def evaluate(self, m, dest, sources):
        v0 = m.getOperand(sources[0])
        v1 = m.getOperand(sources[1])

        result = np.array([min(v0[0], v1[0]),
                           min(v0[1], v1[1]),
                           min(v0[2], v1[2]),
                           min(v0[3], v1[3])])
        return m.setOperand(dest, result, self.saturate)

class MOV_opcode(v_opcode):
    def __init__(self, saturate):
        v_opcode.__init__(self, "MOV", saturate)
        return

    def evaluate(self, m, dest, sources):
        v0 = m.getOperand(sources[0])
        try:
            return m.setOperand(dest, v0, self.saturate)
        except Exception as e:
            print("sources = {0}, v0 = {1}".format(sources[0], v0))
            raise e

class MUL_opcode(vv_opcode):
    def __init__(self, saturate):
        vv_opcode.__init__(self, "MUL", saturate)

    def evaluate(self, m, dest, sources):
        v0 = m.getOperand(sources[0])
        v1 = m.getOperand(sources[1])
        return m.setOperand(dest, v0 * v1, self.saturate)

class POW_opcode(ss_opcode):
    def __init__(self, saturate):
        ss_opcode.__init__(self, "POW", saturate)

    def evaluate(self, m, dest, sources):
        s0 = (m.getOperand(sources[0]))[0]
        s1 = m.getOperand(sources[1])[0]
        r = np.power(s0, s1)
        return m.setOperand(dest, np.array([r, r, r, r]), self.saturate)

class RCC_opcode(s_opcode):
    def __init__(self, saturate):
        s_opcode.__init__(self, "RCC", saturate)

    def evaluate(self, m, dest, sources):
        r = np.reciprocal(m.getOperand(sources[0])[0])

        if not np.signbit(r):
            # Clamp to the IEEE 32-bit binary values 0x5F800000 and 0x1F800000
            # per the NV_vertex_program1_1 spec.
            r = max(min(r, 1.884467e+019), 5.42101e-020)
        else:
            # Clamp to the IEEE 32-bit binary values 0xDF800000 and 0x9F800000
            # per the NV_vertex_program1_1 spec.
            r = min(max(r, -1.884467e+019), -5.42101e-020)

        result = np.array([r, r, r, r])
        return m.setOperand(dest, result, self.saturate)

class RCP_opcode(s_opcode):
    def __init__(self, saturate):
        s_opcode.__init__(self, "RCP", saturate)

    def evaluate(self, m, dest, sources):
        r = np.reciprocal(m.getOperand(sources[0])[0])

        result = np.array([r, r, r, r])
        return m.setOperand(dest, result, self.saturate)


class RFL_opcode(vv_opcode):
    def __init__(self, saturate):
        s_opcode.__init__(self, "RFL", saturate)

    def evaluate(self, m, dest, sources):
        axis = m.getOperand(sources[0])
        direction = m.getOperand(sources[1])

        axis[3] = 0.
        direction[3] = 0.

        s = 2. * np.dot(axis, direction) / np.dot(axis, axis)
        result = s * (axis - direction)
        return m.setOperand(dest, result, self.saturate)


class RSQ_opcode(s_opcode):
    def __init__(self, saturate):
        s_opcode.__init__(self, "RSQ", saturate)

    def evaluate(self, m, dest, sources):
        r = np.reciprocal(np.sqrt(m.getOperand(sources[0])[0]))

        result = np.array([r, r, r, r])
        return m.setOperand(dest, result, self.saturate)

class SCS_opcode(s_opcode):
    def __init__(self, saturate):
        s_opcode.__init__(self, "SCS", saturate)

    @staticmethod
    def destination_mask():
        return ".xy"

    def evaluate(self, m, dest, sources):
        v0 = m.getOperand(sources[0])
        s = math.sin(v0[0])
        c = math.cos(v0[0])
        return m.setOperand(dest,
                            np.array([c, s, float(0xdead), float(0xbeef)]),
                            self.saturate)


class SEQ_opcode(vv_opcode):
    def __init__(self, saturate):
        vv_opcode.__init__(self, "SEQ", saturate)

    def evaluate(self, m, dest, sources):
        v0 = m.getOperand(sources[0])
        v1 = m.getOperand(sources[1])

        result = np.array([ 0.0, 0.0, 0.0, 0.0 ])
        if (v0[0] == v1[0]):
            result[0] = 1.0

        if (v0[1] == v1[1]):
            result[1] = 1.0

        if (v0[2] == v1[2]):
            result[2] = 1.0

        if (v0[3] == v1[3]):
            result[3] = 1.0

        return m.setOperand(dest, result, self.saturate)


class SFL_opcode(vv_opcode):
    def __init__(self, saturate):
        vv_opcode.__init__(self, "SFL", saturate)

    def evaluate(self, m, dest, sources):
        result = np.array([ 0.0, 0.0, 0.0, 0.0 ])
        return m.setOperand(dest, result, self.saturate)


class SGE_opcode(vv_opcode):
    def __init__(self, saturate):
        vv_opcode.__init__(self, "SGE", saturate)

    def evaluate(self, m, dest, sources):
        v0 = m.getOperand(sources[0])
        v1 = m.getOperand(sources[1])

        result = np.array([ 0.0, 0.0, 0.0, 0.0 ])
        if (v0[0] >= v1[0]):
            result[0] = 1.0

        if (v0[1] >= v1[1]):
            result[1] = 1.0

        if (v0[2] >= v1[2]):
            result[2] = 1.0

        if (v0[3] >= v1[3]):
            result[3] = 1.0

        return m.setOperand(dest, result, self.saturate)


class SGT_opcode(vv_opcode):
    def __init__(self, saturate):
        vv_opcode.__init__(self, "SGT", saturate)

    def evaluate(self, m, dest, sources):
        v0 = m.getOperand(sources[0])
        v1 = m.getOperand(sources[1])

        result = np.array([ 0.0, 0.0, 0.0, 0.0 ])
        if (v0[0] > v1[0]):
            result[0] = 1.0

        if (v0[1] > v1[1]):
            result[1] = 1.0

        if (v0[2] > v1[2]):
            result[2] = 1.0

        if (v0[3] > v1[3]):
            result[3] = 1.0

        return m.setOperand(dest, result, self.saturate)

class SIN_opcode(s_opcode):
    def __init__(self, saturate):
        s_opcode.__init__(self, "SIN", saturate)

    def evaluate(self, m, dest, sources):
        v0 = m.getOperand(sources[0])
        r = math.sin(v0[0])
        return m.setOperand(dest, np.array([r, r, r, r]), self.saturate)


class SLE_opcode(vv_opcode):
    def __init__(self, saturate):
        vv_opcode.__init__(self, "SLE", saturate)

    def evaluate(self, m, dest, sources):
        v0 = m.getOperand(sources[0])
        v1 = m.getOperand(sources[1])

        result = np.array([ 0.0, 0.0, 0.0, 0.0 ])
        if (v0[0] <= v1[0]):
            result[0] = 1.0

        if (v0[1] <= v1[1]):
            result[1] = 1.0

        if (v0[2] <= v1[2]):
            result[2] = 1.0

        if (v0[3] <= v1[3]):
            result[3] = 1.0

        return m.setOperand(dest, result, self.saturate)


class SLT_opcode(vv_opcode):
    def __init__(self, saturate):
        vv_opcode.__init__(self, "SLT", saturate)

    def evaluate(self, m, dest, sources):
        v0 = m.getOperand(sources[0])
        v1 = m.getOperand(sources[1])

        result = np.array([ 0.0, 0.0, 0.0, 0.0 ])
        if (v0[0] < v1[0]):
            result[0] = 1.0

        if (v0[1] < v1[1]):
            result[1] = 1.0

        if (v0[2] < v1[2]):
            result[2] = 1.0

        if (v0[3] < v1[3]):
            result[3] = 1.0

        return m.setOperand(dest, result, self.saturate)


class SNE_opcode(vv_opcode):
    def __init__(self, saturate):
        vv_opcode.__init__(self, "SNE", saturate)

    def evaluate(self, m, dest, sources):
        v0 = m.getOperand(sources[0])
        v1 = m.getOperand(sources[1])

        result = np.array([ 0.0, 0.0, 0.0, 0.0 ])
        if (v0[0] != v1[0]):
            result[0] = 1.0

        if (v0[1] != v1[1]):
            result[1] = 1.0

        if (v0[2] != v1[2]):
            result[2] = 1.0

        if (v0[3] != v1[3]):
            result[3] = 1.0

        return m.setOperand(dest, result, self.saturate)


class STR_opcode(vv_opcode):
    def __init__(self, saturate):
        vv_opcode.__init__(self, "STR", saturate)

    def evaluate(self, m, dest, sources):
        result = np.array([1., 1., 1., 1.])
        return m.setOperand(dest, result, self.saturate)


class SUB_opcode(vv_opcode):
    def __init__(self, saturate):
        vv_opcode.__init__(self, "SUB", saturate)

    def evaluate(self, m, dest, sources):
        v0 = m.getOperand(sources[0])
        v1 = m.getOperand(sources[1])
        return m.setOperand(dest, v0 - v1, self.saturate)

class SWZ_opcode(opcode):
    def __init__(self, saturate):
        opcode.__init__(self, "SWZ", 1, saturate)

    def evaluate(self, m, dest, sources):
        v0 = m.getOperand(sources[0])

        result = [0., 0., 0., 0.]

        values = {"0": 0., "-0": 0., "1": 1., "-1": -1.,
                  "x": v0[0], "-x": -v0[0],
                  "y": v0[1], "-y": -v0[1],
                  "z": v0[2], "-z": -v0[2],
                  "w": v0[3], "-w": -v0[3]}

        for s in sources[1:]:
            result[i] = values[s]

        return

    def getInstruction(self, dest, sources):
        return "{opcode}\t{dest}, {s0}, {x}, {y}, {z}, {w};".format(opcode = self.op_string,
                                                                    dest = dest,
                                                                    s0 = sources[0],
                                                                    x = sources[1],
                                                                    y = sources[2],
                                                                    z = sources[3],
                                                                    w = sources[4])


class X2D_opcode(vvv_opcode):
    def __init__(self, saturate):
        vv_opcode.__init__(self, "X2D", saturate)

    def evaluate(self, m, dest, sources):
        v0 = m.getOperand(sources[0])
        v1 = m.getOperand(sources[1])
        v2 = m.getOperand(sources[2])

        x = v0[0] + (v1[0] * v2[0]) + (v1[1] * v2[1])
        y = v0[1] + (v1[0] * v2[2]) + (v1[1] * v2[3])

        result = np.array([x, y, x, y])
        return m.setOperand(dest, result, self.saturate)


class XPD_opcode(vv_opcode):
    def __init__(self, saturate):
        vv_opcode.__init__(self, "XPD", saturate)

    @staticmethod
    def destination_mask():
        return ".xyz"

    def evaluate(self, m, dest, sources):
        v0 = m.getOperand(sources[0])
        v1 = m.getOperand(sources[1])

        result = np.array([v0[1] * v1[2] - v0[2] * v1[1],
                           v0[2] * v1[0] - v0[0] * v1[2],
                           v0[0] * v1[1] - v0[1] * v1[0],
                           float(0xdead)])
        return m.setOperand(dest, result, self.saturate)


def random_vec4():
    return [np.trunc(random.random() * 100000.) / 100000.,
            np.trunc(random.random() * 100000.) / 100000.,
            np.trunc(random.random() * 100000.) / 100000.,
            np.trunc(random.random() * 100000.) / 100000.]


def generate_random_test_vectors(count):
    random.seed(math.pi)
    base_test_vectors = []
    for i in range(count):
        base_test_vectors.append([random_vec4(), random_vec4(), random_vec4()])

    return base_test_vectors


def common_opcodes(nv, fragment_program, filtered = False):
    """Get a list of the common opcode that don't require special inputs

    'nv' selects the version of NVIDIA program extensions.  0.0 means ARB
    programs.  Currently only 1.0 and 1.1 are recognized for vertex programs.

    'fragment_program' selects fragment program opcodes instead of vertex
    program opcodes.

    'filtered' means that only the opcodes added since the previous version
    should be returned.  This currently only has any affect on
    NV_vertex_program1_1."""

    if filtered and not fragment_program and nv == 1.1:
        return [DPH_opcode, SUB_opcode]

    # Opcodes supported by NV_vertex_program, ARB_vertex_program, and
    # ARB_fragment_program.
    opcode_list = [ADD_opcode, DP3_opcode, DP4_opcode, DST_opcode, LIT_opcode,
                   MAD_opcode, MAX_opcode, MIN_opcode, MOV_opcode, MUL_opcode]

    # NV_vertex_program lacks the DPH, SUB, and XPD instructions.  DPH and SUB
    # are added in NV_vertex_program1_1.  XPD exists in ARB shaders.
    if nv != 1.0:
        opcode_list.append(DPH_opcode)
        opcode_list.append(SUB_opcode)

    if nv == 0.0:
        opcode_list.append(XPD_opcode)

    # NV and ARB fragment programs add CMP and LRP instructions.
    if fragment_program:
        opcode_list.append(CMP_opcode)
        opcode_list.append(LRP_opcode)

    return opcode_list


def exp_and_log_opcodes(nv, fragment_program, filtered = False):
    """Get a list of the opcodes that need parameters similar to EXP and LOG.

    'nv' selects the version of NVIDIA program extensions.  0.0 means ARB
    programs.  Currently only 1.0 and 1.1 are recognized for vertex programs.

    'fragment_program' selects fragment program opcodes instead of vertex
    program opcodes.

    'filtered' means that only the opcodes added since the previous version
    should be returned.  This currently only has any affect on
    NV_vertex_program1_1."""

    if filtered and not fragment_program and nv == 1.1:
        return [RCC_opcode]

    if nv == 0.0:
        opcode_list = [EX2_opcode, FLR_opcode, FRC_opcode, LG2_opcode,
                       POW_opcode, RCP_opcode, RSQ_opcode]
    else:
        opcode_list = [RCP_opcode, RSQ_opcode]
        if nv >= 1.1:
            opcode_list.append(RCC_opcode)

    # From issue #5 in the ARB_fragment_program spec:
    #
    #     "...ARB_fragment_program removes the LOG and EXP rough approximation
    #     instructions and the ARL address register load instruction."
    if not fragment_program:
        opcode_list.append(EXP_opcode)
        opcode_list.append(LOG_opcode)

    return opcode_list


def set_opcodes(nv, fragment_program, filtered = False):
    """Get a list of opcodes for 'SET'-like instructions.

    This includes SGE and SLT.

    'nv' selects the version of NVIDIA program extensions.  0.0 means ARB
    programs.  Currently only 1.0 and 1.1 are recognized for vertex programs.

    'fragment_program' selects fragment program opcodes instead of vertex
    program opcodes.

    'filtered' means that only the opcodes added since the previous version
    should be returned.  This currently only has any affect on
    NV_vertex_program1_1."""

    if filtered and not fragment_program and nv == 1.1:
        return []
    else:
        return [SGE_opcode, SLT_opcode]


def emit_test(path_base, template, name, nv, program, test_vectors):
    """Generate a complete test from a program, set of inputs, and a template

    Position data for a square tile for each value in 'test_vectors' is
    generated.

    The program is used to generate the expected output for each input in
    'test_vectors'.

    All of this data, along with the program, is passed to the Mako template.
    The resulting test is stored in path_base/name.shader_test."""

    filename =  "{0}/{1}.shader_test".format(path_base, name)

    print(filename)

    m = machine(nv)

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
        data = test_vectors[i]

        m.env[0:len(data)] = data
        m.env[len(data)] = np.array([0., 0., 1., 0.])

        m.execute_program(program)

        r0 = m.getOperand("R0")

        # Calculate a value that does not appear in any of the expected
        # results.  This is used by (some) templates to preinitialize result
        # registers with impossible values to detect bad write mask handling.
        not_expected = 0.0
        for x in r0:
            if x == 0.0:
                not_expected += 11.
            else:
                not_expected += abs(x)

        [y, x] = locations[i]
        test_vectors_with_results.append([data, r0, not_expected, x, y, w, h])

    f = open(filename, "w")
    f.write(Template(template).render(program = get_program_text(program),
                                      test_vectors = test_vectors_with_results))
    f.close()
    return


def emit_test_from_multiple_programs(path_base, template, name, nv, programs,
                                     test_vectors, fragment, use_attrib):
    """Generate a complete test from a set of programs, set of inputs, and a template

    Position data for a square tile for each value in 'test_vectors' is
    generated.

    Each program in 'programs' is used to generate the expected output for
    each input in 'test_vectors'.

    All of this data, along with the programs, is passed to the Mako template.
    The resulting test is stored in path_base/name.shader_test."""

    filename =  "{0}/{1}.shader_test".format(path_base, name)

    print(filename)

    m = machine(nv)

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

        if use_attrib:
            if fragment:
                m.attrib[0:len(data)] = data
            else:
                # attrib[0] is the vertex position, and it isn't used
                m.attrib[1:1+len(data)] = data

        m.env[0:len(data)] = data

        results = []
        for p in programs:
            m.execute_program(p)

            r0 = m.getOperand("R0")
            results.append(r0)

        # Calculate a value that does not appear in any of the expected
        # results.  This is used by (some) templates to preinitialize result
        # registers with impossible values to detect bad write mask handling.
        not_expected = 0.0
        for v in results:
            for x in v:
                if x == 0.0:
                    not_expected += 11.
                else:
                    not_expected += abs(x)

        [y, x] = locations[i]
        test_vectors_with_results.append([data, results,
                                          not_expected,
                                          x, y, w, h])

    program_text = []
    for p in programs:
        program_text.append(get_program_text(p))

    f = open(filename, "w")
    f.write(Template(template).render(programs = program_text,
                                      test_vectors = test_vectors_with_results))
    f.close()
    return


def get_program_text(program):
    """Get a textual listing of a program."""

    program_text = ""
    for (instruction, destination, sources) in program:
        inst_text = instruction.getInstruction(destination, sources)
        program_text = ''.join([program_text, "\t", inst_text, "\n"])

    return program_text


def get_program_for_instruction(inst, dest, sources, garbage, fragment_program,
                                nv):
    """Generate a program snippet for a single instruction

    'garbage' is a value or a register containing a value that does not appear
    in the expected result in its X compnent and zero in its Y component.  For
    example, if the expected result is {0.59806, 0.64158, 0.07227, 0.95623},
    'garbage' could name a program environment register containing {-7, 0, 0,
    0}.  This is used so that fields that are supposed to be written by the
    instruction are preinitialized to some impossible value and fields not
    written are preinitialized to zero.  Fields may not be written if the
    incoming write mask on 'dest' does not select them or if the opcode does
    not generate them (e.g., XPD and SCS).

    In NV_vertex_program or NV_vertex_program1_1 additional instructions may
    be generated to load some constant values into temporary registers.
    """

    program = []

    # Merge the mask generated by the instruction with the mask selected by
    # the destination.
    inst_mask = inst.destination_mask()
    (dest_base, sep, dest_mask) = dest.partition(".")

    if dest_mask == None:
        dest_mask = "xyzw"

    if inst_mask == '':
        inst_mask = ".xyzw"

    # Calculate the intersection of the instruction mask and the destination
    # mask.  If the result is empty, use the mask generated by the
    # instruction.
    dest_mask = dest_mask.translate(None, "xyzw".translate(None, inst_mask))
    if dest_mask == "":
        dest_mask = inst_mask[1:]

    # Generate a swizzle with 'x' for each component written by the updated
    # destination mask and 'y' for all other components.
    component_map = {"x": 0, "y": 1, "z": 2, "w": 3}
    garbage_swizzle = ["y", "y", "y", "y"]
    for c in dest_mask:
        index = component_map[c]
        garbage_swizzle[index] = 'x'

    if nv != 0.0 and not fragment_program:
        garbage = re.sub("program\.env", "c", garbage)

    program.append([MOV_opcode(False),
                    dest_base,
                    [garbage + '.' + ''.join(garbage_swizzle)]])

    # Merge the destination register and the updated write mask.
    if dest_mask == "xyzw":
        dest = dest_base
    else:
        dest = '.'.join([dest_base, dest_mask])

    # NV_vertex_program cannot read from more than one program constant
    # register in a single instruction.  Generate extra moves to load
    # addtional constant register values to temporary registers.
    if nv != 0.0 and not fragment_program:
        num_constants = 0
        seen_constants = {}
        for i in range(inst.numSources):
            sources[i] = re.sub("vertex\.attrib", "v", sources[i])
            src = re.sub("program\.env", "c", sources[i])
            m = re.match("(-)?c[[]([^]]+)](\.[xyzw]+)?", src)
            if m:
                if m.group(1):
                    neg = "-"
                else:
                    neg = ""

                index = str(m.group(2))

                if m.group(3):
                    swizzle = m.group(3)
                else:
                    swizzle = ''

                # If this is the first address, don't fetch it.  Add it to the
                # hash anyway.  This prevents spurious fetches to temporary
                # registers for cases like
                #
                #     ADD  R0, c[0].y, c[0].x;
                if num_constants == 0:
                    num_constants = 1
                    seen_constants[index] = ''.join(["c[", index, "]"])

                # If this address has not already been fetched into a
                # temporary register, emit an instruction to fetch it.  Try
                # not to double fetch.  This helps improve cases like
                #
                #     MAD  R0, c[0], c[1].x, c[1]y;
                #
                # by only fetcing c[1] into a single temporary register.
                if not seen_constants.has_key(index):
                    temp = "R{0}".format(num_constants)
                    program.append([MOV_opcode(False),
                                    "R{0}".format(num_constants),
                                    [''.join(['c[', index, ']'])]])
                    seen_constants[index] = temp
                    num_constants += 1

                temp = seen_constants[index]
                sources[i] = ''.join([neg, temp, swizzle])

    program.append([inst, dest, sources])
    return program
