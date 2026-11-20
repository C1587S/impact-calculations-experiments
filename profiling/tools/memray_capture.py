"""Run a module under memray, like `memray run -m`, without shadowing the shared env.

Usage:
  python memray_capture.py --output FILE [--aggregate] [--native]
      [--extra-path DIR] -m MODULE [ARGS...]

Pass the folder with memray and its dependencies (jinja2, rich, textual and
theirs) as --extra-path, not on PYTHONPATH. It is appended after
site-packages, so the env's own packages always win inside the projection.
"""

import os
import runpy
import sys


def parse(argv):
    """Split our options from the module and its arguments.

    Parameters
    ----------
    argv : list of str

    Returns
    -------
    dict
    """
    opts = dict(output=None, aggregate=False, native=False, extra_path=[], module=None, args=[])
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--output":
            opts["output"] = argv[i + 1]
            i += 2
        elif arg == "--aggregate":
            opts["aggregate"] = True
            i += 1
        elif arg == "--native":
            opts["native"] = True
            i += 1
        elif arg == "--extra-path":
            opts["extra_path"].append(argv[i + 1])
            i += 2
        elif arg == "-m":
            opts["module"] = argv[i + 1]
            opts["args"] = argv[i + 2:]
            break
        else:
            sys.exit("unknown option %s\n%s" % (arg, __doc__))
    if not opts["output"] or not opts["module"]:
        sys.exit(__doc__)
    return opts


def main():
    opts = parse(sys.argv[1:])
    sys.path.extend(opts["extra_path"])
    import memray

    kwargs = {}
    if opts["aggregate"]:
        kwargs["file_format"] = memray.FileFormat.AGGREGATED_ALLOCATIONS
    destination = memray.FileDestination(opts["output"], overwrite=True)
    with memray.Tracker(destination=destination, native_traces=opts["native"], **kwargs):
        # Same path order as python -m: the current folder (the repo) first,
        # not this tools folder.
        sys.path[0] = os.getcwd()
        sys.argv = [""] + opts["args"]
        runpy.run_module(opts["module"], run_name="__main__", alter_sys=True)


if __name__ == "__main__":
    main()
