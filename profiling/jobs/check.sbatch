#!/bin/bash
#SBATCH --job-name=agri-prof-check
#SBATCH --output=/scratch/midway3/%u/agri-profiling/logs/%x_%j.out
#SBATCH --error=/scratch/midway3/%u/agri-profiling/logs/%x_%j.err
#SBATCH --account=cil
#SBATCH --partition=cil
#SBATCH --ntasks=1
#SBATCH --mem=16G
#SBATCH --time=02:00:00

# Runs the output check of every finished experiment again, against the
# reference run named in its manifest. Each job already checks itself at the
# end when its reference has ended; this covers runs that ended first. Submit
# from hpc-jobs/, best with --dependency=afterany:<all experiment job ids>.
KIT="$SLURM_SUBMIT_DIR/agriculture/profiling"
PROFILE_ROOT="/scratch/midway3/$USER/agri-profiling"
RESULTS_ROOT="${RESULTS_ROOT:-$PROFILE_ROOT/results}"

module load python
source activate /project/cil/home_dirs/rcc/envs/impact-env/

for manifest in "$RESULTS_ROOT"/*/manifest.json; do
    [ -f "$manifest" ] || continue
    RUN=$(basename "$(dirname "$manifest")")
    read -r COMPARE ALLOW EXACT < <(python -c "
import json, sys
m = json.load(open(sys.argv[1]))
ref = m.get('compare_to') or ''
if ref and m.get('quick'):
    ref += '-quick'
print(ref or '-', m.get('allow_missing') or '-', '--exact' if m.get('check_exact') else '-')
" "$manifest")
    [ "$COMPARE" = "-" ] && continue
    [ "$ALLOW" = "-" ] && ALLOW=""
    EXACT_FLAG=()
    [ "$EXACT" = "--exact" ] && EXACT_FLAG=(--exact)
    if [ ! -f "$RESULTS_ROOT/$COMPARE/manifest.json" ]; then
        echo "Skipping $RUN: its reference $COMPARE has not ended"
        continue
    fi
    echo "Checking $RUN against $COMPARE"
    python "$KIT/tools/check_outputs.py" --candidate "$PROFILE_ROOT/$RUN/outputs" \
        --baseline "$PROFILE_ROOT/$COMPARE/outputs" --output "$RESULTS_ROOT/$RUN/check.json" \
        --allow-missing "$ALLOW" "${EXACT_FLAG[@]}"
done
