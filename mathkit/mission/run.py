"""Run a Mission: convert resources to propagator states, execute the command sequence, collect trajectories, events, burns and reports.

Internal frame while running: centered on each propagator's central body, MJ2000Eq axes, km and km/s. Epochs are UTC Julian dates;
ephemeris-driven models convert to TDB through ``core.timeutil``.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import re
import numpy as np
from ..core.constants import ConstantSet, BODIES, D2R, R2D, wrap180
from ..core.elements import rv_from_elements, elements_from_rv
from ..core import timeutil as TU
from ..conventions import vnb_from_dv_alpha_beta, dv_alpha_beta_from_vnb, course_body
from ..dyn.integrators import propagate, Event
from ..dyn.models import two_body_rhs, kepler_propagate, NBodyModel, Perturbation, CR3BP, J2
from . import params as P
from .model import Mission, Propagator, Spacecraft, Command

AUX_BODIES = ('Sun', 'Moon', 'Mercury', 'Venus', 'Earth', 'Mars', 'Jupiter', 'Saturn', 'Uranus', 'Neptune', 'Pluto')


@dataclass
class SatState:
    name: str
    central: str
    r: np.ndarray
    v: np.ndarray
    jd: float                      # UTC Julian date
    jd_start: float
    color: str = '#ff6b4a'


@dataclass
class RunResult:
    samples: dict = field(default_factory=dict)       # sat -> dict(jd=[...], r=[[...]], v=[[...]], central=[...], seg=[...])
    events: list = field(default_factory=list)        # dict(sat, jd, text, kind)
    burns: list = field(default_factory=list)
    reports: dict = field(default_factory=dict)       # name -> dict(columns, rows)
    final: dict = field(default_factory=dict)         # sat -> SatState
    start: dict = field(default_factory=dict)         # sat -> SatState
    warnings: list = field(default_factory=list)
    log: list = field(default_factory=list)
    mission: Mission | None = None


class MissionError(ValueError):
    pass


# ---- initial state -------------------------------------------------------------------------------------------------------------------------
def initial_state(m: Mission, sc: Spacecraft, consts: ConstantSet, eph=None) -> SatState:
    cs = m.coord(sc.coord); jd = P.parse_epoch(sc.epoch, sc.date_format); mu = consts.mu(cs.origin)
    if sc.state_type == 'Keplerian':
        s = sc.state; ecc = s['ECC']; sma = s['SMA']
        if ecc < 1 and sma <= 0: raise MissionError(f'{sc.name}: an elliptical orbit needs SMA > 0 (got {sma})')
        if ecc > 1 and sma >= 0: raise MissionError(f'{sc.name}: a hyperbolic orbit needs SMA < 0 (got {sma})')
        if abs(ecc - 1) < 1e-12: raise MissionError(f'{sc.name}: parabolic orbits (ECC = 1) are not supported')
        r, v, _ = rv_from_elements(mu, sma, ecc, s['INC'], s['RAAN'], s['AOP'], wrap180(s['TA']))
    else:
        s = sc.state; r = np.array([s['X'], s['Y'], s['Z']], float); v = np.array([s['VX'], s['VY'], s['VZ']], float)
    M = P.axes_matrix(cs.axes, cs.origin); r = M.T @ r; v = M.T @ v                  # to MJ2000Eq components
    return SatState(sc.name, cs.origin, r, v, jd, jd, sc.color)


def recentre(st: SatState, central: str, eph) -> SatState:
    """Express a state about another body (needs an ephemeris)."""
    if st.central == central: return st
    if eph is None: raise MissionError(f'{st.name} is defined about {st.central} but its propagator is centered on {central}; an ephemeris is needed to convert')
    jd_tdb = TU.utc_to_tdb(st.jd); rc, vc = eph.state(st.central, jd_tdb, central)
    return SatState(st.name, central, st.r + rc, st.v + vc, st.jd, st.jd_start, st.color)


# ---- dynamics ----------------------------------------------------------------------------------------------------------------------------------
def build_rhs(prop: Propagator, sc_mass: Spacecraft | None, consts: ConstantSet, eph, jd0_utc: float):
    """Right-hand side f(t, y) for a propagator (t in seconds from jd0_utc), or None for the analytic Kepler integrator."""
    if prop.integrator == 'Kepler (analytic)' or prop.dynamics == 'two_body':
        return two_body_rhs(consts.mu(prop.central))
    if eph is None: raise MissionError('this force model needs an ephemeris')
    if prop.dynamics == 'solar_system': pert = [b for b in AUX_BODIES if b != prop.central and b in getattr(eph, 'bodies', AUX_BODIES)]
    else: pert = [b for b in prop.gravity if b != prop.central]
    fo = Perturbation(j2=prop.j2, srp=prop.srp, drag=prop.drag)
    if sc_mass is not None: fo.area, fo.mass, fo.cr = sc_mass.area, sc_mass.mass, sc_mass.cr
    mdl = NBodyModel(prop.central, consts.mu(prop.central), {b: consts.mu(b) for b in pert}, eph, TU.utc_to_tdb(jd0_utc), fo,
                     R_central=consts.R(prop.central), j2_central=J2.get(prop.central, 0.0))
    return mdl.rhs()


# ---- stop conditions ---------------------------------------------------------------------------------------------------------------------------------
@dataclass
class Stop:
    text: str
    sat: str
    kind: str                       # Periapsis | Apoapsis | param
    param: str = ''
    value: float = 0.0
    body: str = ''                  # origin body of the parameter (TA, RMAG ...)


def parse_stop(text: str, central_of) -> Stop:
    t = text.strip()
    m = re.match(r'^(\w+)\.(?:\w+\.)?(Periapsis|Apoapsis)$', t)
    if m: return Stop(t, m.group(1), m.group(2))
    m = re.match(r'^(\w+)\.((?:\w+\.)?\w+)\s*=\s*([-+0-9.eE]+)$', t)
    if not m: raise MissionError(f'cannot read the stop condition "{text}"')
    sat, rest, val = m.group(1), m.group(2), float(m.group(3)); parts = rest.split('.')
    return Stop(t, sat, 'param', parts[-1], val, course_body(parts[0]) if len(parts) == 2 else central_of(sat))


def stop_events(stops: list[Stop], sat_name: str, mu_of_body, ctx_state):
    """Event objects for the stops that belong to one spacecraft. ``ctx_state(t, y)`` -> (r, v) in the stop's body frame is supplied by the caller."""
    evs = []
    for s in stops:
        if s.sat != sat_name: continue
        mu = mu_of_body(s.body or '')
        if s.kind == 'Periapsis': evs.append(Event(lambda t, y: y[:3] @ y[3:], s.text, +1))
        elif s.kind == 'Apoapsis': evs.append(Event(lambda t, y: y[:3] @ y[3:], s.text, -1))
        elif s.param == 'TA':
            def g(t, y, mu=mu, x=s.value):
                el = elements_from_rv(mu, y[:3], y[3:]); return float(wrap180(el['ths'] - x))
            evs.append(Event(g, s.text, +1, accept=lambda t, y, g=g: abs(g(t, y)) < 90.0))
        elif s.param == 'RMAG': evs.append(Event(lambda t, y, x=s.value: float(np.linalg.norm(y[:3]) - x), s.text, 0))
        elif s.param in ('ElapsedSecs', 'ElapsedDays'):
            x = s.value * (86400.0 if s.param == 'ElapsedDays' else 1.0); evs.append(Event(lambda t, y, x=x: t - x, s.text, +1))
        else: raise MissionError(f'unsupported stop condition "{s.text}"')
    return evs


