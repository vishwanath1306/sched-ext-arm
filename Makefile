CLANG ?= clang
BPFTOOL ?= bpftool
CC ?= cc

.DELETE_ON_ERROR:
.PHONY: all clean

all: toy

vmlinux.h:
	$(BPFTOOL) btf dump file /sys/kernel/btf/vmlinux format c > $@

toy.bpf.o: toy.bpf.c vmlinux.h
	$(CLANG) -g -O2 -target bpf -D__TARGET_ARCH_arm64 -I. -c $< -o $@

toy.skel.h: toy.bpf.o
	$(BPFTOOL) gen skeleton $< name toy_bpf > $@

toy: toy.c toy.skel.h
	$(CC) $(CPPFLAGS) $(CFLAGS) -g -O2 -Wall -Wextra toy.c $(LDFLAGS) -lbpf -lelf -lz -o $@

clean:
	rm -f toy toy.bpf.o toy.skel.h vmlinux.h
