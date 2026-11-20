"""Light telemetry for one projection run: memory, CPU, threads and reads every second.

Runs beside the projection as its own process (psutil comes from the tools
folder through PYTHONPATH, never into the projection itself). It also tails
the projection log and stamps the stage lines with the time it saw them.

Writes to --out:
  samples.csv  one row per second
  threads.csv  CPU per thread of the projection process (busy threads only)
  markers.tsv  time and text of each stage line in the log
"""

import argparse
import csv
import os
import signal
import sys
import time

import psutil

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from telemetry import MARKER_RE  # noqa: E402

STOP = False


def _stop(signum, frame):
    global STOP
    STOP = True


def find_projection(root, me):
    """Return the projection's Python process among the job's processes, or None.

    Parameters
    ----------
    root : psutil.Process
    me : int
        The sampler's own pid, left out.

    Returns
    -------
    psutil.Process or None
    """
    best = None
    best_rss = -1
    for proc in root.children(recursive=True):
        if proc.pid == me:
            continue
        try:
            cmd = " ".join(proc.cmdline())
            if "generate.generate" not in cmd:
                continue
            rss = proc.memory_info().rss
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
        if rss > best_rss:
            best, best_rss = proc, rss
    return best


def cgroup_files(pid):
    """Find the memory cgroup files Slurm uses to enforce --mem.

    Parameters
    ----------
    pid : int

    Returns
    -------
    dict
        Paths for usage, max usage and stat, empty if not found.
    """
    try:
        with open("/proc/%d/cgroup" % pid) as fp:
            lines = fp.read().splitlines()
    except OSError:
        return {}
    for line in lines:
        parts = line.split(":", 2)
        if len(parts) != 3:
            continue
        controllers, path = parts[1], parts[2]
        # Slurm enforces --mem on the job folder, above the step and task folders.
        pieces = path.split("/")
        for ii, piece in enumerate(pieces):
            if piece.startswith("job_"):
                path = "/".join(pieces[:ii + 1])
                break
        if "memory" in controllers.split(","):
            base = "/sys/fs/cgroup/memory" + path
            files = dict(usage=base + "/memory.usage_in_bytes", max=base + "/memory.max_usage_in_bytes",
                         stat=base + "/memory.stat", rss_key="total_rss")
            if os.path.exists(files["usage"]):
                return files
        if controllers == "":
            base = "/sys/fs/cgroup" + path
            files = dict(usage=base + "/memory.current", max=base + "/memory.peak",
                         stat=base + "/memory.stat", rss_key="anon")
            if os.path.exists(files["usage"]):
                return files
    return {}


def read_cgroup(files):
    """Read usage, peak and resident memory from the cgroup files.

    Parameters
    ----------
    files : dict

    Returns
    -------
    tuple of (usage, max, rss), each int or None
    """
    def one(path):
        try:
            with open(path) as fp:
                return int(fp.read().split()[0])
        except (OSError, ValueError, IndexError):
            return None

    if not files:
        return None, None, None
    rss = None
    try:
        with open(files["stat"]) as fp:
            for line in fp:
                key, value = line.split()[:2]
                if key == files["rss_key"]:
                    rss = int(value)
                    break
    except (OSError, ValueError):
        pass
    return one(files["usage"]), one(files["max"]), rss


