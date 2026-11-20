#!/bin/bash
#SBATCH --job-name=agri-prof-labor
#SBATCH --output=/scratch/midway3/%u/agri-profiling/logs/%x_%j.out
#SBATCH --error=/scratch/midway3/%u/agri-profiling/logs/%x_%j.err
#SBATCH --account=cil
#SBATCH --partition=amd
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=64G
#SBATCH --time=24:00:00

# The labor single (rcp85, CCSM4, high, SSP3) on master, telemetry
# only: the reference for labor_gccollect_econfix.
# Job 60794948 ran it on amd with 60G and peaked at 41 to 43 GB in 1.6 h.
# 64G here, as the labor montecarlo requests, for both versions. Four files.
#
# Mortality and labor read the same daily temperature files (popwt), so their
# six runs start 30 min apart: all but the first go in with
# --dependency=after:<previous job id>+30 (order in the README).
# Submit from hpc-jobs/ with IMPACT_CALCULATIONS set.
EXP=labor
source "$SLURM_SUBMIT_DIR/agriculture/profiling/jobs/run_experiment.sh"
