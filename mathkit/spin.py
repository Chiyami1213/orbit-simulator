"""Rotation of the Sun, planets and a few moons and minor bodies: the IAU 2009 (WGCCRE) pole and prime-meridian constants exactly as JPL/NAIF distributes them in the SPICE
text kernel ``pck00011.tpc`` (https://naif.jpl.nasa.gov/pub/naif/generic_kernels/pck/pck00011.tpc; Archinal et al. 2011, Celest. Mech. Dyn. Astron. 109, 101).

For each body:  pole right ascension  ra  = ra0  + ra1  * T   (degrees, T = Julian centuries since J2000),
                pole declination      dec = dec0 + dec1 * T,
                prime meridian        W   = w0   + rate  * d   (degrees, d = days since J2000; a negative rate is retrograde rotation).
The periodic nutation / libration terms of the kernel are not included (they are a fraction of a degree), so this is the mean orientation.
The body-fixed frame is  R3(W) R1(90 deg - dec) R3(ra + 90 deg)  applied to ICRF vectors, which is what the 3-D views use to turn the textured spheres.
"""
from __future__ import annotations

J2000_JD = 2451545.0
# name: (NAIF id, ra0, ra1, dec0, dec1, w0, rate)
TABLE = {
    'Sun': (10, 286.13, 0.0, 63.87, 0.0, 84.176, 14.1844),
    'Mercury': (199, 281.0103, -0.0328, 61.4155, -0.0049, 329.5988, 6.1385108),
    'Venus': (299, 272.76, 0.0, 67.16, 0.0, 160.2, -1.4813688),
    'Earth': (399, 0.0, -0.641, 90.0, -0.557, 190.147, 360.9856235),
    'Moon': (301, 269.9949, 0.0031, 66.5392, 0.013, 38.3213, 13.17635815),
    'Mars': (499, 317.269202, -0.10927547, 54.432516, -0.05827105, 176.049863, 350.891982443297),
    'Jupiter': (599, 268.056595, -0.006499, 64.495303, 0.002413, 284.95, 870.536),
    'Saturn': (699, 40.589, -0.036, 83.537, -0.004, 38.9, 810.7939024),
    'Uranus': (799, 257.311, 0.0, -15.175, 0.0, 203.81, -501.1600928),
    'Neptune': (899, 299.36, 0.0, 43.46, 0.0, 249.978, 541.1397757),
    'Pluto': (999, 132.993, 0.0, -6.163, 0.0, 302.695, 56.3625225),
    'Ceres': (2000001, 291.418, 0.0, 66.764, 0.0, 170.65, 952.1532),
    'Vesta': (2000004, 309.031, 0.0, 42.235, 0.0, 285.39, 1617.3329428),
    'Io': (501, 268.05, -0.009, 64.5, 0.003, 200.39, 203.4889538),
    'Europa': (502, 268.08, -0.009, 64.51, 0.003, 36.022, 101.3747235),
    'Ganymede': (503, 268.2, -0.009, 64.57, 0.003, 44.064, 50.3176081),
    'Callisto': (504, 268.72, -0.009, 64.83, 0.003, 259.51, 21.5710715),
}


def spin_for(name: str) -> dict | None:
    """The rotation constants of a known body as a plain dict (JSON friendly), or None for a body without catalogued rotation."""
    r = TABLE.get(name)
    if r is None: return None
    _, ra0, ra1, dec0, dec1, w0, rate = r
    return dict(ra=ra0, ra_rate=ra1, dec=dec0, dec_rate=dec1, w0=w0, rate=rate)


def period_hours(spin: dict | None) -> float:
    """Sidereal rotation period in hours; negative for retrograde rotation, 0 for no rotation."""
    if not spin or not spin.get('rate'): return 0.0
    return 24.0 * 360.0 / spin['rate']


def pole(spin: dict, jd: float) -> tuple[float, float]:
    """(right ascension, declination) of the north pole in degrees at a Julian date."""
    T = (jd - J2000_JD) / 36525.0
    return spin['ra'] + spin.get('ra_rate', 0.0) * T, spin['dec'] + spin.get('dec_rate', 0.0) * T


def prime_meridian(spin: dict, jd: float) -> float:
    """W in degrees (0 to 360) at a Julian date."""
    return (spin['w0'] + spin['rate'] * (jd - J2000_JD)) % 360.0
