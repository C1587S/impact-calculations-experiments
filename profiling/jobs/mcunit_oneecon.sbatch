#!/bin/bash
#SBATCH --job-name=agri-prof-mcunit_oneecon
#SBATCH --output=/scratch/midway3/%u/agri-profiling/logs/%x_%j.out
#SBATCH --error=/scratch/midway3/%u/agri-profiling/logs/%x_%j.err
#SBATCH --account=cil
#SBATCH --partition=cil
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=40G
#SBATCH --time=24:00:00

# The mcunit unit with only the CSV it uses. Reuses the mcunit draws, so submit
# it after mcunit ends:
#   sbatch --dependency=afterok:<mcunit job id> agriculture/profiling/jobs/mcunit_oneecon.sbatch
# Submit from hpc-jobs/ with IMPACT_CALCULATIONS set. Add
# --export=ALL,QUICK=1 --time=03:00:00 for the quick version.
EXP=mcunit_oneecon
COMPARE_TO=mcunit
PVALS_FROM=mcunit
source "$SLURM_SUBMIT_DIR/agriculture/profiling/jobs/run_experiment.sh"
