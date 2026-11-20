"""Load the results of the amd round and draw the figures and tables of amd_round.py.

A run has finished when its manifest.json exists: run_experiment.sh writes it
last and removes it when the run starts again. The winter wheat runs of earlier
rounds used for comparison (baseline and gccollect_econfix) come from the
repo's reports when this folder sits in the repo, otherwise from the results
folder. RESULTS_ROOT points the notebook at another results folder, and
FIGURES, when set, is where the notebook also writes its main figures as PNG.
"""

import json
import math
import os
import re
import subprocess
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.transforms import blended_transform_factory

RESULTS = Path(os.environ.get("RESULTS_ROOT") or "/scratch/midway3/%s/agri-profiling/results" % os.environ.get("USER"))
REPORTS = Path(__file__).resolve().parents[2] / "experiments"
FIGURES = Path(os.environ["FIGURES"]) if os.environ.get("FIGURES") else None

GC = "lazy econ model + gc"
COLORS = {"master": "#898781", GC: "#17645f", "lazy econ model": "#6fa8a2", "master + gc": "#4a4a4a"}
STYLES = {"master": "-", GC: "--", "lazy econ model": "--", "master + gc": "-"}
MARGIN = 1.2  # memory to request: the cgroup peak plus 20 %

CROPS = ["cassava", "corn", "rice", "sorghum", "soy", "wheat_spring", "wheat_winter"]
SECTORS = ["agriculture", "labor", "energy", "mortality"]
# Light to dark in even steps of lightness. The lightest keeps 3:1 against white.
CROP_COLORS = dict(zip(CROPS, ["#679d30", "#4d891f", "#31770b", "#146303", "#004f0b", "#013a10", "#01270d"]))
SECTOR_COLORS = {"labor": "#1a1a1a", "energy": "#9a5b00", "mortality": "#5b3a8c"}
# Crop masters: job 62444670 on amd, whose outputs are the crop references. Median hours and median
# sacct MaxRSS over its 12 scenarios, in GiB (MaxRSS in K divided by 2^20).
EARLIER_MASTER = {"cassava": (2.54, 13.0), "corn": (3.63, 13.4), "rice": (3.62, 17.6), "sorghum": (2.76, 13.4),
                  "soy": (3.74, 13.4), "wheat_spring": (5.41, 15.9), "wheat_winter": (10.74, 19.9)}
REFERENCE = "master"
# Singles are checked against the master outputs here (same_outputs.sbatch)
SHARED = "/project/cil/gcp/outputs_newsocioeconomics"
TARGET = "single/rcp85/CCSM4/high/SSP3"
CROP_RUNS = [c + "_gccollect_econfix" for c in CROPS[:-1]]

ROUND = (["mc3units", "mc3units_gccollect_econfix", "gc5min_econfix", "gcfreeze_econfix"] + CROP_RUNS
         + ["mortality_single", "mortality_single_gccollect_econfix", "labor_mc3units",
            "labor_mc3units_gccollect_econfix", "labor", "labor_gccollect_econfix", "energy",
            "energy_gccollect_econfix"])
EARLIER = ["baseline", "gccollect_econfix"]  # winter wheat single: master on cil, lazy econ model + gc on caslake

# Master and lazy econ model + gc runs of the same setup
PAIRS = {
    "agriculture": [("winter wheat, single", "baseline", "gccollect_econfix"),
                    ("winter wheat, 3 units", "mc3units", "mc3units_gccollect_econfix")],
    "labor": [("labor, single", "labor", "labor_gccollect_econfix"),
              ("labor, 3 units", "labor_mc3units", "labor_mc3units_gccollect_econfix")],
    "energy": [("energy, single", "energy", "energy_gccollect_econfix")],
    "mortality": [("mortality, single", "mortality_single", "mortality_single_gccollect_econfix")],
}
# Each single with its master run (None: the earlier master peak) and its lazy econ model + gc run
SINGLES = {**{c: (None, c + "_gccollect_econfix") for c in CROPS[:-1]}, "wheat_winter": (None, "gccollect_econfix"),
           **{s: PAIRS[s][0][1:] for s in SECTORS[1:]}}
