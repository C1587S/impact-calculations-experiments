#!/bin/bash
#SBATCH --job-name=agri-prof-noglobal
#SBATCH --output=/scratch/midway3/%u/agri-profiling/logs/%x_%j.out
#SBATCH --error=/scratch/midway3/%u/agri-profiling/logs/%x_%j.err
#SBATCH --account=cil
#SBATCH --partition=cil
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=32G
#SBATCH --time=24:00:00

# One core, without the global variant and its histclim copy (six files).
# The other six files are checked against baseline.
# Submit from hpc-jobs/ with IMPACT_CALCULATIONS set. Add
# --export=ALL,QUICK=1 --time=03:00:00 for the quick version.
EXP=noglobal
COMPARE_TO=baseline
ALLOW_MISSING=global
source "$SLURM_SUBMIT_DIR/agriculture/profiling/jobs/run_experiment.sh"
