#!/bin/bash
#SBATCH --job-name=agri-prof-energy_gccollect_econfix
#SBATCH --output=/scratch/midway3/%u/agri-profiling/logs/%x_%j.out
#SBATCH --error=/scratch/midway3/%u/agri-profiling/logs/%x_%j.err
#SBATCH --account=cil
#SBATCH --partition=amd
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=16G
#SBATCH --time=24:00:00

# The other_energy single (rcp85, CCSM4, high, SSP3)
# on the econmodel-memory branch (worktree impact-calculations-econfix, or
# ECONFIX_REPO), with a full garbage collection every minute (GC_INTERVAL
# seconds) in the projection's main thread.
# Same memory request as energy.
#
# Checks its outputs against energy when that run has ended first, and
# check.sbatch does it otherwise.
#
# The two energy runs read the same yearly temperature files, so
# energy_gccollect_econfix goes in with --dependency=after:<energy job id>+30.
# Submit from hpc-jobs/.
EXP=energy_gccollect_econfix
PROFILER=gc
COMPARE_TO=energy
IMPACT_CALCULATIONS="${ECONFIX_REPO:-/project/cil/home_dirs/scadavidsanchez/repos/impact-calculations-econfix}"
source "$SLURM_SUBMIT_DIR/agriculture/profiling/jobs/run_experiment.sh"
