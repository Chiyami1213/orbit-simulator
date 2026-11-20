"""Export a mission trajectory for NAIF's SPICE-enhanced Cosmographia: an SPK kernel (type 13, Hermite, written with the optional ``spiceypy``) plus a JSON catalog.

Needs ``pip install spiceypy`` (optional: the rest of the program never imports it). The kernel holds the spacecraft relative to its center body in J2000 (ICRF-aligned)
axes with ET = TDB seconds past J2000 computed here, so no leap-second kernel is needed to write it. The catalog follows Cosmographia's published catalog format
(spacecraft item with a Spice trajectory); it has not been opened in Cosmographia from this program, so treat it as a starting point (see docs/help.html).
NAIF's rules on SPICE use apply: https://naif.jpl.nasa.gov/naif/rules.html
"""
from __future__ import annotations
import json
import pathlib
import numpy as np
from ..core import timeutil as TU

NAIF_ID = {'Sun': 10, 'Mercury': 199, 'Venus': 299, 'Earth': 399, 'Moon': 301, 'Mars': 499, 'Jupiter': 599, 'Saturn': 699, 'Uranus': 799, 'Neptune': 899, 'Pluto': 999}
SPACECRAFT_ID = -999000


def available() -> bool:
    try:
        import spiceypy  # noqa: F401
        return True
    except Exception:
        return False


def write_spk(path: str | pathlib.Path, sat_id: int, center: str, jd_utc, r, v, name: str = 'ORBIT SIMULATOR') -> tuple[float, float]:
    """Write one type-13 segment. Returns (first_et, last_et). jd_utc strictly increasing; r in km, v in km/s relative to ``center`` (ICRF axes)."""
    import spiceypy as sp
    jd = np.asarray(jd_utc, float); keep = np.concatenate([[True], np.diff(jd) > 1e-9]); jd = jd[keep]; r = np.asarray(r, float)[keep]; v = np.asarray(v, float)[keep]
    if len(jd) < 4: raise ValueError('the trajectory has too few points for an SPK segment')
    et = np.array([(TU.utc_to_tdb(j) - TU.JD_J2000) * 86400.0 for j in jd]); states = np.hstack([r, v])
    p = pathlib.Path(path)
    if p.exists(): p.unlink()
    h = sp.spkopn(str(p), name[:60], 0)
    try:
        deg = min(11, (len(jd) - 1) | 1)                                                  # odd degree, at most 11, below the number of points
        if deg % 2 == 0: deg -= 1
        sp.spkw13(h, sat_id, NAIF_ID[center], 'J2000', float(et[0]), float(et[-1]), 'ORBITSIM TRAJECTORY', max(1, deg), len(et), states.tolist(), et.tolist())
    finally:
        sp.spkcls(h)
    return float(et[0]), float(et[-1])


def catalog(name: str, sat: str, center: str, kernel: str, jd0: float, jd1: float, sat_id: int = SPACECRAFT_ID, radius_km: float = 0.005) -> dict:
    """Cosmographia catalog: loads the SPK and draws the spacecraft as a tiny globe with a trail."""
    def fmt(jd):
        Y, M, D, h, mi, sec = TU.jd_to_calendar(jd); return f'{Y:04d}-{M:02d}-{D:02d} {h:02d}:{mi:02d}:{min(sec, 59.999):06.3f}'
    return {'version': '1.0', 'name': name, 'spiceKernels': [kernel],
            'items': [{'class': 'spacecraft', 'name': sat, 'startTime': fmt(jd0) + ' UTC', 'endTime': fmt(jd1) + ' UTC', 'center': center,
                       'trajectory': {'type': 'Spice', 'target': str(sat_id), 'center': center},
                       'bodyFrame': {'type': 'BodyFixed', 'body': center},
                       'geometry': {'type': 'Globe', 'radius': radius_km},
                       'label': {'color': '#ff6b4a'}, 'trajectoryPlot': {'color': '#ff6b4a', 'fade': 0.0, 'duration': f'{max(1.0, jd1 - jd0)} d', 'lead': '0 d'}}]}


def export(res, sat: str, folder: str | pathlib.Path, mission_name: str = 'mission', sat_id: int = SPACECRAFT_ID) -> dict:
    """Write ``<sat>.bsp`` and ``<sat>_cosmographia.json`` into ``folder`` from a RunResult. Raises ValueError with a clear message when spiceypy is missing."""
    if not available(): raise ValueError('this export needs the optional spiceypy package: run  pip install spiceypy  and try again')
    sm = res.samples[sat]; centers = set(sm['central'])
    if len(centers) != 1: raise ValueError('the spacecraft changes its center body along the trajectory; run the mission in a single propagator center to export it')
    center = next(iter(centers)); folder = pathlib.Path(folder); folder.mkdir(parents=True, exist_ok=True)
    stem = ''.join(c if c.isalnum() or c in '-_' else '_' for c in sat)
    bsp = folder / f'{stem}.bsp'; et0, et1 = write_spk(bsp, sat_id, center, sm['jd'], sm['r'], sm['v'])
    cat = folder / f'{stem}_cosmographia.json'; cat.write_text(json.dumps(catalog(mission_name, sat, center, bsp.name, sm['jd'][0], sm['jd'][-1], sat_id), indent=1), encoding='utf-8')
    return dict(spk=str(bsp), catalog=str(cat), points=len(sm['jd']), center=center, target_id=sat_id)
