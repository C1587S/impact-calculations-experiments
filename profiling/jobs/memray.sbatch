#!/bin/bash
#SBATCH --job-name=agri-prof-memray
#SBATCH --output=/scratch/midway3/%u/agri-profiling/logs/%x_%j.out
#SBATCH --error=/scratch/midway3/%u/agri-profiling/logs/%x_%j.err
#SBATCH --account=cil
#SBATCH --partition=cil
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=40G
#SBATCH --time=48:00:00

# The baseline under memray, aggregated capture (peak and leaks only, small
# file). Writes the flame graph, leaks, table and summary to results/memray/.
# memray stats needs a full capture: add MEMRAY_AGGREGATE=0 (quick mode only,
# a full run would write a huge file). The capture goes to
# /scratch/midway3/$USER/agri-profiling/memray/memray.bin.
# Submit from hpc-jobs/ with IMPACT_CALCULATIONS set. Add
# --export=ALL,QUICK=1 --time=03:00:00 for the quick version.
EXP=memray
PROFILER=memray
COMPARE_TO=baseline
source "$SLURM_SUBMIT_DIR/agriculture/profiling/jobs/run_experiment.sh"
