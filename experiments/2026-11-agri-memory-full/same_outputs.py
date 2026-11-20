# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "marimo",
#     "matplotlib",
#     "netcdf4",
#     "pandas",
#     "xarray",
# ]
# ///

import marimo

__generated_with = "0.25.2"
app = marimo.App(
    width="medium",
    app_title="Same outputs on master and the branch",
)


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    Paths to master and the branch
    """)
    return


@app.cell
def _():
    import glob
    import json
    import os
    import subprocess
    import sys
    import tempfile
    import textwrap

    import marimo as mo
    import matplotlib.pyplot as plt
    import numpy as np
    import pandas as pd
    import xarray as xr

    IMPACT_PYTHON = "/project/cil/home_dirs/rcc/envs/impact-env/bin/python"
    MASTER = "/project/cil/home_dirs/scadavidsanchez/repos/impact-calculations"
    BRANCH = "/project/cil/home_dirs/scadavidsanchez/repos/impact-calculations-econfix"
    PANEL = "/project/cil/gcp/outputs_newsocioeconomics/socioeconomics/1.0.0/"
    SCRATCH = "/scratch/midway3/%s/agri-profiling" % os.environ["USER"]

    # Wheat counties in Kansas, Centre, Punjab, Henan and New South Wales,
    # then Cook County (Illinois), Bogotá (Cundinamarca) and Alimosho (Lagos)
    REGIONS = ["USA.17.906", "FRA.24.28", "IND.28.415.1608", "CHN.12.130.914", "AUS.4.291",
               "USA.14.608", "COL.14.568", "NGA.25.508"]
    YEARS = [2020, 2050, 2099]


    def git(repo, *args):
        return subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True).stdout.strip()


    _impact = subprocess.run([IMPACT_PYTHON, "--version"], capture_output=True, text=True)
    mo.plain_text("\n".join(
        ["notebook Python %s" % sys.version.split()[0],
         "projection %s, %s" % ((_impact.stdout or _impact.stderr).strip(), IMPACT_PYTHON)]
        + ["%s %s %s" % (git(_repo, "rev-parse", "--abbrev-ref", "HEAD"), git(_repo, "rev-parse", "--short", "HEAD"), _repo)
           for _repo in (MASTER, BRANCH)]
    ))
    return (
        BRANCH,
        IMPACT_PYTHON,
        MASTER,
        PANEL,
        REGIONS,
        SCRATCH,
        YEARS,
        glob,
        json,
        mo,
        np,
        os,
        pd,
        plt,
        subprocess,
        tempfile,
        textwrap,
        xr,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    Load the SSP3 low economic model on master
    """)
    return


@app.cell
def _(
    IMPACT_PYTHON,
    MASTER,
    PANEL,
    REGIONS,
    YEARS,
    json,
    mo,
    os,
    pd,
    subprocess,
    tempfile,
    textwrap,
):
    # Runs in impact-env's Python 3.7, with only one clone on PYTHONPATH
    LOAD = r"""
    import json, sys, time
    import numpy as np
    from adaptation.precomputed import new_econmodel

    panel, out, regions, years = sys.argv[1], sys.argv[2], sys.argv[3].split(","), [int(y) for y in sys.argv[4].split(",")]
    print("module", new_econmodel.__file__)

    start = time.time()
    model = new_econmodel.NewSSPEconomicModel("low", "SSP3", panel)
    seconds = time.time() - start
    with open("/proc/self/status") as fp:
        rss = [int(line.split()[1]) for line in fp if line.startswith("VmRSS:")][0] / 2**20
    print("loaded in %.0f s, memory after loading %.1f GiB" % (seconds, rss))

    assert all(region in model.pop_future_years for region in regions)
    rows = []
    for item, get in [("population", model.get_population_year), ("popop", model.get_popop_year)]:
        rows += [(item, region, year, get(region, year)) for region in regions for year in years]
    for k, group in enumerate(["age 0-4 share", "age 5-64 share", "age 65+ share"]):
        rows += [(group, region, year, model.get_age_shares(region, year)[k]) for region in regions for year in years]
    baseline = model.baseline_prepared(2015, 13, np.mean)
    for item in ["loggdppc", "popop"]:
        rows += [("baseline " + item, region, 2015, baseline[region][item]) for region in regions]

    with open(out, "w") as fp:
        json.dump([(item, region, year, float(value)) for item, region, year, value in rows], fp)
    """

    WORK = tempfile.mkdtemp()


    def load(repo, side):
        out = os.path.join(WORK, side + ".json")
        env = {k: v for k, v in os.environ.items() if not k.startswith("PYTHON") and k != "VIRTUAL_ENV"}
        env.update(PYTHONPATH=repo, IMPERICS_SHAREDDIR="/project/cil/gcp")
        args = [PANEL, out, ",".join(REGIONS), ",".join(str(y) for y in YEARS)]
        run = subprocess.run([IMPACT_PYTHON, "-c", textwrap.dedent(LOAD), *args],
                             env=env, capture_output=True, text=True)
        if run.returncode:
            raise RuntimeError(run.stderr[-3000:])
        with open(out) as fp:
            rows = json.load(fp)
        frame = pd.DataFrame(rows, columns=["item", "region", "year", side]).set_index(["item", "region", "year"])
        return frame, run.stdout.strip()


    master, _info = load(MASTER, "master")
    mo.plain_text(_info)
    return load, master


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    Load the SSP3 low economic model on the branch
    """)
    return


@app.cell
def _(BRANCH, load, mo):
    branch, _info = load(BRANCH, "branch")
    mo.plain_text(_info)
    return (branch,)


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    Compare population, popop, baseline and age shares
    """)
    return


