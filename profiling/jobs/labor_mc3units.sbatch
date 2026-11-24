#!/bin/bash
#SBATCH --job-name=agri-prof-labor_mc3units
#SBATCH --output=/scratch/midway3/%u/agri-profiling/logs/%x_%j.out
#SBATCH --error=/scratch/midway3/%u/agri-profiling/logs/%x_%j.err
#SBATCH --account=cil
#SBATCH --partition=amd
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=64G
#SBATCH --time=36:00:00

# Three labor montecarlo units in one process, on master, telemetry only:
# the reference for labor_mc3units_gccollect_econfix. Montecarlo workers run several
# units one after another, so memory could build up across them.
# The labor single peaked at 41 to 43 GB in 1.6 h, so three units take about
# 5 h. 64G for both versions, as the labor montecarlo requests.
# Each unit starts when the projection prints its output folder: the trace
# has a units track, and the manifest (stages.units) and the report give the
# memory at the start of each unit and its peaks. Twelve files, four per unit.
#
# Mortality and labor read the same daily temperature files (popwt), so their
# six runs start 30 min apart: all but the first go in with
# --dependency=after:<previous job id>+30 (order in the README).
# Submit from hpc-jobs/ with IMPACT_CALCULATIONS set.
EXP=labor_mc3units
EXPECTED_FILES=12
source "$SLURM_SUBMIT_DIR/agriculture/profiling/jobs/run_experiment.sh"