# ---- the run -------------------------------------------------------------------------------------------------------------------------------------------
def _maneuver_dv(burn, r, v, mu):
    if burn.axes == 'MJ2000Eq': return np.array([burn.e1, burn.e2, burn.e3], float)
    V = v / np.linalg.norm(v); N = np.cross(r, v); N /= np.linalg.norm(N); B = np.cross(V, N)
    if burn.axes == 'VNB': return burn.e1 * V + burn.e2 * N + burn.e3 * B
    if burn.axes == 'LVLH':                                        # GMAT: X radial, Z = -orbit normal, Y = Z x X
        X = r / np.linalg.norm(r); Z = -N; Y = np.cross(Z, X); return burn.e1 * X + burn.e2 * Y + burn.e3 * Z
    raise MissionError(f'burn axes {burn.axes} are not supported')


def run(m: Mission, eph=None, consts: ConstantSet | None = None, progress=None, max_duration_days: float = 3650.0 * 5) -> RunResult:
    consts = consts or ConstantSet(m.constants); res = RunResult(mission=m)
    states: dict[str, SatState] = {}
    for sc in m.spacecraft:
        states[sc.name] = initial_state(m, sc, consts, eph); res.start[sc.name] = initial_state(m, sc, consts, eph)
        res.samples[sc.name] = dict(jd=[], r=[], v=[], central=[], seg=[], cmd=[], tc=[])
    reports_on = {r.name: r.active for r in m.reports}
    for r in m.reports: res.reports[r.name] = dict(columns=list(r.params), rows=[], units=[P.UNITS.get(p.split('.')[-1], '') for p in r.params], filename=r.filename, precision=r.precision)
    seg_id = [0]; n_cmd = len(m.commands); ctx = dict(ci=0, t0={})

    def record(st: SatState, jd, r, v):
        s = res.samples[st.name]; s['cmd'].append(ctx['ci']); s['tc'].append((jd - ctx['t0'].get(st.name, jd)) * 86400.0); s['jd'].append(jd); s['r'].append(np.asarray(r, float)); s['v'].append(np.asarray(v, float)); s['central'].append(st.central); s['seg'].append(seg_id[0])

    def report_row(sat: str, st: SatState, jd, r, v, only: str | None = None):
        for rf in m.reports:
            if (only is None and not reports_on.get(rf.name)) or (only is not None and rf.name != only): continue
            if not any(p.split('.')[0] == sat for p in rf.params): continue
            ctx = P.ParamContext(st.central, r, v, jd, st.jd_start, consts, eph)
            row = []
            for pn in rf.params:
                try: row.append(P.evaluate(pn, ctx) if pn.split('.')[0] == sat else None)
                except ValueError as ex: row.append(f'n/a ({ex})')
            res.reports[rf.name]['rows'].append(row)

    for ci, cmd in enumerate(m.commands):
        if not cmd.enabled: continue
        ctx['ci'] = ci; ctx['t0'] = {n_: s_.jd for n_, s_ in states.items()}
        if progress: progress(f'{cmd.text()}', ci / max(1, n_cmd))
        if cmd.kind == 'Toggle': reports_on[cmd.report] = cmd.on; continue
        if cmd.kind == 'Report':
            st = states[cmd.params[0].split('.')[0]] if cmd.params else None
            if st is not None:
                ctx = P.ParamContext(st.central, st.r, st.v, st.jd, st.jd_start, consts, eph)
                res.reports.setdefault(cmd.report, dict(columns=list(cmd.params), rows=[], units=[], filename='', precision=8))['rows'].append([P.evaluate(p, ctx) for p in cmd.params])
            continue
        if cmd.kind == 'Maneuver':
            st = states[cmd.sat]; burn = m.burn(cmd.burn); mu = consts.mu(st.central)
            dvec = _maneuver_dv(burn, st.r, st.v, mu); dv, alpha, beta = dv_alpha_beta_from_vnb(*vnb_from_vec(st.r, st.v, dvec))
            seg_id[0] += 1; st.v = st.v + dvec
            res.burns.append(dict(sat=st.name, burn=burn.name, jd=st.jd, dv_vec=dvec.tolist(), dv=float(np.linalg.norm(dvec)), E=list(vnb_from_vec(st.r, st.v - dvec, dvec)), alpha=alpha, beta=beta, central=st.central))
            res.events.append(dict(sat=st.name, jd=st.jd, text=f'{burn.name}: Δv = {np.linalg.norm(dvec):.6g} km/s', kind='burn'))
            record(st, st.jd, st.r, st.v); continue
        if cmd.kind == 'Propagate':
            _propagate_command(m, cmd, states, res, consts, eph, record, report_row, seg_id, max_duration_days, progress, ci / max(1, n_cmd))
    for k, st in states.items(): res.final[k] = st
    for rn, rep in res.reports.items():
        pass
    return res


