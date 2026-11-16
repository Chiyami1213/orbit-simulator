"""Every HW/exam preset must reproduce its printed answers through the same adapters the app uses (rtol per Expect, default 2e-4)."""
import matplotlib
matplotlib.use('Agg')
import pytest
from aae532.presets.runner import all_presets, run_preset

CASES = [(mid, p, x) for mid, p in all_presets() for x in p.expected]


@pytest.mark.parametrize('mid,preset,x', CASES, ids=[f'{m}:{p.label.split(" — ")[0]}:{x.name}' for m, p, x in CASES])
def test_expected_value(mid, preset, x):
    _, rows = run_preset(mid, type(preset)(preset.label, preset.vals, [x], preset.consts, preset.moon_R))
    r = rows[0]
    assert r.ok, f'{preset.label} / {x.name}: got {r.got!r}, expected {r.expected!r} (rtol {r.rtol}) {r.error}'
