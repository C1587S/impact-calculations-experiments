# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "marimo",
#     "matplotlib",
#     "pandas",
# ]
#
# ///

import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium", app_title="Profiling runs")


@app.cell
def _():
    import marimo as mo
    import pandas as pd
    import utils

    return mo, pd, utils


@app.cell
def _(mo, utils):
    runs = utils.load_runs(mo.notebook_location())
    return (runs,)


@app.cell
def _(mo, pd, runs):
    mo.ui.dataframe(pd.DataFrame([{k: v for k, v in r.items() if not isinstance(v, (dict, list, pd.DataFrame))} for r in runs]))
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Setup

    - cil: 2 nodes, Intel Xeon Gold 6448Y, 64 cores and 252 GB per node.
    - caslake: 180 nodes, Intel Xeon Gold 6248R, 48 cores and 180 GB per node. About 1.2 times slower than cil in these runs.
    - amd: 40 nodes, AMD EPYC 7702, 128 cores and 244 GB per node.
    - Quick runs: one region, four files.
    - Single: all regions, eight files.
    - Montecarlo unit: all regions, four files, ten economic models.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Memory
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    Peak memory of the quick runs in the job cgroup, one region.
    """)
    return


@app.cell
def _(runs, utils):
    utils.peak_bars(runs, "quick runs")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    Memory of the full singles on cil over the run.
    """)
    return


@app.cell
def _(runs, utils):
    utils.over_run(runs, "full singles")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    Memory of the montecarlo units over the run, each variant drawn at the same width, since the two ran on different CPUs.
    """)
    return


@app.cell
def _(runs, utils):
    utils.over_run(runs, "montecarlo units", by_stage=True)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    Memory of the garbage collection runs over the run.
    """)
    return


@app.cell
def _(runs, utils):
    utils.over_run(runs, "gc runs")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    Memory of the full singles on cil by stage: peak of the startup, then the median of each year loop.
    """)
    return


@app.cell
def _(runs, utils):
    utils.memory_by_stage(runs, "full singles")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    Memory of the garbage collection runs by stage: peak of the startup, then the median of each year loop.
    """)
    return


@app.cell
def _(runs, utils):
    utils.memory_by_stage(runs, "gc runs")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## CPU and cores
    """)
    return


@app.cell
def _(mo, utils):
    group_picker = mo.ui.dropdown(utils.GROUPS, value="full singles", label="runs")
    measure_picker = mo.ui.dropdown(list(utils.MEASURES), value="cpu", label="measure")
    axis_picker = mo.ui.radio(["hours", "stage"], value="hours", label="x axis", inline=True)
    return axis_picker, group_picker, measure_picker


@app.cell
def _(axis_picker, group_picker, measure_picker, mo):
    mo.hstack([group_picker, measure_picker, axis_picker], justify="start")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    Figure 7. CPU, memory or read rate over the run for the chosen group of runs.
    """)
    return


@app.cell
def _(axis_picker, group_picker, measure_picker, runs, utils):
    utils.over_run(runs, group_picker.value, measure_picker.value, axis_picker.value == "stage")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Time
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    Time of each step in the quick runs.
    """)
    return


@app.cell
def _(runs, utils):
    utils.time_by_step(runs, "quick runs")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    Time of each step in the garbage collection runs, with the time spent collecting.
    """)
    return


@app.cell
def _(runs, utils):
    utils.time_by_step(runs, "gc runs")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Cost
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    Days to finish median and montecarlo for the seven crops, each partition used alone, and SUs on caslake. Memory per job is the setup's measured cgroup peak plus 20%.
    """)
    return


@app.cell
def _(mo, runs, utils):
    mo.plain(utils.cost_table(runs))
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    **Note** Days and SUs in this table are rough estimates. They combine the memory and run times measured in these profiling runs with
    what was observed while updating the montecarlo projections in Oct and Nov 2026.  They assume every crop behaves like winter wheat and that the partitions offer the same capacity as during that update. Actual times depend on how busy each partition is.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Same outputs
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    Output checks against each run's reference.
    """)
    return


@app.cell
def _(mo, runs, utils):
    mo.plain(utils.checks_table(runs))
    return


if __name__ == "__main__":
    app.run()
