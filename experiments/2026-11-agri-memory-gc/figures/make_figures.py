"""Figures for the 2026-11-agri-memory-gc experiment.

Usage: python3 make_figures.py

Writes memory_timeline.png (singles), memory_timeline_mcunit.png (montecarlo
units) and peak_memory.png next to this script, 1600 px wide on white. The gc
runs come from reports/ here, baseline, econfix, mcunit and mcunit_econfix from
the full-run experiment's reports/.
"""

import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

OUT = os.path.dirname(os.path.abspath(__file__))
HERE = os.path.join(os.path.dirname(OUT), "reports")
FULL = os.path.join(os.path.dirname(os.path.dirname(OUT)), "2026-11-agri-memory-full", "reports")

WIDTH_IN, DPI = 8.0, 200

TEXT = "#0b0b0b"
TEXT_2 = "#52514e"
GRID = "#e4e3de"
BAND_A = "#f4f3ef"
BAND_B = "#ffffff"
# Same colors as the dashboard: one per code version
RUNS = {
    "baseline": ("baseline (master)", "#898781", FULL),
    "econfix": ("econfix (lazy economic model)", "#6250d6", FULL),
    "gccollect": ("gccollect (master, collection every minute)", "#1baf7a", HERE),
    "gccollect_econfix": ("gccollect_econfix (lazy economic model, collection every minute)", "#e87ba4", HERE),
    "mcunit": ("mcunit (master)", "#898781", FULL),
    "mcunit_econfix": ("mcunit_econfix (lazy economic model)", "#6250d6", FULL),
    "mcunit_gccollect_econfix": ("mcunit_gccollect_econfix (lazy economic model, collection every minute)", "#e87ba4", HERE),
}
SINGLES = ["baseline", "econfix", "gccollect", "gccollect_econfix"]
UNITS = ["mcunit", "mcunit_econfix", "mcunit_gccollect_econfix"]
VARIANTS = ["fulladapt", "noadapt", "incadapt", "global", "histclim",
            "noadapt-histclim", "incadapt-histclim", "global-histclim"]
UNIT_VARIANTS = ["fulladapt", "noadapt", "incadapt", "histclim"]
STARTUP_WIDTH = 0.5

plt.rcParams.update({
    "font.family": ["Arial", "DejaVu Sans"],
    "font.size": 12,
    "text.color": TEXT,
    "axes.labelcolor": TEXT_2,
    "axes.edgecolor": "#b9b8b2",
    "xtick.color": TEXT_2,
    "ytick.color": TEXT_2,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "savefig.facecolor": "white",
})


def load_run(run):
    """Memory and stages of one run, in seconds since its start, plus its manifest.

    Parameters
    ----------
    run : str

    Returns
    -------
    dict
    """
    folder = os.path.join(RUNS[run][2], run)
    with open(os.path.join(folder, "trace.json")) as fp:
        events = json.load(fp)["traceEvents"]
    with open(os.path.join(folder, "manifest.json")) as fp:
        manifest = json.load(fp)
    memory = [(e["ts"] / 1e6, e["args"]["projection_rss"]) for e in events
              if e.get("name") == "memory GB" and "projection_rss" in e["args"]]
    cgroup = max(e["args"]["cgroup_total"] for e in events if e.get("name") == "memory GB" and "cgroup_total" in e["args"])
    slices = [(e["name"], e["ts"] / 1e6, (e["ts"] + e["dur"]) / 1e6) for e in events if e.get("ph") == "X"]
    startup_end = max(b for n, a, b in slices if n.startswith("startup"))
    stages = [("startup", 0.0, startup_end)] + sorted((s for s in slices if s[0] in VARIANTS), key=lambda s: s[1])
    return dict(memory=memory, cgroup=cgroup, stages=stages, manifest=manifest)


def position(stages, t):
    """Place a time on the shared stage axis: startup is 0.5 wide, each variant 1."""
    for i, (name, a, b) in enumerate(stages):
        if a <= t < b or i == len(stages) - 1:
            start = 0.0 if i == 0 else STARTUP_WIDTH + i - 1
            width = STARTUP_WIDTH if i == 0 else 1.0
            return start + width * min(max((t - a) / max(b - a, 1e-9), 0.0), 1.0)
    return 0.0


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


