#include <signal.h>
#include <stdio.h>
#include <unistd.h>
#include <bpf/libbpf.h>
#include "toy.skel.h"

static volatile sig_atomic_t stop;

static void on_signal(int signo)
{
    (void)signo;
    stop = 1;
}

int main(void)
{
    struct sigaction action = { .sa_handler = on_signal };
    struct toy_bpf *skel;
    struct bpf_link *link;

    sigemptyset(&action.sa_mask);
    if (sigaction(SIGINT, &action, NULL) ||
        sigaction(SIGTERM, &action, NULL)) {
        perror("sigaction");
        return 1;
    }

    skel = toy_bpf__open_and_load();
    if (!skel) {
        fprintf(stderr, "Failed to load toy scheduler; see libbpf errors above.\n");
        return 1;
    }

    link = bpf_map__attach_struct_ops(skel->maps.toy_ops);
    if (!link) {
        perror("Failed to attach scheduler");
        toy_bpf__destroy(skel);
        return 1;
    }

    puts("toy_fifo attached: SCHED_EXT tasks only. Ctrl-C to detach.");
    while (!stop)
        sleep(1);

    bpf_link__destroy(link);
    toy_bpf__destroy(skel);
    return 0;
}
