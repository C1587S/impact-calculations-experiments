# Agriculture profiling

Experiments to find how to lower the SUs of the agriculture projections, run
on the winter wheat single (rcp85, CCSM4, high, SSP3). Results are in
[experiments/](../experiments/).

Profiled with memray (memory) and pyinstrument (time), which run inside the
process. py-spy can't run on Midway (`kernel.yama.ptrace_scope` is 3).

This folder is a copy of `hpc-jobs/agriculture/profiling/` in the agriculture
jobs folder on Midway,
`/project/cil/home_dirs/scadavidsanchez/projects/socioeconomics-update/cil2-hpc-jobs-agriculture/hpc-jobs/agriculture/profiling/`.
The configs here import [`configs/base/wheat_winter_pbarspline.yml`](configs/base/wheat_winter_pbarspline.yml),
a copy of `hpc-jobs/agriculture/configs/wheat_winter_pbarspline.yml`. The kit
on Midway imports the original, and its jobs run from `hpc-jobs/`.

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
| mcunit_econfix | the same unit with the lazy economic model, reusing the mcunit draws | 1 | 40G |
| econfix | baseline with the lazy economic model, the [`econmodel-memory`](https://github.com/ClimateImpactLab/impact-calculations/tree/econmodel-memory) branch of impact-calculations (age shares built on first use, population as one array) | 1 | 32G |
| pyinstrument | baseline under pyinstrument: wall time by function, 10 stacks a second | 1 | 32G |
| memray | baseline under memray: memory at the peak by allocation site | 1 | 40G |
| gccollect | baseline with a full garbage collection every minute, to see whether the peak is garbage that waits for the collector | 1 | 32G |
| gccollect_econfix | the same with the lazy economic model, started 30 min after gccollect so the two never read the weather in step | 1 | 32G |
| mcunit_gccollect_econfix | mcunit with the lazy economic model and a full garbage collection every minute, reusing mcunit's complete draws (both seeds) | 1 | 12G |
| mortality | one mortality quick single on master, the reference for mortality_econfix (quick only) | 1 | 40G |
| mortality_econfix | the same with the lazy economic model. Outputs must be equal, not only close (quick only) | 1 | 40G |
| econfix_check | one economic model from master and one with the lazy economic model: every value identical, memory per item (no projection) | 1 | 24G |

All jobs run on the cil partition, except gccollect, gccollect_econfix and
mcunit_gccollect_econfix, which run on caslake. Every job records memory, CPU,
threads and reads each second, times the stages from the log, writes a
manifest and a Perfetto trace, and checks its outputs against its reference
run (baseline, econfix for gccollect_econfix, or mcunit for mcunit_oneecon,
mcunit_econfix and mcunit_gccollect_econfix) with
`xarray.testing.assert_allclose`. mortality_econfix uses `assert_equal`.
econfix, mcunit_econfix, gccollect_econfix, mcunit_gccollect_econfix,
mortality_econfix and econfix_check run the lazy economic model from the
worktree `/project/cil/home_dirs/scadavidsanchez/repos/impact-calculations-econfix`
(set `ECONFIX_REPO` for another one).

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

# 5. The lazy economic model: value check, agriculture quick and full, mortality pair
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
# mcunit with the lazy economic model and collections, on caslake. It stops
# before the projection if mcunit's pvals.yml lacks seed-csvv or seed-yearorder.
sbatch agriculture/profiling/jobs/mcunit_gccollect_econfix.sbatch

# 7. When they end, on a login node: final sacct numbers and the report
bash agriculture/profiling/jobs/build_report.sh
```

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
- A job writes none of its files under `/project`.

## Options

Pass with `--export=ALL,NAME=value`:

- `QUICK=1`: the quick configs in `configs/quick/`.
- `PYINSTRUMENT_INTERVAL`: seconds between stacks (default 0.1).
- `MEMRAY_AGGREGATE=0` for a full capture, needed for `memray stats` (quick
  mode only, a full run would write a very large file). `MEMRAY_NATIVE=1` for
  C frames.
- `GC_INTERVAL`: seconds between full garbage collections in the gc jobs (default 60).
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
- Tools that attach to another process, like py-spy, cannot run on Midway:
  `kernel.yama.ptrace_scope` is 3. pyinstrument and memray run inside the
  projection's own process instead. pyinstrument records only the main
  thread, which does all the work in single mode.
- srun on the cil partition needs the account too, for example
  `srun -A cil -p cil --mem=8G --time=01:00:00 --pty bash`.
