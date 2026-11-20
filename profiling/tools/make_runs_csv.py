"""Rebuild runs.csv at the repo root, one row per agri-prof-* Slurm job.

Usage, from the repo root:
    python3 profiling/tools/make_runs_csv.py <sacct_all.csv>

The sacct file holds every job since Nov 1, written on a login node with
    sacct -u $USER -S 2026-11-01 -P --delimiter=, \
        --format=JobID,JobName,Partition,Account,AllocCPUS,ReqMem,Elapsed,CPUTime,TotalCPU,MaxRSS,State,ExitCode,Submit,Start,End,NodeList \
        > /project/cil/home_dirs/scadavidsanchez/projects/socioeconomics-update/checks/agriculture/profiling-full/sacct_all.csv

Each job is matched to its report in experiments/*/reports/<run>/ by the job id
in manifest.json. Peaks come from trace.json, the output check from check.json
and the collections from gc.csv. A cell is empty when its source is missing.
"""

import argparse
import csv
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PREFIX = "agri-prof-"
COLUMNS = ["run", "experiment", "job_id", "job_name", "state", "exit_code", "partition", "node", "cpu_model",
           "cores", "mem_requested_gb", "submit", "start", "end", "wall_h", "cpu_h", "peak_process_gib",
           "peak_cgroup_gib", "sacct_maxrss_gib", "impact_calculations_commit", "output_check", "gc_collections",
           "gc_minutes"]

# Jobs with no manifest in this repo: failed tries, check jobs, and quick runs
# whose results stayed on scratch. Named from their Slurm logs where one was
# kept, otherwise from the jobs submitted with them.
NO_MANIFEST = {
    "63311058": ("pyspy-quick", "2026-11-agri-memory"),  # py-spy cannot attach to a process on Midway
    "63311059": ("memray-quick", "2026-11-agri-memory"),
    "63311120": ("memray-quick", "2026-11-agri-memory"),
    "63311460": ("memray-quick", "2026-11-agri-memory"),
    "63322421": ("econfix_check", "2026-11-agri-memory"),
    "63324307": ("check", "2026-11-agri-memory"),
    "63433859": ("check", "2026-11-agri-memory-full"),
    "63433860": ("mcunit-quick", "2026-11-agri-memory-full"),
    "63433861": ("mcunit_econfix-quick", "2026-11-agri-memory-full"),
    "63480993": ("gccollect-quick", "2026-11-agri-memory-gc"),
}
GIB = {"": 1 / 1024 ** 3, "K": 1 / 1024 ** 2, "M": 1 / 1024, "G": 1.0, "T": 1024.0}


def seconds(text):
    """Seconds in a sacct duration: [D-]HH:MM:SS, MM:SS.mmm or SS.mmm."""
    if not text or text in ("Unknown", "INVALID"):
        return None
    days, _, clock = text.rpartition("-")
    parts = [float(p) for p in clock.split(":")]
    hours, minutes, secs = [0.0] * (3 - len(parts)) + parts
    return (int(days) if days else 0) * 86400 + hours * 3600 + minutes * 60 + secs


def gib(text, cores=1):
    """GiB in a sacct size such as 21150368K or 32Gn. A trailing c means per core."""
    found = re.fullmatch(r"([\d.]+)([KMGT]?)([nc]?)", text or "")
    if not found:
        return None
    return float(found.group(1)) * GIB[found.group(2)] * (cores if found.group(3) == "c" else 1)


def number(value, spec):
    return "" if value is None else spec % value


def when(text):
    return "" if text in (None, "", "Unknown", "None") else text


def trace_peaks(path):
    """Largest process and job cgroup memory in a trace, in GiB."""
    peaks = {"projection_rss": None, "cgroup_total": None}
    for event in json.loads(path.read_text())["traceEvents"]:
        if event.get("ph") == "C" and event.get("name") == "memory GB":
            for track, peak in peaks.items():
                value = event["args"].get(track)
                if value is not None and (peak is None or value > peak):
                    peaks[track] = value
    return peaks["projection_rss"], peaks["cgroup_total"]


