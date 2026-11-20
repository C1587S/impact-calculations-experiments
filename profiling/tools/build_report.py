"""Build report/index.html from the manifests in results/.

Static HTML with inline SVG charts, no external files, so it opens straight
from the cluster mount. Standard library only (runs with the env's Python 3.7).

SU model (RCC caslake): SUs = hours x max(cores requested, GB requested / 3.75).
Hours are measured on the cil partition, so every projection scales the
reference hours of each crop by the ratio of the run to the baseline run, and
shifts the reference memory request by the change in measured peak memory.
"""

import argparse
import datetime
import html
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

GB_PER_CORE = 3.75
UNITS_PER_CROP = 5850
REFERENCE_TOTAL = 1.33e6
# Hours per unit and GB requested per task, from the singles with global.
CROPS = [
    ("wheat_winter", 11.3, 25), ("wheat_spring", 6.0, 25), ("soy", 4.3, 25), ("corn", 4.1, 17),
    ("rice", 3.9, 17), ("sorghum", 3.2, 22), ("cassava", 3.0, 17),
]
ORDER = ["baseline", "cores2", "cores4", "cores6", "noglobal", "oneecon", "mcunit", "mcunit_oneecon",
         "mcunit_econfix", "econfix","pyinstrument", "memray", "mortality", "mortality_econfix"]

# Time groups for the pyinstrument profile: label, test on a frame (file,
# name, line) and its caller p (same tuple, or None). pyinstrument gives each
# function its first line and C functions the file "<built-in>".
BUCKETS = [
    ("reading weather files (xarray, netCDF4)",
     lambda f, n, l, p: "xarray/backends" in f or "netCDF4" in f),
    ("weather by month and merging (climate/, fast_dataset)",
     lambda f, n, l, p: "/climate/" in f or "fast_dataset.py" in f),
    ("covariates (adaptation/covariates.py)", lambda f, n, l, p: f.endswith("adaptation/covariates.py")),
    ("curves and coefficients (curvegen, smart_curve)",
     lambda f, n, l, p: "curvegen" in f or "smart_curve" in f),
    ("sums in openest irregular.py: the unused diagnostics (lines 51-56) and the result (line 49)",
     lambda f, n, l, p: (n == "record" and f.endswith("openest/generate/diagnostic.py"))
     or (n == "nansum" and p is not None and p[0].endswith("openest/generate/irregular.py"))),
    ("economic models from the CSVs (adaptation/precomputed)", lambda f, n, l, p: "adaptation/precomputed" in f),
    ("writing the netCDF outputs (write_ncdf)", lambda f, n, l, p: n == "write_ncdf"),
]
# pyinstrument's own frames that are not functions, like [self] for own time.
SYNTHETIC = ("[self]", "[await]", "[out-of-context]", "[root]")

CSS = """
:root {
  color-scheme: light;
  --page: #f9f9f7; --surface: #fcfcfb; --ink: #0b0b0b; --ink-2: #52514e; --muted: #898781;
  --grid: #e1e0d9; --axis: #c3c2b7; --ring: rgba(11,11,11,0.10);
  --series-1: #2a78d6; --reference: #898781; --good: #006300; --bad: #d03b3b;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --page: #0d0d0d; --surface: #1a1a19; --ink: #f0efec; --ink-2: #c3c2b7; --muted: #898781;
    --grid: #2c2c2a; --axis: #383835; --ring: rgba(255,255,255,0.10);
    --series-1: #3987e5; --reference: #898781; --good: #0ca30c; --bad: #e66767;
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --page: #0d0d0d; --surface: #1a1a19; --ink: #f0efec; --ink-2: #c3c2b7; --muted: #898781;
  --grid: #2c2c2a; --axis: #383835; --ring: rgba(255,255,255,0.10);
  --series-1: #3987e5; --reference: #898781; --good: #0ca30c; --bad: #e66767;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--page); color: var(--ink);
  font: 14px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }
main { max-width: 1180px; margin: 0 auto; padding: 24px 16px 64px; }
h1 { font-size: 24px; margin: 0 0 4px; }
h2 { font-size: 17px; margin: 32px 0 8px; }
p, li { color: var(--ink-2); max-width: 80ch; }
.card { background: var(--surface); border: 1px solid var(--ring); border-radius: 8px; padding: 16px; }
.tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 12px; margin-top: 16px; }
.tile .label { color: var(--ink-2); font-size: 13px; }
.tile .value { font-size: 28px; font-weight: 600; margin: 2px 0; }
.tile .note { color: var(--muted); font-size: 12px; }
.scroll { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; font-size: 13px; }
th, td { text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--grid); vertical-align: top; }
th { color: var(--ink-2); font-weight: 600; white-space: nowrap; }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
.ok { color: var(--good); font-weight: 600; }
.bad { color: var(--bad); font-weight: 600; }
.muted { color: var(--muted); }
.charts { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 12px; }
.chart-title { font-weight: 600; margin-bottom: 4px; }
svg { display: block; width: 100%; height: auto; }
svg text { fill: var(--muted); font-size: 11px; }
svg text.value { fill: var(--ink); font-size: 12px; }
svg .hit { fill: transparent; cursor: default; }
svg .hit:hover + .mark, svg .hit:focus + .mark { opacity: 0.8; }
pre { background: var(--surface); border: 1px solid var(--ring); border-radius: 8px; padding: 12px;
  overflow-x: auto; font-size: 12px; color: var(--ink); }
a { color: var(--series-1); }
#tip { position: fixed; pointer-events: none; background: var(--surface); color: var(--ink);
  border: 1px solid var(--ring); border-radius: 6px; padding: 6px 8px; font-size: 12px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.15); display: none; max-width: 280px; }
#tip strong { display: block; font-size: 14px; }
"""

