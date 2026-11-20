# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "marimo",
#     "matplotlib",
#     "pandas",
# ]
# ///

import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium", app_title="amd round")


@app.cell
def _():
    import datetime

    import marimo as mo
    import pandas as pd
    import utils

    def show(caption, item, name=None):
        """A figure or table under its caption line, or a note while none of its runs has finished.
        A figure with a name is also written to FIGURES when that is set."""
        if name:
            utils.save(item, name)
        if item is None:
            item = mo.md("_None of these runs has finished yet._")
        elif isinstance(item, pd.DataFrame):
            item = mo.ui.table(item, selection=None, page_size=max(len(item), 1), show_column_summaries=False)
        return mo.vstack([mo.md(caption), item])

    return datetime, mo, show, utils


@app.cell
def _(utils):
    runs = utils.load_runs()
    return (runs,)


@app.cell(hide_code=True)
def _(datetime, mo, runs, utils):
    mo.md(f"""
    # amd round

    {utils.status_line(runs)}

    Read from `{utils.RESULTS}` at {datetime.datetime.now():%Y-%m-%d %H:%M}.
    """)
    return


@app.cell
def _(runs, show, utils):
    show("Finished runs. Memory to request is the cgroup peak plus 20 %.", utils.summary_table(runs))
    return


@app.cell
def _(runs, show, utils):
    show("Peak memory per single.", utils.peak_overview(runs), "peak_overview")
    return


@app.cell
def _(runs, show, utils):
    show("Peak memory per crop.", utils.peak_overview(runs, utils.CROPS))
    return


@app.cell
def _(runs, show, utils):
    show("Crops against master (job 62444670, medians, MaxRSS).", utils.crops_table(runs))
    return


@app.cell
def _(runs, show, utils):
    show("Job memory over the run, one row per sector.", utils.memory_by_sector(runs), "memory_by_sector")
    return


@app.cell
def _(runs, show, utils):
    show("Winter wheat, lazy econ model, by gc setting.", utils.gc_table(runs))
    return


@app.cell
def _(runs, show, utils):
    pauses = utils.gc_pauses(runs)
    show("gc pause lengths by setting.", pauses) if pauses else None
    return


@app.cell
def _(runs, show, utils):
    show("Three units in one job.", utils.units_figure(runs), "units")
    return


@app.cell
def _(runs, show, utils):
    show("Memory at the start and peak of each unit.", utils.units_table(runs))
    return


@app.cell
def _(runs, show, utils):
    show("Output checks.", utils.checks_table(runs))
    return


if __name__ == "__main__":
    app.run()
