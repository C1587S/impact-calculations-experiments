#!/bin/bash
#SBATCH --job-name=agri-prof-mcunit
#SBATCH --output=/scratch/midway3/%u/agri-profiling/logs/%x_%j.out
#SBATCH --error=/scratch/midway3/%u/agri-profiling/logs/%x_%j.err
#SBATCH --account=cil
#SBATCH --partition=cil
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=40G
#SBATCH --time=24:00:00

# One montecarlo unit (batch 0, rcp85, CCSM4, high, SSP3) with the montecarlo
# settings: four files, all ten economic models in memory. This is the unit
# the 5,850-unit cost is made of.
# Submit from hpc-jobs/ with IMPACT_CALCULATIONS set. Add
# --export=ALL,QUICK=1 --time=03:00:00 for the quick version.
EXP=mcunit
source "$SLURM_SUBMIT_DIR/agriculture/profiling/jobs/run_experiment.sh"