JS = """
(function () {
  var tip = document.getElementById('tip');
  function show(ev) {
    var t = ev.target;
    if (!t.getAttribute || !t.getAttribute('data-value')) { return; }
    tip.textContent = '';
    var v = document.createElement('strong');
    v.textContent = t.getAttribute('data-value');
    var l = document.createElement('span');
    l.textContent = t.getAttribute('data-label');
    tip.appendChild(v); tip.appendChild(l);
    tip.style.display = 'block';
    var r = t.getBoundingClientRect();
    var x = ev.clientX || (r.left + r.width / 2), y = ev.clientY || r.top;
    tip.style.left = Math.min(x + 12, window.innerWidth - 290) + 'px';
    tip.style.top = (y + 12) + 'px';
  }
  function hide() { tip.style.display = 'none'; }
  document.querySelectorAll('[data-value]').forEach(function (el) {
    el.addEventListener('pointermove', show);
    el.addEventListener('focus', show);
    el.addEventListener('pointerleave', hide);
    el.addEventListener('blur', hide);
  });
})();
"""


def esc(value):
    return html.escape("" if value is None else str(value))


def fmt(value, digits=1, suffix=""):
    """Format a number with thousands separators, or a muted n/a."""
    if value is None:
        return '<span class="muted">n/a</span>'
    if isinstance(value, float) and math.isnan(value):
        return '<span class="muted">n/a</span>'
    return "{:,.{d}f}{s}".format(value, d=digits, s=suffix)


def load_runs(results):
    """Read every results/<run>/ folder that has a manifest.

    Parameters
    ----------
    results : str

    Returns
    -------
    list of dict
    """
    runs = []
    for name in sorted(os.listdir(results)) if os.path.isdir(results) else []:
        folder = os.path.join(results, name)
        path = os.path.join(folder, "manifest.json")
        if not os.path.isfile(path):
            continue
        with open(path) as fp:
            m = json.load(fp)
        check_path = os.path.join(folder, "check.json")
        m["check"] = None
        if os.path.isfile(check_path):
            with open(check_path) as fp:
                m["check"] = json.load(fp)
        m["folder"] = name
        m["files_here"] = sorted(os.listdir(folder))
        runs.append(m)
    runs.sort(key=lambda m: (m.get("quick", False), ORDER.index(m["experiment"]) if m["experiment"] in ORDER else 99))
    return runs


def measures(m, headroom):
    """Hours, peak memory, suggested request and SUs per unit of one run.

    Parameters
    ----------
    m : dict
        Manifest.
    headroom : float
        Factor over the peak for the suggested --mem.

    Returns
    -------
    dict
    """
    sacct = m.get("sacct") or {}
    tele = m.get("telemetry") or {}
    hours = sacct.get("hours") if sacct.get("final") else None
    if hours is None:
        hours = (m.get("wall_seconds") or 0) / 3600.0 or None
    peaks = [v for v in (sacct.get("max_rss_gb"), tele.get("peak_tree_rss_gb"), tele.get("peak_rss_gb")) if v]
    peak = max(peaks) if peaks else None
    cores = m.get("cores") or 1
    request = float(math.ceil(peak * headroom)) if peak else None
    billed = max(cores, request / GB_PER_CORE) if request else None
    su = hours * billed if hours and billed else None
    check = m.get("check") or {}
    usable = not m.get("failed") and check.get("status") != "fail"
    return dict(hours=hours, peak=peak, cores=cores, request=request, billed=billed, su=su,
                cpu_eff=sacct.get("cpu_efficiency"), usable=usable, final=bool(sacct.get("final")))


def profiled(m):
    """True for runs under a profiler, which are slower by design."""
    return (m.get("profiler") or "none") != "none"


def agriculture(m):
    """False for the mortality runs, which only check the econmodel-memory branch."""
    return not m["experiment"].startswith("mortality")


