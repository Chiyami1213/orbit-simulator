"""Drive the real Streamlit app headlessly: every page renders, and every preset loads through the UI without an exception."""
import pathlib
import pytest
from streamlit.testing.v1 import AppTest
from aae532.registry import MODULES
from aae532.presets.hw_problems import PRESETS

TIMEOUT = 120
APP = str(pathlib.Path(__file__).resolve().parent.parent / 'app.py')


def fresh():
    at = AppTest.from_file(APP, default_timeout=TIMEOUT); at.run(); return at


def assert_clean(at, where):
    assert not at.exception, f'{where}: {[e.value for e in at.exception]}'
    errs = [e.value for e in at.error]
    assert not errs, f'{where}: error banners {errs}'


@pytest.mark.parametrize('mid', list(MODULES))
def test_module_page_default(mid):
    at = fresh(); at.sidebar.radio(key='page').set_value(MODULES[mid].title).run(); assert_clean(at, MODULES[mid].title)


@pytest.mark.parametrize('page', ['Test cases', 'Julian date & time', 'Constants browser'])
def test_utility_pages(page):
    at = fresh(); at.sidebar.radio(key='page').set_value(page).run(); assert_clean(at, page)


CASES = [(mid, i, p.label) for mid, lst in PRESETS.items() for i, p in enumerate(lst)]


@pytest.mark.parametrize('mid,i,label', CASES, ids=[f'{m}:{l.split(" — ")[0]}' for m, i, l in CASES])
def test_preset_loads_in_ui(mid, i, label):
    at = fresh(); at.sidebar.radio(key='page').set_value(MODULES[mid].title).run()
    at.selectbox(key=f'preset_sel.{mid}').set_value(label).run()
    assert_clean(at, label)
