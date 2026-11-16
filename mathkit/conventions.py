"""Presentation conventions: the course (default) and GMAT.

This module is a *presentation layer only*. Every number inside ``mathkit.core``, ``Result.data``, the presets and the tests
stays in the course convention. Values are converted here when they are shown or exported, never stored back, and never
converted twice (each function takes a course value and returns the GMAT form, or the other way round).

Course quantity                      GMAT quantity
gamma (flight-path angle from the    HFPA = gamma;   VFPA (from the radius vector) = 90 deg - gamma
  local horizon, + when rdot > 0)
theta*, M, E in (-180, 180]          TA, MA, EA in [0, 360)
Delta-v, alpha, beta in VNC          ImpulsiveBurn Element1..3 in VNB  (B = V x N = C-hat)
energy eps                           Energy, C3Energy = 2 eps
Moon                                 Luna
JD                                   UTCModJulian = JD - 2430000.0
"""
from __future__ import annotations
from enum import Enum
import numpy as np
from .core.constants import D2R, R2D, wrap360, wrap180


class Convention(str, Enum):
    COURSE = 'course'
    GMAT = 'gmat'

    @classmethod
    def of(cls, v) -> 'Convention':
        if isinstance(v, Convention): return v
        return cls.GMAT if str(v).lower() == 'gmat' else cls.COURSE


# ---- angles ---------------------------------------------------------------------------------------------------
def vfpa_from_gamma(gamma_deg: float) -> float: return 90.0 - gamma_deg
def gamma_from_vfpa(vfpa_deg: float) -> float: return 90.0 - vfpa_deg
def hfpa_from_gamma(gamma_deg: float) -> float: return gamma_deg
def to_gmat_angle(x_deg: float) -> float: return float(wrap360(x_deg))        # TA, MA, EA in [0, 360)
def from_gmat_angle(x_deg: float) -> float: return float(wrap180(x_deg))      # back to (-180, 180]


# ---- impulses: (dv, alpha, beta) in VNC  <->  GMAT VNB elements ----------------------------------------------------
def vnb_from_dv_alpha_beta(dv: float, alpha_deg: float, beta_deg: float) -> tuple[float, float, float]:
    a, b = alpha_deg * D2R, beta_deg * D2R
    return dv * np.cos(b) * np.cos(a), dv * np.sin(b), dv * np.cos(b) * np.sin(a)


def dv_alpha_beta_from_vnb(e1: float, e2: float, e3: float) -> tuple[float, float, float]:
    dv = float(np.sqrt(e1 * e1 + e2 * e2 + e3 * e3))
    if dv == 0: return 0.0, 0.0, 0.0
    beta = np.arcsin(np.clip(e2 / dv, -1, 1)) * R2D
    alpha = np.arctan2(e3, e1) * R2D
    return dv, float(alpha), float(beta)


# ---- energy, dates, names -----------------------------------------------------------------------------------------
def c3_from_energy(eps: float) -> float: return 2.0 * eps
def modjulian_from_jd(jd: float) -> float: return jd - 2430000.0
def jd_from_modjulian(mjd: float) -> float: return mjd + 2430000.0

GMAT_BODY = {'Moon': 'Luna'}
def gmat_body(name: str) -> str: return GMAT_BODY.get(name, name)
def course_body(name: str) -> str: return {v: k for k, v in GMAT_BODY.items()}.get(name, name)

FRAME_NAMES = {'inertial': 'EarthMJ2000Eq', 'vnc': 'VNB', 'rth': 'LVLH (axis order differs)', 'peri': 'BodyInertial (perifocal is not a GMAT axes type)'}


def gmat_frame(body: str = 'Earth', axes: str = 'MJ2000Eq') -> str: return f'{gmat_body(body)}{axes}'


# ---- the single formatter --------------------------------------------------------------------------------------------
def _fmt(x: float, digits: int = 6) -> str:
    return f'{x:.{digits}g}' if abs(x) >= 1e-3 or x == 0 else f'{x:.3e}'


def present_step(name: str, symbol: str, value, units: str, conv: Convention):
    """Return a list of (name, symbol, value, units, note) rows to show for one calculation step.

    In the course convention the step is returned unchanged. In GMAT mode the flight-path angle gains VFPA/HFPA rows,
    true/mean/eccentric anomalies are wrapped to [0, 360) and renamed, and every converted line carries a 'course: ...' note.
    Non-numeric steps pass through untouched.
    """
    row = (name, symbol, value, units, '')
    if conv is not Convention.GMAT or not isinstance(value, (int, float, np.floating)) or isinstance(value, bool):
        return [row]
    v = float(value); sub = symbol[1:] if len(symbol) > 1 else ''
    deg = units in ('°', 'deg')
    if symbol.startswith('γ') and deg:
        sub = symbol[1:]
        return [(f'{name} (VFPA, from the radius vector)', f'VFPA{sub}', vfpa_from_gamma(v), '°', f'course: γ{sub} = {_fmt(v)}°'),
                (f'{name} (HFPA, from the local horizon)', f'HFPA{sub}', v, '°', 'same as the course γ')]
    for course, gmat, nm in (('θ*', 'TA', 'True anomaly'), ('M', 'MA', 'Mean anomaly'), ('E', 'EA', 'Eccentric anomaly')):
        ok = symbol.startswith(course) if course == 'θ*' else (symbol == course or symbol.startswith(course + '_'))
        if ok and deg:
            s_ = symbol[len(course):]; w = to_gmat_angle(v)
            note = f'course: {symbol} = {_fmt(v)}°' if abs(w - v) > 1e-12 else ''
            return [(name if name else nm, f'{gmat}{s_}', w, '°', note)]
    if symbol == 'ε' or symbol.startswith('ε_'):
        return [row, ('C3 energy (GMAT C3Energy = 2ε)', 'C3Energy' + symbol[1:], c3_from_energy(v), units, 'course: 2ε')]
    return [row]


def present_dict(d: dict, conv: Convention) -> dict:
    """Convert a plain {name: value_deg} dict of the common orbital angles (used by exports and readouts)."""
    if conv is not Convention.GMAT: return dict(d)
    out = dict(d)
    if 'gamma' in d: out['VFPA'] = vfpa_from_gamma(d['gamma']); out['HFPA'] = d['gamma']
    for k_c, k_g in (('ths', 'TA'), ('M', 'MA'), ('E', 'EA')):
        if k_c in d: out[k_g] = to_gmat_angle(d[k_c])
    return out
