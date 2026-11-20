#!/bin/bash
#SBATCH --job-name=agri-prof-gccollect
#SBATCH --output=/scratch/midway3/%u/agri-profiling/logs/%x_%j.out
#SBATCH --error=/scratch/midway3/%u/agri-profiling/logs/%x_%j.err
#SBATCH --account=cil
#SBATCH --partition=caslake
#SBATCH --qos=caslake
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=32G
#SBATCH --time=24:00:00

# The baseline with a full garbage collection every minute (GC_INTERVAL
# seconds), run in the projection's main thread. No change to
# impact-calculations or openest.
#
# Why: in the full runs, memory climbs in steps through the covariates and
# the noadapt and global year loops, and falls in single drops away from any
# stage boundary. openest's FastDataset and its arrays point at each other,
# so a weather year is freed only by a full collection, and Python 3.7 runs
# one rarely while millions of objects are alive. If that sets the peak, this
# run peaks well below the baseline's 20.3 GiB with the same outputs.
# gc.csv (in results/gccollect/) lists each pass and how long it took.
#
# Submit from hpc-jobs/ with IMPACT_CALCULATIONS set. Runs on caslake, and
# gccollect_econfix starts 30 min after it, so the two never read the weather
# in step. caslake has another CPU model than the cil node of baseline, so
# compare its memory with baseline, not its time. Checks its outputs against
# the full baseline, which must still be on scratch.
EXP=gccollect
PROFILER=gc
COMPARE_TO=baseline
source "$SLURM_SUBMIT_DIR/agriculture/profiling/jobs/run_experiment.sh"
