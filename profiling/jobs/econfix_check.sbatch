#!/bin/bash
#SBATCH --job-name=agri-prof-econfix-check
#SBATCH --output=/scratch/midway3/%u/agri-profiling/logs/%x_%j.out
#SBATCH --error=/scratch/midway3/%u/agri-profiling/logs/%x_%j.err
#SBATCH --account=cil
#SBATCH --partition=cil
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=24G
#SBATCH --time=02:00:00

# Builds one economic model (SSP3, high) from master (IMPACT_CALCULATIONS) and
# one from the econmodel-memory branch (worktree impact-calculations-econfix,
# or ECONFIX_REPO), each in its own process. Checks that every population,
# popop, baseline and age-share value is identical, and measures the memory
# of each item. Writes results/econfix_check/check.json on scratch. Submit
# from hpc-jobs/.
KIT="$SLURM_SUBMIT_DIR/agriculture/profiling"
BRANCH="${ECONFIX_REPO:-/project/cil/home_dirs/scadavidsanchez/repos/impact-calculations-econfix}"
PANEL=/project/cil/gcp/outputs_newsocioeconomics/socioeconomics/1.0.0/
RUN_DIR="/scratch/midway3/$USER/agri-profiling/econfix_check"
RESULTS="${RESULTS_ROOT:-/scratch/midway3/$USER/agri-profiling/results}/econfix_check"

if [ -z "${IMPACT_CALCULATIONS:-}" ]; then
    echo "ERROR: IMPACT_CALCULATIONS is not set (the master clone)." >&2
    exit 1
fi
mkdir -p "$RUN_DIR" "$RESULTS"
rm -f "$RESULTS/check.json"

module load python
source activate /project/cil/home_dirs/rcc/envs/impact-env
export IMPERICS_SHAREDDIR=/project/cil/gcp

echo "master: $(git -C "$IMPACT_CALCULATIONS" rev-parse --abbrev-ref HEAD) @ $(git -C "$IMPACT_CALCULATIONS" rev-parse --short HEAD)"
echo "branch: $(git -C "$BRANCH" rev-parse --abbrev-ref HEAD) @ $(git -C "$BRANCH" rev-parse --short HEAD)"
for side in master branch; do
    repo=$IMPACT_CALCULATIONS
    [ "$side" = "branch" ] && repo=$BRANCH
    python "$KIT/tools/econfix_check.py" dump --repo "$repo" --data-dir "$PANEL" --ssp SSP3 --iam high \
        --out "$RUN_DIR/$side.pkl" || exit 1
done
python "$KIT/tools/econfix_check.py" compare --master "$RUN_DIR/master.pkl" --branch "$RUN_DIR/branch.pkl" \
    --output "$RESULTS/check.json"
