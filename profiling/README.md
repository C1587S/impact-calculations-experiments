# Agriculture profiling

Experiments to find how to lower the SUs of the agriculture projections, run
on the winter wheat single (rcp85, CCSM4, high, SSP3), then on the other six
crops and on one single each of labor, energy and mortality. Results are in
[experiments/](../experiments/).

Profiled with memray (memory) and pyinstrument (time), which run inside the
process. py-spy can't run on Midway (`kernel.yama.ptrace_scope` is 3).

This folder is a copy of `hpc-jobs/agriculture/profiling/` in the agriculture
jobs folder on Midway,
`/project/cil/home_dirs/scadavidsanchez/projects/socioeconomics-update/cil2-hpc-jobs-agriculture/hpc-jobs/agriculture/profiling/`.
The agriculture configs here import copies in [`configs/base/`](configs/base/)
of the crop configs in `hpc-jobs/agriculture/configs/`, such as
`wheat_winter_pbarspline.yml`. The kit on Midway imports the originals, and its
jobs run from `hpc-jobs/`. The labor and energy configs import copies of their
model configs in `configs/base/`, in the kit too.

## Experiments

| job | what it tests | cores | `--mem` |
|-----|---------------|-------|---------|
| baseline | the single as it runs today (8 files, one core), telemetry only | 1 | 32G |
| cores2 | `threads: 2`: one thread reads weather and updates covariates, the other computes | 2 | 32G |
| cores4 | `threads: 2` plus 4 library threads, for any gain past two cores | 4 | 32G |
| cores6 | `threads: 2` plus 6 library threads (25 GB is already billed as 6.7 cores) | 6 | 32G |
| noglobal | `do_farmers` without global: 6 files instead of 8 | 1 | 32G |
| oneecon | socioeconomic folder with only the SSP3 OECD CSV: one economic model instead of ten | 1 | 32G |
| mcunit | one montecarlo unit with the montecarlo settings (4 files, ten economic models kept) | 1 | 40G |
| mcunit_oneecon | the same unit with only its CSV, reusing the mcunit draws | 1 | 40G |
| mcunit_econfix | the same unit with the lazy econ model, reusing the mcunit draws | 1 | 40G |
| econfix | baseline with the lazy econ model, the [`econmodel-memory`](https://github.com/ClimateImpactLab/impact-calculations/tree/econmodel-memory) branch of impact-calculations (age shares built on first use, population as one array) | 1 | 32G |
| pyinstrument | baseline under pyinstrument: wall time by function, 10 stacks a second | 1 | 32G |
| memray | baseline under memray: memory at the peak by allocation site | 1 | 40G |
| gccollect | baseline with a full garbage collection every minute, to see whether the peak is garbage that waits for the collector | 1 | 32G |
| gccollect_econfix | the same with the lazy econ model, started 30 min after gccollect so the two never read the weather in step | 1 | 32G |
| mcunit_gccollect_econfix | mcunit with the lazy econ model and a full garbage collection every minute, reusing mcunit's complete draws (both seeds) | 1 | 12G |
| mortality | one mortality quick single on master, the reference for mortality_econfix (quick only) | 1 | 40G |
| mortality_econfix | the same with the lazy econ model. Outputs must be equal, not only close (quick only) | 1 | 40G |
| econfix_check | one economic model from master and one with the lazy econ model: every value identical, memory per item (no projection) | 1 | 24G |
| gc5min_econfix | gccollect_econfix with a full garbage collection every 5 minutes instead of every minute | 1 | 12G |
| gcfreeze_econfix | gccollect_econfix with `gc.freeze()` when the first variant starts, then a full garbage collection every minute, so later passes skip the objects built at startup | 1 | 12G |
| cassava, corn, rice, sorghum, soy and wheat_spring `_gccollect_econfix` | the single of each other crop with the lazy econ model and a full garbage collection every minute | 1 | 12G |
| labor | the labor single (rcp85, CCSM4, high, SSP3, 4 files) on master, telemetry only | 1 | 64G |
| labor_gccollect_econfix | the same with the lazy econ model and a full garbage collection every minute | 1 | 64G |
| energy | the other_energy single (8 files) on master, telemetry only | 1 | 16G |
| energy_gccollect_econfix | the same with the lazy econ model and a full garbage collection every minute | 1 | 16G |
| mortality_single | the mortality single (16 files: young, older, oldest and combined, each with full adaptation, noadapt, incadapt and histclim) on master, telemetry only, with the socioeconomics of the mortality montecarlo | 1 | 45G |
| mortality_single_gccollect_econfix | the same with the lazy econ model and a full garbage collection every minute | 1 | 45G |
| mc3units | three winter wheat montecarlo units in one process (batch 0, rcp85, SSP3, high, CCSM4, GFDL-ESM2M and MIROC5) on master, as montecarlo workers run them, with memory per unit | 1 | 32G |
| mc3units_gccollect_econfix | the same with the lazy econ model and a full garbage collection every minute | 1 | 12G |
| labor_mc3units | the same three units for labor, on master | 1 | 64G |
| labor_mc3units_gccollect_econfix | the same with the lazy econ model and a full garbage collection every minute | 1 | 64G |

The first jobs run on the cil partition. gccollect, gccollect_econfix and
mcunit_gccollect_econfix run on caslake, and every job from gc5min_econfix on
runs on amd, with the 1.0.0 socioeconomic panel. Every job records memory,
CPU, threads and reads each second, times the stages from the log, writes a
manifest and a Perfetto trace, and checks its outputs against its reference
run with `xarray.testing.assert_allclose`. The reference is baseline, econfix
for gccollect_econfix, mcunit for mcunit_oneecon, mcunit_econfix and
mcunit_gccollect_econfix, and the master run of the same pair for
labor_gccollect_econfix, energy_gccollect_econfix,
mortality_single_gccollect_econfix, mc3units_gccollect_econfix and
labor_mc3units_gccollect_econfix. mortality_econfix uses `assert_equal`.
same_outputs.sbatch checks the singles again against the master outputs under
`/project/cil/gcp/outputs_newsocioeconomics/`, the crops included. Every job
with econfix in its name runs the lazy econ model from the worktree
`/project/cil/home_dirs/scadavidsanchez/repos/impact-calculations-econfix`
(set `ECONFIX_REPO` for another one), and econfix_check runs master too.

## How to run

On Midway, from `hpc-jobs/`:

```bash
# 1. Once, on a login node (needs internet). Installs psutil, pyinstrument, and
#    memray with its dependencies into
#    /project/cil/home_dirs/scadavidsanchez/tools/profiling-py37, not the shared env.
bash agriculture/profiling/jobs/install_tools.sh

# 2. Once: the Slurm logs go to scratch, and Slurm needs the folder to exist
mkdir -p /scratch/midway3/$USER/agri-profiling/logs

# 3. Quick check of the kit: one region, four files, about 30 min each.
#    Every job needs IMPACT_CALCULATIONS, the impact-calculations clone it runs.
IC=/project/cil/home_dirs/scadavidsanchez/repos/impact-calculations
for e in baseline cores2 oneecon pyinstrument memray; do
    sbatch --export=ALL,QUICK=1,IMPACT_CALCULATIONS=$IC --time=03:00:00 agriculture/profiling/jobs/$e.sbatch
done
MCQ=$(sbatch --parsable --export=ALL,QUICK=1,IMPACT_CALCULATIONS=$IC --time=03:00:00 agriculture/profiling/jobs/mcunit.sbatch)
sbatch --dependency=afterok:$MCQ --export=ALL,QUICK=1,IMPACT_CALCULATIONS=$IC --time=03:00:00 agriculture/profiling/jobs/mcunit_oneecon.sbatch

# 4. Full runs (12 to 48 h each)
IC=/project/cil/home_dirs/scadavidsanchez/repos/impact-calculations
JOBS=()
for e in baseline cores2 cores4 cores6 noglobal oneecon pyinstrument memray; do
    JOBS+=("$(sbatch --parsable --export=ALL,IMPACT_CALCULATIONS=$IC agriculture/profiling/jobs/$e.sbatch)")
done
MC=$(sbatch --parsable --export=ALL,IMPACT_CALCULATIONS=$IC agriculture/profiling/jobs/mcunit.sbatch)
MC1=$(sbatch --parsable --dependency=afterok:$MC --export=ALL,IMPACT_CALCULATIONS=$IC agriculture/profiling/jobs/mcunit_oneecon.sbatch)
sbatch --dependency=afterany:$(IFS=:; echo "${JOBS[*]}"):$MC:$MC1 agriculture/profiling/jobs/check.sbatch

# 5. The lazy econ model: value check, agriculture quick and full, mortality pair
IC=/project/cil/home_dirs/scadavidsanchez/repos/impact-calculations
sbatch --export=ALL,IMPACT_CALCULATIONS=$IC agriculture/profiling/jobs/econfix_check.sbatch
sbatch --export=ALL,QUICK=1 --time=03:00:00 agriculture/profiling/jobs/econfix.sbatch
sbatch agriculture/profiling/jobs/econfix.sbatch
MQ=$(sbatch --parsable --export=ALL,IMPACT_CALCULATIONS=$IC agriculture/profiling/jobs/mortality.sbatch)
sbatch --dependency=afterok:$MQ agriculture/profiling/jobs/mortality_econfix.sbatch
sbatch --dependency=afterok:$MC agriculture/profiling/jobs/mcunit_econfix.sbatch   # $MC from step 4

# 6. Garbage collection test on caslake: gccollect, then gccollect_econfix
#    30 min after gccollect starts, so the two never read the weather in step.
#    A quick check of the wrapper: add QUICK=1 and --time=03:00:00 to gccollect.
G=$(sbatch --parsable --export=ALL,IMPACT_CALCULATIONS=$IC agriculture/profiling/jobs/gccollect.sbatch)
sbatch --dependency=after:$G+30 agriculture/profiling/jobs/gccollect_econfix.sbatch
# mcunit with the lazy econ model and collections, on caslake. It stops
# before the projection if mcunit's pvals.yml lacks seed-csvv or seed-yearorder.
sbatch agriculture/profiling/jobs/mcunit_gccollect_econfix.sbatch

# 7. The amd round: three-unit montecarlo jobs for winter wheat and labor, two
#    collection settings on winter wheat, the six other crops, and singles of
#    labor, energy and mortality, each pair in two versions (master, and the
#    lazy econ model with a collection every minute). Runs that read the
#    same weather start 30 min apart, longest first: the ten agriculture runs,
#    the six mortality and labor runs (daily temperature), and the two energy
#    runs. Then the output checks again, for the new pairs only.
IC=/project/cil/home_dirs/scadavidsanchez/repos/impact-calculations
J=agriculture/profiling/jobs
ALL=()
chain() {
    local prev="" id e
    for e in "$@"; do
        id=$(sbatch --parsable --export=ALL,IMPACT_CALCULATIONS=$IC ${prev:+--dependency=after:$prev+30} $J/$e.sbatch)
        [ -n "$id" ] || { echo "sbatch failed for $e" >&2; return 1; }
        echo "$e $id"
        ALL+=("$id")
        prev=$id
    done
}
chain mc3units mc3units_gccollect_econfix gc5min_econfix gcfreeze_econfix \
    cassava_gccollect_econfix corn_gccollect_econfix rice_gccollect_econfix \
    sorghum_gccollect_econfix soy_gccollect_econfix wheat_spring_gccollect_econfix
chain mortality_single mortality_single_gccollect_econfix labor_mc3units labor_mc3units_gccollect_econfix \
    labor labor_gccollect_econfix
chain energy energy_gccollect_econfix
CHECK=gc5min_econfix:gcfreeze_econfix:mc3units_gccollect_econfix:mortality_single_gccollect_econfix
CHECK=$CHECK:labor_mc3units_gccollect_econfix:labor_gccollect_econfix:energy_gccollect_econfix
sbatch -p amd --time=04:00:00 --dependency=afterany:$(IFS=:; echo "${ALL[*]}") \
    --export=ALL,RUNS=$CHECK $J/check.sbatch

# 8. When they end, on a login node: final sacct numbers and the report
bash agriculture/profiling/jobs/build_report.sh

# 9. Output checks of the singles against the master outputs in
#    /project/cil/gcp/outputs_newsocioeconomics/, then master against lazy + gc
#    over the years, one PNG and one CSV per sector in same_outputs/ on scratch.
#    tools/same_outputs.py is a copy of experiments/2026-11-amd-round/same_outputs/
#    in the experiments repo.
sbatch $J/same_outputs.sbatch
```

The notebook [`notebooks/amd_round.py`](notebooks/amd_round.py) reads the
results of the finished runs and draws the figures of the round. Copy it with
`utils.py` to a folder on scratch, then on a compute node:

```bash
uv run --with marimo --with matplotlib --with pandas marimo export html amd_round.py -o amd_round.html --no-sandbox -f
```

`RESULTS_ROOT` points it at another results folder, and `FIGURES=<folder>`
also writes its main figures there as PNG.

Results stay on scratch. Copy the small files somewhere safe soon, since
scratch is purged periodically, for example from the Mac:

```bash
rsync -av cadavidsanchez@midway3.rcc.uchicago.edu:/scratch/midway3/cadavidsanchez/agri-profiling/results/ <folder>/
```

Open `report/index.html` (next to `results/` on scratch) in a browser.
Traces open at https://ui.perfetto.dev. pyinstrument's `profile.html` opens
in a browser, and its `profile.speedscope.json` at https://www.speedscope.app.

## Where things go

- `/scratch/midway3/$USER/agri-profiling/results/<run>/`: small files only.
  `manifest.json`, `trace.json`, `check.json`, `gc.csv`, `profile.html`,
  `profile.speedscope.json`, `profile.txt`, `memray-*.html`,
  `memray-summary.txt`, and `error.txt` when a run fails.
  Quick runs end in `-quick`.
- `/scratch/midway3/$USER/agri-profiling/<run>/`: projection outputs, the
  run log, the 1 s samples (`samples.csv`, `threads.csv`, `markers.tsv`),
  `memray.bin`, `pyinstrument.pyisession`, and the projection's own log in
  `logs/generate-0.log`. Each job deletes its own `outputs/` first.
- `/scratch/midway3/$USER/agri-profiling/report/index.html`: the report.
- `/scratch/midway3/$USER/agri-profiling/logs/`: Slurm logs.
- `/scratch/midway3/$USER/agri-profiling/same_outputs/`: PNGs and CSVs of same_outputs.sbatch.
- A job writes none of its files under `/project`.

## Options

Pass with `--export=ALL,NAME=value`:

- `QUICK=1`: the quick configs in `configs/quick/`.
- `PYINSTRUMENT_INTERVAL`: seconds between stacks (default 0.1).
- `MEMRAY_AGGREGATE=0` for a full capture, needed for `memray stats` (quick
  mode only, a full run would write a very large file). `MEMRAY_NATIVE=1` for
  C frames.
- `GC_INTERVAL`: seconds between full garbage collections in the gc jobs (default 60, and 300 in gc5min_econfix).
- `GC_FREEZE=1`: in the gc jobs, one more pass and `gc.freeze()` at the end of
  the first REDO line, when the first variant starts (set in gcfreeze_econfix).
  The run log shows how many objects were frozen.
- `EXPECTED_FILES`: how many output files a complete run writes, when the
  count from `do_farmers` is wrong (16 in the mortality singles, 12 in the
  three-unit runs).
- `RUNS=<run>:<run>` for check.sbatch: check only those runs, so older runs
  keep their check.json.
- `PROFILING_TOOLS` to use another tools folder.
- `RESULTS_ROOT` to write results somewhere else (default: `results/` on scratch).

## Notes

- The jobs call `python -m generate.generate <config> --outputdir=...`,
  which is what `generate.sh` runs, so each user writes to their own scratch.
- The projection system exits with status 0 even when it fails. The jobs
  mark a run failed when the log reports an error or files are missing, and
  copy the error to `results/<run>/error.txt`.
- The jobs run the projection from the run folder on scratch, with the clone
  on `PYTHONPATH`, so its `logs/generate-N.log` goes to scratch, not the clone.
- Compare timings only between runs on the same CPU model (in each manifest).
- A unit starts when the projection prints its output folder, as in
  `.../batch0/rcp85/CCSM4/high/SSP3`. The trace has a units track, and the
  manifest (`stages.units`) and the report give each unit's memory at its
  start and its peaks. The three-unit runs fix `seed-csvv` in their config
  (`pvals:`), so both versions draw the same coefficients even though the
  projection system shuffles the order of the units. The output check then
  matches files by folder, since names repeat across units.
- Stages take their names from the output files: noadapt, incadapt, global and
  histclim at the end of the name, fulladapt when there are none, and for
  mortality the age group first, as in `young noadapt`.
- Tools that attach to another process, like py-spy, cannot run on Midway:
  `kernel.yama.ptrace_scope` is 3. pyinstrument and memray run inside the
  projection's own process instead. pyinstrument records only the main
  thread, which does all the work in single mode.
- srun on the cil partition needs the account too, for example
  `srun -A cil -p cil --mem=8G --time=01:00:00 --pty bash`.
