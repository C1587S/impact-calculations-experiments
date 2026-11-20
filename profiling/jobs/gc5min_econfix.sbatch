#!/bin/bash
#SBATCH --job-name=agri-prof-gc5min_econfix
#SBATCH --output=/scratch/midway3/%u/agri-profiling/logs/%x_%j.out
#SBATCH --error=/scratch/midway3/%u/agri-profiling/logs/%x_%j.err
#SBATCH --account=cil
#SBATCH --partition=amd
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=24G
#SBATCH --time=24:00:00

# gccollect_econfix with a full garbage collection every 5 minutes instead of
# every minute (GC_INTERVAL=300): how much of the lower peak remains with a
# fifth of the passes, and how much time that saves.
#
# Checks its outputs against baseline, the same single on master, whose
# outputs must still be on scratch. baseline ran on cil and this runs on amd,
# so compare its memory with baseline, not its time.
#
# The ten agriculture runs of the amd round read the same rcp85 crop weather,
# so each starts 30 min after the one before: all but the first go in with
# --dependency=after:<previous job id>+30 (order in the README).
# Submit from hpc-jobs/.
EXP=gc5min_econfix
PROFILER=gc
GC_INTERVAL=300
COMPARE_TO=baseline
IMPACT_CALCULATIONS="${ECONFIX_REPO:-/project/cil/home_dirs/scadavidsanchez/repos/impact-calculations-econfix}"
source "$SLURM_SUBMIT_DIR/agriculture/profiling/jobs/run_experiment.sh"
