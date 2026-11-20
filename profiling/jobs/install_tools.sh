#!/bin/bash
# Installs the profiling tools for Python 3.7 outside the shared env, with the
# env's own Python and pip install --target. Run once on a login node (it needs
# internet). Nothing is written into the shared env.
#
#   bash agriculture/profiling/jobs/install_tools.sh
#
# Versions are the newest with Python 3.7 Linux wheels:
#   memray 1.17.2 (1.18 and later have none), with its dependencies (jinja2,
#   rich, textual and theirs), which pip picks for Python 3.7.
#   pyinstrument 4.6.2 (4.7 and later need Python 3.8). It has no dependencies.
#   psutil 7.2.2, no dependencies.
# Both profilers run inside the projection's process. Tools that attach to a
# process, like py-spy, cannot work on Midway (kernel.yama.ptrace_scope is 3).
#
# Folders:
#   lib/           psutil, on the PYTHONPATH of the sampler
#   memray/        memray and its dependencies
#   pyinstrument/  pyinstrument
# The profiled jobs add memray/ or pyinstrument/ after site-packages, so the
# env's own packages win inside the projection.
set -euo pipefail

TOOLS="${PROFILING_TOOLS:-/project/cil/home_dirs/scadavidsanchez/tools/profiling-py37}"
PY=/project/cil/home_dirs/rcc/envs/impact-env/bin/python
PIP=("$PY" -m pip install --no-cache-dir --disable-pip-version-check --only-binary=:all: --upgrade)

echo "Installing into $TOOLS with $("$PY" --version 2>&1), $("$PY" -m pip --version)"
mkdir -p "$TOOLS"

"${PIP[@]}" --no-deps --target "$TOOLS/lib" psutil==7.2.2
"${PIP[@]}" --target "$TOOLS/memray" memray==1.17.2
"${PIP[@]}" --target "$TOOLS/pyinstrument" pyinstrument==4.6.2

echo "Checking the install"
PYTHONPATH="$TOOLS/lib" "$PY" -c "import psutil; print('psutil', psutil.__version__)"
# The way the profiled jobs import them: after site-packages.
for tool in memray pyinstrument; do
    "$PY" -c "import sys, importlib; sys.path.append(sys.argv[1]); m = importlib.import_module(sys.argv[2]); print(sys.argv[2], m.__version__)" \
        "$TOOLS/$tool" "$tool"
done
"$PY" -c "import sys; sys.path.append(sys.argv[1]); from pyinstrument.renderers import SpeedscopeRenderer, HTMLRenderer" \
    "$TOOLS/pyinstrument"
# The memray reports load every memray command, so this also imports textual and rich.
PYTHONPATH="$TOOLS/memray" "$PY" -m memray --version
echo "memray and its dependencies:"
"$PY" -m pip list --disable-pip-version-check --path "$TOOLS/memray"
echo "Done. Tools are in $TOOLS"
