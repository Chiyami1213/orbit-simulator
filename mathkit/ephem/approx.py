"""Built-in analytic ephemeris (no download).

Planets: E. M. Standish, "Keplerian Elements for Approximate Positions of the Major Planets" (JPL Solar System Dynamics, Table 1,
valid 1800-2050 AD): a, e, I, L, long.peri, long.node and their rates per Julian century, referred to the J2000 ecliptic and equinox.
Moon: truncated lunar theory after J. Meeus, Astronomical Algorithms, ch. 47 (the largest periodic terms only).
Frame: heliocentric, equatorial J2000 (ICRF to better than 0.02 arcsec); the Sun is taken at the origin (the true Sun-barycentre offset,
up to about 1.4e6 km, is ignored). Measured against DE440s (2026): Mercury..Mars within 7e4 km, Jupiter..Pluto within 4e6 km, Moon within 50 km.
"""
from __future__ import annotations
import numpy as np
from ..core.kepler import kepler_E

AU = 149597870.7
OBLIQUITY = np.radians(23.4392911)
# name: (a, a_dot, e, e_dot, I, I_dot, L, L_dot, w_bar, w_bar_dot, Omega, Omega_dot)   a in AU, angles in deg, rates per century
ELEMENTS = {
    'Mercury': (0.38709927, 0.00000037, 0.20563593, 0.00001906, 7.00497902, -0.00594749, 252.25032350, 149472.67411175, 77.45779628, 0.16047689, 48.33076593, -0.12534081),
    'Venus':   (0.72333566, 0.00000390, 0.00677672, -0.00004107, 3.39467605, -0.00078890, 181.97909950, 58517.81538729, 131.60246718, 0.00268329, 76.67984255, -0.27769418),
    'EMB':     (1.00000261, 0.00000562, 0.01671123, -0.00004392, -0.00001531, -0.01294668, 100.46457166, 35999.37244981, 102.93768193, 0.32327364, 0.0, 0.0),
    'Mars':    (1.52371034, 0.00001847, 0.09339410, 0.00007882, 1.84969142, -0.00813131, -4.55343205, 19140.30268499, -23.94362959, 0.44441088, 49.55953891, -0.29257343),
    'Jupiter': (5.20288700, -0.00011607, 0.04838624, -0.00013253, 1.30439695, -0.00183714, 34.39644051, 3034.74612775, 14.72847983, 0.21252668, 100.47390909, 0.20469106),
    'Saturn':  (9.53667594, -0.00125060, 0.05386179, -0.00050991, 2.48599187, 0.00193609, 49.95424423, 1222.49362201, 92.59887831, -0.41897216, 113.66242448, -0.28867794),
    'Uranus':  (19.18916464, -0.00196176, 0.04725744, -0.00004397, 0.77263783, -0.00242939, 313.23810451, 428.48202785, 170.95427630, 0.40805281, 74.01692503, 0.04240589),
    'Neptune': (30.06992276, 0.00026291, 0.00859048, 0.00005105, 1.77004347, 0.00035372, -55.12002969, 218.45945325, 44.96476227, -0.32241464, 131.78422574, -0.00508664),
    'Pluto':   (39.48211675, -0.00031596, 0.24882730, 0.00005170, 17.14001206, 0.00004818, 238.92903833, 145.20780515, 224.06891629, -0.04062942, 110.30393684, -0.01183482),
}
MU_SUN = 132712440017.99
MU_EARTH = 398600.4415
MU_MOON = 4902.8005821478

