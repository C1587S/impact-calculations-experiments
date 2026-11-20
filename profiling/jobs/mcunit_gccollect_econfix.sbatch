#!/bin/bash
#SBATCH --job-name=agri-prof-mcunit_gccollect_econfix
#SBATCH --output=/scratch/midway3/%u/agri-profiling/logs/%x_%j.out
#SBATCH --error=/scratch/midway3/%u/agri-profiling/logs/%x_%j.err
#SBATCH --account=cil
#SBATCH --partition=caslake
#SBATCH --qos=caslake
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=12G
#SBATCH --time=24:00:00

# The mcunit unit on the econmodel-memory branch (worktree
# impact-calculations-econfix, or ECONFIX_REPO) with a full garbage collection
# every minute (GC_INTERVAL seconds) in the projection's main thread.
#
# Before the projection starts, the job copies mcunit's pvals.yml into its
# output folder, so every seed matches mcunit. The file must hold both seeds:
# seed-csvv (the coefficients) and seed-yearorder (the histclim year order).
# Without seed-yearorder the projection would hash its own, with the fields in
# another order, and histclim would differ from mcunit. So the job stops here
# if either seed is missing.
#
# Checks its outputs against mcunit, whose outputs must still be on scratch.
# caslake has another CPU model than the cil node of mcunit, so compare its
# memory with mcunit, not its time. Full run only. Submit from hpc-jobs/.
EXP=mcunit_gccollect_econfix
PROFILER=gc
COMPARE_TO=mcunit
PVALS_FROM=mcunit
IMPACT_CALCULATIONS="${ECONFIX_REPO:-/project/cil/home_dirs/scadavidsanchez/repos/impact-calculations-econfix}"

MCUNIT_PVALS=$(find "/scratch/midway3/$USER/agri-profiling/mcunit/outputs" -name pvals.yml 2>/dev/null | head -1)
for seed in seed-csvv seed-yearorder; do
    if ! grep -q "^ *$seed: " "${MCUNIT_PVALS:-/dev/null}"; then
        echo "ERROR: $seed is missing from mcunit's pvals.yml (${MCUNIT_PVALS:-none found on scratch})." >&2
        exit 1
    fi
done
echo "mcunit draws: $MCUNIT_PVALS"
cat "$MCUNIT_PVALS"

source "$SLURM_SUBMIT_DIR/agriculture/profiling/jobs/run_experiment.sh"
