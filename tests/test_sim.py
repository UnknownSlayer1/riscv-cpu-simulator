"""Tests for the RV32I simulator and assembler."""
import unittest
from assembler import assemble
from riscv_sim import CPU


def run(source):
    words, data, _ = assemble(source)
    cpu = CPU()
    cpu.load_program(words)
    if data:
        cpu.load_bytes(data, base=0x1000)
    cpu.run()
    return cpu


class TestAssembler(unittest.TestCase):
    def test_addi(self):
        cpu = run("addi a0, x0, 42\n ecall\n")
        self.assertEqual(cpu.regs[10], 42)

    def test_x0_hardwired_zero(self):
        cpu = run("addi x0, x0, 99\n addi a0, x0, 1\n ecall\n")
        self.assertEqual(cpu.regs[0], 0)
        self.assertEqual(cpu.regs[10], 1)

    def test_fib10(self):
        with open("programs/fib.asm") as f:
            cpu = run(f.read())
        self.assertEqual(cpu.regs[10], 55)

    def test_sum_1_to_100(self):
        with open("programs/sum.asm") as f:
            cpu = run(f.read())
        self.assertEqual(cpu.regs[10], 5050)

    def test_memory_store_load(self):
        with open("programs/memory.asm") as f:
            cpu = run(f.read())
        self.assertEqual(cpu.regs[10], 42)

    def test_branch_and_shift(self):
        cpu = run("""
            addi a0, x0, 8
            slli a1, a0, 2
            srli a2, a1, 1
            blt a0, a1, ok
            addi a3, x0, 99
        ok: ecall
        """)
        self.assertEqual(cpu.regs[11], 32)
        self.assertEqual(cpu.regs[12], 16)
        self.assertEqual(cpu.regs[13], 0)

    def test_jal_and_jalr(self):
        cpu = run("""
            jal ra, target
            ecall
        target:
            addi a0, x0, 7
            jalr x0, 0(ra)
        """)
        self.assertEqual(cpu.regs[10], 7)

    def test_sub_and_slt(self):
        cpu = run("""
            addi a0, x0, 10
            addi a1, x0, 3
            sub a2, a0, a1
            slt a3, a1, a0
            ecall
        """)
        self.assertEqual(cpu.regs[12], 7)
        self.assertEqual(cpu.regs[13], 1)


if __name__ == "__main__":
    unittest.main()
