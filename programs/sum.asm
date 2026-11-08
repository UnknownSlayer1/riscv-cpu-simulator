# Sum 1..100 = 5050, result in a0.
    addi a0, x0, 0
    addi t0, x0, 1
    addi t1, x0, 101
loop:
    beq t0, t1, done
    add a0, a0, t0
    addi t0, t0, 1
    jal x0, loop
done:
    ecall