def scenarios(runs, headroom):
    """Projection inputs for each usable run, relative to its baseline.

    Parameters
    ----------
    runs : list of dict
    headroom : float

    Returns
    -------
    list of dict
    """
    by_name = {m["folder"]: m for m in runs}
    out = []
    for m in runs:
        if profiled(m) or not agriculture(m):
            continue
        base = by_name.get("baseline" + ("-quick" if m.get("quick") else ""))
        if base is None:
            continue
        x, b = measures(m, headroom), measures(base, headroom)
        if not (x["usable"] and b["hours"] and x["hours"] and b["request"] and x["request"]):
            continue
        out.append(dict(name=m["folder"], ratio=x["hours"] / b["hours"], delta_req=x["request"] - b["request"],
                        cores=x["cores"], estimate=False, quick=m.get("quick", False)))
    # Combined estimate, not a run: the montecarlo unit with one economic model,
    # sped up as much as the two-thread split sped up the single.
    names = {s["name"]: s for s in out}
    for suffix in ("", "-quick"):
        mc, c2 = names.get("mcunit_oneecon" + suffix), names.get("cores2" + suffix)
        if mc and c2:
            out.append(dict(name="mcunit_oneecon + cores2 (estimate)" + suffix, ratio=mc["ratio"] * c2["ratio"],
                            delta_req=mc["delta_req"] + max(0.0, c2["delta_req"]), cores=2, estimate=True,
                            quick=bool(suffix)))
    return out


def project(scenario):
    """SUs for 5,850 units of every crop under one scenario.

    Parameters
    ----------
    scenario : dict or None
        None gives the reference (the singles as they ran).

    Returns
    -------
    dict
    """
    ratio = scenario["ratio"] if scenario else 1.0
    delta = scenario["delta_req"] if scenario else 0.0
    cores = scenario["cores"] if scenario else 1
    rows = []
    for crop, hours, req in CROPS:
        new_req = max(req + delta, 2.0)
        new_hours = hours * ratio
        billed = max(cores, new_req / GB_PER_CORE)
        rows.append(dict(crop=crop, hours=new_hours, request=new_req, billed=billed,
                         su=UNITS_PER_CROP * new_hours * billed))
    return dict(rows=rows, total=sum(r["su"] for r in rows))


def evented_pieces(data):
    """Stacks and seconds from the evented speedscope profiles pyinstrument writes.

    Between two events the time belongs to the frames open at that moment,
    root first.

    Parameters
    ----------
    data : dict
        A speedscope file.

    Returns
    -------
    list of (list of int, float)
    """
    pieces = []
    for prof in data.get("profiles", []):
        if prof.get("type") != "evented":
            continue
        stack, last = [], prof.get("startValue", 0)
        for ev in prof.get("events", []):
            at = ev.get("at", last)
            if stack and at > last:
                pieces.append((list(stack), at - last))
            last = at
            if ev.get("type") == "O":
                stack.append(ev.get("frame"))
            elif stack:
                stack.pop()
    return pieces


def profile_summary(path, top=25):
    """Share of wall time per group and per function from pyinstrument's speedscope file.

    Parameters
    ----------
    path : str
    top : int

    Returns
    -------
    dict or None
    """
    try:
        with open(path) as fp:
            data = json.load(fp)
    except (OSError, ValueError):
        return None
    frames = data.get("shared", {}).get("frames", [])

    def info(i):
        """(file, name, line) of frame i, the tuple the BUCKETS tests take."""
        f = frames[i] if isinstance(i, int) and 0 <= i < len(frames) else {}
        return f.get("file") or "", f.get("name") or "?", f.get("line")

    def key(frame):
        file, name, _ = frame
        return "%s (%s)" % (name, os.path.basename(file) if file else "?")

    pieces = evented_pieces(data)
    total = float(sum(w for _, w in pieces))
    if not pieces or total <= 0:
        return None
    selfw, totw, buckets = {}, {}, {label: 0.0 for label, _ in BUCKETS}
    for s, w in pieces:
        stack = [info(i) for i in s]
        stack = [fr for fr in stack if fr[1] not in SYNTHETIC]
        if not stack:
            continue
        seen, hit = set(), set()
        for depth, frame in enumerate(stack):
            k = key(frame)
            if k not in seen:
                totw[k] = totw.get(k, 0.0) + w
                seen.add(k)
            parent = stack[depth - 1] if depth else None
            for label, test in BUCKETS:
                if label not in hit and test(frame[0], frame[1], frame[2], parent):
                    hit.add(label)
        for label in hit:
            buckets[label] += w
        k = key(stack[-1])
        selfw[k] = selfw.get(k, 0.0) + w
    top_self = sorted(selfw.items(), key=lambda kv: -kv[1])[:top]
    top_total = sorted(totw.items(), key=lambda kv: -kv[1])[:top]
    return dict(seconds=total, buckets=[(k, v / total) for k, v in buckets.items()],
                top_self=[(k, v / total) for k, v in top_self], top_total=[(k, v / total) for k, v in top_total])


