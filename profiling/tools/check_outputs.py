"""Compare the .nc4 outputs of one profiling run against a reference run.

Each file present in both runs is opened with xarray and every data variable
is checked with xarray.testing.assert_allclose, or with assert_equal (same
values, NaN where the reference has NaN) when --exact is given. Files are
matched by name, so single and montecarlo folder layouts both work (one unit
per run). Writes check.json and exits with 1 if anything differs.
"""

import argparse
import glob
import json
import os
import re
import sys

import numpy as np
import xarray as xr


def nc4_files(folder):
    """Map file name to path for the projection outputs under a folder.

    Parameters
    ----------
    folder : str

    Returns
    -------
    dict
    """
    found = {}
    for path in glob.glob(os.path.join(folder, "**", "*.nc4"), recursive=True):
        if path.endswith("-aggregated.nc4"):
            continue
        found[os.path.basename(path)] = path
    return found


def compare_var(cand, base, rtol, atol, exact=False):
    """Check one variable and measure how far apart the two runs are.

    Parameters
    ----------
    cand, base : xarray.DataArray
    rtol, atol : float
    exact : bool
        Require equal values instead of close ones.

    Returns
    -------
    dict
    """
    out = dict(ok=True)
    try:
        if exact:
            xr.testing.assert_equal(cand, base)
        else:
            xr.testing.assert_allclose(cand, base, rtol=rtol, atol=atol)
    except AssertionError as ex:
        out["ok"] = False
        out["message"] = str(ex).splitlines()[0][:300]
    if cand.dtype.kind not in "biuf" or base.dtype.kind not in "biuf":
        # Text such as region names: the assert above already compared them.
        return out
    a = np.asarray(cand.values, dtype=float)
    b = np.asarray(base.values, dtype=float)
    if a.shape != b.shape:
        out["ok"] = False
        out["shape"] = [list(a.shape), list(b.shape)]
        return out
    nan_a, nan_b = np.isnan(a), np.isnan(b)
    out["nan_mismatch"] = int(np.sum(nan_a != nan_b))
    both = ~nan_a & ~nan_b
    if both.any():
        diff = np.abs(a[both] - b[both])
        out["max_abs_diff"] = float(diff.max())
        denom = np.abs(b[both])
        rel = diff[denom > 0] / denom[denom > 0]
        out["max_rel_diff"] = float(rel.max()) if rel.size else 0.0
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--candidate", required=True, help="outputs folder of the run to check")
    parser.add_argument("--baseline", required=True, help="outputs folder of the reference run")
    parser.add_argument("--output", required=True, help="where to write check.json")
    parser.add_argument("--rtol", type=float, default=1e-5)
    parser.add_argument("--atol", type=float, default=1e-8)
    parser.add_argument("--allow-missing", default="",
                        help="regex of reference files the candidate may lack, e.g. global")
    parser.add_argument("--exact", action="store_true", help="require equal values (assert_equal)")
    args = parser.parse_args()

    result = dict(candidate=args.candidate, baseline=args.baseline, rtol=args.rtol, atol=args.atol,
                  exact=args.exact, status="skipped", files=[], missing_in_candidate=[],
                  extra_in_candidate=[])
    cand_files = nc4_files(args.candidate)
    base_files = nc4_files(args.baseline)
    if not base_files:
        result["reason"] = "no reference outputs yet"
    elif not cand_files:
        result["reason"] = "no outputs in this run"
        result["status"] = "fail"
    else:
        allow = re.compile(args.allow_missing) if args.allow_missing else None
        result["missing_in_candidate"] = sorted(set(base_files) - set(cand_files))
        result["extra_in_candidate"] = sorted(set(cand_files) - set(base_files))
        all_ok = all(allow and allow.search(n) for n in result["missing_in_candidate"])
        for name in sorted(set(cand_files) & set(base_files)):
            entry = dict(name=name, ok=True, vars={})
            with xr.open_dataset(cand_files[name], decode_times=False) as c, \
                    xr.open_dataset(base_files[name], decode_times=False) as b:
                for var in b.data_vars:
                    if var not in c.data_vars:
                        entry["vars"][var] = dict(ok=False, message="missing in candidate")
                    else:
                        entry["vars"][var] = compare_var(c[var].load(), b[var].load(), args.rtol, args.atol,
                                                         exact=args.exact)
                    entry["ok"] = entry["ok"] and entry["vars"][var]["ok"]
            all_ok = all_ok and entry["ok"]
            result["files"].append(entry)
            print("%s %s" % ("ok  " if entry["ok"] else "DIFF", name))
        result["status"] = "pass" if all_ok else "fail"

    with open(args.output, "w") as fp:
        json.dump(result, fp, indent=1)
    print("check: %s (%s)" % (result["status"], args.output))
    sys.exit(1 if result["status"] == "fail" else 0)


if __name__ == "__main__":
    main()
