# Shared body of the profiling jobs. Each <experiment>.sbatch sets EXP, and
# optionally PROFILER (pyinstrument, memray or gc), COMPARE_TO, ALLOW_MISSING,
# CHECK_EXACT=1 (outputs must equal the reference) and PVALS_FROM, then
# sources this file. Submit from hpc-jobs/.
# QUICK=1 (sbatch --export=ALL,QUICK=1 ...) runs the quick config instead.
# A job writes none of its files under /project: outputs, results, the Slurm
# logs and the projection's own log all go to scratch.

KIT="$SLURM_SUBMIT_DIR/agriculture/profiling"
TOOLS="${PROFILING_TOOLS:-/project/cil/home_dirs/scadavidsanchez/tools/profiling-py37}"
ENV_DIR=/project/cil/home_dirs/rcc/envs/impact-env
PANEL_DIR=/project/cil/gcp/outputs_newsocioeconomics/socioeconomics/1.0.0
PROFILE_ROOT="/scratch/midway3/$USER/agri-profiling"
RESULTS_ROOT="${RESULTS_ROOT:-$PROFILE_ROOT/results}"
PROFILER="${PROFILER:-none}"

if [ "${QUICK:-0}" = "1" ]; then
    SUFFIX="-quick"
    CONFIG="$KIT/configs/quick/$EXP.yml"
else
    SUFFIX=""
    CONFIG="$KIT/configs/$EXP.yml"
fi
RUN="$EXP$SUFFIX"
RUN_DIR="$PROFILE_ROOT/$RUN"
OUTPUTS="$RUN_DIR/outputs"
RESULTS="$RESULTS_ROOT/$RUN"

if [ -z "${IMPACT_CALCULATIONS:-}" ]; then
    echo "ERROR: IMPACT_CALCULATIONS is not set. Point it at your impact-calculations clone:" >&2
    echo "  sbatch --export=ALL,IMPACT_CALCULATIONS=/path/to/impact-calculations <this script>" >&2
    exit 1
fi
REPO=$IMPACT_CALCULATIONS
if [ ! -f "$CONFIG" ]; then
    echo "ERROR: no config $CONFIG" >&2
    exit 1
fi
# Every job needs psutil for the sampler; pyinstrument and memray only their own job.
NEED=("$TOOLS/lib/psutil")
[ "$PROFILER" = "pyinstrument" ] && NEED+=("$TOOLS/pyinstrument/pyinstrument")
[ "$PROFILER" = "memray" ] && NEED+=("$TOOLS/memray/memray")
for need in "${NEED[@]}"; do
    if [ ! -e "$need" ]; then
        echo "ERROR: no $need. Run agriculture/profiling/jobs/install_tools.sh first." >&2
        exit 1
    fi
done
case "$OUTPUTS" in
    /scratch/midway3/?*/agri-profiling/?*/outputs) ;;
    *) echo "ERROR: unexpected output folder $OUTPUTS" >&2; exit 1 ;;
esac

# Earlier outputs would make the projection system skip files, so start clean.
rm -rf "$OUTPUTS"
mkdir -p "$OUTPUTS" "$RESULTS"
for f in manifest.json trace.json check.json error.txt profile.speedscope.json profile.html profile.txt \
         memray-flamegraph.html memray-leaks.html memray-table.html memray-summary.txt memray-stats.json \
         memray-stats.txt gc.csv; do
    rm -f "$RESULTS/$f"
done

module load python
source activate "$ENV_DIR"
export IMPERICS_SHAREDDIR=/project/cil/gcp
export PYTHONUNBUFFERED=1

# Library threads follow the cores Slurm gave the job (1 in the singles).
NCPU="${SLURM_CPUS_PER_TASK:-1}"
export OMP_NUM_THREADS=$NCPU OPENBLAS_NUM_THREADS=$NCPU MKL_NUM_THREADS=$NCPU
export NUMEXPR_NUM_THREADS=$NCPU NUMBA_NUM_THREADS=$NCPU

ARGS=("$CONFIG" "--outputdir=$OUTPUTS")
SSP=$(sed -n 's/^only-ssp: *//p' "$CONFIG")
IAM=$(sed -n 's/^only-iam: *//p' "$CONFIG")
RCP=$(sed -n 's/^only-rcp: *//p' "$CONFIG")

# Files a complete run writes: full adaptation and histclim, plus each farmer.
FARMERS=$(sed -n 's/^do_farmers: *//p' "$CONFIG")
case "$FARMERS" in
    "'always'") EXPECTED_FILES=8 ;;
    true) EXPECTED_FILES=4 ;;
    \[*) EXPECTED_FILES=$(( 3 + $(printf '%s' "$FARMERS" | tr -cd ',' | wc -c) )) ;;
    *) EXPECTED_FILES=1 ;;  # unknown (mortality): at least one
