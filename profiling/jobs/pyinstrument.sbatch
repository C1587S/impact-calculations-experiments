#!/bin/bash
#SBATCH --job-name=agri-prof-pyinstrument
#SBATCH --output=/scratch/midway3/%u/agri-profiling/logs/%x_%j.out
#SBATCH --error=/scratch/midway3/%u/agri-profiling/logs/%x_%j.err
#SBATCH --account=cil
#SBATCH --partition=cil
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=32G
#SBATCH --time=30:00:00

# The baseline under pyinstrument: wall time by function, 10 stacks a second.
# Writes profile.speedscope.json, profile.html and profile.txt to
# results/pyinstrument/, and the full session to
# /scratch/midway3/$USER/agri-profiling/pyinstrument/pyinstrument.pyisession.
# Submit from hpc-jobs/ with IMPACT_CALCULATIONS set. Add
# --export=ALL,QUICK=1 --time=03:00:00 for the quick version.
EXP=pyinstrument
PROFILER=pyinstrument
COMPARE_TO=baseline
source "$SLURM_SUBMIT_DIR/agriculture/profiling/jobs/run_experiment.sh"
