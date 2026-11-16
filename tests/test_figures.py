"""Every preset renders in 2-D (no label overlaps) and 3-D (HTML builds, animation data is finite)."""
import json, re
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pytest
from mathkit.presets.runner import all_presets, run_preset
from mathkit.plots2d.render import render
from mathkit.view3d.animate import build_html, sample_tracks

PRESETS = [(mid, p) for mid, p in all_presets()]
IDS = [f'{m}:{p.label.split(" — ")[0]}' for m, p in PRESETS]


def scenes(res):
    yield 'main', res.scene
    for k, sc in res.scenes.items(): yield k, sc


@pytest.mark.parametrize('mid,preset', PRESETS, ids=IDS)
@pytest.mark.parametrize('theme', ['light', 'dark'])
def test_2d_no_label_overlap(mid, preset, theme):
    res, _ = run_preset(mid, preset)
    for name, sc in scenes(res):
        fig = render(sc, theme, 'Test User')
        try:
            assert fig.label_overlaps == 0, f'{preset.label} [{name}, {theme}]: {fig.label_overlaps} overlapping label pairs of {fig.n_labels}'
        finally:
            plt.close(fig)


@pytest.mark.parametrize('mid,preset', PRESETS, ids=IDS)
def test_3d_builds_and_frames_are_finite(mid, preset):
    res, _ = run_preset(mid, preset)
    for name, sc in scenes(res):
        html = build_html(sc, 'dark', 'Test User', n_frames=60)
        assert '<div id="plot"' in html or 'id="plot"' in html
        if sc.tracks:
            d = sample_tracks(sc, 60)
            for tr in d['tracks']:
                assert np.all(np.isfinite(np.array(tr['xyz'], float))), f'{preset.label}: non-finite animation positions'