esac

# Experiments whose config points at agri-profiling/econ/ get a folder with
# only the CSV of their scenario, so one economic model is loaded, not ten.
if grep -q '^socioeconomic_data_dir: .*/agri-profiling/econ/' "$CONFIG"; then
    case "$IAM" in
        high) LABEL=OECD ;;
        low) LABEL=IIASA ;;
        *) echo "ERROR: unknown only-iam '$IAM' in $CONFIG" >&2; exit 1 ;;
    esac
    ECON_DIR="$PROFILE_ROOT/econ/$SSP-$IAM"
    mkdir -p "$ECON_DIR"
    ln -sfn "$PANEL_DIR/ir_combined_${SSP}_${LABEL}.csv" "$ECON_DIR/ir_combined_${SSP}_${LABEL}.csv"
    ARGS+=("--socioeconomic_data_dir=$ECON_DIR/")
    echo "Economic data folder: $ECON_DIR ($(ls "$ECON_DIR"))"
fi

# Reuse the montecarlo draws of another run, so both outputs can be compared.
if [ -n "${PVALS_FROM:-}" ]; then
    SRC_PVALS=$(find "$PROFILE_ROOT/$PVALS_FROM$SUFFIX/outputs" -name pvals.yml 2>/dev/null | head -1)
    UNIT_DIR="$OUTPUTS/batch0/$RCP/CCSM4/$IAM/$SSP"
    if [ -n "$SRC_PVALS" ]; then
        mkdir -p "$UNIT_DIR"
        cp "$SRC_PVALS" "$UNIT_DIR/pvals.yml"
        echo "Using the draws of $SRC_PVALS"
    else
        echo "WARNING: no pvals.yml from $PVALS_FROM$SUFFIX yet; this run makes its own draws and its output check will fail."
    fi
fi

case "$PROFILER" in
    none)
        CMD=(python -m generate.generate "${ARGS[@]}")
        ;;
    pyinstrument)
        # Runs inside the projection's process (Midway blocks ptrace, so py-spy
        # cannot attach). 10 stacks a second is plenty over 12 h. The reports go
        # to results/, the full session to scratch. pyinstrument goes after
        # site-packages, so the env's own packages win inside the projection.
        rm -f "$RUN_DIR/pyinstrument.pyisession"
        CMD=(python "$KIT/tools/pyinstrument_capture.py" --results "$RESULTS"
             --session "$RUN_DIR/pyinstrument.pyisession" --interval "${PYINSTRUMENT_INTERVAL:-0.1}"
             --extra-path "$TOOLS/pyinstrument" -m generate.generate "${ARGS[@]}")
        ;;
    memray)
        # memray and its dependencies go after site-packages, so the env's own
        # packages win inside the projection.
        MEMRAY_OPTS=(--output "$RUN_DIR/memray.bin" --extra-path "$TOOLS/memray")
        [ "${MEMRAY_AGGREGATE:-1}" = "1" ] && MEMRAY_OPTS+=(--aggregate)
        [ "${MEMRAY_NATIVE:-0}" = "1" ] && MEMRAY_OPTS+=(--native)
        rm -f "$RUN_DIR/memray.bin"
        CMD=(python "$KIT/tools/memray_capture.py" "${MEMRAY_OPTS[@]}" -m generate.generate "${ARGS[@]}")
        ;;
    gc)
        # A full garbage collection every GC_INTERVAL seconds, in the
        # projection's main thread. Each pass is a row of gc.csv.
        CMD=(python "$KIT/tools/gc_capture.py" --interval "${GC_INTERVAL:-60}" --log "$RUN_DIR/gc.csv"
             -m generate.generate "${ARGS[@]}")
        ;;
    *)
        echo "ERROR: unknown PROFILER $PROFILER" >&2
        exit 1
        ;;
esac

echo "Run: $RUN on $(hostname), $NCPU core(s), ${SLURM_MEM_PER_NODE:-?} MB"
echo "impact-calculations: $(git -C "$REPO" rev-parse --abbrev-ref HEAD) @ $(git -C "$REPO" rev-parse --short HEAD)"
echo "Config: $CONFIG"
echo "Outputs: $OUTPUTS"
echo "Command: ${CMD[*]}"

# The projection writes its own log to logs/generate-N.log under the working
# directory, so it runs from the run folder on scratch, not from the clone.
# PYTHONPATH then finds the clone, ahead of site-packages as before.
cd "$RUN_DIR" || exit 1
: > "$RUN_DIR/run.log"
PYTHONPATH="$TOOLS/lib" python "$KIT/tools/sampler.py" --root-pid $$ --log "$RUN_DIR/run.log" \
    --out "$RUN_DIR" --interval 1 &
