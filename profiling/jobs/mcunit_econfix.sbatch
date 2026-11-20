#!/bin/bash
#SBATCH --job-name=agri-prof-mcunit_econfix
#SBATCH --output=/scratch/midway3/%u/agri-profiling/logs/%x_%j.out
#SBATCH --error=/scratch/midway3/%u/agri-profiling/logs/%x_%j.err
#SBATCH --account=cil
#SBATCH --partition=cil
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=40G
#SBATCH --time=24:00:00
# The mcunit unit on the econmodel-memory branch of impact-calculations
# (worktree impact-calculations-econfix, or ECONFIX_REPO): all ten economic
# models kept, each stored compactly. Reuses the mcunit draws and checks its
# outputs against mcunit, so submit it after mcunit ends:
#   sbatch --dependency=afterok:<mcunit job id> agriculture/profiling/jobs/mcunit_econfix.sbatch
# Submit from hpc-jobs/. Add --export=ALL,QUICK=1 --time=03:00:00 for the
# quick version.
EXP=mcunit_econfix
COMPARE_TO=mcunit
PVALS_FROM=mcunit
IMPACT_CALCULATIONS="${ECONFIX_REPO:-/project/cil/home_dirs/scadavidsanchez/repos/impact-calculations-econfix}"
source "$SLURM_SUBMIT_DIR/agriculture/profiling/jobs/run_experiment.sh"
