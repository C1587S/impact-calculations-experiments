"""Run a module under pyinstrument, like `pyinstrument -m`, and write its reports.

Usage:
  python pyinstrument_capture.py --results DIR [--session FILE] [--interval SECONDS]
      [--extra-path DIR] -m MODULE [ARGS...]

pyinstrument runs inside the projection's own process, so it needs no ptrace
(Midway blocks ptrace, which is why py-spy cannot run there). Every
--interval seconds of wall time (default 0.1) it records the stack of the
thread that started it, so time spent reading files counts too. Threads the
module starts itself are not recorded.

When the module ends, fails or gets SIGTERM, this writes to --results:
  profile.speedscope.json  for https://www.speedscope.app
  profile.html             pyinstrument's call tree, opens in a browser
  profile.txt              the call tree and own time by function, as text
and then the whole session to --session, which
`python -m pyinstrument --load FILE -r html -o OUT` renders again with other options.

Pass the folder with pyinstrument as --extra-path, not on PYTHONPATH. It is
appended after site-packages, so the env's own packages always win inside
the projection.
"""

import os
import runpy
import signal
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
    opts = dict(results=None, session=None, interval="0.1", extra_path=[], module=None, args=[])
    valued = {"--results": "results", "--session": "session", "--interval": "interval"}
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in valued and i + 1 < len(argv):
            opts[valued[arg]] = argv[i + 1]
            i += 2
        elif arg == "--extra-path" and i + 1 < len(argv):
            opts["extra_path"].append(argv[i + 1])
            i += 2
        elif arg == "-m" and i + 1 < len(argv):
            opts["module"] = argv[i + 1]
            opts["args"] = argv[i + 2:]
            break
        else:
            sys.exit("unknown or incomplete option %s\n%s" % (arg, __doc__))
    if not opts["results"] or not opts["module"]:
        sys.exit(__doc__)
    try:
        opts["interval"] = float(opts["interval"])
    except ValueError:
        sys.exit("--interval must be a number of seconds, not %s" % opts["interval"])
    return opts


def make_profiler(interval):
    """A pyinstrument Profiler that keeps one copy of each frame name.

    pyinstrument 4.6 makes a new string for every frame of every sample, so
    a 13 h run at 10 samples a second would hold about 5 GB of copies. With
    one shared copy per name, each sample costs a list of references.
    """
    from pyinstrument import Profiler

    if not hasattr(Profiler, "_sampler_saw_call_stack"):
        return Profiler(interval=interval, async_mode="disabled")

    class SharedNamesProfiler(Profiler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._names = {}

        def _sampler_saw_call_stack(self, call_stack, *args):
            names = self._names
            shared = [names.setdefault(name, name) for name in call_stack]
            return super()._sampler_saw_call_stack(shared, *args)

    return SharedNamesProfiler(interval=interval, async_mode="disabled")


def write_reports(session, results, session_path):
    """Write the reports first (small), then the full session (large).

    Parameters
    ----------
    session : pyinstrument.session.Session
    results : str
    session_path : str or None
    """
    from pyinstrument.renderers import ConsoleRenderer, HTMLRenderer, SpeedscopeRenderer

    # Keep frames down to 0.1% of the run (pyinstrument's default drops those under 1%).
    detail = dict(filter_threshold=0.001)
    os.makedirs(results, exist_ok=True)
    reports = [
        ("profile.speedscope.json", lambda: SpeedscopeRenderer(processor_options=detail).render(session)),
        ("profile.html", lambda: HTMLRenderer(processor_options=detail).render(session)),
        ("profile.txt", lambda: ConsoleRenderer(unicode=False, color=False).render(session)
         + "\n\nOwn time by function\n\n"
         + ConsoleRenderer(unicode=False, color=False, flat=True).render(session)),
    ]
    for name, render in reports:
        path = os.path.join(results, name)
        try:
            text = render()
            with open(path, "w") as fp:
                fp.write(text)
            print("pyinstrument: wrote %s" % path)
        except Exception as exc:  # one failed report should not stop the others
            print("pyinstrument: could not write %s: %r" % (path, exc), file=sys.stderr)
    if session_path:
        try:
            session.save(session_path)
            print("pyinstrument: wrote %s" % session_path)
        except Exception as exc:
            print("pyinstrument: could not write %s: %r" % (session_path, exc), file=sys.stderr)
    sys.stdout.flush()


def stop_on_sigterm(signum, frame):
    """Turn SIGTERM (scancel, time limit) into SystemExit, so the reports still get written."""
    raise SystemExit(128 + signum)


def main():
    opts = parse(sys.argv[1:])
    sys.path.extend(opts["extra_path"])
    profiler = make_profiler(opts["interval"])
    # Same path order as python -m: the current folder (the repo) first, not this tools folder.
    sys.path[0] = os.getcwd()
    sys.argv = [""] + opts["args"]
    signal.signal(signal.SIGTERM, stop_on_sigterm)
    status = 0
    profiler.start()
    try:
        runpy.run_module(opts["module"], run_name="__main__", alter_sys=True)
    except SystemExit as exc:
        status = exc.code
    finally:
        session = profiler.stop()
        print("pyinstrument: %d samples over %.2f h" % (session.sample_count, session.duration / 3600.0))
        write_reports(session, opts["results"], opts["session"])
    sys.exit(status)


if __name__ == "__main__":
    main()
