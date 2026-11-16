"""pytest setup: tests must never touch the real %APPDATA%\\OrbSim folder, and no cache folders are created in the repository."""
import os
import sys
import tempfile

_HOME = os.path.join(tempfile.gettempdir(), 'orbsim-tests')
os.environ['ORBSIM_HOME'] = _HOME
os.environ.setdefault('MPLCONFIGDIR', os.path.join(_HOME, 'matplotlib'))
sys.pycache_prefix = os.path.join(_HOME, 'pycache')
