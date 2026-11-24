#!/bin/bash
#SBATCH --job-name=agri-prof-periodicgc
#SBATCH --output=/scratch/midway3/%u/agri-profiling/logs/%x_%j.out
#SBATCH --error=/scratch/midway3/%u/agri-profiling/logs/%x_%j.err
#SBATCH --account=cil
#SBATCH --partition=cil
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=32G
#SBATCH --time=24:00:00

# The winter wheat single on the econmodel-memory branch (worktree
# impact-calculations-econfix, or ECONFIX_REPO) with gc-interval: 60, a full
# garbage collection every minute from the code (generate/periodic_gc.py),
# with no gc_capture.py wrapper, so no gc.csv. Memory is sampled every second
# as in the other runs. gccollect_econfix peaked at 5.3 GiB, and 32G covers
# econfix's 22.9 GiB in case the collections do not run.
# periodicgc_check.sbatch checks it against the master outputs under
# /project/cil/gcp/outputs_newsocioeconomics/.
# Add --export=ALL,QUICK=1 --time=03:00:00 for the quick version, checked
# against periodicgc_off-quick. Submit from hpc-jobs/.
EXP=periodicgc
IMPACT_CALCULATIONS="${ECONFIX_REPO:-/project/cil/home_dirs/scadavidsanchez/repos/impact-calculations-econfix}"
if [ ! -f "$IMPACT_CALCULATIONS/generate/periodic_gc.py" ]; then
    echo "ERROR: $IMPACT_CALCULATIONS has no generate/periodic_gc.py" >&2
    exit 1
fi
source "$SLURM_SUBMIT_DIR/agriculture/profiling/jobs/run_experiment.sh"