def output_check(check, montecarlo):
    """pass, fail, or seed differs (expected) when only histclim differs in a montecarlo
    unit, whose year order depends on the draws it reused. As in the dashboard."""
    files = check.get("files")
    if files is None:  # the economic model check compares values, not files
        return check.get("status") or ""
    failing = [f["name"] for f in files if not f.get("ok")]
    if not failing:
        return "pass"
    return "seed differs (expected)" if montecarlo and all("histclim" in n for n in failing) else "fail"


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("sacct", type=Path, help="sacct export with the columns listed above")
    parser.add_argument("--out", type=Path, default=REPO / "runs.csv")
    args = parser.parse_args()

    with args.sacct.open(newline="") as f:
        rows = list(csv.DictReader(f))
    jobs = sorted((r for r in rows if r["JobName"].startswith(PREFIX)), key=lambda r: int(r["JobID"]))
    batch = {r["JobID"].split(".")[0]: r for r in rows if r["JobID"].endswith(".batch")}

    folders = {p.name: p for p in sorted(REPO.glob("experiments/*/reports/*")) if p.is_dir()}
    manifests = {}
    for folder in folders.values():
        if (folder / "manifest.json").exists():
            manifest = json.loads((folder / "manifest.json").read_text())
            manifests[str(manifest["slurm"]["job_id"])] = (folder, manifest)
    cpu_by_node = {m["node"]["hostname"].split(".")[0]: m["node"]["cpu_model"] for _, m in manifests.values()}

    table = []
    for job in jobs:
        job_id = job["JobID"]
        folder, manifest = manifests.get(job_id, (None, None))
        if manifest:
            run, experiment = manifest["run"], folder.parent.parent.name
        elif job_id in NO_MANIFEST:
            run, experiment = NO_MANIFEST[job_id]
            folder = folders.get(run)  # a folder without a manifest belongs to the job that wrote it
            if folder is not None and (folder / "manifest.json").exists():
                folder = None
        else:  # not copied here yet: the next rebuild after copying fills it in
            run, experiment = job["JobName"][len(PREFIX):], ""

        node = "" if job["NodeList"] in ("", "None assigned") else job["NodeList"]
        cores = int(job["AllocCPUS"] or 0)
        state = re.sub(r"^CANCELLED by \d+$", "CANCELLED", job["State"])
        started = when(job["Start"]) != ""
        finished = state not in ("RUNNING", "PENDING", "REQUEUED", "SUSPENDED")
        process = cgroup = check = None
        if folder is not None and (folder / "trace.json").exists():
            process, cgroup = trace_peaks(folder / "trace.json")
        if folder is not None and (folder / "check.json").exists():
            montecarlo = re.search(r"^mode:\s*montecarlo", ((manifest or {}).get("config") or {}).get("text", ""), re.M)
            check = output_check(json.loads((folder / "check.json").read_text()), bool(montecarlo))
        elif manifest:
            check = "none"
        collections = minutes = None
        if folder is not None and (folder / "gc.csv").exists():
            with (folder / "gc.csv").open(newline="") as f:
                passes = list(csv.DictReader(f))
            collections, minutes = len(passes), sum(float(p["seconds"]) for p in passes) / 60

        table.append({
            "run": run, "experiment": experiment, "job_id": job_id, "job_name": job["JobName"], "state": state,
            "exit_code": job["ExitCode"], "partition": job["Partition"], "node": node,
            "cpu_model": (manifest or {}).get("node", {}).get("cpu_model") or cpu_by_node.get(node, ""),
            "cores": cores or "", "mem_requested_gb": number(gib(job["ReqMem"], cores), "%g"),
            "submit": when(job["Submit"]), "start": when(job["Start"]), "end": when(job["End"]),
            "wall_h": number(seconds(job["Elapsed"]) / 3600 if started else None, "%.2f"),
            "cpu_h": number(seconds(job["TotalCPU"]) / 3600 if started and finished else None, "%.2f"),
            "peak_process_gib": number(process, "%.1f"), "peak_cgroup_gib": number(cgroup, "%.1f"),
            "sacct_maxrss_gib": number(gib(batch.get(job_id, {}).get("MaxRSS")), "%.1f"),
            "impact_calculations_commit": ((manifest or {}).get("impact_calculations") or {}).get("short_sha", ""),
            "output_check": check or "", "gc_collections": number(collections, "%d"),
            "gc_minutes": number(minutes, "%.1f"),
        })

    with args.out.open("w", newline="") as f:
        writer = csv.DictWriter(f, COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(table)
    print("wrote %s, %d jobs" % (args.out, len(table)))


if __name__ == "__main__":
    main()
