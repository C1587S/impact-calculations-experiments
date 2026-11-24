#!/bin/bash
#SBATCH --job-name=agri-prof-mcunit_gfdl_gccollect_econfix
#SBATCH --output=/scratch/midway3/%u/agri-profiling/logs/%x_%j.out
#SBATCH --error=/scratch/midway3/%u/agri-profiling/logs/%x_%j.err
#SBATCH --account=cil
#SBATCH --partition=cil
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=12G
#SBATCH --time=12:00:00

# The GFDL-ESM2M unit of mc3units_gccollect_econfix run alone, on the
# econmodel-memory branch (worktree impact-calculations-econfix, or
# ECONFIX_REPO), with a full garbage collection every minute (GC_INTERVAL
# seconds) and the same seed-csvv. Each unit took about 6 h there.
# Checks its outputs against the GFDL-ESM2M unit of mc3units_gccollect_econfix,
# whose outputs must still be on scratch. The other two units of that run are
# allowed to be missing. Run check.sbatch after it, so check.json names the
# reference by its job. Submit from hpc-jobs/.
EXP=mcunit_gfdl_gccollect_econfix
PROFILER=gc
COMPARE_TO=mc3units_gccollect_econfix
ALLOW_MISSING='/(CCSM4|MIROC5)/'
IMPACT_CALCULATIONS="${ECONFIX_REPO:-/project/cil/home_dirs/scadavidsanchez/repos/impact-calculations-econfix}"
source "$SLURM_SUBMIT_DIR/agriculture/profiling/jobs/run_experiment.sh"
