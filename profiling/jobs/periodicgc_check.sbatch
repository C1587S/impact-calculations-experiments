#!/bin/bash
#SBATCH --job-name=agri-prof-periodicgc_check
#SBATCH --output=/scratch/midway3/%u/agri-profiling/logs/%x_%j.out
#SBATCH --error=/scratch/midway3/%u/agri-profiling/logs/%x_%j.err
#SBATCH --account=cil
#SBATCH --partition=cil
#SBATCH --ntasks=1
#SBATCH --mem=16G
#SBATCH --time=01:00:00

# Output checks of the periodic garbage collection runs, written to
# results/<run>/check.json: periodicgc-quick against periodicgc_off-quick,
# identical values required, and periodicgc against the master outputs under
# /project/cil/gcp/outputs_newsocioeconomics/, where the single writes no
# global files. Also counts the line each run prints when its timer starts.
# Checks only runs that have ended, so submit it after the quick pair and
# again after the full run. Submit from hpc-jobs/.
KIT="$SLURM_SUBMIT_DIR/agriculture/profiling"
PROFILE_ROOT="/scratch/midway3/$USER/agri-profiling"
RESULTS_ROOT="${RESULTS_ROOT:-$PROFILE_ROOT/results}"
SHARED=/project/cil/gcp/outputs_newsocioeconomics/agriculture/wheat_winter/single/rcp85/CCSM4/high/SSP3
ended() { [ -f "$RESULTS_ROOT/$1/manifest.json" ] && [ -d "$PROFILE_ROOT/$1/outputs" ]; }

# One line with gc-interval, none without
for RUN in periodicgc_off-quick periodicgc-quick periodicgc; do
    if [ -f "$PROFILE_ROOT/$RUN/run.log" ]; then
        echo "$RUN: $(grep -c '^Full garbage collection every' "$PROFILE_ROOT/$RUN/run.log") timer line"
    fi
done

module load python
source activate /project/cil/home_dirs/rcc/envs/impact-env/

if ended periodicgc-quick && ended periodicgc_off-quick; then
    JOB=$(python -c "import json, sys; print(json.load(open(sys.argv[1]))['slurm']['job_id'])" \
        "$RESULTS_ROOT/periodicgc_off-quick/manifest.json")
    python "$KIT/tools/check_outputs.py" --exact --candidate "$PROFILE_ROOT/periodicgc-quick/outputs" \
        --baseline "$PROFILE_ROOT/periodicgc_off-quick/outputs" --label "periodicgc_off-quick, job $JOB" \
        --output "$RESULTS_ROOT/periodicgc-quick/check.json"
else
    echo "Skipping the quick check: periodicgc-quick or periodicgc_off-quick has not ended"
fi

if ended periodicgc; then
    python "$KIT/tools/check_outputs.py" --candidate "$PROFILE_ROOT/periodicgc/outputs" --baseline "$SHARED" \
        --allow-missing global --output "$RESULTS_ROOT/periodicgc/check.json"
else
    echo "Skipping the full check: periodicgc has not ended"
fi
