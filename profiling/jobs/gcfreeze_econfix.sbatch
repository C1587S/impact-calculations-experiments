#!/bin/bash
#SBATCH --job-name=agri-prof-gcfreeze_econfix
#SBATCH --output=/scratch/midway3/%u/agri-profiling/logs/%x_%j.out
#SBATCH --error=/scratch/midway3/%u/agri-profiling/logs/%x_%j.err
#SBATCH --account=cil
#SBATCH --partition=amd
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=12G
#SBATCH --time=24:00:00

# gccollect_econfix with one more pass and gc.freeze() at the end of the first
# REDO line, when the first variant starts, then a full garbage collection
# every minute (GC_FREEZE=1, the --freeze-at-first-variant option of
# gc_capture.py). The objects alive then, mostly the economic models and the
# weather setup, move to a permanent generation that later passes skip, so
# each pass should take less time. Frozen objects are never collected, so
# cycles among them that become garbage later stay in memory. The run log
# shows how many were frozen (gc_capture: froze ...).
#
# Checks its outputs against baseline, the same single on master, whose
# outputs must still be on scratch. baseline ran on cil and this runs on amd,
# so compare its memory with baseline, not its time.
#
# The ten agriculture runs of the amd round read the same rcp85 crop weather,
# so each starts 30 min after the one before: all but the first go in with
# --dependency=after:<previous job id>+30 (order in the README).
# Submit from hpc-jobs/.
EXP=gcfreeze_econfix
PROFILER=gc
GC_FREEZE=1
COMPARE_TO=baseline
IMPACT_CALCULATIONS="${ECONFIX_REPO:-/project/cil/home_dirs/scadavidsanchez/repos/impact-calculations-econfix}"
source "$SLURM_SUBMIT_DIR/agriculture/profiling/jobs/run_experiment.sh"
