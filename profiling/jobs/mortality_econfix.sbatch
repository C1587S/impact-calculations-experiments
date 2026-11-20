#!/bin/bash
#SBATCH --job-name=agri-prof-mortality_econfix
#SBATCH --output=/scratch/midway3/%u/agri-profiling/logs/%x_%j.out
#SBATCH --error=/scratch/midway3/%u/agri-profiling/logs/%x_%j.err
#SBATCH --account=cil
#SBATCH --partition=cil
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=40G
#SBATCH --time=04:00:00

# The same mortality quick single on the econmodel-memory branch (worktree
# impact-calculations-econfix, or ECONFIX_REPO). Its outputs must equal the
# mortality run's exactly (xarray.testing.assert_equal). Quick mode only.
# Submit from hpc-jobs/.
EXP=mortality_econfix
QUICK=1
COMPARE_TO=mortality
CHECK_EXACT=1
IMPACT_CALCULATIONS="${ECONFIX_REPO:-/project/cil/home_dirs/scadavidsanchez/repos/impact-calculations-econfix}"
source "$SLURM_SUBMIT_DIR/agriculture/profiling/jobs/run_experiment.sh"
