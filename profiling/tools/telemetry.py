"""Read the sampler files and turn the projection log into timed stages.

Shared by perfetto_export.py, collect_manifest.py and build_report.py.
Standard library only, so it runs with the shared env's Python 3.7.
"""

import csv
import os
import re

GB = 1024 ** 3

# Log lines the sampler keeps, with the time it first saw them.
MARKER_RE = re.compile(
    r"^(Initializing\.\.\.|Loading models\.\.\.|Loading weather\.\.\.|REDO: |Full Adaptation"
    r"|Limited adaptation: |Collecting baseline information|baseline$|Creating calculations"
    r"|Processing years|Push \d{4}|Historical$|Process Time:|Setting up parallel"
    r"|an unknown error occurred|Traceback|ERROR"
    r"|/\S*/rcp\d+/[^/\s]+/[^/\s]+/SSP\d/?$)"
)

# The output folder the projection prints when it starts a unit, as in
# .../batch0/rcp85/CCSM4/high/SSP3 (one per unit, so one in a single).
TARGET_RE = re.compile(r"^/\S*/(rcp\d+)/([^/\s]+)/([^/\s]+)/(SSP\d)/?$")

# Mortality adds the suffix after the path, as in "...-young-histclim.nc4 -histclim".
REDO_RE = re.compile(r"^REDO: Cannot find (.+?)\.nc4(\s.*)?$")
PUSH_RE = re.compile(r"^Push (\d{4})")
PROCESS_TIME_RE = re.compile(r"^Process Time: ([0-9.]+)")
ERROR_RE = re.compile(r"an unknown error occurred|^Traceback|^ERROR")


def read_samples(path):
    """Load samples.csv into a list of dicts with float values.

    Parameters
    ----------
    path : str

    Returns
    -------
    list of dict
    """
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path) as fp:
        for row in csv.DictReader(fp):
            rows.append({k: _float(v) for k, v in row.items()})
    return rows


def read_threads(path):
    """Load threads.csv into a list of (time, thread id, CPU percent).

    Parameters
    ----------
    path : str

    Returns
    -------
    list of tuple
    """
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path) as fp:
        for row in csv.DictReader(fp):
            rows.append((float(row["t"]), int(row["tid"]), float(row["cpu_pct"])))
    return rows


def read_markers(path):
    """Load markers.tsv into a list of (time, line).

    Parameters
    ----------
    path : str

    Returns
    -------
    list of tuple
    """
    markers = []
    if not os.path.exists(path):
        return markers
    with open(path, errors="replace") as fp:
        for line in fp:
            line = line.rstrip("\n")
            if "\t" not in line:
                continue
            t, text = line.split("\t", 1)
            markers.append((float(t), text))
    return markers


VARIANT_PARTS = ("noadapt", "incadapt", "global", "histclim")
AGE_GROUPS = ("young", "older", "oldest", "combined")


def variant_name(nc4_base):
    """Name a variant from its output file.

    wheat_winter-280823-noadapt-histclim gives noadapt-histclim, a file with
    no variant part gives fulladapt, and mortality's
    Agespec_interaction_response-young-noadapt gives young noadapt.

    Parameters
    ----------
    nc4_base : str
        Output path without the .nc4 extension.

    Returns
    -------
    str
    """
    parts = os.path.basename(nc4_base).split("-")
    # Read from the end, since CSVV names may hold dashes (wheat_winter-280823) or not.
    tail = []
    while len(parts) > 1 and parts[-1] in VARIANT_PARTS:
        tail.insert(0, parts.pop())
    name = "-".join(tail) if tail else "fulladapt"
    if len(parts) > 1 and parts[-1] in AGE_GROUPS:
        name = parts[-1] + " " + name
    return name


def build_stages(markers, t_end=None):
    """Turn timed log markers into stage slices.

    Parameters
    ----------
    markers : list of (float, str)
    t_end : float or None
        End of the run, used to close the last open stage.

    Returns
    -------
    dict
        slices: list of dicts (name, start, end, depth); units: list of
        dicts (name, start, end), one per output folder; instants: list of
        (time, name); years: list of (time, year); process_time: float or
        None (the last one); error: first error line or None.
    """
    slices = []
    units = []
    instants = []
    years = []
    process_time = None
    error = None
    if not markers:
        return dict(slices=slices, units=units, instants=instants, years=years, process_time=None, error=None)

    if t_end is None:
        t_end = markers[-1][0]

    t_init = None
    t_weather = None
    claimed = False  # the startup ends at the first output file, not at each unit's
    variant = None  # open variant: dict(name, start, sub=[(name, start)])

    def close_unit(t):
        if units and units[-1]["end"] is None:
            units[-1]["end"] = t

    def close_variant(t):
        if variant is None:
            return
        slices.append(dict(name=variant["name"], start=variant["start"], end=t, depth=0))
        subs = variant["sub"]
        for ii, (name, start) in enumerate(subs):
            end = subs[ii + 1][1] if ii + 1 < len(subs) else t
            slices.append(dict(name=name, start=start, end=end, depth=1))

    for t, line in markers:
        if line.startswith("Initializing...") and t_init is None:
            t_init = t
        elif line.startswith("Loading weather...") and t_weather is None:
            t_weather = t
            if t_init is not None:
                slices.append(dict(name="startup: economic models", start=t_init, end=t, depth=0))
        m = TARGET_RE.match(line)
        if m:
            close_unit(t)
            units.append(dict(name=m.group(2), start=t, end=None))
            continue
        m = REDO_RE.match(line)
        if m:
            if not claimed and t_weather is not None:
                slices.append(dict(name="startup: weather and claim", start=t_weather, end=t, depth=0))
            claimed = True
            close_variant(t)
            variant = dict(name=variant_name(m.group(1)), start=t, sub=[("covariates", t)])
            continue
        if variant is not None:
            if line == "baseline":
                variant["sub"].append(("calculation setup", t))
            elif line.startswith("Processing years"):
                variant["sub"].append(("years", t))
        m = PUSH_RE.match(line)
        if m:
            years.append((t, int(m.group(1))))
            continue
        if line == "Historical":
            instants.append((t, "Historical"))
            continue
        m = PROCESS_TIME_RE.match(line)
        if m:
            process_time = float(m.group(1))
            close_variant(t)
            close_unit(t)
            variant = None
            continue
        if ERROR_RE.search(line):
            instants.append((t, line[:120]))
            if error is None:
                error = line

    close_variant(t_end)
    close_unit(t_end)
    return dict(slices=slices, units=units, instants=instants, years=years, process_time=process_time,
                error=error)


