"""Import a subset of the GMAT script language into a Mission (own tokenizer, no dependencies).

Supported: ``Create`` of Spacecraft / ForceModel / Propagator / CoordinateSystem / ImpulsiveBurn / ReportFile / OrbitView, field assignments (with
or without the leading ``GMAT``), ``{...}`` lists, ``BeginMissionSequence``, ``Propagate`` (including ``Synchronized`` and stop conditions),
``Maneuver``, ``Report``, ``Toggle`` and ``%`` comments. Anything else is listed in ``ImportResult.skipped`` instead of failing.
GMAT is Apache-2.0 licensed software of NASA; nothing of it is used here except the public script syntax.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import re
from ..conventions import course_body
from ..mission.model import Mission, Spacecraft, CoordSys, Propagator, Burn, ReportFile, OrbitView, Command, coord_from_name
from ..mission import params as P

SUPPORTED = ('Spacecraft', 'ForceModel', 'Propagator', 'CoordinateSystem', 'ImpulsiveBurn', 'ReportFile', 'OrbitView')


@dataclass
class ImportResult:
    mission: Mission
    skipped: list = field(default_factory=list)
    notes: list = field(default_factory=list)


def strip_comments(text: str) -> str:
    out = []
    for line in text.splitlines():
        q = None; cut = len(line)
        for i, ch in enumerate(line):
            if ch in ("'", '"'):
                q = None if q == ch else (q or ch)
            elif ch == '%' and q is None: cut = i; break
        out.append(line[:cut])
    return '\n'.join(out)


def split_statements(text: str) -> list[str]:
    """Split on ';' outside quotes and braces/brackets."""
    stm, buf, q, depth = [], [], None, 0
    for ch in text:
        if ch in ("'", '"'): q = None if q == ch else (q or ch)
        if q is None:
            if ch in '{[': depth += 1
            elif ch in '}]': depth -= 1
            elif ch == ';' and depth <= 0:
                s = ''.join(buf).strip()
                if s: stm.append(' '.join(s.split()))
                buf = []; continue
        buf.append(ch)
    s = ''.join(buf).strip()
    if s: stm.append(' '.join(s.split()))
    return stm


def parse_value(v: str):
    v = v.strip()
    if v.startswith('{') and v.endswith('}'): return [x.strip().strip("'\"") for x in v[1:-1].split(',') if x.strip()]
    if v.startswith('[') and v.endswith(']'): return [parse_value(x) for x in v[1:-1].replace(',', ' ').split()]
    if len(v) >= 2 and v[0] in ("'", '"') and v[-1] == v[0]: return v[1:-1]
    try: return float(v)
    except ValueError: return v


def _bool(v) -> bool: return str(v).lower() in ('on', 'true', '1')


def import_script(text: str, name: str = 'Imported mission') -> ImportResult:
    m = Mission(name=name); res = ImportResult(m); res_skipped = res.skipped
    objs: dict[str, tuple[str, dict]] = {}                      # name -> (type, fields)
    in_sequence = False
    for stm in split_statements(strip_comments(text)):
        s = stm[5:].strip() if stm.startswith('GMAT ') else stm
        if s == 'BeginMissionSequence': in_sequence = True; continue
        head = s.split(' ', 1)[0]
        if not in_sequence:
            if head == 'Create':
                parts = s.split(None, 2)
                if len(parts) < 3: res_skipped.append(stm); continue
                typ = parts[1]
                for nm in [x.strip() for x in parts[2].split(',')]:
                    if typ in SUPPORTED: objs[nm] = (typ, {})
                    else: res_skipped.append(f'Create {typ} {nm}')
                continue
            mt = re.match(r'^([\w.]+)\s*=\s*(.+)$', s)
            if mt:
                path, val = mt.group(1), mt.group(2); nm, _, fld = path.partition('.')
                if nm in objs: objs[nm][1][fld] = parse_value(val)
                continue
            res_skipped.append(stm); continue
        # ---- mission sequence
        if head == 'Propagate':
            c = _parse_propagate(s, m, res)
            if c: m.commands.append(c)
        elif head == 'Maneuver':
            mt = re.match(r'^Maneuver\s+(\w+)\s*\(\s*(\w+)\s*\)$', s)
            if mt: m.commands.append(Command('Maneuver', burn=mt.group(1), sat=mt.group(2)))
            else: res_skipped.append(stm)
        elif head == 'Report':
            toks = s.split(); m.commands.append(Command('Report', report=toks[1], params=toks[2:]))
        elif head == 'Toggle':
            toks = s.split()
            if len(toks) >= 3: m.commands.append(Command('Toggle', report=toks[1], on=_bool(toks[2])))
        else: res_skipped.append(stm)
    _build_resources(m, objs, res)
    return res


def _parse_propagate(s: str, m: Mission, res: ImportResult):
    body = s[len('Propagate'):].strip(); sync = False
    if body.startswith('Synchronized'): sync = True; body = body[len('Synchronized'):].strip()
    stops = []
    mt = re.search(r'\{([^}]*)\}\s*$', body)
    if mt: stops = [x.strip() for x in mt.group(1).split(',') if x.strip()]; body = body[:mt.start()].strip()
    items = [[p, [x.strip() for x in a.split(',')]] for p, a in re.findall(r'(\w+)\s*\(([^)]*)\)', body)]
    if not items:
        res.skipped.append(s); return None
    if any(re.search(r'\bBackProp\b|\.Epoch\b|Converge', x) for x in stops): res.notes.append(f'stop condition not modelled: {stops}')
    return Command('Propagate', synchronized=sync, items=items, stops=[_course_stop(x) for x in stops])


def _course_stop(x: str) -> str:
    return re.sub(r'\bLuna\b', 'Moon', x)


def _build_resources(m: Mission, objs: dict, res: ImportResult):
    fms: dict[str, dict] = {n: f for n, (t, f) in objs.items() if t == 'ForceModel'}
    for n, (t, f) in objs.items():
        if t == 'Spacecraft':
            sc = Spacecraft(name=n, date_format=str(f.get('DateFormat', 'UTCGregorian')), coord=str(f.get('CoordinateSystem', 'EarthMJ2000Eq')),
                            state_type=str(f.get('DisplayStateType', 'Keplerian')))
            ep = f.get('Epoch', '01 Jan 2000 12:00:00.000'); sc.epoch = ep if isinstance(ep, str) else repr(ep)
            if sc.date_format != 'UTCGregorian': sc.epoch = str(float(sc.epoch))
            keys = P.KEP_PARAMS[:6] if sc.state_type == 'Keplerian' else P.CART_PARAMS[:6]
            sc.state = {k: float(f.get(k, 0.0)) for k in keys}
            sc.mass = float(f.get('DryMass', 1000.0)); sc.cr = float(f.get('Cr', 1.8)); sc.area = float(f.get('SRPArea', 10.0))
            m.spacecraft.append(sc)
        elif t == 'Propagator':
            fm = fms.get(str(f.get('FM', '')), {}); central = course_body(str(fm.get('CentralBody', 'Earth')))
            bodies = [course_body(b) for b in (fm.get('PrimaryBodies', []) if isinstance(fm.get('PrimaryBodies'), list) else [])]
            bodies += [course_body(b) for b in (fm.get('PointMasses', []) if isinstance(fm.get('PointMasses'), list) else [])]
            if central not in bodies: bodies.insert(0, central)
            typ = str(f.get('Type', 'RungeKutta89'))
            if typ not in ('RungeKutta89', 'PrinceDormand78', 'PrinceDormand45'):
                res.notes.append(f'{n}: integrator {typ} is not available here; RungeKutta89 is used instead'); typ = 'RungeKutta89'
            dyn = 'two_body' if len(set(bodies)) == 1 else 'selected_nbody'
            if any(k.startswith('GravityField') for k in fm) or (fm.get('Drag') not in (None, 'None') and 'Drag.AtmosphereModel' in fm):
                res.notes.append(f'{n}: spherical-harmonic gravity and drag are not modelled; point masses only')
            m.propagators.append(Propagator(name=n, central=central, dynamics=dyn, gravity=list(dict.fromkeys(bodies)), integrator=typ,
                                            initial_step=float(f.get('InitialStepSize', 60)), accuracy=float(f.get('Accuracy', 1e-12)), min_step=float(f.get('MinStep', 0.001)),
                                            max_step=float(f.get('MaxStep', 86400)), srp=_bool(fm.get('SRP', 'Off'))))
        elif t == 'CoordinateSystem':
            m.coords.append(CoordSys(n, course_body(str(f.get('Origin', 'Earth'))), str(f.get('Axes', 'MJ2000Eq'))))
        elif t == 'ImpulsiveBurn':
            m.burns.append(Burn(n, course_body(str(f.get('Origin', 'Earth'))), str(f.get('Axes', 'VNB')), float(f.get('Element1', 0)), float(f.get('Element2', 0)), float(f.get('Element3', 0))))
        elif t == 'ReportFile':
            m.reports.append(ReportFile(n, str(f.get('Filename', n + '.txt')), [_course_stop(x) for x in f.get('Add', [])] if isinstance(f.get('Add'), list) else []))
        elif t == 'OrbitView':
            m.views.append(OrbitView(n, [course_body(x) for x in f.get('Add', [])] if isinstance(f.get('Add'), list) else [], str(f.get('CoordinateSystem', 'EarthMJ2000Eq')),
                                     _bool(f.get('XYPlane', 'On')), _bool(f.get('Axes', 'On')), _bool(f.get('Grid', 'Off'))))
