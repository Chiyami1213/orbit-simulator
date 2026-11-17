"""Mission data model (GMAT-style resources + command sequence). One model, saved as ``.orbitmission`` JSON, exported as a GMAT script.

Everything is stored in km, km/s, s, degrees. Spacecraft states are stored the way the user entered them (Cartesian or Keplerian,
in the named coordinate system) and converted when a mission runs.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
import json

INTEGRATORS = ('RungeKutta89', 'PrinceDormand78', 'PrinceDormand45', 'Kepler (analytic)')
DYNAMICS = ('two_body', 'patched', 'selected_nbody', 'solar_system', 'cr3bp')
DYNAMICS_LABEL = {'two_body': 'Two-body (course)', 'patched': 'Patched conics (SOI hand-offs)', 'selected_nbody': 'Selected N-body', 'solar_system': 'Full Solar System', 'cr3bp': 'Restricted three-body'}
KEPLER = ('SMA', 'ECC', 'INC', 'RAAN', 'AOP', 'TA')
CART = ('X', 'Y', 'Z', 'VX', 'VY', 'VZ')
AXES = ('MJ2000Eq', 'MJ2000Ec', 'BodyInertial')


@dataclass
class Spacecraft:
    name: str = 'Sat'
    date_format: str = 'UTCGregorian'              # UTCGregorian | UTCModJulian | TAIModJulian | A1ModJulian
    epoch: str = '01 Jan 2026 12:00:00.000'        # text in ``date_format`` (a number for the ModJulian formats)
    coord: str = 'EarthMJ2000Eq'
    state_type: str = 'Keplerian'                  # Keplerian | Cartesian
    state: dict = field(default_factory=lambda: dict(SMA=7000.0, ECC=0.0, INC=0.0, RAAN=0.0, AOP=0.0, TA=0.0))
    mass: float = 1000.0
    area: float = 10.0
    cr: float = 1.8
    color: str = '#ff6b4a'


@dataclass
class CoordSys:
    name: str = 'EarthMJ2000Eq'
    origin: str = 'Earth'
    axes: str = 'MJ2000Eq'


@dataclass
class Propagator:
    name: str = 'Prop'
    central: str = 'Earth'
    dynamics: str = 'two_body'
    gravity: list = field(default_factory=lambda: ['Earth'])       # point masses (central body first)
    integrator: str = 'RungeKutta89'
    initial_step: float = 60.0
    accuracy: float = 1e-12
    min_step: float = 0.001
    max_step: float = 86400.0
    j2: bool = False
    srp: bool = False
    drag: bool = False
    cr3bp_primary: str = 'Earth'
    cr3bp_secondary: str = 'Moon'


@dataclass
class Burn:
    name: str = 'DV1'
    origin: str = 'Earth'
    axes: str = 'VNB'                              # VNB | LVLH | MJ2000Eq
    e1: float = 0.0
    e2: float = 0.0
    e3: float = 0.0


@dataclass
class ReportFile:
    name: str = 'RF'
    filename: str = 'report.txt'
    params: list = field(default_factory=lambda: ['Sat.UTCGregorian', 'Sat.Earth.SMA', 'Sat.Earth.ECC', 'Sat.Earth.TA', 'Sat.Earth.RMAG'])
    precision: int = 8
    active: bool = True


@dataclass
class OrbitView:
    name: str = 'View'
    objects: list = field(default_factory=lambda: ['Sat', 'Earth'])
    coord: str = 'EarthMJ2000Eq'
    xy_plane: bool = True
    axes: bool = True
    grid: bool = False


@dataclass
class Command:
    kind: str                                      # Propagate | Maneuver | Report | Toggle
    enabled: bool = True
    # Propagate
    synchronized: bool = False
    items: list = field(default_factory=list)      # [[propagator, [sat, ...]], ...]
    stops: list = field(default_factory=list)      # ['Sat.Earth.TA = 120', 'Sat.Periapsis', ...]
    # Maneuver / Report / Toggle
    burn: str = ''
    sat: str = ''
    report: str = ''
    params: list = field(default_factory=list)
    on: bool = True

    def text(self) -> str:
        if self.kind == 'Propagate':
            body = ' '.join(f'{p}({", ".join(s)})' for p, s in self.items)
            return f'Propagate {"Synchronized " if self.synchronized else ""}{body} {{{", ".join(self.stops)}}}'
        if self.kind == 'Maneuver': return f'Maneuver {self.burn}({self.sat})'
        if self.kind == 'Report': return f'Report {self.report} {" ".join(self.params)}'.strip()
        if self.kind == 'Toggle': return f'Toggle {self.report} {"On" if self.on else "Off"}'
        return self.kind


@dataclass
class Mission:
    name: str = 'Mission'
    convention: str = 'course'                     # which convention the mission was shown in
    spacecraft: list = field(default_factory=list)
    coords: list = field(default_factory=list)
    propagators: list = field(default_factory=list)
    burns: list = field(default_factory=list)
    reports: list = field(default_factory=list)
    views: list = field(default_factory=list)
    commands: list = field(default_factory=list)
    notes: list = field(default_factory=list)      # '% expected: ...' lines carried into the GMAT script
    constants: str = 'Course table'

    # ---- lookups
    def sat(self, n): return next(s for s in self.spacecraft if s.name == n)
    def prop(self, n): return next(p for p in self.propagators if p.name == n)
    def burn(self, n): return next(b for b in self.burns if b.name == n)
    def report(self, n): return next(r for r in self.reports if r.name == n)
    def coord(self, n):
        for c in self.coords:
            if c.name == n: return c
        return coord_from_name(n)

    # ---- persistence
    def to_dict(self) -> dict:
        d = asdict(self); d['format'] = 'orbitmission'; d['version'] = 1; return d

    def to_json(self) -> str: return json.dumps(self.to_dict(), indent=1)

    @classmethod
    def from_dict(cls, d: dict) -> 'Mission':
        m = cls(name=d.get('name', 'Mission'), convention=d.get('convention', 'course'), notes=list(d.get('notes', [])), constants='Course table')                                  # JPL / GMAT constants only (older files may say otherwise)
        m.spacecraft = [Spacecraft(**x) for x in d.get('spacecraft', [])]; m.coords = [CoordSys(**x) for x in d.get('coords', [])]
        m.propagators = [Propagator(**x) for x in d.get('propagators', [])]; m.burns = [Burn(**x) for x in d.get('burns', [])]
        m.reports = [ReportFile(**x) for x in d.get('reports', [])]; m.views = [OrbitView(**x) for x in d.get('views', [])]
        m.commands = [Command(**x) for x in d.get('commands', [])]
        return m

    @classmethod
    def from_json(cls, s: str) -> 'Mission': return cls.from_dict(json.loads(s))


def coord_from_name(name: str) -> CoordSys:
    """'EarthMJ2000Eq' -> CoordSys(origin Earth, MJ2000Eq); 'LunaMJ2000Eq' -> Moon."""
    for ax in ('MJ2000Eq', 'MJ2000Ec', 'BodyInertial'):
        if name.endswith(ax):
            o = name[:-len(ax)] or 'Earth'; return CoordSys(name, 'Moon' if o == 'Luna' else o, ax)
    return CoordSys(name, 'Earth', 'MJ2000Eq')
