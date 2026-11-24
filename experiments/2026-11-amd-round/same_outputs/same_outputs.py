# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "matplotlib",
#     "netcdf4",
#     "numpy",
#     "xarray",
# ]
# ///
"""Master against lazy + gc over the years in a few regions, one PNG per sector, and the largest
absolute difference of every file in a CSV next to the PNG.

Usage:
  same_outputs.py --out labor.png --pair labor <master folder> <lazy + gc folder> [--pair ...]

Files are matched by name below each folder. The plot shows the fulladapt file (the shortest name)
unless --file is given.
"""

import argparse
import csv
import glob
import os

import numpy as np
import xarray as xr
from matplotlib.figure import Figure
from matplotlib.lines import Line2D

# As in the full experiment's same_outputs
REGIONS = {"USA.17.906": "Crawford, Kansas", "USA.14.608": "Cook County, Illinois", "COL.14.568": "Bogotá",
           "NGA.25.508": "Alimosho, Lagos"}
MASTER, GC = "#898781", "#17645f"


def files(folder):
    return {os.path.basename(p): p for p in glob.glob(os.path.join(folder, "**", "*.nc4"), recursive=True)
            if not p.endswith("-aggregated.nc4")}


def largest_difference(a, b):
    """Largest absolute difference over the float variables. NaN in both counts as equal, NaN in one gives NaN."""
    found = []
    with xr.open_dataset(a, decode_times=False) as x, xr.open_dataset(b, decode_times=False) as y:
        for name, var in x.data_vars.items():
            if var.dtype.kind != "f" or name not in y:
                continue
            u, v = var.values, y[name].values
            if u.shape != v.shape:
                return float("nan")
            found.append(np.where(np.isnan(u) & np.isnan(v), 0.0, np.abs(u - v)).max())
    return float(np.max(found)) if found else 0.0


def series(path, variable):
    """Values over the years in each region of REGIONS found in the file."""
    with xr.open_dataset(path, decode_times=False) as ds:
        if variable not in ds:
            variable = next(n for n, v in ds.data_vars.items()
                            if v.dtype.kind == "f" and {"year", "region"} <= set(v.dims))
        names = [str(r) for r in ds["regions"].values]
        var = ds[variable]
        extra = {d: 0 for d in var.dims if d not in ("year", "region")}
        years = ds["year"].values
        return variable, years, {r: var.isel(region=names.index(r), **extra).values for r in REGIONS if r in names}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", required=True, help="PNG to write, the CSV goes next to it")
    parser.add_argument("--pair", nargs=3, action="append", required=True, metavar=("NAME", "MASTER", "RUN"))
    parser.add_argument("--file", help="file to plot, by name (default: the shortest name)")
    parser.add_argument("--variable", default="rebased")
    args = parser.parse_args()

    rows, plots = [], []
    for name, master, run in args.pair:
        a, b = files(master), files(run)
        common = sorted(set(a) & set(b))
        for f in common:
            rows.append((name, f, largest_difference(a[f], b[f])))
        for f in sorted(set(a) ^ set(b)):
            rows.append((name, f, "missing in %s" % ("lazy + gc" if f in a else "master")))
        if common:
            shown = args.file if args.file in common else min(common, key=len)
            variable, years, ref = series(a[shown], args.variable)
            _, _, new = series(b[shown], variable)
            plots.append((name, shown, variable, years, ref, new))

    stem = os.path.splitext(args.out)[0]
    with open(stem + ".csv", "w", newline="") as fp:
        writer = csv.writer(fp)
        writer.writerow(["name", "file", "largest absolute difference"])
        writer.writerows(rows)
    for row in rows:
        print("%-14s %-60s %s" % row)
    if not plots:
        return

    regions = [r for r in REGIONS if any(r in p[4] for p in plots)]
    fig = Figure(figsize=(2.6 * len(regions) + 1.2, 1.8 * len(plots) + 0.6), dpi=150, layout="constrained")
    axes = fig.subplots(len(plots), len(regions), squeeze=False)
    for (name, shown, variable, years, ref, new), row in zip(plots, axes):
        for col, (ax, region) in enumerate(zip(row, regions)):
            for side in ("top", "right"):
                ax.spines[side].set_visible(False)
            ax.tick_params(labelsize=7)
            if region not in ref:
                ax.set_axis_off()
                continue
            ax.plot(years, ref[region], color=MASTER, linewidth=1.8)
            ax.plot(years, new[region], color=GC, linewidth=1.0, linestyle="--")
            if ax is axes[0][col]:
                ax.set_title(REGIONS[region], fontsize=8, loc="left")
        row[0].set_ylabel("%s\n%s" % (name, variable), fontsize=8)
        found = [d for n, f, d in rows if n == name and not isinstance(d, str)]
        largest = float("nan") if any(np.isnan(found)) else max(found, default=0.0)
        row[-1].text(1.02, 0.5, "largest difference\n%.2g" % largest, transform=row[-1].transAxes, fontsize=7,
                     va="center")
    fig.legend(handles=[Line2D([], [], color=MASTER, linewidth=1.8, label="master"),
                        Line2D([], [], color=GC, linewidth=1.0, linestyle="--", label="lazy + gc")],
               loc="outside upper left", ncols=2, frameon=False, fontsize=8)
    fig.savefig(args.out, facecolor="white")
    print("wrote %s and %s.csv" % (args.out, stem))


if __name__ == "__main__":
    main()
