#!/bin/bash
#SBATCH --job-name=agri-prof-cores6
#SBATCH --output=/scratch/midway3/%u/agri-profiling/logs/%x_%j.out
#SBATCH --error=/scratch/midway3/%u/agri-profiling/logs/%x_%j.err
#SBATCH --account=cil
#SBATCH --partition=cil
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=6
#SBATCH --mem=32G
#SBATCH --time=24:00:00

# Six cores: threads: 2 plus six library threads. At 25 GB a task is already
# billed for 6.7 cores, so six cores cost no more. Checked against baseline.
# Submit from hpc-jobs/ with IMPACT_CALCULATIONS set. Add
# --export=ALL,QUICK=1 --time=03:00:00 for the quick version.
EXP=cores6
COMPARE_TO=baseline
source "$SLURM_SUBMIT_DIR/agriculture/profiling/jobs/run_experiment.sh"
