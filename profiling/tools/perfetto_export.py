"""Write a Chrome trace JSON (open it at https://ui.perfetto.dev) from the sampler files.

Stages from the log become slices; memory, CPU, reads, threads and the
current year become counter tracks. Long runs are thinned to --max-points per
track, keeping the maximum memory in each bucket so peaks are not lost.
"""

import argparse
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import telemetry  # noqa: E402

PID = 1
STAGE_TID = 1


def buckets(n, max_points):
    """Split range(n) into consecutive buckets of about equal size.

    Parameters
    ----------
    n : int
    max_points : int

    Returns
    -------
    list of range
    """
    size = max(1, int(math.ceil(n / float(max_points))))
    return [range(i, min(i + size, n)) for i in range(0, n, size)]


def counter(events, name, t, t0, values):
    """Append one counter event; each key of values becomes its own track."""
    values = {k: v for k, v in values.items() if v is not None}
    if values:
        events.append(dict(ph="C", name=name, pid=PID, ts=round((t - t0) * 1e6), args=values))


def build_trace(run_dir, name, max_points):
    """Build the trace event list for one run.

    Parameters
    ----------
    run_dir : str
        Folder with samples.csv, threads.csv and markers.tsv.
    name : str
        Label shown for the process in Perfetto.
    max_points : int

    Returns
    -------
    dict
    """
    samples = telemetry.read_samples(os.path.join(run_dir, "samples.csv"))
    markers = telemetry.read_markers(os.path.join(run_dir, "markers.tsv"))
    threads = telemetry.read_threads(os.path.join(run_dir, "threads.csv"))
    starts = [s["t"] for s in samples[:1]] + [m[0] for m in markers[:1]]
    t0 = min(starts) if starts else 0.0
    t_end = samples[-1]["t"] if samples else (markers[-1][0] if markers else t0)
    stages = telemetry.build_stages(markers, t_end)

    events = [
        dict(ph="M", pid=PID, name="process_name", args=dict(name=name)),
        dict(ph="M", pid=PID, tid=STAGE_TID, name="thread_name", args=dict(name="stages")),
    ]
    for s in sorted(stages["slices"], key=lambda s: (s["start"], s["depth"])):
        dur = max(s["end"] - s["start"], 0.0)
        events.append(dict(ph="X", name=s["name"], cat="stage", pid=PID, tid=STAGE_TID,
                           ts=round((s["start"] - t0) * 1e6), dur=round(dur * 1e6),
                           args=dict(minutes=round(dur / 60.0, 1))))
    for t, label in stages["instants"]:
        events.append(dict(ph="i", s="t", name=label, pid=PID, tid=STAGE_TID, ts=round((t - t0) * 1e6)))
    for t, year in stages["years"]:
        counter(events, "year", t, t0, dict(year=year))

    core_keys = [k for k in (samples[0].keys() if samples else []) if k.startswith("core_")]
    prev = samples[0] if samples else None
    for idx in buckets(len(samples), max_points):
        rows = [samples[i] for i in idx]
        t = rows[0]["t"]

        def top(key):
            vals = [r[key] for r in rows if r.get(key) is not None]
            return round(max(vals) / telemetry.GB, 3) if vals else None

        def mean(key, scale=1.0):
            vals = [r[key] for r in rows if r.get(key) is not None]
            return round(sum(vals) / len(vals) / scale, 1) if vals else None

        counter(events, "memory GB", t, t0, dict(projection_rss=top("rss_main"), all_processes_rss=top("rss_tree"),
                                                  cgroup_total=top("cg_usage"), cgroup_rss=top("cg_rss")))
        counter(events, "CPU % of one core", t, t0, dict(projection=mean("cpu_main"), other=mean("cpu_other")))
        counter(events, "allocated cores %", t, t0, {k.replace("core_", "core "): mean(k) for k in core_keys})
        counter(events, "threads", t, t0, dict(projection=mean("threads_main")))
        # Read rate from the cumulative counters, from the end of the previous
        # bucket to the end of this one (a bucket is often a single sample).
        # read_calls is every byte read() returned, from any filesystem;
        # read_from_disk counts only local block devices, so it can stay at 0
        # on network filesystems.
        last = rows[-1]
        span = last["t"] - prev["t"]
        rates = {}
        for key, label in (("read_chars_main", "read_calls"), ("read_bytes_main", "read_from_disk")):
            if span > 0 and prev.get(key) is not None and last.get(key) is not None:
                delta = last[key] - prev[key]
                if delta >= 0:  # a new projection process restarts the counters
                    rates[label] = round(delta / span / 1e6, 2)
        counter(events, "read MB/s", t, t0, rates)
        prev = last

    # CPU per thread, for the busiest threads only (one in serial runs, two with threads: 2).
    if threads:
        totals = {}
        for _, tid, pct in threads:
            totals[tid] = totals.get(tid, 0.0) + pct
        busy = sorted(totals, key=totals.get, reverse=True)[:6]
        by_time = {}
        for t, tid, pct in threads:
            if tid in busy:
                by_time.setdefault(t, {})[tid] = pct
        times = sorted(by_time)
        for idx in buckets(len(times), max_points):
            ts = [times[i] for i in idx]
            vals = {}
            for tid in busy:
                vals["thread %d" % tid] = round(sum(by_time[t].get(tid, 0.0) for t in ts) / len(ts), 1)
            counter(events, "thread CPU %", ts[0], t0, vals)

    return dict(traceEvents=events, displayTimeUnit="ms",
                metadata=dict(run=name, start_epoch=t0, stage_summary=telemetry.stage_summary(stages)))


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--name", default="projection")
    # 6000 points keep a 12 h trace near 4 MB (one point about every 7 s).
    parser.add_argument("--max-points", type=int, default=6000)
    args = parser.parse_args()
    trace = build_trace(args.run_dir, args.name, args.max_points)
    with open(args.output, "w") as fp:
        json.dump(trace, fp, separators=(",", ":"))
    print("wrote %s (%d events)" % (args.output, len(trace["traceEvents"])))


if __name__ == "__main__":
    main()
