#!/bin/bash
#SBATCH --job-name=agri-prof-mc3units_cil_check
#SBATCH --output=/scratch/midway3/%u/agri-profiling/logs/%x_%j.out
#SBATCH --error=/scratch/midway3/%u/agri-profiling/logs/%x_%j.err
#SBATCH --account=cil
#SBATCH --partition=cil
#SBATCH --ntasks=1
#SBATCH --mem=16G
#SBATCH --time=02:00:00

# Output checks of mc3units_cil, file by file: its CCSM4 unit against mcunit,
# and its three units against mc3units and against mc3units_gccollect_econfix,
# one JSON each. Also writes the order of its units from its run log and the
# pvals.yml of each unit against mc3units. Everything goes to
# mc3units_cil_check/ on scratch. A reference is skipped once scratch has
# purged its outputs. Submit from hpc-jobs/ with
# --dependency=afterany:<mc3units_cil job id>.
KIT="$SLURM_SUBMIT_DIR/agriculture/profiling"
PROFILE_ROOT="/scratch/midway3/$USER/agri-profiling"
RESULTS_ROOT="${RESULTS_ROOT:-$PROFILE_ROOT/results}"
RUN=mc3units_cil
OUT="$PROFILE_ROOT/mc3units_cil_check"
unit() { echo "$PROFILE_ROOT/$1/outputs/batch0/rcp85/$2/high/SSP3"; }
mkdir -p "$OUT"
[ -f "$RESULTS_ROOT/$RUN/manifest.json" ] || echo "WARNING: $RUN has no manifest.json, so it may not have ended"

# The projection prints each unit's output folder when the unit starts
echo "$RUN: $(tr -d '\r' < "$PROFILE_ROOT/$RUN/run.log" | grep -E '/outputs/batch0/rcp85/[^/]+/high/SSP3$' \
    | awk -F/ '{print $(NF-2)}' | paste -sd' ' -)" | tee "$OUT/order.txt"

for GCM in CCSM4 GFDL-ESM2M MIROC5; do
    diff "$(unit mc3units "$GCM")/pvals.yml" "$(unit "$RUN" "$GCM")/pvals.yml" > "$OUT/pvals_$GCM.diff"
    echo "pvals.yml of $GCM against mc3units: $(wc -l < "$OUT/pvals_$GCM.diff") diff lines"
done

check() {  # name, candidate folder, reference folder, label
    if [ -z "$(find "$2" -name '*.nc4' 2>/dev/null | head -1)" ] || [ -z "$(find "$3" -name '*.nc4' 2>/dev/null | head -1)" ]; then
        echo "Skipping $1: no outputs in $2 or $3"
        return
    fi
    python "$KIT/tools/check_outputs.py" --candidate "$2" --baseline "$3" --label "$4" --output "$OUT/$1.json"
}

module load python
source activate /project/cil/home_dirs/rcc/envs/impact-env/
check CCSM4_against_mcunit "$(unit "$RUN" CCSM4)" "$(unit mcunit CCSM4)" "master, job 63433857"
check against_mc3units "$PROFILE_ROOT/$RUN/outputs" "$PROFILE_ROOT/mc3units/outputs" "master, job 63567890"
check against_mc3units_gccollect_econfix "$PROFILE_ROOT/$RUN/outputs" \
    "$PROFILE_ROOT/mc3units_gccollect_econfix/outputs" "mc3units_gccollect_econfix, job 63567891"

# Largest difference in rebased per file
python - "$OUT" <<'EOF'
import glob, json, os, sys
for path in sorted(glob.glob(os.path.join(sys.argv[1], "*.json"))):
    d = json.load(open(path))
    print("%s: %s against %s" % (os.path.basename(path)[:-5], d["status"], d["baseline"]))
    for f in d["files"]:
        name = f["name"].replace("batch0/rcp85/", "").replace("/high/SSP3", "")
        print("  %-55s %s" % (name, f["vars"].get("rebased", {}).get("max_abs_diff", 0.0)))
    for name in d["missing_in_candidate"]:
        print("  %-55s missing in %s" % (name, "mc3units_cil"))
EOF
