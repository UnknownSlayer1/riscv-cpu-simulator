"""RV32I CPU simulator: a small, readable single-cycle-style simulator.

Supports the RV32I base integer ISA subset needed for real programs:
  R: add, sub, sll, slt, sltu, xor, srl, sra, or, and
  I: addi, slti, sltiu, xori, ori, andi, slli, srli, srai,
     lb, lh, lw, lbu, lhu, jalr
  S: sb, sh, sw
  B: beq, bne, blt, bge, bltu, bgeu
  U: lui, auipc
  J: jal
  System: ecall (halts the simulator, a0 is the exit code)

Memory is byte-addressable, little-endian, 64 KiB by default.
Registers are x0-x31; x0 is hard-wired to zero.
"""

MASK32 = 0xFFFFFFFF


def sign_extend(value, bits):
    """Sign-extend a `bits`-wide value to a Python int."""
    if value & (1 << (bits - 1)):
        return value - (1 << bits)
    return value


def to_u32(value):
    return value & MASK32


def to_s32(value):
    value &= MASK32
    return value - (1 << 32) if value & 0x80000000 else value


class Memory:
    def __init__(self, size=64 * 1024):
        self.data = bytearray(size)

    def load(self, addr, size):
        if addr < 0 or addr + size > len(self.data):
            raise IndexError(f"memory access out of bounds: 0x{addr:08x}")
        return int.from_bytes(self.data[addr:addr + size], "little")

    def store(self, addr, size, value):
        if addr < 0 or addr + size > len(self.data):
            raise IndexError(f"memory access out of bounds: 0x{addr:08x}")
        self.data[addr:addr + size] = (value & ((1 << (8 * size)) - 1)).to_bytes(size, "little")


