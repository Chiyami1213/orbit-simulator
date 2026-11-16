"""Result / Step containers shared by every module (inputs, intermediates, quadrant checks, warnings, scene)."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
import numpy as np

# Unit strings (centre dot, superscripts) used everywhere
KM = 'km'; KMS = 'km·s⁻¹'; MU = 'km³·s⁻²'; EPS = 'km²·s⁻²'; HU = 'km²·s⁻¹'; DEG = '°'; SEC = 's'; HR = 'h'
DAY = 'd'; YR = 'yr'; NONE = '—'; RAD = 'rad'; ACC = 'km·s⁻²'


@dataclass
class Step:
    name: str
    symbol: str
    value: Any
    units: str = ''
    equation: str = ''
    note: str = ''
    group: str = ''

    def display(self) -> str:
        return fmt_value(self.value, self.units)


def fmt_num(x: float, sig: int = 6) -> str:
    if x is None:
        return '—'
    if isinstance(x, (bool, np.bool_)):
        return str(bool(x))
    if isinstance(x, str):
        return x
    x = float(x)
    if x == 0:
        return '0'
    if not np.isfinite(x):
        return str(x)
    if abs(x) >= 1e6 or abs(x) < 1e-3:
        return f'{x:.{sig - 1}e}'
    return f'{x:.{sig}g}'


def fmt_value(v: Any, units: str = '') -> str:
    u = f' ({units})' if units and units != NONE else ''
    if isinstance(v, (list, tuple, np.ndarray)):
        arr = np.asarray(v, float)
        return '[' + ',  '.join(fmt_num(x) for x in arr.ravel()) + ']' + u
    return fmt_num(v) + u if not isinstance(v, str) else v + u


@dataclass
class Result:
    title: str
    label: str = ''                      # problem label shown in figure titles (e.g. "HW4 P1")
    inputs: dict = field(default_factory=dict)
    steps: list[Step] = field(default_factory=list)
    checks: list[str] = field(default_factory=list)       # quadrant / sanity checks performed
    warnings: list[str] = field(default_factory=list)
    scene: Any = None                    # aae532.scene.Scene (2D figure + 3D view)
    data: dict = field(default_factory=dict)              # raw numeric outputs for tests / presets
    scenes: dict = field(default_factory=dict)            # extra named Scenes (e.g. planet-centred inset)
    figs: dict = field(default_factory=dict)              # name -> callable(theme, user_name) -> matplotlib Figure

    def add(self, name, symbol, value, units='', equation='', note='', group='') -> Any:
        self.steps.append(Step(name, symbol, value, units, equation, note, group)); return value

    def get(self, symbol: str):
        for s in self.steps:
            if s.symbol == symbol:
                return s.value
        raise KeyError(symbol)

    def check(self, msg: str): self.checks.append(msg)
    def warn(self, msg: str): self.warnings.append(msg)

    def table(self) -> list[dict]:
        return [dict(Group=s.group, Quantity=s.name, Symbol=s.symbol, Value=fmt_value(s.value), Units=s.units,
                     Equation=s.equation, Note=s.note) for s in self.steps]
