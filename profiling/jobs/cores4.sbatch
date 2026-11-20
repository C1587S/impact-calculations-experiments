#!/bin/bash
#SBATCH --job-name=agri-prof-cores4
#SBATCH --output=/scratch/midway3/%u/agri-profiling/logs/%x_%j.out
#SBATCH --error=/scratch/midway3/%u/agri-profiling/logs/%x_%j.err
#SBATCH --account=cil
#SBATCH --partition=cil
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=24:00:00

# Four cores: threads: 2 plus four library threads. Shows whether cores past
# two help. Outputs are checked against baseline.
# Submit from hpc-jobs/ with IMPACT_CALCULATIONS set. Add
# --export=ALL,QUICK=1 --time=03:00:00 for the quick version.
EXP=cores4
COMPARE_TO=baseline
source "$SLURM_SUBMIT_DIR/agriculture/profiling/jobs/run_experiment.sh"
