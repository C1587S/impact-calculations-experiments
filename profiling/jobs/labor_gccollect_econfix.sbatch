#!/bin/bash
#SBATCH --job-name=agri-prof-labor_gccollect_econfix
#SBATCH --output=/scratch/midway3/%u/agri-profiling/logs/%x_%j.out
#SBATCH --error=/scratch/midway3/%u/agri-profiling/logs/%x_%j.err
#SBATCH --account=cil
#SBATCH --partition=amd
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=64G
#SBATCH --time=24:00:00

# The labor single (rcp85, CCSM4, high, SSP3)
# on the econmodel-memory branch (worktree impact-calculations-econfix, or
# ECONFIX_REPO), with a full garbage collection every minute (GC_INTERVAL
# seconds) in the projection's main thread.
# Same memory request as labor.
#
# Checks its outputs against labor when that run has ended first, and
# check.sbatch does it otherwise.
#
# Mortality and labor read the same daily temperature files (popwt), so their
# six runs start 30 min apart: all but the first go in with
# --dependency=after:<previous job id>+30 (order in the README).
# Submit from hpc-jobs/.
EXP=labor_gccollect_econfix
PROFILER=gc
COMPARE_TO=labor
IMPACT_CALCULATIONS="${ECONFIX_REPO:-/project/cil/home_dirs/scadavidsanchez/repos/impact-calculations-econfix}"
source "$SLURM_SUBMIT_DIR/agriculture/profiling/jobs/run_experiment.sh"
