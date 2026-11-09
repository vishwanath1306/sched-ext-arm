#!/usr/bin/env python3
"""Run a command under SCHED_EXT, inheriting the caller's CPU affinity."""

import os
import sys

if len(sys.argv) < 2:
    sys.exit(f"Usage: {sys.argv[0]} COMMAND [ARG ...]")

try:
    # Linux UAPI value; older Python versions do not expose os.SCHED_EXT.
    os.sched_setscheduler(0, 7, os.sched_param(0))
    os.execvp(sys.argv[1], sys.argv[1:])
except OSError as error:
    sys.exit(str(error))
