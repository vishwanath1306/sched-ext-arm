mod bpf;
mod bpf_intf;
mod bpf_skel;

use anyhow::{anyhow, Context, Result};
use bpf::{BpfScheduler, DispatchedTask, RL_CPU_ANY};
use std::collections::VecDeque;
use std::mem::MaybeUninit;

const SLICE_NS: u64 = 5_000_000;

fn main() -> Result<()> {
    let mut open_object = MaybeUninit::uninit();
    let mut scheduler = BpfScheduler::init(
        &mut open_object,
        None,  // Default BPF object open options.
        0,     // Default exit diagnostic buffer size.
        true,  // Only opt-in SCHED_EXT tasks.
        false, // Disable debug output.
        false, // Route workload decisions through Rust, even when a CPU is idle.
        false, // Use one shared queue across NUMA nodes.
        SLICE_NS,
        "toy_fifo_rs",
    )
    .context("attach the Rust scheduler")?;
    let mut ready = VecDeque::new();
    let mut next_order = 1_u64;

    println!("Rust FIFO attached: 5 ms slices, SCHED_EXT tasks only. Ctrl-C to stop.");
    while !scheduler.exited() {
        while let Some(task) = scheduler
            .dequeue_task()
            .map_err(|code| anyhow!("receive runnable task: libbpf error {code}"))?
        {
            ready.push_back(task);
        }

        if let Some(task) = ready.front() {
            let mut dispatch = DispatchedTask::new(task);
            dispatch.cpu = RL_CPU_ANY;
            dispatch.slice_ns = SLICE_NS;
            // The shared BPF queue sorts by vtime; this preserves FIFO order.
            dispatch.vtime = next_order;
            scheduler
                .dispatch_task(&dispatch)
                .context("dispatch the next FIFO task")?;
            ready.pop_front();
            next_order = next_order.wrapping_add(1);
        }

        // Report pending work and yield so the kernel can run dispatched tasks.
        scheduler.notify_complete(ready.len() as u64);
    }

    println!(
        "rust_dispatches={} kernel_bypasses={}",
        next_order.wrapping_sub(1),
        *scheduler.nr_kernel_dispatches_mut(),
    );
    scheduler.shutdown_and_report()?;
    Ok(())
}
