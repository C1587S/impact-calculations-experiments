#!/bin/bash
#SBATCH --job-name=agri-prof-mortality_single_gccollect_econfix
#SBATCH --output=/scratch/midway3/%u/agri-profiling/logs/%x_%j.out
#SBATCH --error=/scratch/midway3/%u/agri-profiling/logs/%x_%j.err
#SBATCH --account=cil
#SBATCH --partition=amd
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=45G
#SBATCH --time=36:00:00

# The mortality single (rcp85, CCSM4, high, SSP3)
# on the econmodel-memory branch (worktree impact-calculations-econfix, or
# ECONFIX_REPO), with a full garbage collection every minute (GC_INTERVAL
# seconds) in the projection's main thread.
# Same memory request as mortality_single.
#
# Checks its outputs against mortality_single when that run has ended first, and
# check.sbatch does it otherwise.
#
# Mortality and labor read the same daily temperature files (popwt), so their
# six runs start 30 min apart: all but the first go in with
# --dependency=after:<previous job id>+30 (order in the README).
# Submit from hpc-jobs/.
EXP=mortality_single_gccollect_econfix
EXPECTED_FILES=16
PROFILER=gc
COMPARE_TO=mortality_single
IMPACT_CALCULATIONS="${ECONFIX_REPO:-/project/cil/home_dirs/scadavidsanchez/repos/impact-calculations-econfix}"
source "$SLURM_SUBMIT_DIR/agriculture/profiling/jobs/run_experiment.sh"
