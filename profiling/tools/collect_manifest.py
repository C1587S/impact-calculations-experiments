"""Write or update the manifest.json of one profiling run.

  collect_manifest.py write ...      at the end of a job: config, cores, memory,
                                     node, impact-calculations commit, timings
  collect_manifest.py sacct FILE...  later, from a login node: adds the final
                                     sacct numbers (MaxRSS, Elapsed, CPU efficiency)
"""

import argparse
import datetime
import glob
import json
import os
import platform
import re
import socket
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import telemetry  # noqa: E402

SLURM_VARS = ["SLURM_JOB_ID", "SLURM_JOB_NAME", "SLURM_JOB_PARTITION", "SLURM_JOB_ACCOUNT",
              "SLURM_CPUS_PER_TASK", "SLURM_MEM_PER_NODE", "SLURM_JOB_NODELIST", "SLURM_SUBMIT_DIR"]
THREAD_VARS = ["OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS",
               "NUMBA_NUM_THREADS"]


def run(cmd, cwd=None, strip=True, env=None):
    """Run a command and return its output, or None if it fails.

    Parameters
    ----------
    cmd : list of str
    cwd : str or None
    strip : bool
        Strip surrounding whitespace (off for git status, whose lines start with a space).
    env : dict or None
        Extra environment variables.

    Returns
    -------
    str or None
    """
    try:
        out = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                             universal_newlines=True, timeout=120,
                             env=dict(os.environ, **env) if env else None)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    return out.stdout.strip() if strip else out.stdout


def cpu_model():
    """CPU model of the node, so timings are compared on like hardware."""
    try:
        with open("/proc/cpuinfo") as fp:
            for line in fp:
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or None


def git_info(repo):
    """Commit, branch and locally changed files of the impact-calculations clone.

    Parameters
    ----------
    repo : str

    Returns
    -------
    dict
    """
    # No optional locks: git status then leaves the clone's index untouched.
    status = run(["git", "status", "--porcelain"], cwd=repo, strip=False, env={"GIT_OPTIONAL_LOCKS": "0"})
    return dict(path=repo,
                branch=run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo),
                sha=run(["git", "rev-parse", "HEAD"], cwd=repo),
                short_sha=run(["git", "rev-parse", "--short", "HEAD"], cwd=repo),
                changed_files=[l[3:] for l in status.splitlines() if l and not l.startswith("??")] if status else [])


def tool_versions(tools):
    """Versions of psutil, memray and pyinstrument found in the tools folder."""
    out = {}
    for name, folder in (("psutil", "lib"), ("memray", "memray"), ("pyinstrument", "pyinstrument")):
        env = dict(os.environ, PYTHONPATH=os.path.join(tools, folder))
        try:
            res = subprocess.run([sys.executable, "-c", "import %s; print(%s.__version__)" % (name, name)],
                                 env=env, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                 universal_newlines=True, timeout=60)
            out[name] = res.stdout.strip() if res.returncode == 0 else None
        except (OSError, subprocess.TimeoutExpired):
            out[name] = None
    return out


def output_files(outputs):
    """Name and size of every .nc4 the run wrote."""
    files = []
    for path in sorted(glob.glob(os.path.join(outputs, "**", "*.nc4"), recursive=True)):
        files.append(dict(name=os.path.relpath(path, outputs), bytes=os.path.getsize(path)))
    return files


def error_tail(run_log, repo, lines=200):
    """Last lines of the projection system's own log when the run reports an error.

    The projection system catches every exception, prints where it logged it
    and exits with status 0, so the job status alone does not show failures.

    Parameters
    ----------
    run_log : str
    repo : str
    lines : int

    Returns
    -------
    str or None
    """
    try:
        with open(run_log, errors="replace") as fp:
            text = fp.read()
    except OSError:
        return None
    m = re.search(r"details are logged at (\S+)", text)
    if not m:
        return None
    path = m.group(1)
    if not os.path.isabs(path):
        path = os.path.join(repo, path)
    try:
        with open(path, errors="replace") as fp:
            return "".join(fp.readlines()[-lines:])
    except OSError:
        return "could not read " + path


