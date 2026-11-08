# RISC-V CPU Simulator (RV32I)

A small, readable RV32I CPU simulator in pure Python — no dependencies.
It simulates registers, a byte-addressable memory, and a two-pass assembler
so you can write real assembly programs and watch them run.

## What it does

- **CPU (`riscv_sim.py`)**: 32 registers (x0 hard-wired to zero), 64 KiB
  little-endian memory, program counter, step limit to catch infinite loops.
  Implements the RV32I base ISA: R/I/S/B/U/J formats, loads/stores,
  branches, `jal`/`jalr`, `lui`/`auipc`, and `ecall` (halt).
- **Assembler (`assembler.py`)**: labels, `#` comments, `.text` / `.data`,
  `.word` / `.byte`, ABI register names (`a0`, `t0`, `ra`, ...).
- **CLI (`main.py`)**: assemble and run a program, with `--trace` and `--regs`.

## Run it

```bash
python3 main.py programs/fib.asm
# halted after 61 steps, pc=0x00000030
# a0 (x10) = 55   a1 (x11) = 34

python3 main.py programs/sum.asm
# halted after 405 steps, pc=0x00000020
# a0 (x10) = 5050   a1 (x11) = 0

python3 main.py programs/memory.asm
# a0 (x10) = 42

python3 main.py programs/fib.asm --trace --regs
```

## Example program (`programs/fib.asm`)

```asm
# Compute fib(10) = 55, result in a0.
    addi a0, x0, 10
    addi a1, x0, 0
    addi a2, x0, 1
    addi t0, x0, 1
loop:
    beq t0, a0, done
    add t1, a1, a2
    add a1, a2, x0
    add a2, t1, x0
    addi t0, t0, 1
    jal x0, loop
done:
    add a0, a2, x0
    ecall
```

## Tests

```bash
python3 -m unittest discover -s tests -v
# Ran 8 tests — OK
```

Tests cover `addi`, x0 hard-wired to zero, fib(10) = 55, sum 1..100 = 5050,
store/load round-trip, branches/shifts, `jal`/`jalr`, and `sub`/`slt`.

## What I built / learned

- How each RV32I instruction format encodes (R/I/S/B/U/J), including the
  scattered immediate bits in branches and jumps.
- Why x0 must be hard-wired to zero, and how sign extension works for
  loads and immediates.
- How a two-pass assembler resolves labels before encoding.
- How a CPU fetches, decodes, and executes one instruction at a time,
  and why a step limit matters for infinite loops.
