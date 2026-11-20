"""Figures for the 2026-11-agri-memory-full experiment, from the files in reports/.

Usage: python3 make_figures.py

Writes memory_timeline.png, memory_by_stage.png, histclim_spike.png and
run_lag.png next to this script, 1600 px wide on white. Each run folder in
reports/ has trace.json (memory, stages and year lines) and markers.tsv (the
stage lines of the log with the time the sampler saw them).
"""

import json
import os
import re
import statistics

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

OUT = os.path.dirname(os.path.abspath(__file__))
REPORTS = os.path.join(os.path.dirname(OUT), "reports")

WIDTH_IN, DPI = 8.0, 200

TEXT = "#0b0b0b"
TEXT_2 = "#52514e"
GRID = "#e4e3de"
AXIS = "#b9b8b2"
BAND_A = "#f4f3ef"
BAND_B = "#ffffff"
COVARIATES = "#e3e1da"
BLUE, ORANGE, AQUA, YELLOW = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"

RUNS = {
    "baseline": ("Single on master (baseline)", BLUE),
    "econfix": ("Single, lazy economic model (econfix)", ORANGE),
    "mcunit": ("Montecarlo unit on master (mcunit)", AQUA),
    "mcunit_econfix": ("Montecarlo unit, lazy economic model (mcunit_econfix)", YELLOW),
}
VARIANTS = ["fulladapt", "noadapt", "incadapt", "global", "histclim",
            "noadapt-histclim", "incadapt-histclim", "global-histclim"]

plt.rcParams.update({
    "font.family": ["Arial", "DejaVu Sans"],
    "font.size": 12,
    "text.color": TEXT,
    "axes.labelcolor": TEXT_2,
    "axes.edgecolor": AXIS,
    "xtick.color": TEXT_2,
    "ytick.color": TEXT_2,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "savefig.facecolor": "white",
})


def load_run(run):
    """Memory, stages, year lines and log markers of one run, in seconds since its start.

    Parameters
    ----------
    run : str

    Returns
    -------
    dict
    """
    with open(os.path.join(REPORTS, run, "trace.json")) as fp:
        trace = json.load(fp)
    events = trace["traceEvents"]
    start = trace["metadata"]["start_epoch"]
    memory = [(e["ts"] / 1e6, e["args"]["projection_rss"]) for e in events
              if e.get("name") == "memory GB" and "projection_rss" in e["args"]]
    slices = sorted(((e["name"], e["ts"] / 1e6, (e["ts"] + e["dur"]) / 1e6)
                     for e in events if e.get("ph") == "X"), key=lambda s: (s[1], -s[2]))
    stages = []
    for name, t0, t1 in slices:
        if name in VARIANTS:
            parts = {n: (a, b) for n, a, b in slices
                     if n in ("covariates", "calculation setup", "years") and t0 <= a < t1}
            stages.append(dict(name=name, start=t0, end=t1, parts=parts))
    startup = [(n, a, b) for n, a, b in slices if n.startswith("startup")]
    markers = []
    with open(os.path.join(REPORTS, run, "markers.tsv"), errors="replace") as fp:
        for line in fp:
            if "\t" in line:
                t, text = line.rstrip("\n").split("\t", 1)
                markers.append((float(t) - start, text))
    return dict(start=start, memory=memory, stages=stages, startup=startup, markers=markers)


