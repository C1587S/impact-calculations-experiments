#!/bin/bash
#SBATCH --job-name=agri-prof-mc3units_cil
#SBATCH --output=/scratch/midway3/%u/agri-profiling/logs/%x_%j.out
#SBATCH --error=/scratch/midway3/%u/agri-profiling/logs/%x_%j.err
#SBATCH --account=cil
#SBATCH --partition=cil
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=32G
#SBATCH --time=1-12:00:00

# mc3units on the cil partition: the same three winter wheat units on master,
# with the same config and seed-csvv, telemetry only. It writes to its own
# folders, so mc3units stays as it is. mc3units_cil_check.sbatch compares its
# outputs with mcunit, mc3units and mc3units_gccollect_econfix.
# Submit from hpc-jobs/ with IMPACT_CALCULATIONS set.
EXP=mc3units_cil
EXPECTED_FILES=12
source "$SLURM_SUBMIT_DIR/agriculture/profiling/jobs/run_experiment.sh"