class CPU:
    def __init__(self, mem_size=64 * 1024, max_steps=100000):
        self.regs = [0] * 32
        self.pc = 0
        self.mem = Memory(mem_size)
        self.max_steps = max_steps
        self.steps = 0
        self.halted = False
        self.trace = []

    # -- register helpers -------------------------------------------------
    def _set_reg(self, rd, value):
        if rd != 0:
            self.regs[rd] = to_u32(value)

    # -- program loading --------------------------------------------------
    def load_program(self, words, base=0):
        """Load a list of 32-bit instruction words at `base` (default 0)."""
        for i, word in enumerate(words):
            self.mem.store(base + 4 * i, 4, word)
        self.pc = base

    def load_bytes(self, data, base=0):
        for i, byte in enumerate(data):
            self.mem.store(base + i, 1, byte)

    # -- one step ---------------------------------------------------------
    def step(self, trace=False):
        if self.halted:
            return False
        instr = self.mem.load(self.pc, 4)
        opcode = instr & 0x7F
        rd = (instr >> 7) & 0x1F
        funct3 = (instr >> 12) & 0x7
        rs1 = (instr >> 15) & 0x1F
        rs2 = (instr >> 20) & 0x1F
        funct7 = (instr >> 25) & 0x7F
        next_pc = self.pc + 4

        if trace:
            self.trace.append((self.pc, instr))

        if opcode == 0x33:  # R-type
            a, b = self.regs[rs1], self.regs[rs2]
            if funct3 == 0x0:
                result = (a - b) if funct7 == 0x20 else (a + b)
            elif funct3 == 0x1:
                result = a << (b & 0x1F)
            elif funct3 == 0x2:
                result = 1 if to_s32(a) < to_s32(b) else 0
            elif funct3 == 0x3:
                result = 1 if a < b else 0
            elif funct3 == 0x4:
                result = a ^ b
            elif funct3 == 0x5:
                result = (to_s32(a) >> (b & 0x1F)) if funct7 == 0x20 else (a >> (b & 0x1F))
            elif funct3 == 0x6:
                result = a | b
            elif funct3 == 0x7:
                result = a & b
            else:
                raise ValueError(f"unknown funct3 {funct3} at pc 0x{self.pc:08x}")
            self._set_reg(rd, result)

        elif opcode == 0x13:  # I-type ALU
            imm = sign_extend((instr >> 20) & 0xFFF, 12)
            a = self.regs[rs1]
            if funct3 == 0x0:
                result = a + imm
            elif funct3 == 0x1:
                result = a << (imm & 0x1F)
            elif funct3 == 0x2:
                result = 1 if to_s32(a) < imm else 0
            elif funct3 == 0x3:
                result = 1 if a < (imm & MASK32) else 0
            elif funct3 == 0x4:
                result = a ^ imm
            elif funct3 == 0x5:
                shamt = imm & 0x1F
                result = (to_s32(a) >> shamt) if funct7 == 0x20 else (a >> shamt)
            elif funct3 == 0x6:
                result = a | imm
            elif funct3 == 0x7:
                result = a & imm
            else:
                raise ValueError(f"unknown funct3 {funct3} at pc 0x{self.pc:08x}")
            self._set_reg(rd, result)

        elif opcode == 0x03:  # loads
            imm = sign_extend((instr >> 20) & 0xFFF, 12)
            addr = to_u32(self.regs[rs1] + imm)
            if funct3 == 0x0:
                value = sign_extend(self.mem.load(addr, 1), 8)
            elif funct3 == 0x1:
                value = sign_extend(self.mem.load(addr, 2), 16)
            elif funct3 == 0x2:
                value = self.mem.load(addr, 4)
            elif funct3 == 0x4:
                value = self.mem.load(addr, 1)
            elif funct3 == 0x5:
                value = self.mem.load(addr, 2)
            else:
                raise ValueError(f"unknown load funct3 {funct3} at pc 0x{self.pc:08x}")
            self._set_reg(rd, value)

        elif opcode == 0x23:  # stores
            imm = sign_extend(((instr >> 25) << 5) | ((instr >> 7) & 0x1F), 12)
            addr = to_u32(self.regs[rs1] + imm)
            if funct3 == 0x0:
                self.mem.store(addr, 1, self.regs[rs2])
            elif funct3 == 0x1:
                self.mem.store(addr, 2, self.regs[rs2])
            elif funct3 == 0x2:
                self.mem.store(addr, 4, self.regs[rs2])
            else:
                raise ValueError(f"unknown store funct3 {funct3} at pc 0x{self.pc:08x}")

        elif opcode == 0x63:  # branches
            imm = sign_extend(
                ((instr >> 31) << 12) | (((instr >> 7) & 0x1) << 11)
                | (((instr >> 25) & 0x3F) << 5) | (((instr >> 8) & 0xF) << 1), 13)
            a, b = self.regs[rs1], self.regs[rs2]
            taken = {
                0x0: a == b,
                0x1: a != b,
                0x4: to_s32(a) < to_s32(b),
                0x5: to_s32(a) >= to_s32(b),
                0x6: a < b,
                0x7: a >= b,
            }.get(funct3)
            if taken is None:
                raise ValueError(f"unknown branch funct3 {funct3} at pc 0x{self.pc:08x}")
            if taken:
                next_pc = self.pc + imm

        elif opcode == 0x37:  # lui
            self._set_reg(rd, (instr & 0xFFFFF000))

        elif opcode == 0x17:  # auipc
            self._set_reg(rd, self.pc + (instr & 0xFFFFF000))

        elif opcode == 0x6F:  # jal
            imm = sign_extend(
                ((instr >> 31) << 20) | (((instr >> 12) & 0xFF) << 12)
                | (((instr >> 20) & 0x1) << 11) | (((instr >> 21) & 0x3FF) << 1), 21)
            self._set_reg(rd, self.pc + 4)
            next_pc = self.pc + imm

        elif opcode == 0x67:  # jalr
            imm = sign_extend((instr >> 20) & 0xFFF, 12)
            self._set_reg(rd, self.pc + 4)
            next_pc = to_u32(self.regs[rs1] + imm) & ~1

        elif opcode == 0x73:  # ecall / system: halt
            self.halted = True

        else:
            raise ValueError(f"unknown opcode 0x{opcode:02x} at pc 0x{self.pc:08x}")

        self.pc = next_pc
        self.steps += 1
        if self.steps >= self.max_steps and not self.halted:
            raise RuntimeError(f"step limit reached ({self.max_steps}) — possible infinite loop")
        return not self.halted

    def run(self, trace=False):
        while self.step(trace=trace):
            pass
        return self

    def dump_regs(self):
        names = ["zero", "ra", "sp", "gp", "tp", "t0", "t1", "t2",
                 "s0", "s1", "a0", "a1", "a2", "a3", "a4", "a5",
                 "a6", "a7", "s2", "s3", "s4", "s5", "s6", "s7",
                 "s8", "s9", "s10", "s11", "t3", "t4", "t5", "t6"]
        lines = []
        for i in range(0, 32, 4):
            parts = []
            for j in range(i, i + 4):
                parts.append(f"x{j:<2} {names[j]:<4} = {self.regs[j]:#010x} ({to_s32(self.regs[j])})")
            lines.append("  ".join(parts))
        return "\n".join(lines)