GC_SETTINGS = [("every minute", "gccollect_econfix"), ("every 5 minutes", "gc5min_econfix"),
               ("freeze, then every minute", "gcfreeze_econfix")]
MULTI_UNIT = [PAIRS["agriculture"][1], PAIRS["labor"][1]]
PARTS = ("covariates", "calculation setup", "years")


# Loading


def load_runs():
    """Finished runs of the round (listed above, or run on amd) and the winter wheat runs of EARLIER, by name."""
    folders = {m.parent.name: m.parent for m in sorted(RESULTS.glob("*/manifest.json"))}
    for name in EARLIER:
        found = sorted(REPORTS.glob("*/reports/%s/manifest.json" % name))
        if found:
            folders[name] = found[-1].parent
    runs = {}
    for name, folder in folders.items():
        manifest = json.loads((folder / "manifest.json").read_text())
        if name in ROUND or name in EARLIER or (manifest.get("slurm") or {}).get("job_partition") == "amd":
            runs[name] = load_run(folder, manifest)
    return runs


def load_run(folder, manifest):
    """Memory over the run, stages and units from trace.json, with the manifest, gc.csv and check.json."""
    name = folder.name
    trace = folder / "trace.json"
    events = json.loads(trace.read_text())["traceEvents"] if trace.exists() else []
    memory = {e["ts"] / 1e6: (e["args"].get("cgroup_total"), e["args"].get("projection_rss"))
              for e in events if e.get("ph") == "C" and e["name"] == "memory GB"}
    series = pd.DataFrame.from_dict(memory, orient="index", columns=["cgroup", "process"]).astype(float).sort_index()

    # Stages: startup, then each variant, numbered when a name comes back (one set per unit)
    slices = sorted(((e["ts"] / 1e6, (e["ts"] + e["dur"]) / 1e6, e["name"], e.get("cat"))
                     for e in events if e.get("ph") == "X"), key=lambda s: s[:2])
    startup = [b for a, b, n, c in slices if c == "stage" and n.startswith("startup")]
    stages = [dict(key="startup", name="startup", start=0.0, end=max(startup, default=0.0))]
    for a, b, n, c in slices:
        if c == "stage" and not n.startswith("startup") and n not in PARTS:
            seen = sum(s["name"] == n for s in stages)
            stages.append(dict(key="%s %d" % (n, seen + 1) if seen else n, name=n, start=a, end=b))
    units = [dict(name=n.split(": ", 1)[-1], start=a, end=b) for a, b, n, c in slices if c == "unit"]

    sector = next((s for s in SECTORS[1:] if name.startswith(s)), "agriculture")
    mode = re.search(r"^mode:\s*(\S+)", (manifest.get("config") or {}).get("text", ""), re.M)
    branch = (manifest.get("impact_calculations") or {}).get("branch")
    telemetry = manifest.get("telemetry") or {}
    gc_log = pd.read_csv(folder / "gc.csv") if (folder / "gc.csv").exists() else None
    crop = next((c for c in CROPS if name.startswith(c)), "wheat_winter") if sector == "agriculture" else ""
    kind = "montecarlo" if mode and mode.group(1) == "montecarlo" else "single"
    version = ("master" if branch == "master" else "lazy econ model") + (" + gc" if manifest.get("profiler") == "gc" else "")
    check = json.loads((folder / "check.json").read_text()) if (folder / "check.json").exists() else None
    compare_to = manifest.get("compare_to")
    if kind == "single" and version != "master":
        compare_to = master_outputs(sector, crop)
        if check is not None and not str(check.get("baseline", "")).startswith(SHARED):
            check = None  # checked against a run on scratch: same_outputs.sbatch checks it again
    return dict(
        name=name, sector=sector, crop=crop, kind=kind, version=version, job_id=(manifest.get("slurm") or {}).get("job_id"),
        partition=(manifest.get("slurm") or {}).get("job_partition"), hours=(manifest.get("wall_seconds") or 0) / 3600,
        peak_process=telemetry.get("peak_rss_gb"),
        peak=telemetry.get("peak_cgroup_gb") or (series["cgroup"].max() if len(series) else None),
        failed=bool(manifest.get("failed")),
        compare_to=compare_to, check=check,
        gc=gc_log, series=series, stages=stages, units=units,
        unit_memory=(manifest.get("stages") or {}).get("units") or [],
    )