def vnb_from_vec(r, v, dvec):
    """Components of a Δv vector on (V, N, B) at the state (r, v)."""
    V = v / np.linalg.norm(v); N = np.cross(r, v); N /= np.linalg.norm(N); B = np.cross(V, N)
    return float(dvec @ V), float(dvec @ N), float(dvec @ B)


def _propagate_command(m, cmd, states, res, consts, eph, record, report_row, seg_id, max_days, progress, frac0):
    cent = lambda sat: states[sat].central
    stops = [parse_stop(s, cent) for s in cmd.stops]
    items = [(m.prop(p), list(sats)) for p, sats in cmd.items]
    for prop, sats in items:
        for s in sats:
            if s not in states: raise MissionError(f'Propagate uses the unknown spacecraft "{s}"')
            states[s] = recentre(states[s], prop.central, eph)
    seg_id[0] += 1

    def trajectory(prop, sat, until_events: list[Event] | None, dt_max: float):
        """Propagate one spacecraft from its state; returns (t_s array, y array, stop_events found)."""
        st = states[sat]; sc = m.sat(sat); y0 = np.concatenate([st.r, st.v])
        if prop.dynamics == 'cr3bp': return _cr3bp(prop, st, until_events or [], dt_max, consts, eph)
        if prop.dynamics == 'patched': return _patched(prop, st, until_events or [], dt_max, consts, eph)
        f = build_rhs(prop, sc, consts, eph, st.jd)
        if prop.integrator == 'Kepler (analytic)':
            return _analytic(prop, st, until_events or [], dt_max, consts)
        sol = propagate(f, y0, 0.0, dt_max, method=prop.integrator, accuracy=prop.accuracy, h0=prop.initial_step, h_min=prop.min_step, h_max=prop.max_step,
                        events=until_events or [], min_points=360)
        return sol.t, sol.y, sol.events

    def default_dt(prop, sat):
        mu = consts.mu(prop.central); st = states[sat]; el = elements_from_rv(mu, st.r, st.v)
        return (el['P'] * 50.0 if el['e'] < 1 else 86400.0 * max_days)

    def mu_of(body): return consts.mu(body or next(iter(states.values())).central)

    # 1. when does the command stop? (first condition to occur, over every spacecraft it names)
    dts = []; cache = {}
    for prop, sats in items:
        for sat in sats:
            evs = stop_events(stops, sat, mu_of, None)
            if not evs: continue
            limit = default_dt(prop, sat)
            for e in evs: e.terminal = True
            t, y, ev = trajectory(prop, sat, evs, limit)
            if ev:
                dts.append((ev[0][0], ev[0][2], sat)); cache[sat] = (t, y)
            else: res.warnings.append(f'"{evs[0].name}" was not reached within {limit / 86400:.1f} days for {sat}')
    if not stops: raise MissionError(f'"{cmd.text()}" has no stop condition')
    if not dts: raise MissionError(f'none of the stop conditions in "{cmd.text()}" was reached')
    dt_stop, why, who = min(dts, key=lambda x: x[0])
    # 2. propagate everything to that moment (synchronized or not, spacecraft do not act on each other)
    for prop, sats in items:
        for sat in sats:
            st = states[sat]
            if sat == who and sat in cache and abs(cache[sat][0][-1] - dt_stop) < 1e-9: t, y = cache[sat]                  # the search already integrated this arc
            else: t, y, _ = trajectory(prop, sat, [], dt_stop)
            for k in range(len(t)):
                jd = st.jd + t[k] / 86400.0; record(st, jd, y[k, :3], y[k, 3:]); report_row(sat, st, jd, y[k, :3], y[k, 3:])
            st_jd0 = st.jd; st.r, st.v, st.jd = y[-1, :3].copy(), y[-1, 3:].copy(), st.jd + t[-1] / 86400.0
            pp = PATHS.pop(sat, None)
            if pp is not None:
                for h in pp.handoffs:
                    if h['t'] <= t[-1] + 1e-6: res.events.append(dict(sat=sat, jd=st_jd0 + h['t'] / 86400.0, text=h['text'], kind=h['kind']))
            res.events.append(dict(sat=sat, jd=st.jd, text=f'stop: {why}' if sat == who else f'propagated to the common epoch ({why})', kind='stop'))


