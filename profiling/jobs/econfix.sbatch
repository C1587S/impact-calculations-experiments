#!/bin/bash
#SBATCH --job-name=agri-prof-econfix
#SBATCH --output=/scratch/midway3/%u/agri-profiling/logs/%x_%j.out
#SBATCH --error=/scratch/midway3/%u/agri-profiling/logs/%x_%j.err
#SBATCH --account=cil
#SBATCH --partition=cil
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=32G
#SBATCH --time=24:00:00

# The baseline config on the econmodel-memory branch of impact-calculations
# (worktree impact-calculations-econfix, or ECONFIX_REPO): age shares built on
# first use, population as one array. Checks its outputs against baseline.
# Submit from hpc-jobs/. Add --export=ALL,QUICK=1 --time=03:00:00 for the
# quick version.
EXP=econfix
COMPARE_TO=baseline
IMPACT_CALCULATIONS="${ECONFIX_REPO:-/project/cil/home_dirs/scadavidsanchez/repos/impact-calculations-econfix}"
source "$SLURM_SUBMIT_DIR/agriculture/profiling/jobs/run_experiment.sh"
