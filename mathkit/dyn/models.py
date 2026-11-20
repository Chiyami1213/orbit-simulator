"""Dynamics models for the Mission workspace. State vector y = [x, y, z, vx, vy, vz] in km and km/s, inertial axes (ICRF ~ EarthMJ2000Eq),
centered on the model's central body. Time is seconds past the model epoch (TDB for ephemeris-driven models).

1  two-body       central body only (the analytic course model; numerically integrated here, or solved exactly by ``kepler_propagate``)
2  CR3BP          circular restricted three-body problem in the rotating frame (see ``CR3BP``)
3  patched conics see ``mathkit/mission/patched.py``
4  selected N-body   central body + the bodies ticked 'Gravity'
5  full Solar System every ephemeris body
Direct + indirect third-body form, as documented in core/nbody.py:  a = -mu_c r/r^3 + sum_j mu_j [ (d_j - r)/|d_j - r|^3 - d_j/|d_j|^3 ]
with d_j the position of body j relative to the central body.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import numpy as np
from ..core.constants import D2R, R2D
from ..core.elements import rv_from_elements, elements_from_rv
from ..core.kepler import propagate as kepler_prop_theta


def two_body_accel(mu: float, r: np.ndarray) -> np.ndarray:
    return -mu * r / np.linalg.norm(r) ** 3


def two_body_rhs(mu: float):
    def f(t, y):
        return np.concatenate([y[3:], two_body_accel(mu, y[:3])])
    return f


def kepler_propagate(mu: float, r0, v0, dt: float):
    """Exact two-body propagation using the verified course solver (ellipse or hyperbola). Returns (r, v)."""
    r0 = np.asarray(r0, float); v0 = np.asarray(v0, float)
    if dt == 0: return r0.copy(), v0.copy()
    el = elements_from_rv(mu, r0, v0)
    ths = kepler_prop_theta(mu, el['a'], el['e'], el['ths'], dt)
    r, v, _ = rv_from_elements(mu, el['a'], el['e'], el['inc'], el['Om'], el['om'], ths)
    return r, v


@dataclass
class Perturbation:
    """Optional forces for models 4 and 5."""
    j2: bool = False
    srp: bool = False
    drag: bool = False
    area: float = 10.0          # m^2
    mass: float = 1000.0        # kg
    cr: float = 1.8
    cd: float = 2.2


J2 = {'Earth': 1.08262668e-3, 'Mars': 1.96045e-3, 'Moon': 2.0323e-4, 'Venus': 4.458e-6, 'Jupiter': 1.4736e-2, 'Saturn': 1.6298e-2}
POLE = {'Earth': (0.0, 90.0), 'Mars': (317.68143, 52.88650), 'Moon': (269.9949, 66.5392)}      # IAU pole (RA, Dec) in degrees


def pole_vector(body: str) -> np.ndarray:
    ra, dec = POLE.get(body, (0.0, 90.0)); ra, dec = ra * D2R, dec * D2R
    return np.array([np.cos(dec) * np.cos(ra), np.cos(dec) * np.sin(ra), np.sin(dec)])


@dataclass
class NBodyModel:
    """Spacecraft acceleration about ``central`` with ``perturbers`` taken from the ephemeris provider ``eph``.

    ``eph.state(body, jd_tdb, center)`` returns (r, v) in km, km/s; ``epoch_jd_tdb`` is the model's t = 0.
    """
    central: str
    mu_central: float
    perturbers: dict                # name -> mu (km^3 s^-2)
    eph: object
    epoch_jd_tdb: float
    forces: Perturbation = field(default_factory=Perturbation)
    R_central: float = 0.0
    j2_central: float = 0.0
    sun_mu: float = 132712440017.99

    def jd(self, t: float) -> float: return self.epoch_jd_tdb + t / 86400.0

    def rhs(self):
        names = list(self.perturbers); mus = np.array([self.perturbers[n] for n in names]); eph = self.eph; central = self.central
        fo = self.forces; Rc = self.R_central; j2c = self.j2_central; pole = pole_vector(central)
        def f(t, y):
            r = y[:3]; rn = np.linalg.norm(r); a = -self.mu_central * r / rn ** 3
            jd = self.jd(t)
            for n, mu in zip(names, mus):
                d = eph.position(n, jd, central); s = d - r
                a += mu * (s / np.linalg.norm(s) ** 3 - d / np.linalg.norm(d) ** 3)
            if fo.j2 and j2c and Rc:                       # J2 of the central body about its pole axis
                z = r @ pole; k = 1.5 * j2c * self.mu_central * Rc ** 2 / rn ** 5; zr = (z / rn) ** 2
                a += k * ((5 * zr - 1) * r - 2 * z * pole)
            if fo.srp:                                     # cannonball radiation pressure, 1 AU solar flux
                sun = eph.position('Sun', jd, central); s = r - sun; sn = np.linalg.norm(s)
                P = 4.56e-6 * (149597870.7 / sn) ** 2          # N m^-2 at distance sn from the Sun (1 AU: 4.56e-6)
                a += fo.cr * P * fo.area / fo.mass * 1e-3 * s / sn   # km s^-2
            if fo.drag and central in ('Earth', 'Mars'):
                alt = rn - Rc
                if 0 < alt < 1000:
                    rho0, H = (1.225e9, 8.5) if central == 'Earth' else (0.020e9, 11.1)             # kg km^-3 at the surface, scale height km
                    rho = rho0 * np.exp(-alt / H)
                    om = 7.2921159e-5 if central == 'Earth' else 7.0882e-5
                    vrel = y[3:] - np.cross([0, 0, om], r); vn = np.linalg.norm(vrel)
                    a += -0.5 * rho * fo.cd * fo.area * 1e-6 / fo.mass * vn * vrel
            return np.concatenate([y[3:], a])
        return f


# ---------------------------------------------------------------------------------------------------------------------------
# Circular restricted three-body problem (non-dimensional rotating frame, barycenter at the origin)
# ---------------------------------------------------------------------------------------------------------------------------
@dataclass
class CR3BP:
    mu: float                  # m2 / (m1 + m2)
    L: float                   # separation (km): unit of length
    T: float                   # 1 / n (s): unit of time  (n = sqrt((mu1 + mu2) / L^3))

    @classmethod
    def from_bodies(cls, mu1: float, mu2: float, L: float) -> 'CR3BP':
        n = np.sqrt((mu1 + mu2) / L ** 3)
        return cls(mu2 / (mu1 + mu2), L, 1.0 / n)

    def rhs(self):
        mu = self.mu
        def f(t, y):
            x, yy, z, vx, vy, vz = y
            r1 = np.sqrt((x + mu) ** 2 + yy ** 2 + z ** 2); r2 = np.sqrt((x - 1 + mu) ** 2 + yy ** 2 + z ** 2)
            ax = x + 2 * vy - (1 - mu) * (x + mu) / r1 ** 3 - mu * (x - 1 + mu) / r2 ** 3
            ay = yy - 2 * vx - (1 - mu) * yy / r1 ** 3 - mu * yy / r2 ** 3
            az = -(1 - mu) * z / r1 ** 3 - mu * z / r2 ** 3
            return np.array([vx, vy, vz, ax, ay, az])
        return f

    def jacobi(self, y) -> float:
        mu = self.mu; x, yy, z, vx, vy, vz = y
        r1 = np.sqrt((x + mu) ** 2 + yy ** 2 + z ** 2); r2 = np.sqrt((x - 1 + mu) ** 2 + yy ** 2 + z ** 2)
        return x * x + yy * yy + 2 * (1 - mu) / r1 + 2 * mu / r2 - (vx * vx + vy * vy + vz * vz)

    def lagrange_points(self) -> dict:
        """L1..L5 on the x axis / triangular points, positions in the non-dimensional rotating frame (barycentric)."""
        mu = self.mu
        def root(p):                                  # collinear point: real root near the wanted interval of the quintic in gamma
            r = np.roots(p); r = r[np.abs(r.imag) < 1e-9].real; return r
        g1 = [r for r in root([1, -(3 - mu), 3 - 2 * mu, -mu, 2 * mu, -mu]) if 0 < r < 1][0]                  # L1: x = 1 - mu - g
        g2 = [r for r in root([1, 3 - mu, 3 - 2 * mu, -mu, -2 * mu, -mu]) if r > 0][0]                       # L2: x = 1 - mu + g
        g3 = [r for r in root([1, 2 + mu, 1 + 2 * mu, -(1 - mu), -2 * (1 - mu), -(1 - mu)]) if r > 0][0]      # L3: x = -mu - g
        return {'L1': np.array([1 - mu - g1, 0, 0]), 'L2': np.array([1 - mu + g2, 0, 0]), 'L3': np.array([-mu - g3, 0, 0]),
                'L4': np.array([0.5 - mu, np.sqrt(3) / 2, 0]), 'L5': np.array([0.5 - mu, -np.sqrt(3) / 2, 0])}

    def to_inertial(self, y, t):
        """Rotating non-dimensional state -> inertial dimensional (km, km/s), barycenter at the origin, frame aligned at t = 0."""
        c, s = np.cos(t), np.sin(t); x, yy, z, vx, vy, vz = y
        R = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
        r = R @ np.array([x, yy, z]); v = R @ np.array([vx - yy, vy + x, vz])
        return r * self.L, v * self.L / self.T


def soi_radius(a: float, m: float, M: float) -> float:
    """Laplace sphere of influence radius r_SOI = a (m / M)^(2/5)."""
    return a * (m / M) ** 0.4
