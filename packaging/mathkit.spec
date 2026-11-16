# -*- mode: python ; coding: utf-8 -*-
# Build:  python -m PyInstaller packaging/mathkit.spec --noconfirm --distpath build_out/dist --workpath build_out/build
import pathlib
import plotly
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

root = pathlib.Path(SPECPATH).parent
plotly_js = pathlib.Path(plotly.__file__).parent / 'package_data' / 'plotly.min.js'

datas = [(str(root / 'mathkit' / 'ui' / 'web'), 'mathkit/ui/web'),
         (str(plotly_js), 'mathkit/ui/web/vendor')]                 # bundled so the 3-D plots work offline
datas += collect_data_files('webview')
# matplotlib loads its output backends dynamically, so PyInstaller cannot see them: list them explicitly
hidden = collect_submodules('webview') + collect_submodules('mathkit') + [
    'matplotlib.backends.backend_agg', 'matplotlib.backends.backend_svg', 'matplotlib.backends.backend_pdf']

a = Analysis([str(root / 'run.py')], pathex=[str(root)], datas=datas, hiddenimports=hidden,
             excludes=['scipy', 'tkinter', 'pytest', 'IPython', 'notebook', 'PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'streamlit', 'pyflakes'])
pyz = PYZ(a.pure)
import os
import sys
ICON = str(root / 'packaging' / ('icon.icns' if sys.platform == 'darwin' else 'icon.ico'))
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='OrbitSimulator', console=False, icon=ICON if os.path.exists(ICON) else None)
coll = COLLECT(exe, a.binaries, a.datas, name='OrbitSimulator')
if sys.platform == 'darwin':
    app = BUNDLE(coll, name='Orbit Simulator.app', icon=ICON if os.path.exists(ICON) else None, bundle_identifier='io.github.chiyami1213.orbit-simulator', version='1.0.0',
                 info_plist={'CFBundleDisplayName': 'Orbit Simulator', 'NSHighResolutionCapable': True, 'LSApplicationCategoryType': 'public.app-category.education'})
