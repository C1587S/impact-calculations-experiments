#!/bin/bash
#SBATCH --job-name=agri-prof-gccollect_econfix
#SBATCH --output=/scratch/midway3/%u/agri-profiling/logs/%x_%j.out
#SBATCH --error=/scratch/midway3/%u/agri-profiling/logs/%x_%j.err
#SBATCH --account=cil
#SBATCH --partition=caslake
#SBATCH --qos=caslake
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=32G
#SBATCH --time=24:00:00

# gccollect on the econmodel-memory branch (worktree impact-calculations-econfix,
# or ECONFIX_REPO): a full garbage collection every minute (GC_INTERVAL
# seconds) in the projection's main thread. Shows how low the lazy econ model peaks
# once dropped weather is freed promptly.
#
# Runs on caslake, 30 min after gccollect starts, so the two never read the
# weather in step. Submit it with --dependency=after:<gccollect job id>+30.
# caslake has another CPU model than the cil node of econfix, so compare its
# memory with econfix, not its time.
#
# Checks its outputs against econfix, the same code without the extra
# collections, which must still be on scratch. Submit from hpc-jobs/.
EXP=gccollect_econfix
PROFILER=gc
COMPARE_TO=econfix
IMPACT_CALCULATIONS="${ECONFIX_REPO:-/project/cil/home_dirs/scadavidsanchez/repos/impact-calculations-econfix}"
source "$SLURM_SUBMIT_DIR/agriculture/profiling/jobs/run_experiment.sh"
