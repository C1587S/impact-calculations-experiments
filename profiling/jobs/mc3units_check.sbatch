#!/bin/bash
#SBATCH --job-name=agri-prof-mc3units_check
#SBATCH --output=/scratch/midway3/%u/agri-profiling/logs/%x_%j.out
#SBATCH --error=/scratch/midway3/%u/agri-profiling/logs/%x_%j.err
#SBATCH --account=cil
#SBATCH --partition=cil
#SBATCH --ntasks=1
#SBATCH --mem=16G
#SBATCH --time=01:00:00

# Where mc3units_gccollect_econfix departs from mc3units. The CCSM4 unit of
# each run is checked against mcunit, the same unit run alone on master with
# the same seed-csvv, and GFDL-ESM2M and MIROC5 of the two runs against each
# other, one JSON per pair. Also writes each run's units in the order they
# started, from its run log, and the CCSM4 pvals.yml of each run against
# mcunit's. Everything goes to mc3units_check/ on scratch.
# Submit from hpc-jobs/.
KIT="$SLURM_SUBMIT_DIR/agriculture/profiling"
PROFILE_ROOT="/scratch/midway3/$USER/agri-profiling"
OUT="$PROFILE_ROOT/mc3units_check"
RUNS=(mc3units mc3units_gccollect_econfix)
unit() { echo "$PROFILE_ROOT/$1/outputs/batch0/rcp85/$2/high/SSP3"; }
mkdir -p "$OUT"

# The projection prints each unit's output folder when the unit starts
for RUN in "${RUNS[@]}"; do
    echo "$RUN: $(tr -d '\r' < "$PROFILE_ROOT/$RUN/run.log" | grep -E '/outputs/batch0/rcp85/[^/]+/high/SSP3$' \
        | awk -F/ '{print $(NF-2)}' | paste -sd' ' -)"
done | tee "$OUT/order.txt"

for RUN in "${RUNS[@]}"; do
    diff "$(unit mcunit CCSM4)/pvals.yml" "$(unit "$RUN" CCSM4)/pvals.yml" > "$OUT/pvals_CCSM4_$RUN.diff"
    echo "pvals.yml of CCSM4, $RUN against mcunit: $(wc -l < "$OUT/pvals_CCSM4_$RUN.diff") diff lines"
done

check() {  # name, candidate folder, reference folder, label
    if ! ls "$2"/*.nc4 > /dev/null 2>&1 || ! ls "$3"/*.nc4 > /dev/null 2>&1; then
        echo "Skipping $1: outputs missing in $2 or $3"
        return
    fi
    python "$KIT/tools/check_outputs.py" --candidate "$2" --baseline "$3" --label "$4" --output "$OUT/$1.json"
}

module load python
source activate /project/cil/home_dirs/rcc/envs/impact-env/
for RUN in "${RUNS[@]}"; do
    check "CCSM4_$RUN" "$(unit "$RUN" CCSM4)" "$(unit mcunit CCSM4)" "master, job 63433857"
done
for GCM in GFDL-ESM2M MIROC5; do
    check "${GCM}_mc3units_gccollect_econfix" "$(unit mc3units_gccollect_econfix "$GCM")" \
        "$(unit mc3units "$GCM")" "master, job 63567890"
done

# Largest difference in rebased per file
python - "$OUT" <<'EOF'
import glob, json, os, sys
for path in sorted(glob.glob(os.path.join(sys.argv[1], "*.json"))):
    d = json.load(open(path))
    print("%s: %s against %s" % (os.path.basename(path)[:-5], d["status"], d["baseline"]))
    for f in d["files"]:
        print("  %-45s %s" % (os.path.basename(f["name"]), f["vars"].get("rebased", {}).get("max_abs_diff", 0.0)))
EOF
