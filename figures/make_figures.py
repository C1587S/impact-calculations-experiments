"""Figures for the Summary of the root README, in the dashboard's figure style.

Usage: python3 figures/make_figures.py

Writes peak_memory.png, memory_singles.png and memory_annotated.png next to
this script, from the runs under experiments/*/reports/, loaded with
dashboard/utils.py. Over the run, hours are those of baseline on cil, and each
stage of the other runs is stretched to its length in baseline.
"""

import os
import sys
from pathlib import Path

import numpy as np
from matplotlib.patches import Patch

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "dashboard"))
import utils  # noqa: E402

OUT = Path(__file__).resolve().parent
NAMES = {"master": "master", "branch": "lazy economic model", "master + gc": "master + gc every minute",
         "branch + gc": "lazy economic model + gc every minute"}
SINGLES = ["baseline", "econfix", "gccollect", "gccollect_econfix"]
UNITS = ["mcunit", "mcunit_econfix", "mcunit_gccollect_econfix"]


def peaks(runs):
    """Cgroup peak of the full runs: singles and montecarlo units side by side, on one x scale."""
    fig, axes = utils.figure(height=1.9, ncols=2, sharey=False, sharex=True)
    for ax, names, title in zip(axes, (SINGLES, UNITS), ("single", "montecarlo unit")):
        chosen = [runs[n] for n in names]
        y = np.arange(len(chosen))
        ax.barh(y, [r["peak"] for r in chosen], color=[utils.COLORS[r["version"]] for r in chosen], height=0.65)
        for yi, r in zip(y, chosen):
            ax.text(r["peak"] + 0.3, yi, "%.1f" % r["peak"], va="center", fontsize=7)
        ax.set_yticks(y, names)
        ax.set_ylim(len(SINGLES) - 0.5, -0.5)
        ax.set_title(title, fontsize=8)
        ax.set_xlabel("Peak memory, job cgroup (GiB)")
    axes[0].set_xlim(0, 25)
    fig.legend(handles=[Patch(color=utils.COLORS[v], label=NAMES[v]) for v in utils.VERSIONS],
               loc="outside upper left", ncols=2)
    fig.savefig(OUT / "peak_memory.png", dpi=200)
    print("wrote peak_memory.png")


def singles(runs):
    """Job memory of the four full singles over the run, on baseline's clock."""
    chosen = [runs[n] for n in SINGLES]
    ref = runs["baseline"]
    position = utils.stage_axis(ref)
    fig, (ax,) = utils.figure(height=2.8)
    for r in chosen:
        values = r["series"]["cgroup"].dropna()
        ax.plot(position(r, values.index.to_numpy()), values.to_numpy(), color=utils.COLORS[r["version"]],
                label="%s (%s)" % (r["name"], NAMES[r["version"]]))
    utils.stage_names(ax, ref)
    ax.set_ylim(0, None)
    ax.set_xlabel(utils.time_label(ref))
    ax.set_ylabel("Job memory, cgroup (GiB)")
    fig.legend(loc="outside upper left", ncols=2)
    fig.savefig(OUT / "memory_singles.png", dpi=200)
    print("wrote memory_singles.png")


def annotated(runs):
    """Baseline against the lazy economic model with a collection every minute, with two notes, on baseline's clock."""
    chosen = [runs["baseline"], runs["gccollect_econfix"]]
    ref = runs["baseline"]
    position = utils.stage_axis(ref)
    spans = {s["key"]: (s["start"] / 3600, s["end"] / 3600) for s in ref["stages"]}
    fig, (ax,) = utils.figure(height=4.0)
    fig.set_size_inches(10, 4)
    lines = {}
    for r in chosen:
        values = r["series"]["cgroup"].dropna()
        x, y = position(r, values.index.to_numpy()), values.to_numpy()
        ax.plot(x, y, color=utils.COLORS[r["version"]], linewidth=1.8,
                label="%s (%s)" % (r["name"], NAMES[r["version"]]))
        lines[r["name"]] = (x, y)
        last = np.flatnonzero(~np.isnan(x))[-1]
        ax.text(x[last] + 0.1, y[last], "peak %.1f GiB" % r["peak"], va="center", fontsize=12)

    # Point at the startup peak and at the start of the histclim spike of baseline.
    x, y = lines["baseline"]
    startup = np.nanargmax(np.where(x < spans["startup"][1], y, np.nan))
    a, b = spans["histclim"]
    spike = np.nanargmax(np.where((x >= a) & (x < b), y, np.nan))
    arrow = dict(arrowstyle="-|>", color="black", linewidth=0.8, shrinkA=2, shrinkB=3)
    ax.annotate("loading the ten\neconomic models", xy=(x[startup], y[startup]), xytext=(0.2, 15.5),
                fontsize=12, arrowprops=arrow)
    ax.annotate("weather data not yet freed", xy=(x[spike], y[spike]), xytext=(1.6, 21.5),
                fontsize=12, arrowprops=arrow)

    utils.stage_names(ax, ref, fontsize=11)
    ax.tick_params(labelsize=11)
    ax.set_ylim(0, 24)
    ax.set_xlabel(utils.time_label(ref), fontsize=12)
    ax.set_ylabel("Job memory, cgroup (GiB)", fontsize=12)
    fig.legend(loc="outside upper left", ncols=2, fontsize=12)
    fig.savefig(OUT / "memory_annotated.png", dpi=200)
    print("wrote memory_annotated.png")


def main():
    runs = {r["name"]: r for r in utils.load_runs(REPO / "dashboard")}
    peaks(runs)
    singles(runs)
    annotated(runs)


if __name__ == "__main__":
    main()
