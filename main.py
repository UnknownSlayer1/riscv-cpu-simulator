#!/usr/bin/env python3
"""CLI for the RV32I simulator: assemble and run a .asm program.

Usage:
    python main.py programs/fib.asm
    python main.py programs/fib.asm --trace --regs
"""
import argparse
import sys
from assembler import assemble
from riscv_sim import CPU


def main():
    parser = argparse.ArgumentParser(description="RV32I CPU simulator")
    parser.add_argument("program", help="assembly source file (.asm)")
    parser.add_argument("--trace", action="store_true", help="print pc/instruction trace")
    parser.add_argument("--regs", action="store_true", help="dump registers after run")
    parser.add_argument("--max-steps", type=int, default=100000)
    args = parser.parse_args()

    with open(args.program) as f:
        source = f.read()
    words, data, labels = assemble(source)

    cpu = CPU(max_steps=args.max_steps)
    cpu.load_program(words, base=0)
    if data:
        cpu.load_bytes(data, base=0x1000)
    cpu.run(trace=args.trace)

    if args.trace:
        for pc, instr in cpu.trace:
            print(f"0x{pc:08x}: 0x{instr:08x}")
    print(f"halted after {cpu.steps} steps, pc=0x{cpu.pc:08x}")
    print(f"a0 (x10) = {cpu.regs[10]}   a1 (x11) = {cpu.regs[11]}")
    if args.regs:
        print(cpu.dump_regs())
    return 0


if __name__ == "__main__":
    sys.exit(main())
