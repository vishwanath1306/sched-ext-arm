# Toy scheduler with a Rust policy

The scheduling policy is in `src/main.rs`: collect runnable tasks in a
`VecDeque`, take the oldest task, assign a 5 ms slice, and dispatch it to the
first available allowed CPU. The monotonically increasing `vtime` preserves
FIFO ordering in the framework's shared dispatch queue. CPU affinity applies;
FIFO dispatch order does not imply global execution order across CPUs.

This uses `scx_rustland_core` to run the policy in userspace. Its C/BPF shim
passes tasks and dispatch decisions between Rust and the kernel. This is not
an all-Rust BPF program. The policy includes no weights or latency heuristics.
The framework can dispatch directly from BPF during queue congestion and for
its own scheduler thread and certain kernel threads.

## Build and run

Build natively on the Arm64 host. Dependencies: Rust/Cargo 1.91 or later,
rustfmt, Clang with BPF support, libclang for bindgen, a C toolchain,
pkg-config, and libelf/zlib/libseccomp development files. The Rust libbpf dependency
builds bundled libbpf. `BPF_CLANG` can select a Clang executable; bindgen also
needs to locate its libclang shared library.

From this directory:

```sh
BPF_CLANG=/usr/bin/clang LIBCLANG_PATH=/usr/lib64 cargo build --locked --release
sudo ./target/release/toy-rust-scheduler
```

The build generates the C/BPF shim, Rust connector, and bindings using the
framework. Generated `intf.h`, `main.bpf.c`, and `src/bpf.rs` are ignored.
Framework versions are pinned and Cargo.lock records the resolved dependencies.

## Smoke test

With no sched_ext scheduler running, execute this from the `rust` directory:

```sh
sudo python3 smoke-test.py
```

It attaches the scheduler, starts two CPU-bound `SCHED_EXT` workers on the same
CPU for three seconds, and checks that both enter sched_ext and get CPU time.
It also checks that the ordinary test driver remains outside sched_ext.
It then stops the scheduler, verifies nonzero Rust dispatches and zero kernel bypasses,
and checks that sched_ext is disabled. It restores the framework's VM setting
even if startup fails. Scheduler output is saved in `smoke-test.log`.

Expected output ends with `PASS`. This checks basic execution through Rust,
not exact 5 ms timing, fairness under load, or performance against the default
scheduler.

## Run your own workload

In another terminal, from this directory, opt a short workload into sched_ext:

```sh
cat /sys/kernel/sched_ext/state
taskset -c 0 python3 ../run-ext.py python3 -c 'import time; end = time.monotonic() + 5
while time.monotonic() < end: pass'
```

Partial mode is enabled: only `SCHED_EXT` tasks participate, including the
framework's scheduler thread. Normal fair-class tasks take precedence.
The framework registers under a name beginning with `toy_fifo_rs`.
Ctrl-C or SIGTERM stops it; queue errors return an error and detach it.
The kernel falls back to the fair scheduler on detachment or a sched_ext abort.

The framework uses a 64 MiB allocator arena and locks process memory. It also
sets `vm.compact_unevictable_allowed=0` while running and attempts to restore
the previous value on normal cleanup. This is part of the framework, not the
FIFO policy. Root privileges are required for this example.

## Status

Built and smoke-tested on 2026-11-06 on this Arm Neoverse V2 host running
`6.16.1-0_fbk6_0_g8fc89c59249c`, using Rust 1.98.1 and Clang 22.1.3.
The test passed with 500 Rust dispatches, zero kernel bypasses, and about
1.48 CPU-seconds per worker during the three-second run on CPU 0.
The ordinary driver stayed outside sched_ext. The scheduler detached cleanly
and `vm.compact_unevictable_allowed` returned to its original value of 1.

The required compiler and development packages are now installed on this host.
The scheduler is stopped after testing; the smoke-test command starts and
stops its own instance. Run the binary directly to leave it active for your
own workloads.
