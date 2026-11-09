# Toy Arm sched_ext scheduler

For a scheduling policy implemented in Rust userspace, see
[the Rust example](rust/README.md) and [its policy](rust/src/main.rs).
The C/BPF version below runs its policy entirely in the kernel.

One BPF callback puts runnable tasks on the kernel's global FIFO with a
5 ms time slice. The kernel supplies default CPU selection and consumes the
global queue, so no custom `select_cpu` or `dispatch` callback is needed.
CPU affinity still applies. This is a toy policy with no weight-based fairness.

`SCX_OPS_SWITCH_PARTIAL` opts in only tasks explicitly set to `SCHED_EXT`.
Other normal tasks stay on the fair scheduler, which takes precedence over
the ext class in partial mode. CPU affinity does not reserve cores.

## Build

Build on the target Arm64 host with Clang's BPF backend, a C compiler, make,
bpftool, and libbpf/libelf/zlib development headers and libraries. Use a recent
libbpf with `.struct_ops.link` support. No Rust toolchain is needed.

```sh
make
```

The build generates `vmlinux.h` from the running kernel's BTF. Run `make clean`
before rebuilding for a different kernel: sched_ext's BPF API can change.

## Run

Attach the scheduler with root privileges and keep the loader running:

```sh
sudo ./toy
```

In another terminal, check that sched_ext is enabled, then opt a command into
the scheduler. For example, this CPU-bound loop runs for about five seconds
with affinity to CPU 0:

```sh
cat /sys/kernel/sched_ext/state
taskset -c 0 python3 run-ext.py python3 -c 'import time; end = time.monotonic() + 5
while time.monotonic() < end: pass'
```

The launcher uses `sched_setscheduler(..., SCHED_EXT, ...)` and then executes
your command. The installed `chrt` on this host has no `--ext` option.
Children inherit the scheduling policy. If local permissions reject the
policy change, run the launcher with the appropriate privileges.

Ctrl-C in the loader detaches the scheduler. The kernel falls back to the
fair scheduler after detachment or a sched_ext abort. Setting `SCHED_EXT`
alone does not prove the BPF scheduler is active; check its state too.

## Status

Written for this host's Arm64 Linux `6.16.1-0_fbk6_0_g8fc89c59249c` kernel.
The `scx_bpf_dsq_insert` signature, global queue ID, and partial-mode flag
were checked against its live BTF. The code has not been compiled or loaded.
Clang was absent from `PATH`, and `/usr/include/bpf` headers were unavailable
when this example was written.
