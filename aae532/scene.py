"""Renderer-independent scene description + the annotation layer.

Modules build a ``Scene`` once; ``plots2d.render`` draws it with matplotlib (Cartesian, equal axes) and
``view3d.scene`` draws it with Plotly. All coordinates are inertial 3-vectors in km with the attracting focus at the
origin (planet-centred insets are separate scenes). Velocity-type vectors carry a display ``scale`` so km/s can share
the km axes.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Optional
import numpy as np

D2R = np.pi / 180


def unit(v):
    v = np.asarray(v, float); n = np.linalg.norm(v); return v / n if n > 0 else v


def Rz(deg: float) -> np.ndarray:
    c, s = np.cos(deg * D2R), np.sin(deg * D2R)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1.0]])


@dataclass
class Orbit:
    name: str
    p: float
    e: float
    Q: np.ndarray = field(default_factory=lambda: np.eye(3))   # columns e_hat, p_hat, h_hat in inertial axes
    role: str = 'orbit'
    ths_range: Optional[tuple] = None   # (start, end) deg, true anomaly; None = whole conic
    dash: bool = False
    label_ths: Optional[float] = None   # where to put the name label
    rmax: Optional[float] = None        # cap for hyperbolas / parabolas

    @property
    def a(self): return self.p / (1 - self.e ** 2) if abs(self.e - 1) > 1e-12 else np.inf

    def r(self, ths_deg):
        return self.p / (1 + self.e * np.cos(np.asarray(ths_deg) * D2R))

    def pos(self, ths_deg) -> np.ndarray:
        t = np.asarray(ths_deg, float) * D2R; r = self.p / (1 + self.e * np.cos(t))
        local = np.stack([r * np.cos(t), r * np.sin(t), np.zeros_like(t)], axis=-1)
        return local @ self.Q.T

    def vel_dir(self, ths_deg) -> np.ndarray:
        t = ths_deg * D2R
        loc = np.array([-np.sin(t), self.e + np.cos(t), 0.0]); return unit(self.Q @ loc)

    def sample(self, n: int = 721) -> np.ndarray:
        if self.ths_range is not None:
            a0, a1 = self.ths_range
            if a1 < a0: a1 += 360
            ths = np.linspace(a0, a1, n)
        elif self.e < 1:
            ths = np.linspace(-180, 180, n)
        else:
            lim = np.degrees(np.arccos(-1 / self.e)) - 0.5 if self.e > 1 else 175.0
            if self.rmax:
                c = (self.p / self.rmax - 1) / self.e
                if abs(c) < 1: lim = min(lim, np.degrees(np.arccos(c)))
            ths = np.linspace(-lim, lim, n)
        return self.pos(ths)


@dataclass
class Vec:
    origin: np.ndarray
    vec: np.ndarray
    label: str
    role: str = 'vector'
    scale: float = 1.0
    dash: bool = False


@dataclass
class Pt:
    pos: np.ndarray
    label: str = ''
    role: str = 'ink'
    marker: str = 'o'
    size: float = 6


@dataclass
class Line:
    p0: np.ndarray
    p1: np.ndarray
    label: str = ''
    role: str = 'muted'
    dash: bool = True
    width: float = 1.0
    label_frac: float = 0.5


@dataclass
class Arc:
    origin: np.ndarray
    u: np.ndarray            # start direction
    w: np.ndarray            # end direction
    radius: float
    label: str = ''
    role: str = 'ink2'
    normal: Optional[np.ndarray] = None   # sweep from u to w counter-clockwise about this axis
    long_way: bool = False
    only3d: bool = False                  # skip in the 2-D figure (meaningless when projected)

    def points(self, n=40):
        u = unit(self.u); w = unit(self.w)
        nrm = unit(self.normal) if self.normal is not None else unit(np.cross(u, w))
        if np.linalg.norm(nrm) == 0: nrm = np.array([0, 0, 1.0])
        ang = np.arctan2(np.dot(nrm, np.cross(u, w)), np.dot(u, w))
        if ang < 0: ang += 2 * np.pi
        if ang < 1e-7 or ang > 2 * np.pi - 1e-7: ang = 0.0     # degenerate (u parallel to w): no arc
        if self.long_way: ang = 2 * np.pi - ang if ang < np.pi else ang
        t = np.linspace(0, ang, n); v = np.cross(nrm, u)
        return self.origin + self.radius * (np.outer(np.cos(t), u) + np.outer(np.sin(t), v)), ang


@dataclass
class Disk:
    center: np.ndarray
    radius: float
    label: str = ''
    role: str = 'body'


@dataclass
class Poly:
    pts: np.ndarray
    label: str = ''
    role: str = 'muted'
    dash: bool = True
    width: float = 1.0
    label_frac: float = 0.5


@dataclass
class Triad:
    origin: np.ndarray
    axes: np.ndarray          # columns are the three unit vectors
    names: tuple
    length: float
    role: str = 'ink2'
    only3d: bool = False


@dataclass
class Plane:
    normal: np.ndarray
    size: float
    label: str = ''
    center: np.ndarray = field(default_factory=lambda: np.zeros(3))
    role: str = 'muted'


@dataclass
class Track:
    """A moving point for the 3-D animation. ``fn(t_s) -> position`` and optional ``state(t_s) -> dict`` readout."""
    name: str
    fn: Callable[[float], np.ndarray]
    role: str = 'orbit'
    state: Optional[Callable[[float], dict]] = None
    trail: bool = True


@dataclass
class Scene:
    title: str = ''
    label: str = ''
    orbits: list[Orbit] = field(default_factory=list)
    vecs: list[Vec] = field(default_factory=list)
    pts: list[Pt] = field(default_factory=list)
    lines: list[Line] = field(default_factory=list)
    arcs: list[Arc] = field(default_factory=list)
    disks: list[Disk] = field(default_factory=list)
    polys: list[Poly] = field(default_factory=list)
    triads: list[Triad] = field(default_factory=list)
    planes: list[Plane] = field(default_factory=list)
    tracks: list[Track] = field(default_factory=list)
    plane2d: tuple = (np.array([1.0, 0, 0]), np.array([0, 1.0, 0]))   # 2-D projection basis
    duration_s: float = 0.0     # animation length (one period of the main orbit by default)
    units: str = 'km'
    is3d: bool = False          # prefer the 3-D tab by default
    notes: list[str] = field(default_factory=list)
    focus_name: str = ''        # label for the attracting focus

    def extent(self) -> float:
        """Characteristic half-width (km) used to size glyphs: max of finite orbit samples / points."""
        pts = []
        for o in self.orbits: pts.append(o.sample(181))
        for p in self.pts: pts.append(np.atleast_2d(p.pos))
        for v in self.vecs: pts.append(np.atleast_2d(v.origin + v.vec * v.scale))
        for l in self.lines: pts.append(np.array([l.p0, l.p1]))
        if not pts: return 1.0
        P = np.vstack(pts); P = P[np.all(np.isfinite(P), axis=1)]
        return float(np.max(np.abs(P))) if P.size else 1.0


# ----------------------------------------------------------------------------------------------------------------
# Annotation layer: functions that add the standard graded marks to a scene.
# ----------------------------------------------------------------------------------------------------------------

def vector(sc: Scene, origin, vec, label, role='vector', scale=1.0, dash=False):
    sc.vecs.append(Vec(np.asarray(origin, float), np.asarray(vec, float), label, role, scale, dash))


def local_horizon(sc: Scene, pos, hhat, length, label='local horizon', role='muted'):
    """Line through ``pos`` perpendicular to the radius vector, in the orbit plane (theta_hat direction)."""
    pos = np.asarray(pos, float); rh = unit(pos); th = unit(np.cross(hhat, rh))
    sc.lines.append(Line(pos - length * th, pos + length * th, label, role, True, 1.0, 0.95))


def angle_arc(sc: Scene, origin, u, w, radius, label, role='ink2', normal=None, long_way=False, only3d=False):
    sc.arcs.append(Arc(np.asarray(origin, float), np.asarray(u, float), np.asarray(w, float), radius, label, role,
                       None if normal is None else np.asarray(normal, float), long_way, only3d))


def apsides_line(sc: Scene, orbit: Orbit, label='line of apsides'):
    e_hat = orbit.Q[:, 0]
    if orbit.e < 1:
        ra = orbit.p / (1 - orbit.e); rp = orbit.p / (1 + orbit.e)
        sc.lines.append(Line(-1.12 * ra * e_hat, 1.12 * rp * e_hat, label, 'muted', True, 1.0, 0.04))
    else:
        rp = orbit.p / (1 + orbit.e); a_abs = abs(orbit.a) if orbit.e > 1 else rp
        sc.lines.append(Line(-0.4 * rp * e_hat, (rp + 2.2 * a_abs) * e_hat * 1.0, label, 'muted', True, 1.0, 0.9))


def minor_axis(sc: Scene, orbit: Orbit, label='minor axis'):
    if orbit.e >= 1: return
    a = orbit.a; b = a * np.sqrt(1 - orbit.e ** 2); c = orbit.Q @ np.array([-a * orbit.e, 0, 0]); ph = orbit.Q[:, 1]
    sc.lines.append(Line(c - b * ph, c + b * ph, label, 'muted', True, 1.0, 0.92))


def unit_triad(sc: Scene, origin, axes, names, length, role='ink2', only3d=False):
    sc.triads.append(Triad(np.asarray(origin, float), np.asarray(axes, float), tuple(names), length, role, only3d))


def aux_circle(sc: Scene, orbit: Orbit, label='auxiliary circle'):
    a = orbit.a; c = orbit.Q @ np.array([-a * orbit.e, 0, 0]); t = np.linspace(0, 2 * np.pi, 361)
    pts = c + a * (np.outer(np.cos(t), orbit.Q[:, 0]) + np.outer(np.sin(t), orbit.Q[:, 1]))
    sc.polys.append(Poly(pts, label, 'muted', True, 1.0, 0.62))


def asymptotes(sc: Scene, orbit: Orbit, length=None, label='asymptotes'):
    e = orbit.e; a_abs = orbit.p / (e * e - 1); b = a_abs * np.sqrt(e * e - 1)
    th = np.arccos(-1 / e); C = orbit.Q @ np.array([a_abs * e, 0, 0]); L = length or 4 * a_abs * e
    for s, lab in ((-1, 'incoming asymptote'), (1, 'outgoing asymptote')):
        d = orbit.Q @ np.array([np.cos(th), s * np.sin(th), 0])
        sc.lines.append(Line(C - 0.35 * L * d, C + L * d, lab, 'muted', True, 1.0, 0.8 if s == 1 else 0.2))
        if s == 1: sc.pts.append(Pt(C, 'center', 'muted', '+', 5))
    return b


def aim_point_b(sc: Scene, orbit: Orbit, label_aim='aim point', label_b='b'):
    """Foot of the perpendicular from the focus onto the incoming asymptote (impact parameter b) and the
    hyperbola point at theta*_aim = -(theta*_inf - 90 deg). d_aim = |a| is measured from the hyperbola centre."""
    e = orbit.e; a_abs = orbit.p / (e * e - 1); b = a_abs * np.sqrt(e * e - 1)
    th = np.arccos(-1 / e); C = orbit.Q @ np.array([a_abs * e, 0, 0])
    d_in = orbit.Q @ np.array([np.cos(th), -np.sin(th), 0])            # direction of the incoming asymptote (to far side)
    foot = C + np.dot(-C, d_in) * d_in                                  # closest point of that line to the focus
    sc.lines.append(Line(np.zeros(3), foot, label_b + f' = {b:,.0f} km', 'warn', False, 1.4, 0.5))
    sc.lines.append(Line(C, foot, 'd_aim = |a|', 'muted', True, 1.0, 0.5))
    sc.pts.append(Pt(foot, label_aim, 'warn', 'D', 6))
    th_aim = -(np.degrees(th) - 90)
    sc.pts.append(Pt(orbit.pos(th_aim), 'θ*_aim', 'warn', 'o', 5))
    return foot, b


def vacant_focus(sc: Scene, orbit: Orbit, label='vacant focus F'):
    f2 = orbit.Q @ np.array([-2 * orbit.a * orbit.e, 0, 0]); sc.pts.append(Pt(f2, label, 'ink2', 'x', 7)); return f2


def nodes_line(sc: Scene, Om_deg: float, size: float, label='line of nodes'):
    n = np.array([np.cos(Om_deg * D2R), np.sin(Om_deg * D2R), 0.0])
    sc.lines.append(Line(-size * n, size * n, label, 'muted', True, 1.0, 0.97)); return n


def equatorial_plane(sc: Scene, size: float, label='equatorial plane'):
    sc.planes.append(Plane(np.array([0, 0, 1.0]), size, label))


def focus_marker(sc: Scene, label='F'):
    sc.pts.append(Pt(np.zeros(3), label, 'ink', 'o', 5))
