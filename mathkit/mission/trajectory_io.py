"""Import reference trajectories: CSV (including this program's own export), CCSDS OEM text, and SPK kernels (through jplephem).

Result: dict(name, center, jd (UTC Julian dates), r (km), v (km/s or None)), ready to draw next to a mission and to compare with it.
Only inertial frames equal to ICRF / EME2000 / J2000 are accepted; anything else is reported as an error rather than silently misplotted.
"""
from __future__ import annotations
import csv
import io
import re
import numpy as np
from ..core import timeutil as TU

_INERTIAL = {'EME2000', 'ICRF', 'J2000', 'GCRF', 'ICRF_J2000'}
_BODY = {'EARTH': 'Earth', 'MOON': 'Moon', 'LUNA': 'Moon', 'SUN': 'Sun', 'MARS': 'Mars', 'VENUS': 'Venus', 'MERCURY': 'Mercury', 'JUPITER': 'Jupiter', 'SATURN': 'Saturn',
         'URANUS': 'Uranus', 'NEPTUNE': 'Neptune', 'PLUTO': 'Pluto', 'SOLAR SYSTEM BARYCENTER': 'SSB', 'SSB': 'SSB'}


def _epoch(tok: str) -> float:
    """ISO 'YYYY-MM-DDThh:mm:ss.sss', GMAT 'DD Mon YYYY hh:mm:ss.sss', or a Julian date (> 2.4e6) -> UTC Julian date."""
    t = tok.strip().strip('"\'')
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2}(?:\.\d+)?)$', t)
    if m: return TU.calendar_to_jd(int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)), int(m.group(5)), float(m.group(6)))
    m = re.match(r'^(\d{4})-(\d{3})T(\d{2}):(\d{2}):(\d{2}(?:\.\d+)?)$', t)                       # year-day-of-year form allowed by CCSDS
    if m: return TU.calendar_to_jd(int(m.group(1)), 1, 1, int(m.group(3)), int(m.group(4)), float(m.group(5))) + int(m.group(2)) - 1
    if re.match(r'^\d{1,2} [A-Za-z]{3} \d{4}', t): return TU.parse_gregorian(t)
    x = float(t)
    return x if x > 2.0e6 else TU.modjulian_to_jd(x)


def parse_csv(text: str, name: str = 'Imported') -> dict:
    """Header names (case-insensitive): an epoch column (UTC / JD_UTC / EPOCH / TIME), X, Y, Z, optional VX, VY, VZ (with or without _km / _kms). A ``# centre: Earth``
    comment line (or a ``centre`` column) names the origin; the default is Earth."""
    center = 'Earth'; lines = []
    for ln in text.splitlines():
        m = re.match(r'^\s*#\s*(?:centre|center|origin)\s*[:=]\s*(\w+)', ln, flags=re.I)
        if m: center = _BODY.get(m.group(1).upper(), m.group(1).title()); continue
        if ln.strip() and not ln.lstrip().startswith('#'): lines.append(ln)
    if len(lines) < 3: raise ValueError('the CSV needs a header row and at least two data rows')
    rows = list(csv.reader(io.StringIO('\n'.join(lines))))
    head = [h.strip().lower().replace('_km', '').replace('_kms', '').replace('_km/s', '') for h in rows[0]]
    def col(*names):
        for n in names:
            if n in head: return head.index(n)
        return None
    ie = col('jd_utc', 'jd', 'epoch', 'utc', 'time'); ix, iy, iz = col('x'), col('y'), col('z')
    if ie is None or None in (ix, iy, iz): raise ValueError('the CSV needs an epoch column (UTC, JD_UTC or EPOCH) and X, Y, Z columns')
    ivx, ivy, ivz = col('vx'), col('vy'), col('vz'); ic = col('centre', 'center')
    jd, r, v = [], [], []
    for row in rows[1:]:
        if len(row) < len(head): continue
        jd.append(_epoch(row[ie])); r.append([float(row[ix]), float(row[iy]), float(row[iz])])
        if None not in (ivx, ivy, ivz): v.append([float(row[ivx]), float(row[ivy]), float(row[ivz])])
        if ic is not None: center = _BODY.get(row[ic].upper(), row[ic])
    return _pack(name, center, jd, r, v if len(v) == len(jd) else None)