@app.cell
def _(REGIONS, branch, master, mo):
    assert master.index.equals(branch.index)
    assert set(master.index.get_level_values("region")) == set(REGIONS)
    table = master.join(branch)
    table["difference"] = table["branch"] - table["master"]
    assert (table["master"] == table["branch"]).all(), table[table["master"] != table["branch"]].to_string()
    mo.vstack([
        mo.ui.table(table.reset_index().astype({"year": str}), page_size=len(table), selection=None),
        mo.plain_text("%d values, all equal" % len(table)),
    ])
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    Open the fulladapt output of the baseline and econfix runs
    """)
    return


@app.cell
def _(REGIONS, SCRATCH, glob, mo, os, xr):
    FILE = "wheat_winter-280823.nc4"


    def find(run):
        found = glob.glob(os.path.join(SCRATCH, run, "outputs", "**", FILE), recursive=True)
        return found[0] if found else None


    paths = {"master": find("baseline"), "branch": find("econfix")}
    quick = None in paths.values()
    if quick:
        paths = {"master": find("baseline-quick"), "branch": find("econfix-quick")}
    assert None not in paths.values(), "no baseline and econfix outputs on scratch"

    outputs = {}
    for _side, _path in paths.items():
        with xr.open_dataset(_path, decode_times=False) as _ds:
            _names = list(_ds["regions"].values)
            here = [r for r in REGIONS if r in _names]
            outputs[_side] = _ds.isel(region=[_names.index(r) for r in here]).assign_coords(region=here).load()
    # The quick runs hold only USA.17.906
    assert quick or here == REGIONS, here
    mo.plain_text("\n".join(
        ["scratch " + SCRATCH]
        + ["%s %s" % (side, os.path.relpath(path, SCRATCH)) for side, path in paths.items()]
        + ["regions " + ", ".join(here)]
    ))
    return (outputs,)


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    Compare the outputs, with rebased in four regions
    """)
    return


@app.cell
def _(mo, np, outputs, pd, plt):
    _plotted = {
        "USA.17.906": "Crawford, Kansas",
        "USA.14.608": "Cook County, Illinois",
        "COL.14.568": "Bogotá, Cundinamarca",
        "NGA.25.508": "Alimosho, Lagos",
    }
    _plots = []
    for _region, _name in _plotted.items():
        if _region not in outputs["master"]["region"].values:
            continue
        _fig, _ax = plt.subplots(figsize=(8, 4), dpi=110)
        _series = {side: outputs[side]["rebased"].sel(region=_region) for side in outputs}
        _ax.plot(_series["master"]["year"], _series["master"], color="#2a78d6", lw=2, label="master (baseline)")
        _ax.plot(_series["branch"]["year"], _series["branch"], color="#eb6834", lw=0, marker="o", markersize=8,
                 markerfacecolor="none", markeredgewidth=1.5, markevery=5, label="branch (econfix)")
        _ax.set_title("rebased in %s, fulladapt" % _region, loc="left")
        _ax.set_xlabel("year")
        _ax.set_ylabel("rebased")
        _ax.grid(color="#e4e3de", lw=0.8)
        _ax.spines["top"].set_visible(False)
        _ax.spines["right"].set_visible(False)
        _ax.legend(frameon=False)
        _plots += [mo.md(f"[{_region}](https://ir-to-adm.vercel.app/?sel=unit%3Aadm2%3A{_region}), {_name}"), _fig]

    # NaN in only one run gives NaN here, which fails the check
    _diff = {}
    for _var in outputs["master"].data_vars:
        _a, _b = outputs["master"][_var].values, outputs["branch"][_var].values
        if _a.dtype.kind == "f":
            _diff[_var] = np.max(np.where(np.isnan(_a) & np.isnan(_b), 0.0, np.abs(_a - _b)))
    _diff = pd.Series(_diff, name="max absolute difference")
    assert (_diff == 0).all(), _diff.to_string()
    mo.vstack(_plots + [mo.plain_text(_diff.to_string())])
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    Full-run output checks: econfix against baseline, 8 of 8 files identical ([output check](https://c1587s.github.io/impact-calculations-experiments/experiments/2026-11-agri-memory-full/reports/econfix/check.json)). mcunit_econfix against mcunit, 3 of 4 identical, histclim has another year-order seed ([output check](https://c1587s.github.io/impact-calculations-experiments/experiments/2026-11-agri-memory-full/reports/mcunit_econfix/check.json)).
    """)
    return


if __name__ == "__main__":
    app.run()
