"""A small two-pass assembler for the RV32I subset in riscv_sim.py.

Syntax (one instruction per line, `#` comments):
    label:  addi x1, x0, 42
    loop:   beq x1, x0, done
            addi x1, x1, -1
            jal x0, loop
    done:   ecall

Directives: `.text`, `.data`, `.word <value>`, `.byte <value>`.
Registers may be written as x0-x31 or by ABI name (ra, sp, a0, t0, ...).
Numbers may be decimal, 0x hex, or negative.
"""

import re
from riscv_sim import to_u32

ABI = {
    "zero": 0, "ra": 1, "sp": 2, "gp": 3, "tp": 4,
    "t0": 5, "t1": 6, "t2": 7, "s0": 8, "fp": 8, "s1": 9,
    "a0": 10, "a1": 11, "a2": 12, "a3": 13, "a4": 14, "a5": 15,
    "a6": 16, "a7": 17, "s2": 18, "s3": 19, "s4": 20, "s5": 21,
    "s6": 22, "s7": 23, "s8": 24, "s9": 25, "s10": 26, "s11": 27,
    "t3": 28, "t4": 29, "t5": 30, "t6": 31,
}

R_OPS = {
    "add": (0x0, 0x00), "sub": (0x0, 0x20), "sll": (0x1, 0x00),
    "slt": (0x2, 0x00), "sltu": (0x3, 0x00), "xor": (0x4, 0x00),
    "srl": (0x5, 0x00), "sra": (0x5, 0x20), "or": (0x6, 0x00),
    "and": (0x7, 0x00),
}
I_OPS = {
    "addi": 0x0, "slti": 0x2, "sltiu": 0x3, "xori": 0x4,
    "ori": 0x6, "andi": 0x7,
}
SHIFT_OPS = {"slli": (0x1, 0x00), "srli": (0x5, 0x00), "srai": (0x5, 0x20)}
LOAD_OPS = {"lb": 0x0, "lh": 0x1, "lw": 0x2, "lbu": 0x4, "lhu": 0x5}
STORE_OPS = {"sb": 0x0, "sh": 0x1, "sw": 0x2}
BRANCH_OPS = {"beq": 0x0, "bne": 0x1, "blt": 0x4, "bge": 0x5, "bltu": 0x6, "bgeu": 0x7}


def reg(name):
    name = name.strip()
    if name.startswith("x") and name[1:].isdigit():
        n = int(name[1:])
        if 0 <= n <= 31:
            return n
    if name in ABI:
        return ABI[name]
    raise ValueError(f"unknown register '{name}'")


def num(text, labels=None):
    text = text.strip()
    if labels is not None and text in labels:
        return labels[text]
    return int(text, 0)


def _enc_r(funct7, rs2, rs1, funct3, rd, opcode):
    return (funct7 << 25) | (rs2 << 20) | (rs1 << 15) | (funct3 << 12) | (rd << 7) | opcode


def _enc_i(imm, rs1, funct3, rd, opcode):
    return ((imm & 0xFFF) << 20) | (rs1 << 15) | (funct3 << 12) | (rd << 7) | opcode


def _enc_s(imm, rs2, rs1, funct3, opcode):
    return (((imm >> 5) & 0x7F) << 25) | (rs2 << 20) | (rs1 << 15) | (funct3 << 12) | (((imm) & 0x1F) << 7) | opcode


def _enc_b(imm, rs2, rs1, funct3, opcode):
    return (((imm >> 12) & 0x1) << 31) | (((imm >> 5) & 0x3F) << 25) | (rs2 << 20) | (rs1 << 15) | (funct3 << 12) | (((imm >> 11) & 0x1) << 7) | (((imm >> 1) & 0xF) << 8) | opcode


def _enc_u(imm, rd, opcode):
    return (imm & 0xFFFFF000) | (rd << 7) | opcode


