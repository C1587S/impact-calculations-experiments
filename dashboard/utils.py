"""Load the profiling runs and draw the comparison figures and tables for dashboard.py.

The first block holds the values meant to be edited by hand.
"""

import io
import json
import math
import re
import urllib.request
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd
from matplotlib.figure import Figure
from matplotlib.patches import Patch

LABELS = {
    "master": "master",
    "branch": "lazy econ model",
    "master + gc": "master + gc every minute",
    "branch + gc": "lazy econ model + gc every minute",
    "years": "year loop",
    "gc": "garbage collection",
}
COLORS = {"master": "#898781", "branch": "#6250d6", "master + gc": "#1baf7a", "branch + gc": "#e87ba4"}
LINESTYLES = {"single": "-", "montecarlo unit": "--", "quick": ":"}

# Cost. Hours of one median (single) run per crop, from the AMEL sheet.
CROP_HOURS = {"wheat_winter": 11.3, "wheat_spring": 6.0, "soy": 4.3, "corn": 4.1, "rice": 3.9, "sorghum": 3.2,
              "cassava": 3.0}
UNITS_PER_CROP = {"median": 390, "montecarlo": 5850}
MONTECARLO_HOURS = 0.59  # montecarlo unit over single, measured: mcunit / baseline
MEMORY_MARGIN = 1.2  # memory per job: the setup's measured peak plus 20 %
CIL = dict(nodes=2, cores=64, memory_gb=252)  # not billed
CASLAKE_JOBS = 100  # jobs running at once on caslake
CASLAKE_SPEED = 1.22  # caslake hours over cil hours, measured: mcunit_econfix / mcunit
GB_PER_CORE = 3.75  # caslake bills hours x max(cores, GB / 3.75)
AMD_MEMORY_GB = 9882 * 64 / (11 * 24)  # in use at once in the labor montecarlo: CPU hours x GB / hours
AMD_SPEED = 1.0  # amd hours over cil hours, not measured

VERSIONS = ["master", "branch", "master + gc", "branch + gc"]
GROUPS = ["quick runs", "full singles", "montecarlo units", "gc runs"]
MEASURES = {  # trace counter, track, axis label. "memory GB" is in GiB (1024 ** 3 bytes).
    "memory": ("memory GB", "projection_rss", "Memory (GiB)"),
    "cpu": ("CPU % of one core", "projection", "CPU (% of one core)"),
    "read": ("read MB/s", "read_calls", "Read rate (MB/s)"),
    "cgroup": ("memory GB", "cgroup_total", "Job memory, cgroup (GiB)"),
}
FILES = ("manifest.json", "trace.json", "check.json", "gc.csv")


def label(key):
    return LABELS.get(key, key)


# Loading ---------------------------------------------------------------------


def load_runs(location):
    """Every run with a manifest under experiments/*/reports/*.

    location is mo.notebook_location(): this folder when run here, the page's
    URL on Pages (dashboard/ or a folder below it). A page cannot list folders,
    so a local run writes the list to dashboard/runs.json and the page reads it.
    """
    here = location
    while here.name and here.name != "dashboard":
        here = here.parent
    root = here.parent if here.name == "dashboard" else location.parent
    local = isinstance(root, Path)
    if local:
        folders = {m.parent.relative_to(root).as_posix(): sorted(f.name for f in m.parent.iterdir() if f.name in FILES)
                   for m in sorted(root.glob("experiments/*/reports/*/manifest.json"))}
        index = root / "dashboard" / "runs.json"
        text = json.dumps(folders, indent=1) + "\n"
        if not index.exists() or index.read_text() != text:
            index.write_text(text)
    else:
        folders = json.loads(_read(root / "dashboard" / "runs.json", local))
    runs = [_load_run(root, folder, files, local) for folder, files in folders.items()]
    return sorted(runs, key=lambda r: (GROUPS.index(r["group"]), VERSIONS.index(r["version"]), r["start"]))


