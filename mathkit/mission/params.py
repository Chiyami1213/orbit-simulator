"""GMAT parameters (dotted names) evaluated from a state, plus epoch-format helpers.

``Sat.Earth.SMA``, ``Sat.EarthMJ2000Eq.INC``, ``Sat.UTCGregorian``, ``Sat.ElapsedSecs``, ``Sat.RMAG`` ...
All angles in degrees, lengths in km, speeds in km/s; GMAT conventions (TA, MA, EA in [0, 360), VFPA from the radius vector).
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from ..core.constants import R2D, D2R, wrap360, BODIES
from ..core.elements import elements_from_rv
from ..core import timeutil as TU
from ..conventions import gmat_body, course_body, vfpa_from_gamma
from ..dyn.models import pole_vector

TIME_PARAMS = ('UTCGregorian', 'UTCModJulian', 'TAIModJulian', 'A1ModJulian', 'ElapsedSecs', 'ElapsedDays')
CART_PARAMS = ('X', 'Y', 'Z', 'VX', 'VY', 'VZ', 'RMAG', 'VMAG')
KEP_PARAMS = ('SMA', 'ECC', 'INC', 'RAAN', 'AOP', 'TA', 'MA', 'EA', 'HA', 'RadPer', 'RadApo', 'OrbitPeriod', 'MeanMotion')
OTHER_PARAMS = ('Energy', 'C3Energy', 'HMAG', 'HX', 'HY', 'HZ', 'VelPeriapsis', 'VelApoapsis', 'HFPA', 'VFPA')
ALL_PARAMS = TIME_PARAMS + CART_PARAMS + KEP_PARAMS + OTHER_PARAMS
UNITS = {'SMA': 'km', 'ECC': '', 'INC': 'deg', 'RAAN': 'deg', 'AOP': 'deg', 'TA': 'deg', 'MA': 'deg', 'EA': 'deg', 'HA': 'deg', 'RadPer': 'km', 'RadApo': 'km',
         'OrbitPeriod': 's', 'MeanMotion': 'deg/s', 'RMAG': 'km', 'VMAG': 'km/s', 'X': 'km', 'Y': 'km', 'Z': 'km', 'VX': 'km/s', 'VY': 'km/s', 'VZ': 'km/s',
         'Energy': 'km^2/s^2', 'C3Energy': 'km^2/s^2', 'HMAG': 'km^2/s', 'HX': 'km^2/s', 'HY': 'km^2/s', 'HZ': 'km^2/s', 'VelPeriapsis': 'km/s',
         'VelApoapsis': 'km/s', 'HFPA': 'deg', 'VFPA': 'deg', 'ElapsedSecs': 's', 'ElapsedDays': 'days'}
OBLIQUITY = np.radians(23.4392911)


# ---- epoch formats ------------------------------------------------------------------------------------------------------------------
def format_epoch(jd_utc: float, fmt: str):
    if fmt == 'UTCGregorian': return TU.format_gregorian(jd_utc)
    if fmt == 'UTCModJulian': return TU.jd_to_modjulian(jd_utc)
    tai = TU.utc_to_tai(jd_utc)
    if fmt == 'TAIModJulian': return TU.jd_to_modjulian(tai)
    if fmt == 'A1ModJulian': return TU.jd_to_modjulian(TU.tai_to_a1(tai))
    raise ValueError(f'unknown date format {fmt}')


def parse_epoch(text, fmt: str) -> float:
    """Epoch text -> UTC Julian date."""
    if fmt == 'UTCGregorian': return TU.parse_gregorian(str(text))
    jd = TU.modjulian_to_jd(float(text))
    if fmt == 'UTCModJulian': return jd
    jd_tai = jd if fmt == 'TAIModJulian' else jd - TU.A1_MINUS_TAI / 86400.0
    return jd_tai - TU.tai_minus_utc(jd_tai) / 86400.0


# ---- frame helpers ----------------------------------------------------------------------------------------------------------------
def axes_matrix(axes: str, body: str = 'Earth') -> np.ndarray:
    """Rotation from MJ2000Eq components to the named axes (rows are the new axes in the MJ2000Eq basis)."""
    if axes == 'MJ2000Eq': return np.eye(3)
    if axes == 'MJ2000Ec':
        c, s = np.cos(OBLIQUITY), np.sin(OBLIQUITY); return np.array([[1, 0, 0], [0, c, s], [0, -s, c]])
    if axes == 'BodyInertial':
        z = pole_vector(body); x = np.cross([0, 0, 1.0], z)
        if np.linalg.norm(x) < 1e-12: return np.eye(3)
        x /= np.linalg.norm(x); y = np.cross(z, x); return np.array([x, y, z])
    raise ValueError(f'unknown axes {axes}')


def keplerian(mu: float, r, v) -> dict:
    el = elements_from_rv(mu, np.asarray(r, float), np.asarray(v, float)); e = el['e']; a = el['a']; rn = el['r']; vn = el['v']
    h = el['hv']; d = dict(SMA=a, ECC=e, INC=el['inc'], RAAN=el['Om'], AOP=el['om'], TA=float(wrap360(el['ths'])), RMAG=rn, VMAG=vn,
                           Energy=el['eps'], C3Energy=2 * el['eps'], HMAG=el['h'], HX=h[0], HY=h[1], HZ=h[2], HFPA=el['gamma'], VFPA=vfpa_from_gamma(el['gamma']),
                           X=r[0], Y=r[1], Z=r[2], VX=v[0], VY=v[1], VZ=v[2])
    if e < 1:
        n = np.sqrt(mu / a ** 3); d.update(MA=float(wrap360(el['M'])), EA=float(wrap360(el['E'])), HA=float('nan'), OrbitPeriod=2 * np.pi / n, MeanMotion=n * R2D)
        d.update(RadPer=a * (1 - e), RadApo=a * (1 + e), VelPeriapsis=np.sqrt(mu / a * (1 + e) / (1 - e)), VelApoapsis=np.sqrt(mu / a * (1 - e) / (1 + e)))
    else:
        n = np.sqrt(mu / abs(a) ** 3); H = el['H']; d.update(MA=(e * np.sinh(H) - H) * R2D, EA=float('nan'), HA=H * R2D, OrbitPeriod=float('nan'), MeanMotion=n * R2D,
                                                             RadPer=a * (1 - e), RadApo=float('nan'), VelPeriapsis=np.sqrt(mu / abs(a) * (e + 1) / (e - 1)), VelApoapsis=float('nan'))
    return d


@dataclass
class ParamContext:
    """What a parameter needs: the spacecraft state about its propagator's central body (MJ2000Eq), the epoch, and how to re-center it."""
    central: str
    r: np.ndarray
    v: np.ndarray
    jd_utc: float
    jd_start: float
    consts: object
    eph: object = None
    coords: dict | None = None               # name -> CoordSys

    def mu(self, body: str) -> float: return self.consts.mu(body)

    def state_about(self, body: str, axes: str = 'MJ2000Eq'):
        r, v = self.r, self.v
        if body != self.central:
            if self.eph is None: raise ValueError(f'a state about {body} needs an ephemeris (the propagator is centered on {self.central})')
            jd_tdb = TU.utc_to_tdb(self.jd_utc); rc, vc = self.eph.state(self.central, jd_tdb, body)       # central body relative to ``body``
            r = r + rc; v = v + vc
        M = axes_matrix(axes, body); return M @ r, M @ v