def dot_line_chart(points, title, unit, digits):
    """SVG of one series over cores, dots joined by a line, from zero.

    Parameters
    ----------
    points : list of (cores, value, label)
    title : str
    unit : str
    digits : int

    Returns
    -------
    str
    """
    if not points:
        return '<p class="muted">No runs yet.</p>'
    w, h, left, right, top, bottom = 440, 240, 44, 20, 16, 36
    xs = [1, 2, 4, 6]
    ymax = max(v for _, v, _ in points) * 1.15 or 1
    step = nice_step(ymax / 4)
    ymax = step * math.ceil(ymax / step)

    def X(c):
        return left + (c - 1) / 5.0 * (w - left - right)

    def Y(v):
        return h - bottom - v / ymax * (h - top - bottom)

    parts = ['<svg viewBox="0 0 %d %d" role="img" aria-label="%s">' % (w, h, esc(title))]
    y = 0.0
    while y <= ymax + 1e-9:
        parts.append('<line x1="%d" x2="%d" y1="%.1f" y2="%.1f" stroke="var(--grid)" stroke-width="1"/>'
                     % (left, w - right, Y(y), Y(y)))
        parts.append('<text x="%d" y="%.1f" text-anchor="end" dominant-baseline="middle">%s</text>'
                     % (left - 6, Y(y), fmt_tick(y)))
        y += step
    for c in xs:
        parts.append('<text x="%.1f" y="%d" text-anchor="middle">%d</text>' % (X(c), h - bottom + 16, c))
    parts.append('<text x="%.1f" y="%d" text-anchor="middle">cores</text>' % ((left + w - right) / 2.0, h - 4))
    pts = sorted(points)
    if len(pts) > 1:
        path = " ".join("%s%.1f,%.1f" % ("M" if i == 0 else "L", X(c), Y(v)) for i, (c, v, _) in enumerate(pts))
        parts.append('<path d="%s" fill="none" stroke="var(--series-1)" stroke-width="2" '
                     'stroke-linejoin="round" stroke-linecap="round"/>' % path)
    for i, (c, v, label) in enumerate(pts):
        value = "{:,.{d}f} {u}".format(v, d=digits, u=unit)
        parts.append('<circle class="hit" cx="%.1f" cy="%.1f" r="14" tabindex="0" data-value="%s" data-label="%s"/>'
                     % (X(c), Y(v), esc(value), esc(label)))
        parts.append('<circle class="mark" cx="%.1f" cy="%.1f" r="5" fill="var(--series-1)" '
                     'stroke="var(--surface)" stroke-width="2" pointer-events="none"/>' % (X(c), Y(v)))
        if i in (0, len(pts) - 1):
            parts.append('<text class="value" x="%.1f" y="%.1f" text-anchor="middle">%s</text>'
                         % (X(c), Y(v) - 12, esc("{:,.{d}f}".format(v, d=digits))))
    parts.append("</svg>")
    return "".join(parts)


def bar_chart(rows, unit, reference=None):
    """SVG of ranked horizontal bars, one hue, value at the tip.

    Parameters
    ----------
    rows : list of (label, value)
    unit : str
    reference : float or None
        Drawn as a muted line labeled baseline.

    Returns
    -------
    str
    """
    if not rows:
        return '<p class="muted">No runs yet.</p>'
    rows = sorted(rows, key=lambda r: r[1])
    band, bar, left, right, top = 34, 20, 210, 70, 8
    w = 720
    h = top + band * len(rows) + 28
    vmax = max([v for _, v in rows] + [reference or 0]) * 1.05
    step = nice_step(vmax / 4)
    vmax = step * math.ceil(vmax / step)

    def X(v):
        return left + v / vmax * (w - left - right)

    parts = ['<svg viewBox="0 0 %d %d" role="img" aria-label="SUs per unit by run">' % (w, h)]
    v = 0.0
    while v <= vmax + 1e-9:
        parts.append('<line x1="%.1f" x2="%.1f" y1="%d" y2="%d" stroke="var(--grid)" stroke-width="1"/>'
                     % (X(v), X(v), top, h - 24))
        parts.append('<text x="%.1f" y="%d" text-anchor="middle">%s</text>' % (X(v), h - 8, fmt_tick(v)))
        v += step
    for i, (label, value) in enumerate(rows):
        y = top + i * band + (band - bar) / 2.0
        x1 = X(value)
        r = min(4.0, (x1 - left) / 2.0)
        path = ("M%.1f,%.1f H%.1f a%.1f,%.1f 0 0 1 %.1f,%.1f V%.1f a%.1f,%.1f 0 0 1 %.1f,%.1f H%.1f Z"
                % (left, y, x1 - r, r, r, r, r, y + bar - r, r, r, -r, r, left))
        parts.append('<text x="%d" y="%.1f" text-anchor="end" dominant-baseline="middle" class="value">%s</text>'
                     % (left - 8, y + bar / 2.0, esc(label)))
        parts.append('<rect class="hit" x="%d" y="%.1f" width="%.1f" height="%d" tabindex="0" '
                     'data-value="%s" data-label="%s"/>'
                     % (left, top + i * band, max(x1 - left, 4) + 60, band, esc("{:,.1f} {}".format(value, unit)),
                        esc(label)))
        parts.append('<path class="mark" d="%s" fill="var(--series-1)" pointer-events="none"/>' % path)
        parts.append('<text class="value" x="%.1f" y="%.1f" dominant-baseline="middle">%s</text>'
                     % (x1 + 6, y + bar / 2.0, esc("{:,.1f}".format(value))))
    if reference:
        parts.append('<line x1="%.1f" x2="%.1f" y1="%d" y2="%d" stroke="var(--reference)" stroke-width="2"/>'
                     % (X(reference), X(reference), top, h - 24))
        parts.append('<text x="%.1f" y="%d" text-anchor="start">baseline</text>' % (X(reference) + 4, top + 8))
    parts.append("</svg>")
    return "".join(parts)