def _read(path, local):
    if local:
        return Path(path).read_text()
    with urllib.request.urlopen(str(path)) as response:
        return response.read().decode()


def _load_run(root, folder, files, local):
    def read(name):
        return _read(root / folder / name, local) if name in files else None

    manifest = json.loads(read("manifest.json"))
    events = json.loads(read("trace.json") or '{"traceEvents": []}')["traceEvents"]
    name = folder.rsplit("/", 1)[-1]
    mode = re.search(r"^mode:\s*(\S+)", (manifest.get("config") or {}).get("text", ""), re.M)
    kind = "quick" if manifest.get("quick") else ("montecarlo unit" if mode and mode.group(1) == "montecarlo" else "single")
    gc = manifest.get("profiler") == "gc" or "gccollect" in name
    version = ("master" if (manifest.get("impact_calculations") or {}).get("branch") == "master" else "branch") + (" + gc" if gc else "")

    # Samples: one row per time in seconds, a column per measure
    rows = {}
    for e in events:
        for key, (counter, track, _) in MEASURES.items():
            if e.get("ph") == "C" and e["name"] == counter and track in e["args"]:
                rows.setdefault(e["ts"] / 1e6, {})[key] = e["args"][track]
    series = pd.DataFrame.from_dict(rows, orient="index", columns=list(MEASURES)).sort_index()

    # Stages: startup, then each variant with its covariates, calculation setup and year loop
    slices = sorted((e["ts"] / 1e6, (e["ts"] + e["dur"]) / 1e6, e["name"]) for e in events if e.get("ph") == "X")
    parts = ("covariates", "calculation setup", "years")
    stages = [dict(key="startup", start=0.0, end=max(b for a, b, n in slices if n.startswith("startup")), parts={})]
    for a, b, n in slices:
        if not n.startswith("startup") and n not in parts:
            key = n if all(s["key"] != n for s in stages) else "%s %d" % (n, sum(s["key"].startswith(n) for s in stages) + 1)
            stages.append(dict(key=key, start=a, end=b, parts={p: (pa, pb) for pa, pb, p in slices if p in parts and a <= pa < b}))

    totals = (manifest.get("stages") or {}).get("totals") or {}
    gc_log = pd.read_csv(io.StringIO(read("gc.csv"))) if "gc.csv" in files else None
    return dict(
        name=name, kind=kind, version=version, gc=gc,
        group="quick runs" if kind == "quick" else "gc runs" if gc else "full singles" if kind == "single" else "montecarlo units",
        partition=(manifest.get("slurm") or {}).get("job_partition"),
        cores=manifest.get("cores"), profiler=manifest.get("profiler"), compare_to=manifest.get("compare_to"),
        start=manifest.get("start") or "", hours=(manifest.get("wall_seconds") or 0) / 3600,
        peak=series["cgroup"].max(), series=series, stages=stages,  # peak of the job cgroup
        steps={"startup": sum(((manifest.get("stages") or {}).get("startup") or {}).values()),
               "covariates": totals.get("covariates_s"), "calculation setup": totals.get("calculation_setup_s"),
               "years": totals.get("years_s"), "gc": gc_log["seconds"].sum() if gc_log is not None else None},
        check=json.loads(read("check.json")) if "check.json" in files else None,
    )


# Stage axis ------------------------------------------------------------------


def stage_axis(runs):
    """Stage keys in one order (the longest run's, then any it lacks) and a function placing
    a run's times on that axis, each stage one unit wide whatever its length."""
    order = []
    for run in sorted(runs, key=lambda r: -len(r["stages"])):
        order += [s["key"] for s in run["stages"] if s["key"] not in order]

    def position(run, seconds):
        x = np.full(len(seconds), np.nan)
        for s in run["stages"]:
            inside = (seconds >= s["start"]) & (seconds < s["end"])
            x[inside] = order.index(s["key"]) + (seconds[inside] - s["start"]) / max(s["end"] - s["start"], 1e-9)
        return x

    return order, position


# Figures ---------------------------------------------------------------------


