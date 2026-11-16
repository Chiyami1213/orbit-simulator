"""Run presets through the same adapters as the app and compare with the expected values."""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from ..core.constants import ConstantSet
from ..registry import MODULES, ModuleSpec, Preset
from ..results import Result
from .hw_problems import PRESETS


def defaults(spec: ModuleSpec) -> dict:
    return {f.key: f.default for f in spec.fields}


def full_vals(spec: ModuleSpec, preset: Preset, label: str = '') -> dict:
    v = defaults(spec); v.update(preset.vals); v['_label'] = label or preset.label.split(' — ')[0]; return v


def constants_for(preset: Preset) -> ConstantSet:
    return ConstantSet(preset.consts, preset.moon_R)


@dataclass
class Row:
    name: str
    got: float | None
    expected: float
    rtol: float
    ok: bool
    error: str = ''


def run_preset(module_id: str, preset: Preset) -> tuple[Result | None, list[Row]]:
    spec = MODULES[module_id]
    res = spec.run(full_vals(spec, preset), constants_for(preset))
    rows = []
    for x in preset.expected:
        try:
            got = float(x.get(res)); ok = abs(got - x.value) <= x.rtol * abs(x.value)
            rows.append(Row(x.name, got, x.value, x.rtol, bool(ok)))
        except Exception as ex:                      # an extractor failing is a test failure, reported with its message
            rows.append(Row(x.name, None, x.value, x.rtol, False, f'{type(ex).__name__}: {ex}'))
    return res, rows


def all_presets():
    for mid, lst in PRESETS.items():
        for p in lst:
            yield mid, p