def nice_step(raw):
    """Round a raw axis step up to 1, 2, 2.5 or 5 times a power of ten."""
    if raw <= 0:
        return 1.0
    mag = 10 ** math.floor(math.log10(raw))
    for m in (1, 2, 2.5, 5, 10):
        if raw <= m * mag:
            return m * mag
    return 10 * mag


def fmt_tick(v):
    if v >= 10000:
        return "{:,.0f}K".format(v / 1000.0)
    if v == int(v):
        return "{:,.0f}".format(v)
    return "{:,.1f}".format(v)


def link(folder, name, label):
    return '<a href="../results/%s/%s">%s</a>' % (esc(folder), esc(name), esc(label))


def build(runs, headroom):
    """Return the whole report page as one HTML string."""
    now =datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    full = [m for m in runs if not m.get("quick")]
    meas = {m["folder"]: measures(m, headroom) for m in runs}
    scen = scenarios(runs, headroom)
    ref = project(None)
    out = []
    out.append("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
               "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
               "<title>Agriculture profiling</title><style>%s</style></head><body><main>" % CSS)
    out.append("<h1>Agriculture profiling: winter wheat</h1>")
    out.append("<p>Built %s from %d runs in results/. Hours were measured on the cil partition; the projections "
               "scale each crop's reference hours by the ratio of the run to the baseline, shift its memory request "
               "by the change in measured peak, and bill SUs = hours &times; max(cores, GB / 3.75). Suggested memory "
               "requests are the peak &times; %.2f, rounded up.</p>" % (now, len(runs), headroom))

    # Tiles
    base = meas.get("baseline")
    usable = [s for s in scen if not s["quick"] and not s["estimate"]]
    best = None
    for s in usable:
        p = project(s)
        if best is None or p["total"] < best[1]["total"]:
            best = (s, p)
    checks = [m["check"] for m in runs if m.get("check")]
    passed = sum(1 for c in checks if c.get("status") == "pass")
    out.append('<section class="tiles">')
    out.append(tile("Baseline hours, winter wheat single", fmt(base["hours"], 2) if base else fmt(None),
                    "on the cil partition, one core"))
    out.append(tile("Baseline peak memory", fmt(base["peak"], 1, " GB") if base else fmt(None),
                    "largest of sacct MaxRSS and the sampler"))
    out.append(tile("Lowest projected total", fmt(best[1]["total"], 0) if best else fmt(None),
                    ("%s, %+.0f%% vs 1.33M" % (best[0]["name"], 100 * (best[1]["total"] / REFERENCE_TOTAL - 1)))
                    if best else "needs a finished baseline and one more run"))
    out.append(tile("Output checks passed", "%d of %d" % (passed, len(checks)), "xarray.testing.assert_allclose"))
    out.append("</section>")

    # Experiments table
    out.append("<h2>Runs</h2><div class=\"card scroll\"><table><thead><tr>"
               "<th>run</th><th>state</th><th>output check</th><th class=num>cores</th><th class=num>hours</th>"
               "<th class=num>vs baseline</th><th class=num>peak GB</th><th class=num>suggested --mem</th>"
               "<th class=num>billed cores</th><th class=num>SUs per unit</th><th class=num>CPU efficiency</th>"
               "<th>node</th><th>files</th></tr></thead><tbody>")
    for m in runs:
        x = meas[m["folder"]]
        b = meas.get("baseline" + ("-quick" if m.get("quick") else ""))
        ratio = (x["hours"] / b["hours"] if b and b["hours"] and x["hours"] and not m.get("failed")
                 and agriculture(m) else None)
        state = '<span class="bad">failed</span>' if m.get("failed") else '<span class="ok">ok</span>'
        if not x["final"]:
            state += ' <span class="muted">(sacct not final)</span>'
        check = m.get("check")
        if check is None:
            ctext = '<span class="muted">none</span>'
        else:
            cls = {"pass": "ok", "fail": "bad"}.get(check.get("status"), "muted")
            ctext = '<span class="%s">%s</span>' % (cls, esc(check.get("status")))
            if check.get("missing_in_candidate"):
                ctext += ' <span class="muted">(%d files not made)</span>' % len(check["missing_in_candidate"])
        files = []
        for fname, label in (("trace.json", "Perfetto trace"), ("profile.html", "pyinstrument"),
                             ("profile.speedscope.json", "speedscope"), ("profile.txt", "profile text"),
                             ("memray-flamegraph.html", "flame graph"), ("memray-table.html", "memray table"),
                             ("memray-leaks.html", "leaks"), ("memray-summary.txt", "memray summary"),
                             ("memray-stats.txt", "memray stats"),
                             ("check.json", "check"), ("error.txt", "error"), ("manifest.json", "manifest")):
            if fname in m["files_here"]:
                files.append(link(m["folder"], fname, label))
        node = m.get("node") or {}
        out.append("<tr%s><td>%s</td><td>%s</td><td>%s</td><td class=num>%d</td><td class=num>%s</td>"
                   "<td class=num>%s</td><td class=num>%s</td><td class=num>%s</td><td class=num>%s</td>"
                   "<td class=num>%s</td><td class=num>%s</td><td title=\"%s\">%s</td><td>%s</td></tr>"
                   % (' class="muted"' if m.get("failed") else "", esc(m["folder"]), state, ctext, x["cores"],
                      fmt(x["hours"], 2), fmt(ratio, 2, "&times;") if ratio else fmt(None), fmt(x["peak"], 1),
                      fmt(x["request"], 0), fmt(x["billed"], 2), fmt(x["su"], 1),
                      fmt(100 * x["cpu_eff"], 0, "%") if x["cpu_eff"] else fmt(None),
                      esc(node.get("cpu_model")), esc(node.get("hostname")), ", ".join(files)))
    out.append("</tbody></table></div>")
    out.append("<p>SUs per unit here use the measured cil hours. Peak GB is the largest of sacct MaxRSS and the "
               "sampler (all processes of the job). A failed run or a failed output check is left out of every "
               "chart and projection below, and so are the pyinstrument and memray runs, which the profilers "
               "slow down. Hover a node name for its CPU model; compare timings only between "
               "runs on the same CPU model.</p>")

    # Scaling charts
    pts_h, pts_su = [], []
    for name, cores in (("baseline", 1), ("cores2", 2), ("cores4", 4), ("cores6", 6)):
        x = meas.get(name)
        if x and x["usable"] and x["hours"]:
            pts_h.append((cores, x["hours"], name))
            if x["su"]:
                pts_su.append((cores, x["su"], name))
    out.append("<h2>Scaling with cores</h2><div class=\"charts\">")
    out.append('<div class="card"><div class="chart-title">Hours per unit, by cores</div>%s</div>'
               % dot_line_chart(pts_h, "Hours per unit by cores", "h", 2))
    out.append('<div class="card"><div class="chart-title">SUs per unit, by cores</div>%s</div>'
               % dot_line_chart(pts_su, "SUs per unit by cores", "SUs", 1))
    out.append("</div><p>cores2, cores4 and cores6 all use threads: 2, the most single mode allows; the extra "
               "cores only add library threads. Up to GB / 3.75 cores cost nothing extra, so any speedup there "
               "is a direct saving.</p>")

    # Bars
    bars = [(m["folder"], meas[m["folder"]]["su"]) for m in full if meas[m["folder"]]["usable"]
            and meas[m["folder"]]["su"] and not profiled(m) and agriculture(m)]
    out.append("<h2>SUs per unit by run</h2><div class=\"card\">%s</div>"
               % bar_chart(bars, "SUs per unit", base["su"] if base and base["su"] else None))

    # Projections
    out.append("<h2>Projected SUs, %s units per crop</h2>" % "{:,}".format(UNITS_PER_CROP))
    out.append("<p>The reference row uses the numbers given for the singles with global (hours per unit and "
               "GB requested per crop). Its formula total is %s; the planning figure is 1.33M. Each other row "
               "applies one run's time ratio and memory change to every crop, which assumes the other crops "
               "change like winter wheat.</p>" % fmt(ref["total"], 0))
    out.append("<div class=\"card scroll\"><table><thead><tr><th>scenario</th><th class=num>time ratio</th>"
               "<th class=num>&Delta; --mem GB</th><th class=num>cores</th><th class=num>winter wheat SUs</th>"
               "<th class=num>all crops SUs</th><th class=num>vs 1.33M</th></tr></thead><tbody>")
    rows = [(dict(name="reference (singles as they ran)", ratio=1.0, delta_req=0.0, cores=1), ref)]
    rows += [(s, project(s)) for s in scen if not s["quick"]]
    for s, p in rows:
        ww = p["rows"][0]["su"]
        change = 100 * (p["total"] / REFERENCE_TOTAL - 1)
        out.append("<tr><td>%s</td><td class=num>%s</td><td class=num>%+.0f</td><td class=num>%d</td>"
                   "<td class=num>%s</td><td class=num>%s</td><td class=num>%+.0f%%</td></tr>"
                   % (esc(s["name"]), fmt(s["ratio"], 2, "&times;"), s["delta_req"], s["cores"], fmt(ww, 0),
                      fmt(p["total"], 0), change))
    out.append("</tbody></table></div>")
    if best:
        out.append("<p>Per crop, for %s:</p>" % esc(best[0]["name"]))
        out.append("<div class=\"card scroll\"><table><thead><tr><th>crop</th><th class=num>hours per unit</th>"
                   "<th class=num>--mem GB</th><th class=num>billed cores</th><th class=num>SUs</th>"
                   "<th class=num>reference SUs</th></tr></thead><tbody>")
        for r, r0 in zip(best[1]["rows"], ref["rows"]):
            out.append("<tr><td>%s</td><td class=num>%s</td><td class=num>%s</td><td class=num>%s</td>"
                       "<td class=num>%s</td><td class=num>%s</td></tr>"
                       % (esc(r["crop"]), fmt(r["hours"], 2), fmt(r["request"], 0), fmt(r["billed"], 2),
                          fmt(r["su"], 0), fmt(r0["su"], 0)))
        out.append("</tbody></table></div>")

    # Stages
    variant_order = ["fulladapt", "noadapt", "incadapt", "global", "histclim", "noadapt-histclim",
                     "incadapt-histclim", "global-histclim"]
    out.append("<h2>Where the time goes</h2><p>Minutes per stage, from the log lines the sampler timed "
               "(1 s resolution). The first two columns are startup: building the economic models from the "
               "CSVs, then weather discovery and claiming the folder. Each variant column is the whole "
               "variant; hover it for the split between its covariates (baseline climate and income) and its "
               "year loop, which includes writing the file.</p>")
    out.append("<div class=\"card scroll\"><table><thead><tr><th>run</th><th class=num>economic models</th>"
               "<th class=num>weather</th>%s<th class=num>all covariates</th><th class=num>all years</th>"
               "</tr></thead><tbody>" % "".join("<th class=num>%s</th>" % esc(v) for v in variant_order))
    for m in runs:
        st = m.get("stages") or {}
        su = st.get("startup", {})
        by_name = {v["name"]: v for v in st.get("variants", [])}
        cells = []
        for name in variant_order:
            v = by_name.get(name)
            if v is None:
                cells.append('<td class=num><span class="muted">-</span></td>')
            else:
                cells.append('<td class=num title="covariates %.0f min, years %.0f min">%s</td>'
                             % ((v.get("covariates_s") or 0) / 60, (v.get("years_s") or 0) / 60,
                                fmt(v["seconds"] / 60, 0)))
        totals = st.get("totals", {})
        out.append("<tr><td>%s</td><td class=num>%s</td><td class=num>%s</td>%s<td class=num>%s</td>"
                   "<td class=num>%s</td></tr>"
                   % (esc(m["folder"]), fmt((su.get("economic models") or 0) / 60, 1),
                      fmt((su.get("weather and claim") or 0) / 60, 1), "".join(cells),
                      fmt((totals.get("covariates_s") or 0) / 60, 0), fmt((totals.get("years_s") or 0) / 60, 0)))
    out.append("</tbody></table></div>")

    # pyinstrument
    for m in runs:
        if "profile.speedscope.json" not in m["files_here"]:
            continue
        summ = profile_summary(os.path.join(RESULTS_DIR, m["folder"], "profile.speedscope.json"))
        if not summ:
            continue
        out.append("<h2>Time profile: %s</h2><p>pyinstrument, %s h of wall time in the main thread "
                   "(%s, %s). Time counts in a group when any frame of its stack matches, so the groups "
                   "overlap. Frames under 0.1%% of the run are folded into their caller.</p>"
                   % (esc(m["folder"]), fmt(summ["seconds"] / 3600.0, 2),
                      link(m["folder"], "profile.html", "call tree"), link(m["folder"], "profile.txt", "as text")))
        out.append("<div class=\"card scroll\"><table><thead><tr><th>group</th><th class=num>share of time</th>"
                   "</tr></thead><tbody>")
        for label, share in summ["buckets"]:
            out.append("<tr><td>%s</td><td class=num>%s</td></tr>" % (esc(label), fmt(100 * share, 1, "%")))
        out.append("</tbody></table></div><div class=\"charts\" style=\"margin-top:12px\">")
        for title, key in (("Top functions, own time", "top_self"), ("Top functions, including callees", "top_total")):
            out.append("<div class=\"card scroll\"><div class=\"chart-title\">%s</div><table><tbody>" % title)
            for name, share in summ[key]:
                out.append("<tr><td>%s</td><td class=num>%s</td></tr>" % (esc(name), fmt(100 * share, 1, "%")))
            out.append("</tbody></table></div>")
        out.append("</div>")

    # Economic model check (econfix_check.sbatch), which has no manifest
    out.append(econfix_section(os.path.join(RESULTS_DIR, "econfix_check", "check.json")))

    # memray
    for m in runs:
        texts = []
        for fname in ("memray-summary.txt", "memray-stats.txt"):
            if fname in m["files_here"]:
                with open(os.path.join(RESULTS_DIR, m["folder"], fname), errors="replace") as fp:
                    texts.append(fp.read())
        if not texts:
            continue
        text = "\n\n".join(texts)
        out.append("<h2>Memory profile: %s</h2><p>%s, %s. Peak and leaks are by allocation site; "
                   "compare the memray peak with the RSS peak to see how much is held by the allocator.</p>"
                   % (esc(m["folder"]), link(m["folder"], "memray-flamegraph.html", "flame graph of the peak"),
                      link(m["folder"], "memray-table.html", "table")))
        out.append("<pre>%s</pre>" % esc(text[:20000]))

    out.append("<h2>Opening the files</h2><ul>"
               "<li>Perfetto trace: go to <a href=\"https://ui.perfetto.dev\">ui.perfetto.dev</a>, "
               "Open trace file, pick results/&lt;run&gt;/trace.json. Stages are slices; memory, CPU, reads and "
               "the current year are counters.</li>"
               "<li>pyinstrument profile: open profile.html in a browser for the call tree, or drop "
               "profile.speedscope.json on <a href=\"https://www.speedscope.app\">speedscope.app</a>; Left Heavy "
               "shows where the time adds up.</li>"
               "<li>memray flame graph and table: open the HTML files in a browser.</li></ul>")
    out.append("</main><div id=\"tip\" role=\"tooltip\"></div><script>%s</script></body></html>" % JS)
    return "".join(out)