def figure(height=2.6, ncols=1, sharey=True, sharex=False):
    """A white figure with black left and bottom axes, ticks outward, no grid, small sans-serif text."""
    matplotlib.rcParams.update({
        "font.family": "sans-serif", "font.size": 8, "legend.fontsize": 7, "legend.frameon": False,
        "xtick.labelsize": 7, "ytick.labelsize": 7, "axes.linewidth": 0.8, "axes.edgecolor": "black",
        "axes.spines.top": False, "axes.spines.right": False, "axes.grid": False,
        "xtick.direction": "out", "ytick.direction": "out", "lines.linewidth": 1.0,
        "figure.facecolor": "white", "axes.facecolor": "white", "figure.dpi": 150,
    })
    fig = Figure(figsize=(6.0, height), layout="constrained")
    return fig, fig.subplots(1, ncols, sharey=sharey, sharex=sharex, squeeze=False)[0]


def _legend(fig, runs):
    fig.legend(handles=[Patch(color=COLORS[v], label=label(v)) for v in VERSIONS
                        if any(r["version"] == v for r in runs)], loc="outside upper left", ncols=2)


def peak_bars(runs, group):
    """Peak memory of the job cgroup in each run of a group."""
    runs = [r for r in runs if r["group"] == group]
    fig, (ax,) = figure(height=0.22 * len(runs) + 0.8)
    y = np.arange(len(runs))
    ax.barh(y, [r["peak"] for r in runs], color=[COLORS[r["version"]] for r in runs], height=0.65)
    for yi, r in zip(y, runs):
        ax.text(r["peak"] + 0.15, yi, "%.1f" % r["peak"], va="center", fontsize=7)
    ax.set_yticks(y, [r["name"] for r in runs])
    ax.invert_yaxis()
    ax.set_xlabel("Peak memory, job cgroup (GiB)")
    _legend(fig, runs)
    return fig


def over_run(runs, group, measure="memory", by_stage=False):
    """One line per run of a group over hours, or over stages each drawn at the same width."""
    runs = [r for r in runs if r["group"] == group]
    order, position = stage_axis(runs)
    fig, (ax,) = figure(height=2.8)
    for r in runs:
        values = r["series"][measure].dropna()
        seconds = values.index.to_numpy()
        ax.plot(position(r, seconds) if by_stage else seconds / 3600, values.to_numpy(), color=COLORS[r["version"]],
                linestyle=LINESTYLES[r["kind"]], label="%s (%s)" % (r["name"], label(r["version"])))
    if by_stage:
        ax.set_xticks([i + 0.5 for i in range(len(order))], [k.replace("-", "-\n") for k in order])
        ax.set_xlim(0, len(order))
    else:
        ax.set_xlim(0, None)
        ax.set_xlabel("Time since start (h)")
    ax.set_ylim(0, None)
    ax.set_ylabel(MEASURES[measure][2])
    fig.legend(loc="outside upper left", ncols=2)
    return fig


def memory_by_stage(runs, group):
    """Peak memory of startup, then the median of each year loop, for each run of a group."""
    runs = [r for r in runs if r["group"] == group]
    order, _ = stage_axis(runs)
    fig, (ax,) = figure(height=2.6)
    for r in runs:
        memory = r["series"]["memory"].dropna()
        t, v = memory.index.to_numpy(), memory.to_numpy()
        cells = {s["key"]: v[t <= s["end"]].max() if s["key"] == "startup" else
                 np.median(v[(t >= s["parts"]["years"][0]) & (t < s["parts"]["years"][1])])
                 for s in r["stages"] if s["key"] == "startup" or "years" in s["parts"]}
        ax.plot(range(len(order)), [cells.get(k, np.nan) for k in order], marker="o", markersize=3,
                color=COLORS[r["version"]], linestyle=LINESTYLES[r["kind"]], label="%s (%s)" % (r["name"], label(r["version"])))
    ax.set_xticks(range(len(order)), ["startup\n(peak)"] + [k.replace("-", "-\n") for k in order[1:]])
    ax.set_ylim(0, None)
    ax.set_ylabel("Memory (GiB)")
    fig.legend(loc="outside upper left", ncols=2)
    return fig


