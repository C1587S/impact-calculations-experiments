#!/bin/bash
#SBATCH --job-name=agri-prof-periodicgc_off
#SBATCH --output=/scratch/midway3/%u/agri-profiling/logs/%x_%j.out
#SBATCH --error=/scratch/midway3/%u/agri-profiling/logs/%x_%j.err
#SBATCH --account=cil
#SBATCH --partition=cil
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=16G
#SBATCH --time=03:00:00

# econfix-quick on the econmodel-memory branch with periodic garbage
# collection in the code (worktree impact-calculations-econfix, or
# ECONFIX_REPO), with no gc-interval in its config, so no collections. The
# reference for periodicgc-quick. Quick only: submit with --export=ALL,QUICK=1.
# Submit from hpc-jobs/.
EXP=periodicgc_off
IMPACT_CALCULATIONS="${ECONFIX_REPO:-/project/cil/home_dirs/scadavidsanchez/repos/impact-calculations-econfix}"
if [ ! -f "$IMPACT_CALCULATIONS/generate/periodic_gc.py" ]; then
    echo "ERROR: $IMPACT_CALCULATIONS has no generate/periodic_gc.py" >&2
    exit 1
fi
source "$SLURM_SUBMIT_DIR/agriculture/profiling/jobs/run_experiment.sh"
