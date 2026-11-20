#!/bin/bash
#SBATCH --job-name=agri-prof-same_outputs
#SBATCH --output=/scratch/midway3/%u/agri-profiling/logs/%x_%j.out
#SBATCH --error=/scratch/midway3/%u/agri-profiling/logs/%x_%j.err
#SBATCH --account=cil
#SBATCH --partition=cil
#SBATCH --ntasks=1
#SBATCH --mem=16G
#SBATCH --time=03:00:00

# Output checks of the singles against the master outputs under
# /project/cil/gcp/outputs_newsocioeconomics/, written to results/<run>/check.json,
# then same_outputs.py: master against lazy + gc over the years, one PNG and one
# CSV per sector in same_outputs/ on scratch. While a crop's shared folder is
# empty, the job reads the same files from reference/<crop>/ on scratch, and
# check.json still names the shared path. A run is skipped while it runs, once
# scratch has purged its outputs, or while its master outputs are missing.
# tools/same_outputs.py is a copy of experiments/2026-11-amd-round/same_outputs/
# in the experiments repo, run with uv. Submit from hpc-jobs/.
KIT="$SLURM_SUBMIT_DIR/agriculture/profiling"
PROFILE_ROOT="/scratch/midway3/$USER/agri-profiling"
RESULTS_ROOT="${RESULTS_ROOT:-$PROFILE_ROOT/results}"
SHARED=/project/cil/gcp/outputs_newsocioeconomics
TARGET=single/rcp85/CCSM4/high/SSP3
OUT="$PROFILE_ROOT/same_outputs"

# Each single, its master outputs and its label in the plots
RUNS=(econfix gccollect gccollect_econfix gc5min_econfix gcfreeze_econfix
      cassava_gccollect_econfix corn_gccollect_econfix rice_gccollect_econfix sorghum_gccollect_econfix
      soy_gccollect_econfix wheat_spring_gccollect_econfix
      labor_gccollect_econfix energy_gccollect_econfix mortality_single_gccollect_econfix)
declare -A REF NAME
for RUN in econfix gccollect gccollect_econfix gc5min_econfix gcfreeze_econfix; do
    REF[$RUN]=agriculture/wheat_winter
done
for CROP in cassava corn rice sorghum soy wheat_spring; do
    REF[${CROP}_gccollect_econfix]=agriculture/$CROP
    NAME[${CROP}_gccollect_econfix]=${CROP/_/ }
done
NAME[gccollect_econfix]="wheat winter"
REF[labor_gccollect_econfix]=labor
REF[energy_gccollect_econfix]=energy/other_energy
REF[mortality_single_gccollect_econfix]=mortality

# Folder holding a run's master outputs: the shared one, else for crops the copy on scratch
masters() {
    local shared="$SHARED/${REF[$1]}/$TARGET" copy="$PROFILE_ROOT/reference/${REF[$1]#agriculture/}"
    if ls "$shared"/*.nc4 > /dev/null 2>&1; then
        echo "$shared"
    elif [[ ${REF[$1]} == agriculture/* ]] && ls "$copy"/*.nc4 > /dev/null 2>&1; then
        echo "$copy"
    fi
}

ready() {
    [ -f "$RESULTS_ROOT/$1/manifest.json" ] && [ -d "$PROFILE_ROOT/$1/outputs" ] && [ -n "$(masters "$1")" ]
}

(
    module load python
    source activate /project/cil/home_dirs/rcc/envs/impact-env/
    for RUN in "${RUNS[@]}"; do
        if ! ready "$RUN"; then
            echo "Skipping the check of $RUN: not ended, outputs purged, or no master outputs"
            continue
        fi
        echo "Checking $RUN against $(masters "$RUN")"
        python "$KIT/tools/check_outputs.py" --candidate "$PROFILE_ROOT/$RUN/outputs" \
            --baseline "$(masters "$RUN")" --label "$SHARED/${REF[$RUN]}/$TARGET" \
            --output "$RESULTS_ROOT/$RUN/check.json"
    done
)

module load uv
export UV_CACHE_DIR=/project/cil/home_dirs/scadavidsanchez/.uv-cache
mkdir -p "$OUT"
plot() {
    local sector=$1 args=() run
    shift
    for run in "$@"; do
        ready "$run" && args+=(--pair "${NAME[$run]:-$sector}" "$(masters "$run")" "$PROFILE_ROOT/$run/outputs")
    done
    if [ ${#args[@]} -eq 0 ]; then
        echo "No $sector run to plot"
        return
    fi
    uv run --no-project "$KIT/tools/same_outputs.py" --out "$OUT/$sector.png" "${args[@]}"
}
plot agriculture gccollect_econfix cassava_gccollect_econfix corn_gccollect_econfix rice_gccollect_econfix \
    sorghum_gccollect_econfix soy_gccollect_econfix wheat_spring_gccollect_econfix
plot labor labor_gccollect_econfix
plot energy energy_gccollect_econfix
plot mortality mortality_single_gccollect_econfix