# Meeus ch. 47, arguments (D, M, M', F) multipliers; sums in 1e-6 deg (longitude, latitude) and 1e-3 km (distance)
_LR = [  # D, M, Mp, F, sin-coefficient (longitude), cos-coefficient (distance)
    (0, 0, 1, 0, 6288774, -20905355), (2, 0, -1, 0, 1274027, -3699111), (2, 0, 0, 0, 658314, -2955968), (0, 0, 2, 0, 213618, -569925),
    (0, 1, 0, 0, -185116, 48888), (0, 0, 0, 2, -114332, -3149), (2, 0, -2, 0, 58793, 246158), (2, -1, -1, 0, 57066, -152138),
    (2, 0, 1, 0, 53322, -170733), (2, -1, 0, 0, 45758, -204586), (0, 1, -1, 0, -40923, -129620), (1, 0, 0, 0, -34720, 108743),
    (0, 1, 1, 0, -30383, 104755), (2, 0, 0, -2, 15327, 10321), (0, 0, 1, 2, -12528, 0), (0, 0, 1, -2, 10980, 79661),
    (4, 0, -1, 0, 10675, -34782), (0, 0, 3, 0, 10034, -23210), (4, 0, -2, 0, 8548, -21636), (2, 1, -1, 0, -7888, 24208),
    (2, 1, 0, 0, -6766, 30824), (1, 0, -1, 0, -5163, -8379), (1, 1, 0, 0, 4987, -16675), (2, -1, 1, 0, 4036, -12831),
    (2, 0, 2, 0, 3994, -10445), (4, 0, 0, 0, 3861, -11650), (2, 0, -3, 0, 3665, 14403), (0, 1, -2, 0, -2689, -7003),
    (2, 0, -1, 2, -2602, 0), (2, -1, -2, 0, 2390, 10056), (1, 0, 1, 0, -2348, 6322), (2, -2, 0, 0, 2236, -9884)]
_B = [   # D, M, Mp, F, sin-coefficient (latitude)
    (0, 0, 0, 1, 5128122), (0, 0, 1, 1, 280602), (0, 0, 1, -1, 277693), (2, 0, 0, -1, 173237), (2, 0, -1, 1, 55413), (2, 0, -1, -1, 46271),
    (2, 0, 0, 1, 32573), (0, 0, 2, 1, 17198), (2, 0, 1, -1, 9266), (0, 0, 2, -1, 8822), (2, -1, 0, -1, 8216), (2, 0, -2, -1, 4324),
    (2, 0, 1, 1, 4200), (2, 1, 0, -1, -3359)]


def _rot_x(v, ang):
    c, s = np.cos(ang), np.sin(ang)
    return np.array([v[0], c * v[1] - s * v[2], s * v[1] + c * v[2]])


def _planet_helio_ecl(name: str, jd_tdb: float) -> np.ndarray:
    a0, ad, e0, ed, i0, id_, L0, Ld, w0, wd, O0, Od = ELEMENTS[name]; T = (jd_tdb - 2451545.0) / 36525.0
    a = (a0 + ad * T) * AU; e = e0 + ed * T; inc = np.radians(i0 + id_ * T); L = L0 + Ld * T; w = w0 + wd * T; Om = np.radians(O0 + Od * T)
    M = np.radians((L - w + 180.0) % 360.0 - 180.0); om = np.radians(w) - Om
    E = kepler_E(M, e); xp = a * (np.cos(E) - e); yp = a * np.sqrt(1 - e * e) * np.sin(E)
    co, so, cO, sO, ci, si = np.cos(om), np.sin(om), np.cos(Om), np.sin(Om), np.cos(inc), np.sin(inc)
    return np.array([(co * cO - so * sO * ci) * xp + (-so * cO - co * sO * ci) * yp,
                     (co * sO + so * cO * ci) * xp + (-so * sO + co * cO * ci) * yp,
                     (so * si) * xp + (co * si) * yp])