def _analytic(prop, st, events, dt_max, consts, state_fn=None):
    """Kepler solution (or any analytic ``state_fn(t)``) sampled finely, with event refinement by bracketing on the sampled orbit."""
    mu = consts.mu(prop.central); el = elements_from_rv(mu, st.r, st.v)
    sf = state_fn or (lambda t: np.concatenate(kepler_propagate(mu, st.r, st.v, t)))
    span = dt_max; n = 800 if el['e'] < 1 else 600
    ts = np.unique(np.concatenate([np.linspace(0.0, span, n + 1), np.geomspace(max(span * 1e-9, 1.0), span, 500)])); n = len(ts) - 1; ys = np.array([sf(t) for t in ts])
    found = []; tcut = span
    if events:
        from ..dyn.integrators import _illinois
        for ev in events:
            g = [ev.fn(t, y) for t, y in zip(ts, ys)]
            for i in range(n):
                a, b = g[i], g[i + 1]
                crossed = (a < 0 <= b) if ev.direction > 0 else (a > 0 >= b) if ev.direction < 0 else (a * b < 0)
                if not crossed: continue
                te = _illinois(lambda t: ev.fn(t, sf(t)), ts[i], ts[i + 1], a, b, tol=1e-9)
                ye = sf(te)
                if ev.accept is not None and not ev.accept(te, ye): continue
                found.append((te, ye, ev.name)); break
        if found:
            found.sort(key=lambda x: x[0]); tcut = found[0][0]
    keep = ts < tcut; t_out = np.concatenate([ts[keep], [tcut]]); y_out = np.array([sf(t) for t in t_out])
    return t_out, y_out, found[:1]


