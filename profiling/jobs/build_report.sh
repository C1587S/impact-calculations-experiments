#!/bin/bash
# Adds the final sacct numbers to every manifest, rebuilds each finished run's
# Perfetto trace from its samples (so fixes to the exporter reach runs that
# already ended), then builds report/index.html. Reads and writes scratch only.
# Run on a login node, from hpc-jobs/, after the jobs end:
#
#   bash agriculture/profiling/jobs/build_report.sh
set -euo pipefail

KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROFILE_ROOT="/scratch/midway3/$USER/agri-profiling"
RESULTS_ROOT="${RESULTS_ROOT:-$PROFILE_ROOT/results}"
PY=/project/cil/home_dirs/rcc/envs/impact-env/bin/python

shopt -s nullglob
manifests=("$RESULTS_ROOT"/*/manifest.json)
if [ ${#manifests[@]} -eq 0 ]; then
    echo "No manifests in $RESULTS_ROOT yet."
else
    "$PY" "$KIT/tools/collect_manifest.py" sacct "${manifests[@]}"
    for manifest in "${manifests[@]}"; do
        run=$(basename "$(dirname "$manifest")")
        run_dir="$PROFILE_ROOT/$run"
        if [ -f "$run_dir/samples.csv" ]; then
            "$PY" "$KIT/tools/perfetto_export.py" --run-dir "$run_dir" \
                --output "$(dirname "$manifest")/trace.json" --name "$run"
        fi
    done
fi
"$PY" "$KIT/tools/build_report.py" --results "$RESULTS_ROOT" --output "$PROFILE_ROOT/report/index.html" "$@"
echo "Report: $PROFILE_ROOT/report/index.html"