SAMPLER=$!

START=$(date +%s.%N)
set -o pipefail
env PYTHONPATH="$REPO${PYTHONPATH:+:$PYTHONPATH}" "${CMD[@]}" 2> >(tee "$RUN_DIR/run.err" >&2) \
    | tee "$RUN_DIR/run.log"
STATUS=$?
set +o pipefail
END=$(date +%s.%N)
sleep 2
kill -TERM "$SAMPLER" 2>/dev/null
wait "$SAMPLER" 2>/dev/null
echo "Projection finished with status $STATUS after $(python -c "print(round(($END - $START) / 3600, 2))") h"

if [ "$PROFILER" = "memray" ] && [ -f "$RUN_DIR/memray.bin" ]; then
    # The reports run in their own process, with memray's dependencies first.
    MEMRAY=(env "PYTHONPATH=$TOOLS/memray" python -m memray)
    "${MEMRAY[@]}" flamegraph --force -o "$RESULTS/memray-flamegraph.html" "$RUN_DIR/memray.bin"
    "${MEMRAY[@]}" flamegraph --leaks --force -o "$RESULTS/memray-leaks.html" "$RUN_DIR/memray.bin"
    "${MEMRAY[@]}" table --force -o "$RESULTS/memray-table.html" "$RUN_DIR/memray.bin"
    # Wide columns, or rich cuts the table at 80 characters in a file.
    COLUMNS=200 "${MEMRAY[@]}" summary "$RUN_DIR/memray.bin" > "$RESULTS/memray-summary.txt" 2>&1
    if [ "${MEMRAY_AGGREGATE:-1}" = "1" ]; then
        echo "memray stats needs a full capture (MEMRAY_AGGREGATE=0); see memray-summary.txt" \
            > "$RESULTS/memray-stats.txt"
    else
        COLUMNS=200 "${MEMRAY[@]}" stats -n 25 "$RUN_DIR/memray.bin" > "$RESULTS/memray-stats.txt" 2>&1
        "${MEMRAY[@]}" stats -n 25 --json --force -o "$RESULTS/memray-stats.json" "$RUN_DIR/memray.bin" \
            > /dev/null 2>&1
    fi
fi

[ "$PROFILER" = "gc" ] && [ -f "$RUN_DIR/gc.csv" ] && cp "$RUN_DIR/gc.csv" "$RESULTS/gc.csv"

python "$KIT/tools/perfetto_export.py" --run-dir "$RUN_DIR" --output "$RESULTS/trace.json" --name "$RUN"

# Check only against a reference that has ended (its manifest is written last
# and removed when it starts again). Otherwise check.sbatch does it later.
EXACT_CHECK=()
EXACT_MANIFEST=()
if [ "${CHECK_EXACT:-0}" = "1" ]; then
    EXACT_CHECK=(--exact)
    EXACT_MANIFEST=(--check-exact)
fi
if [ -n "${COMPARE_TO:-}" ]; then
    if [ -f "$RESULTS_ROOT/$COMPARE_TO$SUFFIX/manifest.json" ]; then
        python "$KIT/tools/check_outputs.py" --candidate "$OUTPUTS" \
            --baseline "$PROFILE_ROOT/$COMPARE_TO$SUFFIX/outputs" --output "$RESULTS/check.json" \
            --allow-missing "${ALLOW_MISSING:-}" "${EXACT_CHECK[@]}"
    else
        echo "Reference $COMPARE_TO$SUFFIX has not ended yet; run check.sbatch after it does."
    fi
fi

QUICK_FLAG=()
[ -n "$SUFFIX" ] && QUICK_FLAG=(--quick)
python "$KIT/tools/collect_manifest.py" write --run "$RUN" --experiment "$EXP" "${QUICK_FLAG[@]}" \
    --profiler "$PROFILER" --compare-to "${COMPARE_TO:-}" --allow-missing "${ALLOW_MISSING:-}" \
    "${EXACT_MANIFEST[@]}" \
    --config "$CONFIG" --command "${CMD[*]}" \
    --run-dir "$RUN_DIR" --results "$RESULTS" --outputs "$OUTPUTS" --repo "$REPO" --tools "$TOOLS" \
    --start "$START" --end "$END" --status "$STATUS" --expected-files "${EXPECTED_FILES:-0}"
MANIFEST_STATUS=$?
python "$KIT/tools/collect_manifest.py" sacct "$RESULTS/manifest.json"

# The projection system exits with 0 even when it fails, so a missing file or
# a logged error marks the job as failed here.
if [ "$STATUS" -eq 0 ] && [ "$MANIFEST_STATUS" -eq 3 ]; then
    STATUS=1
fi
exit "$STATUS"
