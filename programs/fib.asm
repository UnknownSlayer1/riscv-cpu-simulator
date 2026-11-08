# Compute fib(10) = 55, result in a0.
# a0 = n, a1 = fib(n-1), a2 = fib(n-2), t0 = counter
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
