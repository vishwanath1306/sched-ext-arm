#include "vmlinux.h"
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_tracing.h>

char LICENSE[] SEC("license") = "GPL";

extern void scx_bpf_dsq_insert(struct task_struct *p, u64 dsq_id,
                              u64 slice, u64 enq_flags) __ksym;

SEC("struct_ops/toy_enqueue")
void BPF_PROG(toy_enqueue, struct task_struct *p, u64 enq_flags)
{
    /* The kernel consumes this FIFO; each task gets a 5 ms slice. */
    scx_bpf_dsq_insert(p, SCX_DSQ_GLOBAL, 5 * 1000 * 1000, enq_flags);
}

SEC(".struct_ops.link")
struct sched_ext_ops toy_ops = {
    .enqueue = (void *)toy_enqueue,
    .flags = SCX_OPS_SWITCH_PARTIAL,
    .name = "toy_fifo",
};