PATHS: dict = {}                                   # sat -> PatchedPath of the latest patched-conic arc (for the hand-off events)


def _patched(prop, st, events, dt_max, consts, eph):
    from .patched import PatchedPath
    if eph is None: raise MissionError('the patched-conic model needs an ephemeris')
    path = PatchedPath(consts, eph, st.jd, prop.central, st.r, st.v, prop.central, dt_max); PATHS[st.name] = path
    return _analytic(prop, st, events, dt_max, consts, state_fn=path.state)


def _cr3bp(prop, st, events, dt_max, consts, eph):
    """Circular restricted three-body run. The spacecraft state is about the primary (inertial axes); the rotating frame is aligned at t = 0 with the
    secondary's position and orbit normal taken from the ephemeris (or from a circular orbit in the equator plane without one)."""
    mu1, mu2 = consts.mu(prop.cr3bp_primary), consts.mu(prop.cr3bp_secondary)
    if eph is not None and prop.cr3bp_secondary in getattr(eph, 'bodies', ()) and prop.cr3bp_primary in getattr(eph, 'bodies', ()):
        rs, vs = eph.state(prop.cr3bp_secondary, TU.utc_to_tdb(st.jd), prop.cr3bp_primary)
    else:
        a0 = BODIES[prop.cr3bp_secondary].get('a') or 384400.0; rs = np.array([a0, 0, 0.0]); vs = np.array([0, np.sqrt((mu1 + mu2) / a0), 0.0])
    L = float(np.linalg.norm(rs)); sys = CR3BP.from_bodies(mu1, mu2, L); T = sys.T; mu = sys.mu
    ex = rs / L; ez = np.cross(rs, vs); ez /= np.linalg.norm(ez); ey = np.cross(ez, ex); Rm = np.array([ex, ey, ez])          # rows: rotating axes in inertial components
    def to_rot(r, v):
        rb = Rm @ r + np.array([-mu * L, 0, 0]); vb = Rm @ v + np.array([0, -mu * L / T, 0]); x = rb / L; vn = vb / (L / T)
        return np.concatenate([x, [vn[0] + x[1], vn[1] - x[0], vn[2]]])
    def to_in(y, t):
        r, v = sys.to_inertial(y, t); c, s_ = np.cos(t), np.sin(t)
        r = r - mu * L * np.array([c, s_, 0]); v = v - mu * L / T * np.array([-s_, c, 0])        # primary-centered, still in the rotating-aligned (t = 0) axes
        return Rm.T @ r, Rm.T @ v
    evs = [Event((lambda t, y, ev=ev: ev.fn(t * T, np.concatenate(to_in(y, t)))), ev.name, ev.direction, ev.terminal, (None if ev.accept is None else (lambda t, y, ev=ev: ev.accept(t * T, np.concatenate(to_in(y, t)))))) for ev in events]
    y0 = to_rot(st.r, st.v)
    sol = propagate(sys.rhs(), y0, 0.0, dt_max / T, method=prop.integrator if prop.integrator != 'Kepler (analytic)' else 'RungeKutta89', accuracy=prop.accuracy,
                    h0=0.01, h_min=1e-9, h_max=0.05, events=evs, min_points=360)
    ys = np.array([np.concatenate(to_in(y, t)) for t, y in zip(sol.t, sol.y)])
    return sol.t * T, ys, [(t * T, np.concatenate(to_in(y, t)), n) for t, y, n in sol.events]
