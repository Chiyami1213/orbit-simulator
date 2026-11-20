"""Backup, restore and import of the user's data (settings, exports, screenshots).

A backup is a zip file with a ``backup.json`` manifest. Restoring/importing validates the archive (manifest, no path escaping, size cap) and only
writes to the three known locations; before anything is overwritten a safety backup of the current data is made automatically.
Backups live in ``<app data>/backups``; an imported file is copied there first, so it appears in the list like any other backup.
"""
from __future__ import annotations
import datetime
import io
import json
import pathlib
import re
import zipfile
from . import shell

ALLOWED_FILES = ('settings.json',)
ALLOWED_DIRS = ('exports/', 'screenshots/', 'designs/')
MAX_UNCOMPRESSED = 1_500_000_000                  # refuse archives that expand beyond ~1.5 GB (zip bombs)
APP = 'OrbSim'
APP_NAMES = ('OrbSim', 'Orbit Simulator')            # backups made before the rename carry the old name and still restore


def backups_dir() -> pathlib.Path:
    return shell.folder('backups')


def _allowed(name: str) -> bool:
    return name == 'backup.json' or name in ALLOWED_FILES or name.startswith(ALLOWED_DIRS)


def _safe_member(name: str) -> bool:
    p = pathlib.PurePosixPath(name.replace('\\', '/'))
    return not p.is_absolute() and '..' not in p.parts and not re.match(r'^[A-Za-z]:', name)


def create_backup(label: str = 'backup') -> pathlib.Path:
    """Zip settings.json, exports/ and screenshots/ into backups/OrbSim <label> <timestamp>.zip."""
    home = shell.appdata_dir(); stamp = datetime.datetime.now().strftime('%Y-%m-%d %H-%M-%S')
    out = shell.unique_path(backups_dir(), f'{APP} {label} {stamp}', 'zip'); count = 0
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for f in ALLOWED_FILES:
            if (home / f).is_file(): z.write(home / f, f); count += 1
        for d in ALLOWED_DIRS:
            for p in sorted((home / d.rstrip('/')).rglob('*')):
                if p.is_file(): z.write(p, d + p.relative_to(home / d.rstrip('/')).as_posix()); count += 1
        z.writestr('backup.json', json.dumps(dict(app=APP, created=stamp, files=count), indent=1))
    return out


def list_backups() -> list[dict]:
    out = []
    for p in sorted(backups_dir().glob('*.zip'), key=lambda x: x.stat().st_mtime, reverse=True):
        info = dict(name=p.name, size=p.stat().st_size, modified=datetime.datetime.fromtimestamp(p.stat().st_mtime).strftime('%Y-%m-%d %H:%M'), files=None)
        try:
            with zipfile.ZipFile(p) as z: info['files'] = json.loads(z.read('backup.json')).get('files')
        except Exception:
            info['invalid'] = True
        out.append(info)
    return out


def _validate(z: zipfile.ZipFile) -> None:
    try:
        meta = json.loads(z.read('backup.json'))
    except Exception:
        raise ValueError('this file is not an OrbSim backup (no manifest)')
    if meta.get('app') not in APP_NAMES: raise ValueError('this file is not an OrbSim backup')
    total = 0
    for i in z.infolist():
        if i.is_dir(): continue
        if not _safe_member(i.filename): raise ValueError(f'unsafe path in backup: {i.filename}')
        if not _allowed(i.filename): raise ValueError(f'unexpected file in backup: {i.filename}')
        total += i.file_size
    if total > MAX_UNCOMPRESSED: raise ValueError('backup is too large')


def restore_backup(path: pathlib.Path) -> dict:
    """Validate then restore. A safety backup of the current data is created first. Returns a summary."""
    with zipfile.ZipFile(path) as z:
        _validate(z)
        safety = create_backup('before restore'); home = shell.appdata_dir(); n = 0
        for i in z.infolist():
            if i.is_dir() or i.filename == 'backup.json': continue
            target = (home / i.filename).resolve()
            if home.resolve() not in target.parents: raise ValueError(f'unsafe path in backup: {i.filename}')
            target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(z.read(i)); n += 1
    return dict(restored=n, safety=safety.name)


def import_backup(filename: str, data: bytes) -> dict:
    """Import a backup file chosen by the user (any location): validate, keep a copy in backups/, then restore it."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z: _validate(z)
    except zipfile.BadZipFile:
        raise ValueError('this file is not a zip archive')
    stem = re.sub(r'[^\w .()-]+', '_', pathlib.Path(filename).stem)[:80] or 'imported'
    kept = shell.unique_path(backups_dir(), stem + ' (imported)', 'zip'); kept.write_bytes(data)
    return dict(restore_backup(kept), imported=kept.name)


def delete_backup(name: str) -> None:
    p = (backups_dir() / pathlib.PurePosixPath(name).name).resolve()
    if p.parent != backups_dir().resolve() or p.suffix != '.zip': raise ValueError('not a backup file')
    p.unlink(missing_ok=True)
