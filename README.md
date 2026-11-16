# AAE 532 Orbit Toolkit

Python app for the recurring Purdue AAE 532 (Orbit Mechanics, Bate–Mueller–White) problem types: step-by-step results tables,
annotated Cartesian 2-D figures (matplotlib) and an interactive 3-D animation (Plotly), in a Streamlit UI.

    pip install -r requirements.txt
    streamlit run app.py

* `aae532/core/` – verified math, ported without formula changes from `orbitcore.py` (173 regression checks in `tests/test_hw.py`).
* `aae532/modules/` – the 12 problem modules (N-body, two-body, conics, Kepler/f&g, hyperbolas, 3-D elements, impulses,
  transfers, plane change, patched conics, gravity assist, Lambert).
* `aae532/presets/` – every HW/exam problem that has printed answers, run against the same code path as the UI (also the *Test cases* page).
* `tests/` – `pytest` (core, presets, figures with label-overlap checks, headless UI). The slow UI suite: `pytest tests/test_app.py`.

Known errors in the solution PDFs are listed in `BUILD_PROMPT.md` §9; the tests use the corrected values.