def clean(ax, grid_axis="y"):
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.grid(axis=grid_axis, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(length=0)


def save(fig, name):
    fig.savefig(os.path.join(OUT, name), dpi=DPI)
    plt.close(fig)
    print("wrote", name)


def window(run_data, a, b):
    """Memory points with a <= t < b."""
    return [y for t, y in run_data["memory"] if a <= t < b]


def timeline(data):
    """Memory of the projection process over each run, with the variants shaded.

    Each panel shades the stages of its own runs: mcunit_econfix ran on a
    slower CPU, so its stages fall later than mcunit's.
    """
    fig, axes = plt.subplots(3, 1, figsize=(WIDTH_IN, 9.0), sharex=True, sharey=True)
    fig.subplots_adjust(left=0.075, right=0.985, top=0.9, bottom=0.062, hspace=0.12)
    top = 25.0
    for ax, runs in zip(axes, (["baseline", "econfix"], ["mcunit"], ["mcunit_econfix"])):
        ref = data[runs[0]]
        for i, st in enumerate(ref["stages"]):
            ax.axvspan(st["start"] / 3600, st["end"] / 3600, color=BAND_A if i % 2 == 0 else BAND_B,
                       linewidth=0, zorder=0)
            a, b = st["parts"]["covariates"]
            ax.axvspan(a / 3600, b / 3600, color=COVARIATES, linewidth=0, zorder=0)
            label = st["name"].replace("-", "\n")
            ax.text((st["start"] + st["end"]) / 7200, top - 0.6, label, ha="center", va="top",
                    fontsize=9, color=TEXT_2, linespacing=1.0)
            ax.plot(st["end"] / 3600, top, marker="v", markersize=5, color=TEXT_2, clip_on=False,
                    zorder=4)
        load_end = [b for n, a, b in ref["startup"] if n.endswith("economic models")][0]
        load_peak = max(window(ref, 0, load_end + 2))
        ax.annotate("economic models", xy=(load_end / 3600, load_peak), xytext=(0.3, 7.5),
                    fontsize=9, color=TEXT_2, ha="left", va="center",
                    arrowprops=dict(arrowstyle="-", color=TEXT_2, linewidth=0.8))
        for run in runs:
            xs = [t / 3600 for t, _ in data[run]["memory"]]
            ys = [y for _, y in data[run]["memory"]]
            color = RUNS[run][1]
            ax.plot(xs, ys, color=color, linewidth=1.3, zorder=3)
            k = max(range(len(ys)), key=ys.__getitem__)
            ax.plot(xs[k], ys[k], "o", color=color, markersize=6, markeredgecolor="white",
                    markeredgewidth=1.2, zorder=5)
        clean(ax)
        ax.set_ylim(0, top)
        ax.set_yticks(range(0, 25, 4))
        ax.set_ylabel("GiB")
    axes[-1].set_xlim(0, 10.32)
    axes[-1].set_xlabel("Hours since the start of the run")
    handles = [Line2D([], [], color=RUNS[r][1], linewidth=2.5) for r in RUNS]
    handles += [Patch(color=COVARIATES), Line2D([], [], marker="v", color=TEXT_2, linestyle="none",
                                                 markersize=6)]
    labels = [RUNS[r][0] for r in RUNS] + ["Covariates (reads the baseline weather)", "Output file written"]
    fig.legend(handles, labels, loc="upper left", ncol=2, frameon=False, bbox_to_anchor=(0.065, 1.0),
               fontsize=10, handlelength=1.6, columnspacing=1.4)
    save(fig, "memory_timeline.png")


def by_stage(data):
    """Master against the lazy economic model at the same stage: startup peak, then the median of each year loop."""
    rows = []
    for run in ("baseline", "econfix"):
        load_end = [b for n, a, b in data[run]["startup"] if n.endswith("economic models")][0]
        values = [max(window(data[run], 0, load_end + 2))]
        for st in data[run]["stages"]:
            a, b = st["parts"]["years"]
            values.append(statistics.median(window(data[run], a, b)))
        rows.append(values)
    labels = ["Startup (peak)"] + ["%s year loop" % v for v in VARIANTS]
    fig, ax = plt.subplots(figsize=(WIDTH_IN, 4.6))
    fig.subplots_adjust(left=0.27, right=0.82, top=0.9, bottom=0.12)
    ys = list(range(len(labels)))[::-1]
    for y, master, branch in zip(ys, rows[0], rows[1]):
        ax.plot([master, branch], [y, y], color=AXIS, linewidth=2, zorder=2)
        ax.plot(master, y, "o", color=BLUE, markersize=9, markeredgecolor="white", zorder=3)
        ax.plot(branch, y, "o", color=ORANGE, markersize=9, markeredgecolor="white", zorder=3)
        diff = branch - master
        text = "%+.1f GiB" % diff if abs(diff) >= 0.05 else "0.0 GiB"
        ax.text(20.6, y, text.replace("-", "−"), va="center", ha="left", fontsize=11,
                fontweight="bold")
    ax.set_yticks(ys)
    ax.set_yticklabels(labels, fontsize=11, color=TEXT)
    clean(ax, grid_axis="x")
    ax.spines["bottom"].set_visible(False)
    ax.set_xlim(0, 20)
    ax.set_xticks(range(0, 21, 4))
    ax.set_ylim(-0.6, len(labels) - 0.4)
    ax.set_xlabel("GiB")
    handles = [Line2D([], [], marker="o", color=c, linestyle="none", markersize=9) for c in (BLUE, ORANGE)]
    fig.legend(handles, ["Master (baseline)", "Lazy economic model (econfix)"], loc="upper left", ncol=2, frameon=False,
               bbox_to_anchor=(0.02, 1.0), fontsize=11)
    ax.text(20.6, len(labels) - 0.45, "lazy economic model\nminus master", ha="left", va="bottom", fontsize=10,
            color=TEXT_2, clip_on=False)
    save(fig, "memory_by_stage.png")


def histclim_spike(data):
    """The covariate step of the first histclim variant, with each seasonal covariate marked."""
    fig, ax = plt.subplots(figsize=(WIDTH_IN, 4.0))
    fig.subplots_adjust(left=0.075, right=0.985, top=0.86, bottom=0.14)
    ref = None
    for run in ("baseline", "econfix"):
        st = [s for s in data[run]["stages"] if s["name"] == "histclim"][0]
        a, b = st["parts"]["covariates"]
        pts = [((t - a) / 60, y) for t, y in data[run]["memory"] if a - 120 <= t <= b + 60]
        ax.plot([p[0] for p in pts], [p[1] for p in pts], color=RUNS[run][1], linewidth=1.6, zorder=3)
        if run == "econfix":
            ref = (data[run], a, b)
    run_data, a, b = ref
    for t, text in run_data["markers"]:
        match = re.match(r"Collecting baseline information: Mean of (\w+)", text)
        if match and a - 1 <= t <= b:
            x = (t - a) / 60
            ax.axvline(x, color=AXIS, linewidth=0.8, linestyle=(0, (3, 3)), zorder=1)
            ax.text(x + 0.15, 23.6, match.group(1), fontsize=9, color=TEXT_2, va="top")
    ax.axvline((b - a) / 60, color=TEXT_2, linewidth=0.8, zorder=1)
    ax.text((b - a) / 60 - 0.15, 22.4, "year loop starts", fontsize=9, color=TEXT_2, va="top", ha="right")
    clean(ax)
    ax.set_xlim(-2, (b - a) / 60 + 1)
    ax.set_ylim(8, 24)
    ax.set_yticks(range(8, 25, 4))
    ax.set_ylabel("GiB")
    ax.set_xlabel("Minutes since the histclim variant started")
    handles = [Line2D([], [], color=RUNS[r][1], linewidth=2.5) for r in ("baseline", "econfix")]
    fig.legend(handles, [RUNS[r][0] for r in ("baseline", "econfix")], loc="upper left", ncol=2,
               frameon=False, bbox_to_anchor=(0.065, 1.0), fontsize=11)
    save(fig, "histclim_spike.png")


def keyed_markers(run_data):
    """Map (variant, log line, nth time) to its time, so two runs can be matched line by line."""
    out = {}
    counts = {}
    variant = None
    for t, text in run_data["markers"]:
        match = re.match(r"REDO: Cannot find (.+?)\.nc4", text)
        if match:
            parts = os.path.basename(match.group(1)).split("-")
            variant = "-".join(parts[2:]) or "fulladapt"
        key = (variant, re.sub(r"/scratch\S+", "", text))
        counts[key] = counts.get(key, 0) + 1
        out[key + (counts[key],)] = t
    return out


def lag(data):
    """How far each run is behind the master single at the same log line."""
    base = keyed_markers(data["baseline"])
    fig, ax = plt.subplots(figsize=(WIDTH_IN, 3.6))
    fig.subplots_adjust(left=0.085, right=0.985, top=0.87, bottom=0.15)
    for run in ("econfix", "mcunit"):
        other = keyed_markers(data[run])
        segments = {}
        for key, t in base.items():
            if key in other and key[0] is not None:
                behind = (data[run]["start"] + other[key]) - (data["baseline"]["start"] + t)
                segments.setdefault(key[0], []).append((t / 3600, behind))
        for variant in VARIANTS:
            if variant in segments and (run != "mcunit" or variant in ("fulladapt", "noadapt", "incadapt")):
                pts = sorted(segments[variant])
                ax.plot([p[0] for p in pts], [p[1] for p in pts], color=RUNS[run][1], linewidth=1.6)
    ax.axhline(0, color=TEXT_2, linewidth=0.8)
    clean(ax)
    ax.set_xlim(0, 10.32)
    ax.set_ylim(-60, 340)
    ax.set_yticks(range(-50, 351, 50))
    ax.set_ylabel("Seconds behind baseline")
    ax.set_xlabel("Hours since the start of the run")
    handles = [Line2D([], [], color=RUNS[r][1], linewidth=2.5) for r in ("econfix", "mcunit")]
    fig.legend(handles, [RUNS[r][0] for r in ("econfix", "mcunit")], loc="upper left", ncol=2,
               frameon=False, bbox_to_anchor=(0.075, 1.0), fontsize=11)
    save(fig, "run_lag.png")


if __name__ == "__main__":
    runs = {run: load_run(run) for run in RUNS}
    timeline(runs)
    by_stage(runs)
    histclim_spike(runs)
    lag(runs)