def econfix_section(path):
    """The result of econfix_check.sbatch: identical values and memory per item."""
    try:
        with open(path) as fp:
            check = json.load(fp)
    except (OSError, ValueError):
        return ""
    cls = "ok" if check.get("status") == "pass" else "bad"
    bad = [name for name, c in check.get("checks", {}).items() if not c.get("identical")]
    rows = "".join("<tr><td>%s</td><td class=num>%s</td><td class=num>%s</td><td class=num>%s</td>"
                   "<td class=num>%s</td><td>%s</td></tr>"
                   % (esc(i["item"]), fmt(i["master_mb"], 1), fmt(i["branch_mb"], 1),
                      fmt(i["saved_per_model_mb"], 1), fmt(i["saved_ten_models_gb"], 2), esc(i.get("note", "")))
                   for i in check.get("memory", []))
    return ("<h2>Economic model check</h2><p>One economic model (%s, %s) built from master and from the "
            "econmodel-memory branch: every population, popop, baseline and age-share value is "
            '<span class="%s">%s</span>%s. Memory is what tracemalloc counts each item freeing when it is '
            "deleted.</p><div class=\"card scroll\"><table><thead><tr><th>item</th><th class=num>master MB</th>"
            "<th class=num>branch MB</th><th class=num>saved per model MB</th>"
            "<th class=num>saved, ten models GB</th><th>note</th></tr></thead><tbody>%s</tbody></table></div>"
            % (esc(check.get("ssp")), esc(check.get("iam")), cls,
               "identical" if check.get("status") == "pass" else "different",
               "" if not bad else " (" + esc(", ".join(bad)) + ")", rows))


def tile(label, value, note):
    return ('<div class="card tile"><div class="label">%s</div><div class="value">%s</div>'
            '<div class="note">%s</div></div>' % (esc(label), value, esc(note)))


RESULTS_DIR = ""


def main():
    global RESULTS_DIR
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--results", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--headroom", type=float, default=1.2, help="--mem = peak x this, rounded up")
    args = parser.parse_args()
    RESULTS_DIR = args.results
    runs = load_runs(args.results)
    page = build(runs, args.headroom)
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w") as fp:
        fp.write(page)
    print("wrote %s from %d runs" % (args.output, len(runs)))


if __name__ == "__main__":
    main()
