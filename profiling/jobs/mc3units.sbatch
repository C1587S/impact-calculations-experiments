#!/bin/bash
#SBATCH --job-name=agri-prof-mc3units
#SBATCH --output=/scratch/midway3/%u/agri-profiling/logs/%x_%j.out
#SBATCH --error=/scratch/midway3/%u/agri-profiling/logs/%x_%j.err
#SBATCH --account=cil
#SBATCH --partition=amd
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=32G
#SBATCH --time=36:00:00

# Three winter wheat montecarlo units in one process, on master, telemetry only:
# the reference for mc3units_gccollect_econfix. Montecarlo workers run several
# units one after another, so memory could build up across them.
# mcunit peaked at 20.2 GiB with its one unit, so 32G leaves room for memory
# that builds up from one unit to the next. The gc version asks for 12G, as
# mcunit_gccollect_econfix peaked at 5.0 GiB.
# Each unit starts when the projection prints its output folder: the trace
# has a units track, and the manifest (stages.units) and the report give the
# memory at the start of each unit and its peaks. Twelve files, four per unit.
#
# The ten agriculture runs of the amd round read the same rcp85 crop weather,
# so each starts 30 min after the one before: all but the first go in with
# --dependency=after:<previous job id>+30 (order in the README).
# Submit from hpc-jobs/ with IMPACT_CALCULATIONS set.
EXP=mc3units
EXPECTED_FILES=12
source "$SLURM_SUBMIT_DIR/agriculture/profiling/jobs/run_experiment.sh"