def write(args):
    """Write results/<run>/manifest.json from the job's environment and files."""
    run_dir = args.run_dir
    samples = telemetry.read_samples(os.path.join(run_dir, "samples.csv"))
    markers = telemetry.read_markers(os.path.join(run_dir, "markers.tsv"))
    stages = telemetry.build_stages(markers, args.end)
    summary = telemetry.stage_summary(stages)
    files = output_files(args.outputs)

    with open(args.config) as fp:
        config_text = fp.read()

    tail = error_tail(os.path.join(run_dir, "run.log"), args.repo)
    if tail:
        with open(os.path.join(args.results, "error.txt"), "w") as fp:
            fp.write(tail)

    failed = args.status != 0 or summary["error"] is not None or tail is not None
    if args.expected_files and len(files) < args.expected_files:
        failed = True

    manifest = dict(
        run=args.run, experiment=args.experiment, quick=args.quick, profiler=args.profiler,
        compare_to=args.compare_to or None, allow_missing=args.allow_missing or None,
        check_exact=args.check_exact,
        config=dict(path=args.config, text=config_text),
        command=args.command,
        slurm={k.replace("SLURM_", "").lower(): os.environ.get(k) for k in SLURM_VARS},
        cores=int(os.environ.get("SLURM_CPUS_PER_TASK", "1")),
        mem_requested_gb=round(int(os.environ.get("SLURM_MEM_PER_NODE", "0")) / 1024.0, 1) or None,
        node=dict(hostname=socket.gethostname(), cpu_model=cpu_model(), cpus_online=os.cpu_count(),
                  kernel=platform.release()),
        thread_env={k: os.environ.get(k) for k in THREAD_VARS},
        impact_calculations=git_info(args.repo),
        python=platform.python_version(),
        conda_env=os.environ.get("CONDA_PREFIX"),
        tools=tool_versions(args.tools),
        start=datetime.datetime.fromtimestamp(args.start).isoformat(timespec="seconds"),
        end=datetime.datetime.fromtimestamp(args.end).isoformat(timespec="seconds"),
        wall_seconds=round(args.end - args.start, 1),
        exit_status=args.status,
        failed=failed,
        error=summary["error"] or (tail.strip().splitlines()[-1] if tail else None),
        outputs=dict(dir=args.outputs, count=len(files), expected=args.expected_files or None, files=files),
        telemetry=telemetry.sample_summary(samples),
        stages=summary,
        sstat=sstat(os.environ.get("SLURM_JOB_ID")),
        sacct=None,
    )
    path = os.path.join(args.results, "manifest.json")
    with open(path, "w") as fp:
        json.dump(manifest, fp, indent=1)
    print("wrote " + path)
    if failed:
        print("WARNING: this run looks failed (status %s, error: %s, %d of %s files)" % (
            args.status, manifest["error"], len(files), args.expected_files or "?"))
        # The job turns this into a failed Slurm state.
        sys.exit(3)


def sstat(job_id):
    """Peak memory of the running batch step so far, as sacct does not have it yet.

    Parameters
    ----------
    job_id : str or None

    Returns
    -------
    dict or None
    """
    if not job_id:
        return None
    out = run(["sstat", "-j", job_id + ".batch", "--noheader", "--parsable2", "--format=MaxRSS,AveCPU"])
    if not out:
        return None
    fields = out.splitlines()[0].split("|")
    return dict(max_rss_gb=parse_mem_gb(fields[0]), ave_cpu=fields[1] if len(fields) > 1 else None)


def parse_mem_gb(text):
    """Read a Slurm memory value such as 21388044K, 32G or 32Gn as GB.

    Parameters
    ----------
    text : str

    Returns
    -------
    float or None
    """
    m = re.match(r"^\s*([0-9.]+)\s*([KMGT]?)", text or "")
    if not m:
        return None
    scale = {"": 1.0 / 1024 ** 3, "K": 1.0 / 1024 ** 2, "M": 1.0 / 1024, "G": 1.0, "T": 1024.0}[m.group(2)]
    return round(float(m.group(1)) * scale, 2)


