"""Optional live GMAT check: run an exported script with ``GmatConsole`` in a subprocess and read its ReportFile.

Nothing here imports ``gmatpy``; if GMAT is not configured the caller just shows "GMAT not configured".
"""
from __future__ import annotations
import pathlib
import re
import subprocess
import tempfile


def find_console(folder: str | None) -> pathlib.Path | None:
    if not folder: return None
    base = pathlib.Path(folder)
    for sub in ('', 'bin'):
        for name in ('GmatConsole.exe', 'GmatConsole', 'GmatConsole.app/Contents/MacOS/GmatConsole'):
            p = (base / sub / name) if sub else (base / name)
            if p.is_file(): return p
    return None


def run_script(console: pathlib.Path, script: str, timeout: float = 120.0) -> dict:
    """Returns dict(ok, reports={filename: text}, log). Report files are redirected to a temporary folder."""
    tmp = pathlib.Path(tempfile.mkdtemp(prefix='orbitsim_gmat_'))
    names = re.findall(r"\.Filename\s*=\s*'([^']+)'", script)
    for n in names: script = script.replace(f"'{n}'", "'" + str(tmp / pathlib.Path(n).name).replace('\\', '/') + "'")
    sp = tmp / 'mission.script'; sp.write_text(script, encoding='utf-8')
    try:
        cp = subprocess.run([str(console), '--run', str(sp), '--exit'], capture_output=True, text=True, timeout=timeout, cwd=str(console.parent))
    except subprocess.TimeoutExpired:
        return dict(ok=False, error=f'GMAT did not finish within {timeout:.0f} s', reports={})
    reps = {pathlib.Path(n).name: (tmp / pathlib.Path(n).name).read_text(errors='replace') for n in names if (tmp / pathlib.Path(n).name).exists()}
    return dict(ok=cp.returncode == 0 and bool(reps), error='' if cp.returncode == 0 else f'GMAT exited with code {cp.returncode}', reports=reps, log=(cp.stdout or '')[-2000:])


def parse_report(text: str, columns: list[str]) -> list[dict]:
    """Rows of a GMAT ReportFile as dicts keyed by the column names (a UTCGregorian value spans four whitespace-separated tokens)."""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) < 2: return []
    rows = []
    for ln in lines[1:]:
        tok = ln.split(); row = {}; i = 0
        for c in columns:
            if c.endswith('Gregorian'): row[c] = ' '.join(tok[i:i + 4]); i += 4
            else:
                try: row[c] = float(tok[i])
                except (ValueError, IndexError): row[c] = None
                i += 1
        rows.append(row)
    return rows
