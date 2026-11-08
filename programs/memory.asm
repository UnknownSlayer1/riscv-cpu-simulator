# Store 42 to memory and load it back; a0 should be 42.
    addi t0, x0, 42
    lui t1, 1
    sw t0, 0(t1)
    lw a0, 0(t1)
    ecall