def timeline(data, runs, variants, name, legend_columns):
    """Memory of the projection process in the given runs, on one stage axis."""
    fig, ax = plt.subplots(figsize=(WIDTH_IN, 4.8))
    fig.subplots_adjust(left=0.075, right=0.985, top=0.84 if legend_columns == 2 else 0.8, bottom=0.04)
    top = 25.0
    ax.axvspan(0, STARTUP_WIDTH, color=BAND_B, linewidth=0, zorder=0)
    ax.text(STARTUP_WIDTH / 2, top - 0.6, "start-\nup", ha="center", va="top", fontsize=9, color=TEXT_2, linespacing=1.0)
    for i, variant in enumerate(variants):
        x0 = STARTUP_WIDTH + i
        ax.axvspan(x0, x0 + 1, color=BAND_A if i % 2 == 0 else BAND_B, linewidth=0, zorder=0)
        ax.text(x0 + 0.5, top - 0.6, variant.replace("-", "\n"), ha="center", va="top", fontsize=9, color=TEXT_2,
                linespacing=1.0)
    for run in runs:
        d = data[run]
        xs = [position(d["stages"], t) for t, _ in d["memory"]]
        ys = [y for _, y in d["memory"]]
        color = RUNS[run][1]
        ax.plot(xs, ys, color=color, linewidth=1.3, zorder=3)
        k = max(range(len(ys)), key=ys.__getitem__)
        ax.plot(xs[k], ys[k], "o", color=color, markersize=6, markeredgecolor="white", markeredgewidth=1.2, zorder=5)
    clean(ax)
    ax.set_xlim(0, STARTUP_WIDTH + len(variants))
    ax.set_xticks([])
    ax.set_ylim(0, top)
    ax.set_yticks(range(0, 25, 4))
    ax.set_ylabel("GiB")
    handles = [Line2D([], [], color=RUNS[r][1], linewidth=2.5) for r in runs]
    fig.legend(handles, [RUNS[r][0] for r in runs], loc="upper left", ncol=legend_columns, frameon=False,
               bbox_to_anchor=(0.065, 1.0), fontsize=10, handlelength=1.6, columnspacing=1.4)
    save(fig, name)


def peaks(data):
    """Peak of the job's memory cgroup in each run, singles first, then the montecarlo units."""
    fig, ax = plt.subplots(figsize=(WIDTH_IN, 4.6))
    fig.subplots_adjust(left=0.3, right=0.9, top=0.97, bottom=0.11)
    rows = [(i, run) for i, run in enumerate(SINGLES)] + [(i + len(SINGLES) + 0.6, run) for i, run in enumerate(UNITS)]
    for y, run in rows:
        value = data[run]["cgroup"]
        ax.barh(y, value, color=RUNS[run][1], height=0.6, zorder=3)
        ax.text(value + 0.3, y, "%.1f GiB" % value, va="center", ha="left", fontsize=11, fontweight="bold")
    ax.set_yticks([y for y, _ in rows])
    ax.set_yticklabels([RUNS[r][0].replace(" (", "\n(").replace(", collection", ",\ncollection") for _, r in rows],
                       fontsize=10, color=TEXT, linespacing=1.0)
    ax.set_ylim(rows[-1][0] + 0.6, -0.6)
    clean(ax, grid_axis="x")
    ax.spines["bottom"].set_visible(False)
    ax.set_xlim(0, 25)
    ax.set_xticks(range(0, 25, 4))
    ax.set_xlabel("GiB")
    save(fig, "peak_memory.png")


def main():
    data = {run: load_run(run) for run in RUNS}
    timeline(data, SINGLES, VARIANTS, "memory_timeline.png", 2)
    timeline(data, UNITS, UNIT_VARIANTS, "memory_timeline_mcunit.png", 1)
    peaks(data)


if __name__ == "__main__":
    main()