def master_outputs(sector, crop):
    """Folder of the master outputs a single is checked against, below SHARED."""
    product = {"agriculture": "agriculture/" + crop, "energy": "energy/other_energy"}.get(sector, sector)
    return "%s/%s" % (product, TARGET)


def _get(runs, name):
    """A run for the figures: finished without error and with memory samples, or None."""
    run = runs.get(name)
    return run if run is not None and not run["failed"] and len(run["series"]) else None


def _queue():
    """Slurm state of the profiling jobs by run name, or None where squeue does not answer."""
    try:
        out = subprocess.run(["squeue", "-u", os.environ.get("USER", ""), "-h", "-o", "%j|%T|%M"],
                             capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode:
        return None
    jobs = {}
    for line in out.stdout.splitlines():
        job, state, elapsed = line.split("|")
        if job.startswith("agri-prof-"):
            jobs[job[len("agri-prof-"):]] = ("Running", elapsed) if state == "RUNNING" else \
                ("Queued", None) if state == "PENDING" else (state.capitalize(), None)
    return jobs


def status_line(runs):
    """One line on the runs of the round: how many finished, and those left out and why."""
    jobs = _queue()
    groups = {}
    for name in ROUND:
        if name in runs:
            continue
        if jobs and name in jobs:
            group, detail = jobs[name]
        elif (RESULTS / name).is_dir():
            group, detail = ("Ended without a manifest" if jobs is not None else "No manifest yet"), None
        else:
            group, detail = "No results yet", None
        groups.setdefault(group, []).append(name + (" (%s)" % detail if detail else ""))
    parts = ["%d of %d runs finished." % (sum(n in runs for n in ROUND), len(ROUND))]
    parts += ["%s: %s." % (group, ", ".join(names)) for group, names in groups.items()]
    failed = [n for n in ROUND if n in runs and runs[n]["failed"]]
    if failed:
        parts.append("Failed: %s." % ", ".join(failed))
    missing = [n for n in EARLIER if n not in runs]
    if missing:
        parts.append("Not found: %s." % ", ".join(missing))
    return " ".join(parts)


# Tables


def _one(value):
    return "" if value is None or value != value else "%.1f" % value


def _change(master, other):
    return ("%+.0f %%" % (100 * (other / master - 1))).replace("-", "−")


def _clock(hours):
    seconds = round(hours * 3600)
    return "%d:%02d:%02d" % (seconds // 3600, seconds // 60 % 60, seconds % 60)


def round_runs(runs):
    """Runs of this round by sector and crop, singles first, master first."""
    chosen = [r for n, r in runs.items() if n in ROUND or (n not in EARLIER and r["partition"] == "amd")]
    return sorted(chosen, key=lambda r: (SECTORS.index(r["sector"]), r["crop"], r["kind"] != "single",
                                         r["version"] != "master", r["name"]))


def reference_label(run, runs):
    """The reference as recorded: the master outputs path for singles, "master, job <id>" for the rest."""
    ref = run["compare_to"]
    if run["kind"] == "single" or ref not in runs:
        return ref
    return "master, job %s" % runs[ref]["job_id"]


def check_status(run, runs):
    """The output check in a few words: reference, pending, or the result against the reference."""
    if run["failed"]:
        return "run failed"
    if run["version"] == "master":
        return "reference"
    ref = run["compare_to"]
    if not ref:
        return "no reference"
    if run["check"] is None:
        if ref in ROUND and ref not in runs:
            return "pending"
        return "pending, run %s" % ("same_outputs.sbatch" if run["kind"] == "single" else "check.sbatch")
    return "%s against %s" % (run["check"].get("status"), REFERENCE if run["kind"] == "single" else reference_label(run, runs))


def summary_table(runs):
    """One row per finished run of the round."""
    rows = []
    for r in round_runs(runs):
        gc = r["gc"]
        rows.append({
            "sector": r["sector"], "crop": r["crop"], "run": r["name"], "partition": r["partition"],
            "wall (h)": _one(r["hours"]), "process peak (GiB)": _one(r["peak_process"]),
            "cgroup peak (GiB)": _one(r["peak"]), "gc collections": "" if gc is None else str(len(gc)),
            "gc minutes": "" if gc is None else _one(gc["seconds"].sum() / 60), "output check": check_status(r, runs),
            "memory to request": "%dG" % math.ceil(r["peak"] * MARGIN) if r["peak"] else "",
        })
    return pd.DataFrame(rows) if rows else None


def gc_table(runs):
    """Peak, gc time and wall time of the winter wheat single under each gc setting."""
    rows = []
    for label, name in GC_SETTINGS:
        r = _get(runs, name)
        if r is not None:
            rows.append({"setting": label, "partition": r["partition"], "cgroup peak (GiB)": _one(r["peak"]),
                         "gc minutes": "" if r["gc"] is None else _one(r["gc"]["seconds"].sum() / 60),
                         "elapsed": _clock(r["hours"])})
    return pd.DataFrame(rows) if rows else None


def crops_table(runs):
    """Each crop single with the lazy econ model + gc next to the crop master."""
    rows = []
    for crop in CROPS:
        r = _get(runs, SINGLES[crop][1])
        if r is None:
            continue
        hours, peak = EARLIER_MASTER[crop]
        rows.append({"crop": crop, "run": r["name"], "partition": r["partition"], "wall (h)": _one(r["hours"]),
                     "cgroup peak (GiB)": _one(r["peak"]), "master hours": "%.1f" % hours,
                     "master MaxRSS (GiB)": "%.1f" % peak, "peak change": _change(peak, r["peak"])})
    return pd.DataFrame(rows) if rows else None


def units_table(runs):
    """Time and memory of each unit of the runs with several units in one process."""
    rows = []
    for _, *names in MULTI_UNIT:
        for name in names:
            units = runs[name]["unit_memory"] if name in runs else []
            for u in units:
                rows.append({
                    "run": name, "unit": u["unit"], "GCM": u["name"], "starts at (h)": _one(u["start_h"]),
                    "hours": _one(u["seconds"] / 3600), "process GiB at start": _one(u["rss_at_start_gb"]),
                    "peak process (GiB)": _one(u["peak_rss_gb"]), "peak cgroup (GiB)": _one(u["peak_cgroup_gb"]),
                    "peak cgroup over unit 1 (GiB)": "%+.1f" % (u["peak_cgroup_gb"] - units[0]["peak_cgroup_gb"]),
                })
    return pd.DataFrame(rows) if rows else None


def checks_table(runs):
    """Output check of each run of the round that has a reference."""
    rows = []
    for r in round_runs(runs):
        if not r["compare_to"] or r["version"] == "master":
            continue
        check = r["check"] or {}
        files = check.get("files", [])
        diffs = [v["max_abs_diff"] for f in files for v in f.get("vars", {}).values() if v.get("max_abs_diff")]
        rows.append({
            "run": r["name"], "reference": reference_label(r, runs), "status": check.get("status", "pending"),
            "files": len(files) if r["check"] else "",
            "identical": sum(bool(f.get("ok")) and not any(v.get("max_abs_diff") for v in f.get("vars", {}).values())
                             for f in files) if r["check"] else "",
            "largest difference": "%.3g" % max(diffs) if diffs else "",
            "differing files": ", ".join(f["name"] for f in files if not f.get("ok")),
            "missing files": ", ".join(check.get("missing_in_candidate", [])),
        })
    return pd.DataFrame(rows) if rows else None


# Figures


def figure(height, nrows=1, ncols=1, width=8.0, **kw):
    """A white figure with black left and bottom axes, as in the dashboard."""
    matplotlib.rcParams.update({
        "font.family": "sans-serif", "font.size": 8, "legend.fontsize": 8, "legend.frameon": False,
        "xtick.labelsize": 7, "ytick.labelsize": 7, "axes.linewidth": 0.8, "axes.edgecolor": "black",
        "axes.spines.top": False, "axes.spines.right": False, "axes.grid": False,
        "xtick.direction": "out", "ytick.direction": "out", "lines.linewidth": 1.2,
        "figure.facecolor": "white", "axes.facecolor": "white", "figure.dpi": 150,
    })
    fig = Figure(figsize=(width, height), layout="constrained")
    return fig, fig.subplots(nrows, ncols, squeeze=False, **kw)


def save(fig, name):
    """Write the figure to FIGURES/<name>.png when FIGURES is set."""
    if FIGURES is not None and fig is not None:
        FIGURES.mkdir(parents=True, exist_ok=True)
        fig.savefig(FIGURES / ("%s.png" % name), dpi=150)


def legend(fig, versions, lines=True, extra=()):
    """The code versions present, in the fixed order of COLORS."""
    handles = [Line2D([], [], color=c, linewidth=1.8, label=v) if lines else Patch(color=c, label=v)
               for v, c in COLORS.items() if v in versions] + list(extra)
    fig.legend(handles=handles, loc="outside upper left", ncols=len(handles))


def stage_axis(ref):
    """A function placing a run's times on the reference run's clock, in hours. Each stage of the
    run is stretched to the length of the same stage in the reference, so runs on another CPU
    still line up. Units repeat the stages, so they line up in the order they ran."""
    spans = {s["key"]: (s["start"], s["end"]) for s in ref["stages"]}

    def position(run, seconds):
        x = np.full(len(seconds), np.nan)
        for s in run["stages"]:
            if s["key"] in spans:
                a, b = spans[s["key"]]
                inside = (seconds >= s["start"]) & (seconds < s["end"])
                x[inside] = a + (b - a) * (seconds[inside] - s["start"]) / max(s["end"] - s["start"], 1e-9)
        return x / 3600

    return position


def marks(ax, ref, smallest=0.04, bands=False):
    """Stage names of the reference run above the plot, or its units when it ran several. Each
    stage starts at a thin line, or gets a band of alternating gray with `bands`. Stages shorter
    than `smallest` of the run get no name."""
    total = ref["stages"][-1]["end"]
    for i, s in enumerate(ref["stages"]):
        if bands:
            ax.axvspan(s["start"] / 3600, s["end"] / 3600, color=("#f3f3f3", "#e6e6e6")[i % 2], linewidth=0,
                       zorder=0)
        elif i:
            ax.axvline(s["start"] / 3600, color="0.88", linewidth=0.5, zorder=0)
    if len(ref["units"]) > 1:
        spans = [(u["start"], u["end"], "unit %d" % (i + 1)) for i, u in enumerate(ref["units"])]
        for a, _, _ in spans[1:]:
            ax.axvline(a / 3600, color="0.55", linewidth=0.8, zorder=0)
    else:
        spans = [(s["start"], s["end"], s["key"].replace("-", "-\n").replace(" ", "\n")) for s in ref["stages"]]
    named = [(a, b, n) for a, b, n in spans if (b - a) / total >= smallest]
    top = ax.secondary_xaxis("top")
    top.set_xticks([(a + b) / 7200 for a, b, _ in named], [n for _, _, n in named])
    top.tick_params(length=0, labelsize=7)
    top.spines["top"].set_visible(False)
    ax.set_xlim(0, total / 3600)


def end_labels(fig, panels, size=7):
    """Text right of the last point of each line. panels holds (axes, [(x, y, text), ...], spread).
    With spread, labels that would overlap are pushed up, with a thin line back to their point.
    Without it, a panel whose labels would overlap gets none. Call it last: the labels are placed on
    the final layout and kept out of it, with room kept for them first. Returns the axes left bare."""
    for ax, ends, _ in panels:
        if ends:
            room = " " * 8 + max((t for _, _, t in ends), key=len)
            ax.text(1.0, 0.0, room, transform=ax.transAxes, alpha=0, fontsize=size, va="bottom")
    fig.draw_without_rendering()
    gap = 1.25 * size  # points between two labels
    bare = []
    for ax, ends, spread in panels:
        heights = sorted((ax.transData.transform((x, y))[1] * 72 / fig.dpi, x, y, text) for x, y, text in ends)
        if not spread and any(b[0] - a[0] < gap for a, b in zip(heights, heights[1:])):
            bare.append(ax)
            continue
        placed = None
        for height, x, y, text in heights:
            target = height if placed is None else max(height, placed + gap)
            placed = target
            moved = target - height > 1
            label = ax.annotate(text, (x, y), xytext=(12 if moved else 3, target - height),
                                textcoords="offset points", va="center", fontsize=size, annotation_clip=False,
                                arrowprops=dict(arrowstyle="-", color="0.6", linewidth=0.5, shrinkA=1, shrinkB=0)
                                if moved else None)
            label.set_in_layout(False)
    return bare


def memory_lines(ax, pair, ylabel="Job memory, cgroup (GiB)"):
    """Job memory of a master run and its lazy econ model + gc run, on the master's clock. The other
    run alone keeps its own clock. Returns the line ends, for end_labels."""
    chosen = [r for r in pair if r is not None]
    ref = chosen[0]
    position = stage_axis(ref)
    ends = []
    for r in chosen:
        values = r["series"]["cgroup"].dropna()
        x, y = position(r, values.index.to_numpy()), values.to_numpy()
        ax.plot(x, y, color=COLORS[r["version"]])
        drawn = np.flatnonzero(~np.isnan(x))
        if len(drawn):
            ends.append((x[drawn[-1]], y[drawn[-1]], "peak %.1f GiB" % r["peak"]))
    ax.set_ylim(0, 1.15 * max(r["peak"] for r in chosen))
    marks(ax, ref)
    ax.set_xlabel("Hours since start (%s, %s)" % (ref["name"], ref["partition"]))
    ax.set_ylabel(ylabel)
    return ends


def peak_overview(runs, names=tuple(SINGLES)):
    """Cgroup peak of master and lazy econ model + gc for each single, sorted by the master's peak,
    with the change at the end of each pair. Crops take the MaxRSS of their master job."""
    rows = []
    for single in names:
        m, g = SINGLES[single]
        master = EARLIER_MASTER[single][1] if m is None else (_get(runs, m) or {}).get("peak")
        gc = (_get(runs, g) or {}).get("peak")
        if master is not None or gc is not None:
            rows.append(dict(name=single.replace("_", " "), master=master, earlier=m is None, gc=gc))
    if not rows:
        return None
    rows.sort(key=lambda r: (r["master"] is None, -(r["master"] or r["gc"])))
    fig, ((ax,),) = figure(height=0.32 * len(rows) + 1.0)
    edge = blended_transform_factory(ax.transAxes, ax.transData)
    hatched = dict(facecolor="white", edgecolor=COLORS["master"], hatch="//////")
    for yi, r in enumerate(rows):
        if r["master"] is not None:
            ax.barh(yi - 0.2, r["master"], height=0.38, **(hatched if r["earlier"] else dict(color=COLORS["master"])))
            ax.text(r["master"], yi - 0.2, " %.1f" % r["master"], va="center", fontsize=7)
        if r["gc"] is not None:
            ax.barh(yi + 0.2, r["gc"], height=0.38, color=COLORS[GC])
            ax.text(r["gc"], yi + 0.2, " %.1f" % r["gc"], va="center", fontsize=7)
        if r["master"] is not None and r["gc"] is not None:
            ax.text(1.0, yi, _change(r["master"], r["gc"]), transform=edge, ha="right", va="center", fontsize=8,
                    fontweight="bold")
    if any(r["master"] and r["gc"] for r in rows):
        ax.text(1.0, -0.85, "change", transform=edge, ha="right", va="center", fontsize=7)
    ax.set_yticks(range(len(rows)), [r["name"] for r in rows])
    ax.set_ylim(len(rows) - 0.5, -1.1)
    ax.set_xlim(0, 1.3 * max(max(r["master"] or 0, r["gc"] or 0) for r in rows))
    ax.set_xlabel("Peak memory (GiB)")
    versions = {"master"} if any(r["master"] and not r["earlier"] for r in rows) else set()
    versions |= {GC} if any(r["gc"] for r in rows) else set()
    earlier = [Patch(label="master (MaxRSS)", **hatched)] if any(r["earlier"] for r in rows) else []
    legend(fig, versions, lines=False, extra=earlier)
    return fig


def memory_by_sector(runs):
    """Job memory over the run of every single, one row per sector, on the master's stages. Crops in
    greens, labor black, energy amber, mortality purple. Solid is master, dashed lazy econ model + gc.
    Crop peaks go in the legend, and winter wheat's at its line ends when they do not overlap."""
    crops = [(_get(runs, n), "wheat_winter") for n in EARLIER] + [(_get(runs, n), c) for n, c in zip(CROP_RUNS, CROPS)]
    rows = [("agriculture", [(r, CROP_COLORS[c], c) for r, c in crops if r])]
    for sector in SECTORS[1:]:
        pair = [_get(runs, n) for n in PAIRS[sector][0][1:]]
        rows.append((sector, [(r, SECTOR_COLORS[sector], None) for r in pair if r]))
    rows = [(sector, lines) for sector, lines in rows if lines]
    if not rows:
        return None
    fig, axes = figure(height=2.2 * len(rows) + 0.5, nrows=len(rows), width=16, sharey=True)
    top = max(r["peak"] for _, lines in rows for r, _, _ in lines)
    panels = []
    for (sector, lines), (ax,) in zip(rows, axes):
        ref = lines[0][0]  # the master when it has finished, as it comes first
        position = stage_axis(ref)
        ends = []
        for r, color, crop in lines:
            values = r["series"]["cgroup"].dropna()
            x, y = position(r, values.index.to_numpy()), values.to_numpy()
            ax.plot(x, y, color=color, linestyle=STYLES[r["version"]], linewidth=1.0)
            drawn = np.flatnonzero(~np.isnan(x))
            if len(drawn) and crop in (None, "wheat_winter"):
                ends.append((x[drawn[-1]], y[drawn[-1]], "%.1f" % r["peak"]))
        ax.set_ylim(0, 1.1 * top)
        marks(ax, ref, smallest=0.02, bands=True)
        ax.set_xlabel("Hours since start (%s, %s)" % (ref["name"], ref["partition"]))
        ax.set_ylabel("%s\nJob memory (GiB)" % sector)
        panels.append((ax, ends, sector != "agriculture"))
    versions = {r["version"] for _, lines in rows for r, _, _ in lines}
    fig.legend(handles=[Line2D([], [], color="0.25", linestyle=STYLES[v], linewidth=1.2, label=v)
                        for v in COLORS if v in versions], loc="outside upper left", ncols=len(versions))
    bare = end_labels(fig, panels)
    if rows[0][0] == "agriculture":
        ax, lines = axes[0][0], rows[0][1]
        handles = []
        for crop in CROPS:
            peaks = ["%.1f" % r["peak"] for r, _, c in lines if c == crop]
            if peaks and (crop != "wheat_winter" or ax in bare):
                label = "%s, %s" % (crop.replace("_", " "), " and ".join(peaks))
            elif peaks:
                label = crop.replace("_", " ")
            else:
                continue
            handles.append(Line2D([], [], color=CROP_COLORS[crop], linewidth=1.8, label=label))
        ax.legend(handles=handles, loc="upper left", ncols=len(handles), fontsize=7)
    return fig


def versions_over_run(chosen, series="cgroup", ylabel="Job memory (GiB)", width=10.0, height=3.4):
    """Memory of several runs on the first run's stages, in light gray stage bands: gray master,
    dark teal lazy econ model, dashed with a collection every minute, the peak at each line end."""
    ref = chosen[0]
    position = stage_axis(ref)
    fig, ((ax,),) = figure(height=height, width=width)
    ends, tops = [], []
    for r in chosen:
        code, gc = r["version"].replace(" + gc", ""), r["version"].endswith("+ gc")
        values = r["series"][series].dropna()
        x, y = position(r, values.index.to_numpy()), values.to_numpy()
        label = "%s (%s)" % (r["name"], r["version"].replace("lazy econ model + gc", "lazy + gc"))
        color = COLORS["master"] if code == "master" else COLORS[GC]
        ax.plot(x, y, color=color, linestyle="--" if gc else "-", linewidth=1.2, label=label)
        peak = r["peak"] if series == "cgroup" else r["peak_process"]
        tops.append(peak)
        drawn = np.flatnonzero(~np.isnan(x))
        if len(drawn):
            ends.append((x[drawn[-1]], y[drawn[-1]], "peak %.1f GiB" % peak))
    ax.set_ylim(0, 1.15 * max(tops))
    marks(ax, ref, smallest=0.02, bands=True)
    ax.set_xlabel("Hours since start (%s, %s)" % (ref["name"], ref["partition"]))
    ax.set_ylabel(ylabel)
    fig.legend(loc="outside upper left", ncols=len(chosen))
    end_labels(fig, [(ax, ends, True)])
    return fig


def gc_pauses(runs):
    """Length of each garbage collection pass, one panel per gc setting, once two settings have finished."""
    chosen = [(label, _get(runs, n)) for label, n in GC_SETTINGS if _get(runs, n) and runs[n]["gc"] is not None]
    if len(chosen) < 2:
        return None
    fig, axes = figure(height=1.9, ncols=len(chosen), sharex=True)
    bins = np.linspace(0, max(r["gc"]["seconds"].max() for _, r in chosen), 31)
    for ax, (label, r) in zip(axes[0], chosen):
        seconds = r["gc"]["seconds"]
        ax.hist(seconds, bins=bins, color=COLORS[r["version"]])
        ax.set_xlabel("Pause (s), %s\nmedian %.1f s, %d passes" % (label, seconds.median(), len(seconds)))
    axes[0][0].set_ylabel("Passes")
    return fig


def units_figure(runs):
    """Job memory of master and lazy econ model + gc with three units in one process, one row per pair,
    on the master's clock with each unit marked and the peak at each line end."""
    rows = [(label, [_get(runs, m), _get(runs, g)]) for label, m, g in MULTI_UNIT]
    rows = [(label, pair) for label, pair in rows if any(pair)]
    if not rows:
        return None
    fig, axes = figure(height=2.3 * len(rows) + 0.4, nrows=len(rows))
    panels = [(ax, memory_lines(ax, pair, ylabel="%s\nJob memory (GiB)" % label), True)
              for (label, pair), (ax,) in zip(rows, axes)]
    legend(fig, {r["version"] for _, pair in rows for r in pair if r})
    end_labels(fig, panels)
    return fig