class LogTail(object):
    """Follow a growing log file and return the new stage lines."""

    def __init__(self, path):
        self.path = path
        self.offset = 0
        self.partial = b""

    def new_markers(self):
        """Read what was added since the last call.

        Returns
        -------
        list of str
        """
        try:
            with open(self.path, "rb") as fp:
                fp.seek(self.offset)
                data = fp.read()
                self.offset = fp.tell()
        except OSError:
            return []
        if not data:
            return []
        data = self.partial + data
        lines = data.split(b"\n")
        self.partial = lines.pop()
        out = []
        for raw in lines:
            line = raw.decode("utf-8", "replace").rstrip("\r")
            if MARKER_RE.match(line):
                out.append(line)
        return out


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root-pid", type=int, required=True, help="pid of the job script")
    parser.add_argument("--log", required=True, help="projection log to tail")
    parser.add_argument("--out", required=True, help="folder for the CSV files")
    parser.add_argument("--interval", type=float, default=1.0)
    args = parser.parse_args()

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    me = os.getpid()
    root = psutil.Process(args.root_pid)
    # The cores Slurm gave the job (the sampler shares the job's CPU set).
    if hasattr(os, "sched_getaffinity"):
        cores = sorted(os.sched_getaffinity(0))
    else:
        cores = list(range(psutil.cpu_count()))
    tail = LogTail(args.log)

    os.makedirs(args.out, exist_ok=True)
    fsamples = open(os.path.join(args.out, "samples.csv"), "w", newline="")
    fthreads = open(os.path.join(args.out, "threads.csv"), "w", newline="")
    fmarkers = open(os.path.join(args.out, "markers.tsv"), "w")
    columns = ["t", "rss_main", "rss_tree", "cpu_main", "cpu_other", "threads_main",
               "read_chars_main", "read_bytes_main", "write_chars_main",
               "cg_usage", "cg_max", "cg_rss"] + ["core_%d" % c for c in cores]
    samples = csv.writer(fsamples)
    samples.writerow(columns)
    threads_out = csv.writer(fthreads)
    threads_out.writerow(["t", "tid", "cpu_pct"])

    psutil.cpu_percent(percpu=True)  # first call only sets the reference point
    proc = None
    cg = {}
    last_cpu = {}  # pid -> (time, cpu seconds)
    last_thread = {}  # tid -> cpu seconds
    t_last = time.time()
    n = 0

    while not STOP:
        t = time.time()
        dt = max(t - t_last, 1e-3)
        t_last = t

        for line in tail.new_markers():
            fmarkers.write("%.3f\t%s\n" % (t, line))

        if proc is None or not proc.is_running():
            proc = find_projection(root, me)
            if proc is not None:
                cg = cgroup_files(proc.pid)

        rss_main = cpu_main = threads_main = None
        rchar = rbytes = wchar = None
        rss_tree = 0
        cpu_other = 0.0
        try:
            family = [p for p in root.children(recursive=True) if p.pid != me]
        except psutil.NoSuchProcess:
            break
        for p in family:
            try:
                with p.oneshot():
                    rss = p.memory_info().rss
                    times = p.cpu_times()
                    cpu_s = times.user + times.system
                    rss_tree += rss
                    prev = last_cpu.get(p.pid)
                    last_cpu[p.pid] = (t, cpu_s)
                    pct = 100.0 * (cpu_s - prev[1]) / max(t - prev[0], 1e-3) if prev else None
                    if proc is not None and p.pid == proc.pid:
                        rss_main = rss
                        cpu_main = pct
                        threads_main = p.num_threads()
                        try:
                            io = p.io_counters()
                            rchar = getattr(io, "read_chars", None)
                            rbytes = io.read_bytes
                            wchar = getattr(io, "write_chars", None)
                        except (AttributeError, psutil.AccessDenied):
                            pass
                        try:
                            threads = p.threads()
                        except psutil.AccessDenied:
                            threads = []
                        for th in threads:
                            used = th.user_time + th.system_time
                            before = last_thread.get(th.id)
                            last_thread[th.id] = used
                            if before is not None:
                                tpct = 100.0 * (used - before) / dt
                                if tpct >= 0.5:
                                    threads_out.writerow([round(t, 3), th.id, round(tpct, 1)])
                    elif pct is not None:
                        cpu_other += pct
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        usage, cmax, crss = read_cgroup(cg)
        per_core = psutil.cpu_percent(percpu=True)
        core_vals = [per_core[c] if c < len(per_core) else None for c in cores]
        samples.writerow([round(t, 3), rss_main, rss_tree, _r(cpu_main), round(cpu_other, 1), threads_main,
                          rchar, rbytes, wchar, usage, cmax, crss] + core_vals)
        n += 1
        if n % 10 == 0:
            fsamples.flush()
            fthreads.flush()
            fmarkers.flush()
        if not root.is_running():
            break
        time.sleep(max(0.0, args.interval - (time.time() - t)))

    # Pick up the last log lines written before the stop.
    t = time.time()
    for line in tail.new_markers():
        fmarkers.write("%.3f\t%s\n" % (t, line))
    for f in (fsamples, fthreads, fmarkers):
        f.close()


def _r(value):
    return None if value is None else round(value, 1)


if __name__ == "__main__":
    main()