def evaluate(name: str, ctx: ParamContext):
    """Value of a dotted GMAT parameter such as ``Sat.Earth.TA`` for the context's state."""
    parts = name.split('.')
    if len(parts) == 1: p = parts[0]; mid = None
    elif len(parts) == 2: p = parts[1]; mid = None
    else: p = parts[2]; mid = parts[1]
    if p == 'UTCGregorian': return TU.format_gregorian(ctx.jd_utc)
    if p in ('UTCModJulian', 'TAIModJulian', 'A1ModJulian'): return format_epoch(ctx.jd_utc, p)
    if p == 'ElapsedSecs': return (ctx.jd_utc - ctx.jd_start) * 86400.0
    if p == 'ElapsedDays': return ctx.jd_utc - ctx.jd_start
    body, axes = ctx.central, 'MJ2000Eq'
    if mid:
        for ax in ('MJ2000Eq', 'MJ2000Ec', 'BodyInertial'):
            if mid.endswith(ax): body = course_body(mid[:-len(ax)] or 'Earth'); axes = ax; break
        else: body = course_body(mid)
    r, v = ctx.state_about(body, axes)
    if p in ('Periapsis', 'Apoapsis'): raise ValueError(f'{p} is a stop condition, not a value')
    if p not in ALL_PARAMS: raise ValueError(f'unknown parameter {name}')
    return keplerian(ctx.mu(body), r, v)[p]