def parse_seconds(text):
    """Read a Slurm duration such as 1-02:03:04, 02:03:04 or 03:04.567 as seconds.

    Parameters
    ----------
    text : str

    Returns
    -------
    float or None
    """
    if not text:
        return None
    days = 0
    if "-" in text:
        d, text = text.split("-", 1)
        days = int(d)
    parts = [float(p) for p in text.split(":")]
    while len(parts) < 3:
        parts.insert(0, 0.0)
    h, m, s = parts
    return days * 86400 + h * 3600 + m * 60 + s


def sacct(paths):
    """Add the sacct numbers of each run's job to its manifest."""
    fields =["JobID", "Partition", "AllocCPUS", "ReqMem", "MaxRSS", "Elapsed", "ElapsedRaw", "TotalCPU",
              "State", "ExitCode", "NodeList"]
    for path in paths:
        with open(path) as fp:
            manifest = json.load(fp)
        job_id = (manifest.get("slurm") or {}).get("job_id")
        if not job_id:
            print("skip %s: no job id" % path)
            continue
        out = run(["sacct", "-j", job_id, "--noheader", "--parsable2", "--units=K",
                   "--format=" + ",".join(fields)])
        if not out:
            print("skip %s: sacct gave nothing for job %s" % (path, job_id))
            continue
        rows = [dict(zip(fields, line.split("|"))) for line in out.splitlines()]
        main_row = next((r for r in rows if r["JobID"] == job_id), rows[0])
        steps = [r for r in rows if r["JobID"].startswith(job_id + ".")]
        rss = [parse_mem_gb(r["MaxRSS"]) for r in steps if parse_mem_gb(r["MaxRSS"])]
        elapsed = float(main_row["ElapsedRaw"] or 0)
        cpus = int(main_row["AllocCPUS"] or 1)
        total_cpu = parse_seconds(main_row["TotalCPU"])
        info = dict(
            partition=main_row["Partition"], alloc_cpus=cpus, req_mem_gb=parse_mem_gb(main_row["ReqMem"]),
            max_rss_gb=max(rss) if rss else None, elapsed=main_row["Elapsed"], elapsed_s=elapsed,
            hours=round(elapsed / 3600.0, 3), total_cpu_s=total_cpu,
            cpu_efficiency=round(total_cpu / (elapsed * cpus), 3) if total_cpu and elapsed else None,
            state=main_row["State"], exit_code=main_row["ExitCode"], nodelist=main_row["NodeList"],
            final=not main_row["State"].startswith(("RUNNING", "PENDING")),
            collected=datetime.datetime.now().isoformat(timespec="seconds"),
        )
        manifest["sacct"] = info
        with open(path, "w") as fp:
            json.dump(manifest, fp, indent=1)
        print("%s: %s, %.2f h, MaxRSS %s GB, CPU efficiency %s" % (
            manifest["run"], info["state"], info["hours"], info["max_rss_gb"], info["cpu_efficiency"]))


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd")
    w = sub.add_parser("write")
    w.add_argument("--run", required=True)
    w.add_argument("--experiment", required=True)
    w.add_argument("--quick", action="store_true")
    w.add_argument("--profiler", default="none")
    w.add_argument("--compare-to", default="")
    w.add_argument("--allow-missing", default="")
    w.add_argument("--check-exact", action="store_true", help="the output check requires equal values")
    w.add_argument("--config", required=True)
    w.add_argument("--command", default="")
    w.add_argument("--run-dir", required=True)
    w.add_argument("--results", required=True)
    w.add_argument("--outputs", required=True)
    w.add_argument("--repo", required=True)
    w.add_argument("--tools", required=True)
    w.add_argument("--start", type=float, required=True)
    w.add_argument("--end", type=float, required=True)
    w.add_argument("--status", type=int, required=True)
    w.add_argument("--expected-files", type=int, default=0)
    s = sub.add_parser("sacct")
    s.add_argument("manifests", nargs="+")
    args = parser.parse_args()
    if args.cmd == "write":
        write(args)
    elif args.cmd == "sacct":
        sacct(args.manifests)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
