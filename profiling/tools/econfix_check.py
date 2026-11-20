"""Check new_econmodel.py on the econmodel-memory branch against master, on the real panel.

Usage, with the shared env:
  python econfix_check.py dump --repo CLONE --data-dir PANEL --ssp SSP3 --iam high --out FILE.pkl
  python econfix_check.py compare --master A.pkl --branch B.pkl --output check.json

dump builds one NewSSPEconomicModel from CLONE (run it once per clone, each in
its own process) and records:
  - a digest per region of every value, with its type, returned by
    get_population_year, get_popop_year, baseline_prepared, get_age_shares and
    PrecomputedAgeShareBipartiteData, for every region plus a few missing
    ones, years 1975 to 2106 and some odd years (2020.0, '2020', None, ...);
  - memory: tracemalloc's count of what each item frees when it is deleted
    (pop_future_years, the age shares), how much reading the age shares adds,
    and the process RSS.
compare checks that the two dumps are identical and writes check.json with
the memory per item, for one model and for ten.
"""

import argparse
import gc
import hashlib
import json
import pickle
import sys
import time
import tracemalloc

import numpy as np

MB = 1e6
INT_YEARS = list(range(1975, 2107)) + [np.int64(2030), np.int32(2040)]
ODD_YEARS = [2020.0, np.float64(2050.0), 2020.5, "2020", None, float("nan")]
MISSING_REGIONS = ["ZZZ", "USA.99.999", "", "USA"]
AGE_GROUPS = ("age0-4", "age5-64", "age65+")


def feed(h, value):
    """Add a value and its type to a hash, exactly (arrays by their bytes)."""
    if isinstance(value, np.ndarray):
        h.update(("ndarray %s %s|" % (value.dtype, value.shape)).encode())
        h.update(np.ascontiguousarray(value).tobytes())
    elif isinstance(value, dict):
        h.update(b"dict{")
        for key in value:
            feed(h, key)
            feed(h, value[key])
        h.update(b"}")
    elif isinstance(value, (list, tuple)):
        h.update(b"[")
        for item in value:
            feed(h, item)
        h.update(b"]")
    else:
        h.update(("%s %r|" % (type(value).__name__, value)).encode())


def digest(values):
    h = hashlib.sha1()
    for value in values:
        feed(h, value)
    return h.hexdigest()


def process_mb():
    """RSS and peak RSS of this process, in MB."""
    out = {}
    try:
        with open("/proc/self/status") as fp:
            for line in fp:
                if line.startswith(("VmRSS:", "VmHWM:")):
                    out[line.split(":")[0]] = int(line.split()[1]) / 1e3
    except OSError:  # not Linux
        pass
    return dict(rss_mb=out.get("VmRSS"), peak_mb=out.get("VmHWM"),
                tracemalloc_overhead_mb=round(tracemalloc.get_tracemalloc_memory() / MB, 1))


def traced_mb():
    gc.collect()
    return tracemalloc.get_traced_memory()[0] / MB


def dump(args):
    sys.path.insert(0, args.repo)
    from adaptation.precomputed import new_econmodel as em

    out = dict(repo=args.repo, module=em.__file__, ssp=args.ssp, iam=args.iam, checks={}, memory={})
    regions_extra = MISSING_REGIONS
    tracemalloc.start()
    start = traced_mb()
    t0 = time.time()
    model = em.NewSSPEconomicModel(args.iam, args.ssp, args.data_dir)
    out["init_seconds"] = round(time.time() - t0, 1)
    out["memory"]["model_after_init_mb"] = round(traced_mb() - start, 1)
    out["memory"]["process_after_init"] = process_mb()

    regions = list(model.pop_future_years)
    queries = regions + regions_extra
    checks = out["checks"]
    checks["regions"] = digest(regions)
    checks["n_regions"] = len(regions)
    checks["iso_to_hierids"] = digest([model._iso_to_hierids])
    checks["population"] = {r: digest(model.get_population_year(r, y) for y in INT_YEARS + ODD_YEARS)
                            for r in queries}
    checks["popop"] = {r: digest(model.get_popop_year(r, y) for y in INT_YEARS + ODD_YEARS) for r in queries}
    for country in (False, True):
        prepared = model.baseline_prepared(2015, 13, lambda xs: np.array(xs, dtype=np.float64), country)
        checks["baseline_prepared country=%s" % country] = dict(
            order=digest(list(prepared)), values={r: digest([v]) for r, v in prepared.items()})
        del prepared

    # Reading the age shares builds them on the branch (on master they exist already).
    before = traced_mb()
    t0 = time.time()
    checks["has_age_shares"] = hasattr(model, "_age_shares")
    out["age_shares_seconds"] = round(time.time() - t0, 1)
    out["memory"]["reading_age_shares_adds_mb"] = round(traced_mb() - before, 1)
    out["memory"]["process_after_age_shares"] = process_mb()
    checks["age_shares"] = {r: digest(model.get_age_shares(r, y) for y in INT_YEARS) for r in queries}
    loader = em.PrecomputedAgeShareBipartiteData(model)
    checks["loader_regions"] = digest(loader.regions)
    for group in AGE_GROUPS:
        lazy = loader.load(1950, 2100, args.iam, args.ssp, group, shareonly=True)
        checks["loader " + group] = {r: digest([lazy.get_time(r)]) for r in queries}
        del lazy
    del loader

    # Memory of each item: what deleting it frees.
    before = traced_mb()
    del model.pop_future_years
    out["memory"]["pop_future_years_mb"] = round(before - traced_mb(), 1)
    before = traced_mb()
    if isinstance(type(model).__dict__.get("_age_shares"), property):
        model._age_shares = None
    else:
        del model._age_shares
    out["memory"]["age_shares_mb"] = round(before - traced_mb(), 1)
    tracemalloc.stop()

    with open(args.out, "wb") as fp:
        pickle.dump(out, fp)
    print(json.dumps(dict((k, v) for k, v in out.items() if k != "checks"), indent=1))


