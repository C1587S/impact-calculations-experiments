"""Run a module with a full garbage collection every few seconds, and log each pass.

Usage:
  python gc_capture.py --interval SECONDS --log FILE -m MODULE [ARGS...]

A timer signal runs gc.collect() in the main thread, between two Python
statements, so a pass never runs alongside a file read in C code. Each pass
adds a row to --log: when it started, how long it took and how many objects
it freed. Standard library only.
"""

import csv
import gc
import os
import runpy
import signal
import sys
import time


def parse(argv):
    """Split our options from the module and its arguments.

    Parameters
    ----------
    argv : list of str

    Returns
    -------
    dict
    """
    opts = dict(interval=60.0, log=None, module=None, args=[])
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--interval":
            opts["interval"] = float(argv[i + 1])
            i += 2
        elif arg == "--log":
            opts["log"] = argv[i + 1]
            i += 2
        elif arg == "-m":
            opts["module"] = argv[i + 1]
            opts["args"] = argv[i + 2:]
            break
        else:
            sys.exit("unknown option %s\n%s" % (arg, __doc__))
    if not opts["log"] or not opts["module"] or opts["interval"] <= 0:
        sys.exit(__doc__)
    return opts


def main():
    opts = parse(sys.argv[1:])
    log = open(opts["log"], "w", newline="")
    writer = csv.writer(log)
    writer.writerow(["t", "seconds", "collected"])

    def collect(signum, frame):
        start = time.time()
        freed = gc.collect()
        writer.writerow([round(start, 3), round(time.time() - start, 3), freed])
        log.flush()

    signal.signal(signal.SIGALRM, collect)
    # Restart system calls the timer interrupts, so reads in C code never see EINTR.
    signal.siginterrupt(signal.SIGALRM, False)
    signal.setitimer(signal.ITIMER_REAL, opts["interval"], opts["interval"])
    try:
        # Same path order as python -m: the current folder first, not this tools folder.
        sys.path[0] = os.getcwd()
        sys.argv = [""] + opts["args"]
        runpy.run_module(opts["module"], run_name="__main__", alter_sys=True)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        log.close()


if __name__ == "__main__":
    main()