def moon_geocentric_eq(jd_tdb: float) -> np.ndarray:
    """Geocentric Moon position (km), equatorial J2000, from the truncated Meeus theory."""
    T = (jd_tdb - 2451545.0) / 36525.0
    Lp = 218.3164477 + 481267.88123421 * T - 0.0015786 * T * T
    D = np.radians(297.8501921 + 445267.1114034 * T - 0.0018819 * T * T)
    M = np.radians(357.5291092 + 35999.0502909 * T - 0.0001536 * T * T)
    Mp = np.radians(134.9633964 + 477198.8675055 * T + 0.0087414 * T * T)
    F = np.radians(93.2720950 + 483202.0175233 * T - 0.0036539 * T * T)
    E = 1 - 0.002516 * T - 0.0000074 * T * T
    sl = sr = sb = 0.0
    for d, m, mp, f, cl, cr in _LR:
        arg = d * D + m * M + mp * Mp + f * F; ef = E ** abs(m)
        sl += cl * ef * np.sin(arg); sr += cr * ef * np.cos(arg)
    for d, m, mp, f, cb in _B:
        sb += cb * E ** abs(m) * np.sin(d * D + m * M + mp * Mp + f * F)
    A1 = np.radians(119.75 + 131.849 * T); A2 = np.radians(53.09 + 479264.290 * T); A3 = np.radians(313.45 + 481266.484 * T)
    Lr = np.radians(Lp)
    sl += 3958 * np.sin(A1) + 1962 * np.sin(Lr - F) + 318 * np.sin(A2)
    sb += -2235 * np.sin(Lr) + 382 * np.sin(A3) + 175 * np.sin(A1 - F) + 175 * np.sin(A1 + F) + 127 * np.sin(Lr - Mp) - 115 * np.sin(Lr + Mp)
    lam = np.radians(Lp + sl / 1e6); bet = np.radians(sb / 1e6); dist = 385000.56 + sr / 1000.0
    lam -= np.radians(1.396971 * T + 0.0003086 * T * T)                      # mean equinox of date -> J2000 (general precession in longitude)
    v = dist * np.array([np.cos(bet) * np.cos(lam), np.cos(bet) * np.sin(lam), np.sin(bet)])
    return _rot_x(v, OBLIQUITY)


class AnalyticEphemeris:
    name = 'built-in analytic ephemeris'
    accuracy = 'inner planets within ~1e4-7e4 km, Jupiter to Pluto within ~4e6 km (Standish 1800-2050, the Sun is fixed at the origin), Moon within ~50 km (truncated Meeus)'
    bodies = ('Sun', 'Mercury', 'Venus', 'Earth', 'Moon', 'Mars', 'Jupiter', 'Saturn', 'Uranus', 'Neptune', 'Pluto')
    valid = (2305447.5, 2469807.5)                        # 1800 .. 2250 (elements are specified for 1800-2050)

    def _pos(self, body: str, jd: float) -> np.ndarray:            # heliocentric, equatorial J2000, km
        if body == 'Sun': return np.zeros(3)
        if body in ('Earth', 'Moon'):
            emb = _rot_x(_planet_helio_ecl('EMB', jd), OBLIQUITY); mg = moon_geocentric_eq(jd); f = MU_MOON / (MU_EARTH + MU_MOON)
            return emb - f * mg if body == 'Earth' else emb + (1 - f) * mg
        return _rot_x(_planet_helio_ecl(body, jd), OBLIQUITY)

    def position(self, body: str, jd_tdb: float, center: str = 'Sun'):
        """Position only (no finite-difference velocity): what the force models call."""
        return self._pos(body, jd_tdb) - (self._pos(center, jd_tdb) if center not in ('Sun', 'SSB') else 0.0)

    def state(self, body: str, jd_tdb: float, center: str = 'Sun'):
        """(r, v) of ``body`` relative to ``center`` ('Sun', 'SSB' (taken equal to the Sun) or any body name); km and km/s."""
        def p(b, jd): return self._pos(b, jd) - (self._pos(center, jd) if center not in ('Sun', 'SSB') else 0.0)
        h = 30.0 / 86400.0                                                    # central difference over 60 s
        r = p(body, jd_tdb); v = (p(body, jd_tdb + h) - p(body, jd_tdb - h)) / (2 * h * 86400.0)
        return r, v
