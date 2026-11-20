#!/bin/bash
#SBATCH --job-name=agri-prof-mortality_single
#SBATCH --output=/scratch/midway3/%u/agri-profiling/logs/%x_%j.out
#SBATCH --error=/scratch/midway3/%u/agri-profiling/logs/%x_%j.err
#SBATCH --account=cil
#SBATCH --partition=amd
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=45G
#SBATCH --time=36:00:00

# The mortality single (rcp85, CCSM4, high, SSP3) on master, telemetry
# only: the reference for mortality_single_gccollect_econfix.
# Job 59882812 ran it on the cil partition with 45G and peaked at 26 to 29 GB
# in about 20 h, with the old output-wpp socioeconomics (four CSVs). The 1.0.0
# panel has ten, as in the mortality montecarlo, which asks for 36G on cil.
# Winter wheat took about 8% longer on amd than on cil, hence 36 h. 45G here,
# for both versions. Sixteen files: young, older, oldest and combined, each
# with full adaptation, noadapt, incadapt and histclim.
#
# Mortality and labor read the same daily temperature files (popwt), so their
# six runs start 30 min apart: all but the first go in with
# --dependency=after:<previous job id>+30 (order in the README).
# Submit from hpc-jobs/ with IMPACT_CALCULATIONS set.
EXP=mortality_single
EXPECTED_FILES=16
source "$SLURM_SUBMIT_DIR/agriculture/profiling/jobs/run_experiment.sh"
