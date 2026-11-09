#!/usr/bin/env python3
"""Check attach, Rust dispatch, task progress, and clean detachment on this host."""

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
STATE = Path("/sys/kernel/sched_ext/state")
VM_SETTING = Path("/proc/sys/vm/compact_unevictable_allowed")


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def ext_enabled():
    for line in Path("/proc/self/sched").read_text().splitlines():
        if line.startswith("ext.enabled"):
            return int(line.split(":", 1)[1])
    raise RuntimeError("kernel does not expose ext.enabled in /proc/self/sched")


def worker(cpu):
    os.sched_setaffinity(0, {cpu})
    os.sched_setscheduler(0, 7, os.sched_param(0))
    require(ext_enabled() == 1, "worker did not enter sched_ext")
    start_cpu = time.process_time()
    end = time.monotonic() + 3
    while time.monotonic() < end:
        pass
    require(ext_enabled() == 1, "sched_ext detached during the workload")
    print(json.dumps({"pid": os.getpid(), "cpu": cpu,
                      "cpu_seconds": time.process_time() - start_cpu,
                      "policy": os.sched_getscheduler(0), "ext_enabled": 1}))


def stop(process):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def main():
    require(os.geteuid() == 0, "run with sudo: sudo python3 smoke-test.py")
    require(STATE.read_text().strip() == "disabled", "a sched_ext scheduler is already active")
    binary = ROOT / "target/release/toy-rust-scheduler"
    require(binary.is_file(), "build first: cargo build --release")
    original_vm = VM_SETTING.read_text()
    cpu = min(os.sched_getaffinity(0))
    workers = []
    log_path = ROOT / "smoke-test.log"
    with log_path.open("w") as log:
        scheduler = subprocess.Popen([str(binary)], stdout=log, stderr=log)
        try:
            deadline = time.monotonic() + 20
            while STATE.read_text().strip() != "enabled":
                require(scheduler.poll() is None, f"scheduler exited; see {log_path}")
                require(time.monotonic() < deadline, f"attach timed out; see {log_path}")
                time.sleep(0.05)
            require(ext_enabled() == 0, "partial mode unexpectedly enrolled the test driver")
            # Both workers contend for the same CPU; the scheduler may use other CPUs.
            for _ in range(2):
                workers.append(subprocess.Popen(
                    [sys.executable, str(Path(__file__).resolve()), "--worker", str(cpu)],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                ))
            for process in workers:
                stdout, stderr = process.communicate(timeout=15)
                require(process.returncode == 0, f"worker failed: {stderr}")
                result = json.loads(stdout)
                require(result["policy"] == 7, "worker lost SCHED_EXT policy")
                require(result["cpu_seconds"] > 0.1, f"worker made too little progress: {result}")
                print(json.dumps(result))
            require(STATE.read_text().strip() == "enabled", "scheduler detached during test")
        finally:
            for process in workers:
                stop(process)
            stop(scheduler)
            # Restore this framework's VM change even after a startup failure or crash.
            if VM_SETTING.read_text() != original_vm:
                VM_SETTING.write_text(original_vm)
                print("Restored vm.compact_unevictable_allowed after scheduler exit.")

    require(scheduler.returncode == 0, f"scheduler failed; see {log_path}")
    require(STATE.read_text().strip() == "disabled", "scheduler did not detach")
    counts = re.search(r"rust_dispatches=(\d+) kernel_bypasses=(\d+)", log_path.read_text())
    require(counts is not None, f"missing dispatch counters; see {log_path}")
    require(int(counts.group(1)) > 0, "no Rust dispatch decisions observed")
    require(int(counts.group(2)) == 0, "some tasks bypassed the Rust policy")
    print(f"PASS: {counts.group(0)}; both workers ran; sched_ext disabled after cleanup.")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--worker":
        worker(int(sys.argv[2]))
    else:
        main()
