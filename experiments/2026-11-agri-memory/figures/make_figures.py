"""Figures for the 2026-11-agri-memory experiment, from the files in reports/.

Usage: python3 make_figures.py

Writes memory_timeline.png, peak_memory.png, memory_at_peak.png and
time_breakdown.png next to this script, 1600 px wide on white.
flamegraph_screenshot.png is a capture of the memray flame graph in a browser,
zoomed on the NewSSPEconomicModel call, so this script does not make it.
"""

import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

OUT = os.path.dirname(os.path.abspath(__file__))
REPORTS = os.path.join(os.path.dirname(OUT), "reports")

GiB = 1024 ** 3
WIDTH_IN, DPI = 8.0, 200

TEXT = "#0b0b0b"
TEXT_2 = "#52514e"
GRID = "#e4e3de"
AXIS = "#b9b8b2"
BAND_A = "#f1f0ec"
BAND_B = "#ffffff"
NEUTRAL = "#b9b8b2"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
RUN_COLOR = {"baseline-quick": BLUE, "econfix-quick": ORANGE, "oneecon-quick": AQUA}

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


def load(path):
    with open(path) as fp:
        return json.load(fp)


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


def pct(share):
    return "%d%%" % round(share * 100) if share >= 0.095 else "%.1f%%" % (share * 100)


def timeline():
    """Memory of the projection process each second, with the stages shaded."""
    runs = [("baseline-quick", "Master (baseline-quick)"),
            ("econfix-quick", "Lazy economic model (econfix-quick)")]
    fig, axes = plt.subplots(2, 1, figsize=(WIDTH_IN, 5.6), sharex=True, sharey=True)
    fig.subplots_adjust(left=0.085, right=0.98, top=0.9, bottom=0.11, hspace=0.18)
    for ax, (run, _) in zip(axes, runs):
        trace = load(os.path.join(REPORTS, run, "trace.json"))["traceEvents"]
        points = [(e["ts"] / 6e7, e["args"]["projection_rss"]) for e in trace
                  if e.get("name") == "memory GB" and "projection_rss" in e["args"]]
        variants = sorted((e for e in trace if e.get("ph") == "X"
                           and e["name"] in ("fulladapt", "noadapt", "incadapt", "histclim")),
                          key=lambda e: e["ts"])
        bands = [("startup", 0.0, variants[0]["ts"] / 6e7)]
        bands += [(e["name"], e["ts"] / 6e7, (e["ts"] + e["dur"]) / 6e7) for e in variants]
        for i, (name, start, end) in enumerate(bands):
            ax.axvspan(start, end, color=BAND_A if i % 2 == 0 else BAND_B, linewidth=0, zorder=0)
            ax.text((start + end) / 2, 11.55, name, ha="center", va="top", fontsize=11, color=TEXT_2)
        xs, ys = zip(*points)
        ax.plot(xs, ys, color=RUN_COLOR[run], linewidth=1.9, zorder=3)
        clean(ax)
        ax.set_ylim(0, 12)
        ax.set_yticks(range(0, 13, 2))
        ax.set_ylabel("GiB")
        ax.set_xlim(0, max(bands[-1][2], xs[-1]))
    axes[-1].set_xlabel("Minutes since the start of the run")
    handles = [Line2D([], [], color=RUN_COLOR[run], linewidth=2.5) for run, _ in runs]
    fig.legend(handles, [label for _, label in runs], loc="upper left", ncol=2, frameon=False,
               bbox_to_anchor=(0.075, 0.995), fontsize=12, handlelength=1.6)
    save(fig, "memory_timeline.png")


def peaks():
    """Peak memory of each quick run, from the manifests."""
    rows = [("baseline-quick", "Master, ten economic models\nbaseline-quick"),
            ("oneecon-quick", "Master, one economic model\noneecon-quick"),
            ("econfix-quick", "Lazy economic model, ten models\neconfix-quick")]
    values = [load(os.path.join(REPORTS, run, "manifest.json"))["telemetry"]["peak_rss_gb"]
              for run, _ in rows]
    fig, ax = plt.subplots(figsize=(WIDTH_IN, 3.0))
    fig.subplots_adjust(left=0.34, right=0.96, top=0.97, bottom=0.18)
    ys = list(range(len(rows)))[::-1]
    for y, (run, _), value in zip(ys, rows, values):
        ax.barh(y, value, height=0.56, color=RUN_COLOR[run], zorder=2)
        ax.text(value + 0.15, y, "%.1f GiB" % value, va="center", fontsize=13, fontweight="bold")
    ax.set_yticks(ys)
    ax.set_yticklabels([label for _, label in rows], fontsize=12, color=TEXT)
    clean(ax, grid_axis="x")
    ax.spines["bottom"].set_visible(False)
    ax.set_xlim(0, 12)
    ax.set_xticks(range(0, 13, 2))
    ax.set_xlabel("GiB")
    save(fig, "peak_memory.png")