def _enc_j(imm, rd, opcode):
    return (((imm >> 20) & 0x1) << 31) | (((imm >> 1) & 0x3FF) << 21) | (((imm >> 11) & 0x1) << 20) | (((imm >> 12) & 0xFF) << 12) | (rd << 7) | opcode


def assemble(source):
    """Assemble source text -> (list of 32-bit words, data bytes, labels)."""
    lines = []
    for raw in source.splitlines():
        line = raw.split("#", 1)[0].strip()
        if line:
            lines.append(line)

    # Pass 1: labels and section sizes
    labels = {}
    pc = 0
    data = bytearray()
    items = []  # (kind, pc_or_addr, text)
    in_data = False
    for line in lines:
        if line == ".text":
            in_data = False
            continue
        if line == ".data":
            in_data = True
            continue
        while ":" in line:
            label, rest = line.split(":", 1)
            label = label.strip()
            if in_data:
                labels[label] = 0x1000 + len(data)
            else:
                labels[label] = pc
            line = rest.strip()
            if not line:
                break
        if not line:
            continue
        if in_data:
            if line.startswith(".word"):
                for v in line[5:].split(","):
                    data += (num(v.strip()) & 0xFFFFFFFF).to_bytes(4, "little")
            elif line.startswith(".byte"):
                for v in line[5:].split(","):
                    data += bytes([num(v.strip()) & 0xFF])
            else:
                raise ValueError(f"unknown data directive: {line}")
        else:
            items.append((pc, line))
            pc += 4

    # Pass 2: encode
    words = []
    for addr, line in items:
        parts = re.split(r"[,\s]+", line.strip())
        op = parts[0].lower()
        args = [p for p in parts[1:] if p]
        if op in R_OPS:
            funct3, funct7 = R_OPS[op]
            words.append(_enc_r(funct7, reg(args[2]), reg(args[1]), funct3, reg(args[0]), 0x33))
        elif op in I_OPS:
            words.append(_enc_i(num(args[2], labels), reg(args[1]), I_OPS[op], reg(args[0]), 0x13))
        elif op in SHIFT_OPS:
            funct3, funct7 = SHIFT_OPS[op]
            words.append(_enc_i((funct7 << 5) | (num(args[2]) & 0x1F), reg(args[1]), funct3, reg(args[0]), 0x13))
        elif op in LOAD_OPS:
            m = re.match(r"(-?\w+)\((\w+)\)", args[1])
            imm, base = int(m.group(1), 0), reg(m.group(2))
            words.append(_enc_i(imm, base, LOAD_OPS[op], reg(args[0]), 0x03))
        elif op in STORE_OPS:
            m = re.match(r"(-?\w+)\((\w+)\)", args[1])
            imm, base = int(m.group(1), 0), reg(m.group(2))
            words.append(_enc_s(imm, reg(args[0]), base, STORE_OPS[op], 0x23))
        elif op in BRANCH_OPS:
            target = num(args[2], labels)
            words.append(_enc_b(target - addr, reg(args[1]), reg(args[0]), BRANCH_OPS[op], 0x63))
        elif op == "lui":
            words.append(_enc_u(num(args[1]) << 12, reg(args[0]), 0x37))
        elif op == "auipc":
            words.append(_enc_u(num(args[1]) << 12, reg(args[0]), 0x17))
        elif op == "jal":
            if len(args) == 1:
                words.append(_enc_j(num(args[0], labels) - addr, 1, 0x6F))
            else:
                words.append(_enc_j(num(args[1], labels) - addr, reg(args[0]), 0x6F))
        elif op == "jalr":
            m = re.match(r"(-?\w+)\((\w+)\)", args[1])
            imm, base = int(m.group(1), 0), reg(m.group(2))
            words.append(_enc_i(imm, base, 0x0, reg(args[0]), 0x67))
        elif op == "ecall":
            words.append(0x00000073)
        elif op == "nop":
            words.append(0x00000013)
        else:
            raise ValueError(f"unknown instruction '{op}' in: {line}")
    return words, bytes(data), labels
