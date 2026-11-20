#!/bin/bash
#SBATCH --job-name=agri-prof-mortality
#SBATCH --output=/scratch/midway3/%u/agri-profiling/logs/%x_%j.out
#SBATCH --error=/scratch/midway3/%u/agri-profiling/logs/%x_%j.err
#SBATCH --account=cil
#SBATCH --partition=cil
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=40G
#SBATCH --time=04:00:00

# One mortality quick single (rcp45, CCSM4, low, SSP3, one region) on the
# clone in IMPACT_CALCULATIONS (master): the reference for mortality_econfix.
# Quick mode only. Submit from hpc-jobs/ with IMPACT_CALCULATIONS set.
EXP=mortality
QUICK=1
source "$SLURM_SUBMIT_DIR/agriculture/profiling/jobs/run_experiment.sh"