def memray_breakdown():
    """What held memory at the peak, from the data inside memray's flame graph."""
    with open(os.path.join(REPORTS, "memray-quick", "memray-flamegraph.html")) as fp:
        html = fp.read()
    start = html.find("packed_data = ") + len("packed_data = ")
    data, _ = json.JSONDecoder().raw_decode(html[start:])
    nodes, strings = data["nodes"], data["strings"]
    total = nodes["value"][0]

    def line_total(lineno):
        return sum(v for f, fn, ln, v in zip(nodes["filename"], nodes["function"], nodes["lineno"],
                                             nodes["value"])
                   if strings[f].endswith("new_econmodel.py") and strings[fn] == "__init__"
                   and ln == lineno)

    parts = [("Age shares (line 100)", line_total(100), BLUE),
             ("Population table (line 84)", line_total(84), ORANGE)]
    parts.append(("Everything else", total - sum(p[1] for p in parts), NEUTRAL))
    fig, ax = plt.subplots(figsize=(WIDTH_IN, 1.9))
    fig.subplots_adjust(left=0.02, right=0.98, top=0.98, bottom=0.02)
    left = 0.0
    for name, value, color in parts:
        ax.barh(0, value / GiB, left=left, height=0.5, color=color, edgecolor="white",
                linewidth=2, zorder=2)
        ax.text(left + 0.06, 0.34, name, ha="left", va="bottom", fontsize=12, fontweight="bold")
        ax.text(left + 0.06, -0.34, "%.1f GiB, %s" % (value / GiB, pct(value / total)), ha="left",
                va="top", fontsize=12, color=TEXT_2)
        left += value / GiB
    ax.set_xlim(0, total / GiB)
    ax.set_ylim(-0.66, 0.66)
    ax.axis("off")
    save(fig, "memory_at_peak.png")


def time_shares():
    """Time by group, from the pyinstrument session inside profile.html."""
    with open(os.path.join(REPORTS, "pyinstrument-quick", "profile.html")) as fp:
        html = fp.read()
    start = html.find("const sessionData = ") + len("const sessionData = ")
    session, _ = json.JSONDecoder().raw_decode(html[start:])
    totals = {}

    def group_of(name, path, group):
        if name == "create_covariator":
            return "Climate covariates"
        if name == "generate" and path.endswith("generate/effectset.py"):
            return "Impacts (yearly loop)"
        if name == "iterate_econmodels_new":
            return "Economic models"
        return group

    # Each frame's own time goes to the group of its nearest grouped caller.
    # xarray's file format check, and everything it calls, is its own group.
    def walk(frame, group, detecting):
        name = frame["function"]
        group = group_of(name, frame.get("file_path_short", ""), group)
        if name == "try_read_magic_number_from_path":
            detecting = True
        children = frame.get("children", [])
        own = float(frame["time"]) - sum(float(c["time"]) for c in children)
        key = "File format detection" if detecting else group
        totals[key] = totals.get(key, 0.0) + max(own, 0.0)
        for child in children:
            walk(child, group, detecting)

    walk(session["root_frame"], "Everything else", False)
    whole = float(session["root_frame"]["time"])
    order = ["Climate covariates", "Impacts (yearly loop)", "Economic models",
             "File format detection", "Everything else"]
    fig, ax = plt.subplots(figsize=(WIDTH_IN, 3.3))
    fig.subplots_adjust(left=0.235, right=0.96, top=0.97, bottom=0.16)
    ys = list(range(len(order)))[::-1]
    for y, key in zip(ys, order):
        value = totals.get(key, 0.0)
        ax.barh(y, value, height=0.58, color=BLUE, zorder=2)
        ax.text(value + 15, y, "%s s, %s" % (format(round(value), ","), pct(value / whole)),
                va="center", fontsize=12, fontweight="bold")
    ax.set_yticks(ys)
    ax.set_yticklabels(order, fontsize=12, color=TEXT)
    clean(ax, grid_axis="x")
    ax.spines["bottom"].set_visible(False)
    ax.set_xlim(0, 2000)
    ax.set_xlabel("Seconds")
    save(fig, "time_breakdown.png")


if __name__ == "__main__":
    timeline()
    peaks()
    memray_breakdown()
    time_shares()