def time_by_step(runs, group):
    """Time of each step in each run of a group, a panel per step, in minutes for short runs."""
    runs = [r for r in runs if r["group"] == group]
    steps = [s for s in ("startup", "covariates", "calculation setup", "years", "gc") if any(r["steps"][s] for r in runs)]
    scale, unit = (60, "min") if max(r["hours"] for r in runs) < 2 else (3600, "h")
    fig, axes = figure(height=0.22 * len(runs) + 1.0, ncols=len(steps))
    y = np.arange(len(runs))
    for ax, step in zip(axes, steps):
        ax.barh(y, [(r["steps"][step] or 0) / scale for r in runs], color=[COLORS[r["version"]] for r in runs], height=0.65)
        ax.set_title(label(step), fontsize=8)
        ax.set_xlabel("Time (%s)" % unit)
    axes[0].set_yticks(y, [r["name"] for r in runs])
    axes[0].invert_yaxis()
    _legend(fig, runs)
    return fig


# Tables ----------------------------------------------------------------------


def cost_table(runs):
    """Days to finish median and montecarlo for every crop, each partition used alone, and SUs on caslake.
    Memory per job is the cgroup peak of the setup's run (one core, no profiler other than gc) plus 20 %."""
    rows = []
    for runs_kind, kind in (("median", "single"), ("montecarlo", "montecarlo unit")):
        job_hours = sum(UNITS_PER_CROP[runs_kind] * h for h in CROP_HOURS.values()) * (MONTECARLO_HOURS if kind != "single" else 1)
        for setup in ("master", "branch", "branch + gc"):
            found = [r for r in runs if r["kind"] == kind and r["version"] == setup and r["cores"] == 1
                     and r["profiler"] in (None, "none", "gc")]
            found.sort(key=lambda r: r["start"], reverse=True)  # latest first,
            found.sort(key=lambda r: r["compare_to"] is not None)  # and a reference run before its variants
            row = {"runs": runs_kind, "setup": label(setup)}
            if found:
                memory = math.ceil(found[0]["peak"] * MEMORY_MARGIN)
                jobs = {"cil": CIL["nodes"] * min(CIL["cores"], CIL["memory_gb"] // memory),
                        "amd": AMD_MEMORY_GB // memory, "caslake": CASLAKE_JOBS}
                speed = {"cil": 1.0, "amd": AMD_SPEED, "caslake": CASLAKE_SPEED}
                row.update({"days on %s" % p: "%.1f" % (job_hours * speed[p] / jobs[p] / 24) for p in jobs})
                row["SUs on caslake"] = "{:,.0f}".format(job_hours * CASLAKE_SPEED * max(1, memory / GB_PER_CORE))
            rows.append(row)
    return pd.DataFrame(rows).set_index(["runs", "setup"]).fillna("not run")


def checks_table(runs):
    """Output check of each run against its reference. Only histclim differing in a
    montecarlo unit that reused its reference's draws counts as an expected seed difference."""
    rows = []
    for r in runs:
        if r["check"]:
            files = r["check"].get("files", [])
            failing = [f["name"] for f in files if not f.get("ok")]
            diffs = [v["max_abs_diff"] for f in files for v in f.get("vars", {}).values() if v.get("max_abs_diff") is not None]
            seed = r["kind"] == "montecarlo unit" and failing and all("histclim" in f for f in failing)
            rows.append({"run": r["name"], "reference": r["compare_to"], "files": len(files),
                         "identical": sum(f.get("ok") and not any(v.get("max_abs_diff") for v in f.get("vars", {}).values()) for f in files),
                         "largest difference": "%.3g" % max(diffs) if diffs else "",
                         "differing files": ", ".join(failing),
                         "status": "pass" if not failing else "seed differs (expected)" if seed else "fail"})
    return pd.DataFrame(rows).set_index("run")
