#!/bin/bash
#SBATCH --job-name=agri-prof-energy
#SBATCH --output=/scratch/midway3/%u/agri-profiling/logs/%x_%j.out
#SBATCH --error=/scratch/midway3/%u/agri-profiling/logs/%x_%j.err
#SBATCH --account=cil
#SBATCH --partition=amd
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=16G
#SBATCH --time=24:00:00

# The other_energy single (rcp85, CCSM4, high, SSP3) on master, telemetry
# only: the reference for energy_gccollect_econfix.
# Job 61798435 ran it on amd with 15G and peaked at about 10 GB in 6 to 8 h.
# 16G here, for both versions. Eight files.
#
# The two energy runs read the same yearly temperature files, so
# energy_gccollect_econfix goes in with --dependency=after:<energy job id>+30.
# Submit from hpc-jobs/ with IMPACT_CALCULATIONS set.
EXP=energy
source "$SLURM_SUBMIT_DIR/agriculture/profiling/jobs/run_experiment.sh"