def parse_oem(text: str, name: str = 'Imported') -> dict:
    """CCSDS OEM 2.0 (KVN). Several segments are joined in time order; all must share one centre."""
    center = None; jd, r, v = [], [], []; in_meta = False; ref = 'EME2000'; tsys = 'UTC'; obj = name
    for ln in text.splitlines():
        s = ln.strip()
        if not s or s.startswith('COMMENT'): continue
        if s == 'META_START': in_meta = True; continue
        if s == 'META_STOP': in_meta = False; continue
        if in_meta:
            k, _, val = s.partition('='); k, val = k.strip(), val.strip()
            if k == 'CENTER_NAME':
                c = _BODY.get(val.upper(), val.title())
                if center not in (None, c): raise ValueError('segments with different centres are not supported')
                center = c
            elif k == 'REF_FRAME': ref = val.upper()
            elif k == 'TIME_SYSTEM': tsys = val.upper()
            elif k == 'OBJECT_NAME': obj = val
            continue
        if '=' in s or s.startswith(('CCSDS_', 'CREATION', 'ORIGINATOR')): continue
        if s in ('DATA_START', 'DATA_STOP', 'COVARIANCE_START', 'COVARIANCE_STOP'): continue
        tok = s.split()
        if len(tok) >= 7:
            if ref not in _INERTIAL: raise ValueError(f'reference frame {ref} is not supported (only EME2000 / ICRF)')
            if tsys not in ('UTC',): raise ValueError(f'time system {tsys} is not supported (only UTC)')
            jd.append(_epoch(tok[0])); r.append([float(x) for x in tok[1:4]]); v.append([float(x) for x in tok[4:7]])
    if not jd: raise ValueError('no state lines were found in this OEM file')
    return _pack(obj, center or 'Earth', jd, r, v)


def parse_spk(path: str, target: int | None = None, n: int = 600, name: str = 'Imported') -> dict:
    """Sample one segment of an SPK kernel with jplephem (types it can read; most mission kernels are type 2, 3 or 9/13 depending on the version)."""
    from jplephem.spk import SPK
    k = SPK.open(path); segs = list(k.segments)
    if target is not None: segs = [s for s in segs if int(s.target) == target]
    if not segs: raise ValueError('no segment found in this kernel')
    seg = segs[0]; names = {10: 'Sun', 399: 'Earth', 301: 'Moon', 3: 'Earth', 499: 'Mars', 4: 'Mars', 299: 'Venus', 2: 'Venus', 199: 'Mercury', 1: 'Mercury', 5: 'Jupiter', 6: 'Saturn', 7: 'Uranus', 8: 'Neptune', 9: 'Pluto', 0: 'SSB'}
    center = names.get(int(seg.center))
    if center is None: raise ValueError(f'centre body NAIF id {int(seg.center)} is not supported')
    t0, t1 = seg.start_jd, seg.end_jd; tdb = np.linspace(t0, t1, n); r, v = [], []
    for t in tdb:
        try: p, vv = seg.compute_and_differentiate(t)
        except Exception as ex: raise ValueError(f'this SPK segment type cannot be read: {ex}')
        r.append(np.asarray(p, float)); v.append(np.asarray(vv, float) / 86400.0)
    jd = [t - TU.tdb_minus_utc(t) / 86400.0 for t in tdb]                              # TDB -> UTC to within a millisecond
    return _pack(name or f'SPK {int(seg.target)}', center, jd, r, v)


def _pack(name, center, jd, r, v) -> dict:
    jd = np.asarray(jd, float); order = np.argsort(jd)
    return dict(name=name, center=center, jd=jd[order].tolist(), r=np.asarray(r, float)[order].tolist(), v=(np.asarray(v, float)[order].tolist() if v is not None else None))


def import_text(filename: str, text: str) -> dict:
    stem = filename.rsplit('.', 1)[0]
    if filename.lower().endswith(('.oem', '.txt')) or 'CCSDS_OEM_VERS' in text[:400]: return parse_oem(text, stem)
    return parse_csv(text, stem)


def compare_with(ref: dict, jd, r) -> dict:
    """Difference between a reference trajectory and a propagated one (arrays of UTC JDs and positions): interpolated at the reference epochs."""
    jd = np.asarray(jd, float); r = np.asarray(r, float); rj = np.asarray(ref['jd']); rr = np.asarray(ref['r'])
    m = (rj >= jd[0]) & (rj <= jd[-1])
    if m.sum() < 2: return dict(points=0)
    p = np.stack([np.interp(rj[m], jd, r[:, k]) for k in range(3)], axis=1); d = np.linalg.norm(p - rr[m], axis=1)
    return dict(points=int(m.sum()), max_km=float(d.max()), rms_km=float(np.sqrt(np.mean(d ** 2))), end_km=float(d[-1]))
