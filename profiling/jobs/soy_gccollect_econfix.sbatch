#!/bin/bash
#SBATCH --job-name=agri-prof-soy_gccollect_econfix
#SBATCH --output=/scratch/midway3/%u/agri-profiling/logs/%x_%j.out
#SBATCH --error=/scratch/midway3/%u/agri-profiling/logs/%x_%j.err
#SBATCH --account=cil
#SBATCH --partition=amd
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=12G
#SBATCH --time=24:00:00

# The soy single (rcp85, CCSM4, high, SSP3)
# on the econmodel-memory branch (worktree impact-calculations-econfix, or
# ECONFIX_REPO), with a full garbage collection every minute (GC_INTERVAL
# seconds) in the projection's main thread.
# As gccollect_econfix for winter wheat: shows whether the other crops fit in
# 12G too. The master single took about 4.0 h on amd (job 61258866).
#
# Output check: same_outputs.sbatch, against
# /project/cil/gcp/outputs_newsocioeconomics/agriculture/soy/single/rcp85/CCSM4/high/SSP3/.
#
# The ten agriculture runs of the amd round read the same rcp85 crop weather,
# so each starts 30 min after the one before: all but the first go in with
# --dependency=after:<previous job id>+30 (order in the README).
# Submit from hpc-jobs/.
EXP=soy_gccollect_econfix
PROFILER=gc
IMPACT_CALCULATIONS="${ECONFIX_REPO:-/project/cil/home_dirs/scadavidsanchez/repos/impact-calculations-econfix}"
source "$SLURM_SUBMIT_DIR/agriculture/profiling/jobs/run_experiment.sh"