def compare(args):
    with open(args.master, "rb") as fp:
        a = pickle.load(fp)
    with open(args.branch, "rb") as fp:
        b = pickle.load(fp)
    result = dict(master=a["repo"], branch=b["repo"], ssp=a["ssp"], iam=a["iam"], checks={})
    ok = True
    for name in a["checks"]:
        x, y = a["checks"][name], b["checks"].get(name)
        if isinstance(x, dict) and "values" in x:
            bad = [r for r in x["values"] if x["values"][r] != (y or {}).get("values", {}).get(r)]
            same = not bad and x["order"] == (y or {}).get("order")
        elif isinstance(x, dict):
            bad = [r for r in x if x[r] != (y or {}).get(r)]
            same = not bad
        else:
            bad, same = [], x == y
        ok = ok and same
        result["checks"][name] = dict(identical=same, differing_regions=len(bad), first=bad[:10])
        print("%-36s %s" % (name, "identical" if same else "DIFFERENT (%d regions)" % len(bad)))
    result["status"] = "pass" if ok else "fail"

    ma, mb = a["memory"], b["memory"]
    items = [
        dict(item="pop_future_years", master_mb=ma["pop_future_years_mb"], branch_mb=mb["pop_future_years_mb"]),
        dict(item="_age_shares at start", master_mb=ma["age_shares_mb"], branch_mb=0.0,
             note="the branch builds them on first use: %.1f MB when read" % mb["reading_age_shares_adds_mb"]),
        dict(item="whole model after start", master_mb=ma["model_after_init_mb"], branch_mb=mb["model_after_init_mb"]),
    ]
    for item in items:
        item["saved_per_model_mb"] = round(item["master_mb"] - item["branch_mb"], 1)
        item["saved_ten_models_gb"] = round(10 * item["saved_per_model_mb"] / 1e3, 2)
    result["memory"] = items
    result["seconds"] = dict(master_init=a["init_seconds"], branch_init=b["init_seconds"],
                             branch_first_age_shares=b["age_shares_seconds"])
    result["process"] = dict(master=ma, branch=mb)
    print("\n%-26s %10s %10s %14s %16s" % ("item", "master MB", "branch MB", "saved / model", "saved, 10 models"))
    for item in items:
        print("%-26s %10.1f %10.1f %11.1f MB %13.2f GB" % (item["item"], item["master_mb"], item["branch_mb"],
                                                            item["saved_per_model_mb"], item["saved_ten_models_gb"]))
    print("model build: %.0f s on master, %.0f s on the branch; first age-share read on the branch: %.0f s"
          % (a["init_seconds"], b["init_seconds"], b["age_shares_seconds"]))
    with open(args.output, "w") as fp:
        json.dump(result, fp, indent=1)
    print("check: %s (%s)" % (result["status"], args.output))
    sys.exit(0 if ok else 1)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd")
    d = sub.add_parser("dump")
    d.add_argument("--repo", required=True)
    d.add_argument("--data-dir", required=True)
    d.add_argument("--ssp", default="SSP3")
    d.add_argument("--iam", default="high")
    d.add_argument("--out", required=True)
    c = sub.add_parser("compare")
    c.add_argument("--master", required=True)
    c.add_argument("--branch", required=True)
    c.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.cmd == "dump":
        dump(args)
    elif args.cmd == "compare":
        compare(args)
    else:
        parser.error("give dump or compare")


if __name__ == "__main__":
    main()