def unit_memory(stages, samples):
    """Time and memory of each unit: at its start, and its peaks.

    A montecarlo job that runs several units in one process shows here
    whether memory builds up from one unit to the next.

    Parameters
    ----------
    stages : dict
        Output of build_stages.
    samples : list of dict
        Output of read_samples.

    Returns
    -------
    list of dict
    """
    t0 = samples[0]["t"] if samples else None
    out = []
    for ii, u in enumerate(stages.get("units", [])):
        rows = [r for r in samples if u["start"] <= r["t"] < u["end"]]

        def gib(row, key):
            return round(row[key] / GB, 2) if row and row.get(key) is not None else None

        def peak(key):
            vals = [r[key] for r in rows if r.get(key) is not None]
            return round(max(vals) / GB, 2) if vals else None

        out.append(dict(unit=ii + 1, name=u["name"], seconds=round(u["end"] - u["start"], 1),
                        start_h=round((u["start"] - t0) / 3600.0, 3) if t0 is not None else None,
                        rss_at_start_gb=gib(rows[0] if rows else None, "rss_main"),
                        peak_rss_gb=peak("rss_main"), peak_cgroup_gb=peak("cg_usage")))
    return out


def stage_summary(stages):
    """Durations per stage, in seconds.

    Parameters
    ----------
    stages : dict
        Output of build_stages.

    Returns
    -------
    dict
    """
    out = dict(startup={}, variants=[], totals={})
    current = None
    for s in stages["slices"]:
        seconds = round(s["end"] - s["start"], 1)
        if s["depth"] == 0 and s["name"].startswith("startup"):
            out["startup"][s["name"].split(": ", 1)[1]] = seconds
        elif s["depth"] == 0:
            current = dict(name=s["name"], seconds=seconds)
            out["variants"].append(current)
        elif current is not None:
            current[s["name"].replace(" ", "_") + "_s"] = seconds
            key = s["name"].replace(" ", "_") + "_s"
            out["totals"][key] = round(out["totals"].get(key, 0) + seconds, 1)
    out["totals"]["variants_s"] = round(sum(v["seconds"] for v in out["variants"]), 1)
    out["units"] = [dict(unit=ii + 1, name=u["name"], seconds=round(u["end"] - u["start"], 1))
                    for ii, u in enumerate(stages.get("units", []))]
    out["process_time_s"] = stages["process_time"]
    out["error"] = stages["error"]
    return out


def sample_summary(samples):
    """Peaks and means from the 1 s samples.

    Parameters
    ----------
    samples : list of dict

    Returns
    -------
    dict
    """
    if not samples:
        return dict(samples=0)
    t0 = samples[0]["t"]

    def peak(key):
        vals = [(r.get(key), r["t"]) for r in samples if r.get(key) is not None]
        if not vals:
            return None, None
        v, t = max(vals)
        return round(v / GB, 2), round(t - t0, 1)

    out = dict(samples=len(samples), seconds=round(samples[-1]["t"] - t0, 1))
    out["peak_rss_gb"], out["peak_rss_at_s"] = peak("rss_main")
    out["peak_tree_rss_gb"], _ = peak("rss_tree")
    out["peak_cgroup_gb"], _ = peak("cg_usage")
    out["peak_cgroup_rss_gb"], _ = peak("cg_rss")
    out["cgroup_max_usage_gb"], _ = peak("cg_max")
    cpu = [r["cpu_main"] for r in samples if r.get("cpu_main") is not None]
    if cpu:
        out["mean_cpu_pct"] = round(sum(cpu) / len(cpu), 1)
        out["p95_cpu_pct"] = round(sorted(cpu)[int(0.95 * (len(cpu) - 1))], 1)
    # read_gb: bytes returned by read() calls. read_disk_gb: bytes from local
    # block devices only, which stays near 0 when files sit on a network filesystem.
    # Sum of increases, so a new projection process (counters back at 0) still adds up.
    for key, name in (("read_chars_main", "read_gb"), ("read_bytes_main", "read_disk_gb")):
        reads = [r[key] for r in samples if r.get(key) is not None]
        if reads:
            out[name] = round(sum(b - a for a, b in zip(reads, reads[1:]) if b > a) / GB, 1)
    threads = [r["threads_main"] for r in samples if r.get("threads_main") is not None]
    if threads:
        out["max_threads"] = int(max(threads))
    return out


def _float(value):
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None
