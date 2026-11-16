"""Backup / restore / import of the user's data. Each test uses its own temporary data folder."""
import io
import json
import zipfile
import pytest
from mathkit.ui import backup, shell, api


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv('ORBSIM_HOME', str(tmp_path)); return tmp_path


def seed(home):
    shell.save_settings({'name': 'Test User', 'appearance': 'light'})
    (home / 'exports').mkdir(exist_ok=True); (home / 'exports' / 'a.png').write_bytes(b'png-bytes')
    (home / 'screenshots').mkdir(exist_ok=True); (home / 'screenshots' / 's.png').write_bytes(b'shot')


def make_zip(entries, manifest=True):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        if manifest: z.writestr('backup.json', json.dumps(dict(app='OrbSim', files=len(entries))))
        for n, d in entries.items(): z.writestr(n, d)
    return buf.getvalue()


def test_roundtrip_restores_deleted_data(home):
    seed(home); path = backup.create_backup()
    assert path.parent == home / 'backups' and path.suffix == '.zip'
    (home / 'settings.json').unlink(); (home / 'exports' / 'a.png').unlink()
    r = backup.restore_backup(path)
    assert r['restored'] == 3 and (home / 'exports' / 'a.png').read_bytes() == b'png-bytes' and shell.load_settings()['name'] == 'Test User'
    assert any('before restore' in b['name'] for b in backup.list_backups())          # a safety backup was made first


def test_backup_never_contains_caches_logs_or_other_backups(home):
    seed(home); (home / 'cache').mkdir(); (home / 'cache' / 'x').write_text('x'); (home / 'logs').mkdir(); (home / 'logs' / 'l.log').write_text('log')
    first = backup.create_backup(); second = backup.create_backup()
    for p in (first, second):
        names = zipfile.ZipFile(p).namelist(); assert all(n == 'backup.json' or n == 'settings.json' or n.startswith(('exports/', 'screenshots/')) for n in names), names


def test_import_from_anywhere_keeps_a_copy_and_restores(home):
    seed(home); data = backup.create_backup().read_bytes()
    for f in (home / 'settings.json', home / 'exports' / 'a.png'): f.unlink()
    r = backup.import_backup('my old backup.zip', data)
    assert r['restored'] == 3 and (home / 'backups' / r['imported']).is_file() and shell.load_settings()['appearance'] == 'light'


@pytest.mark.parametrize('entries', [{'../evil.txt': 'x'}, {'/abs.txt': 'x'}, {'exports/../../evil.txt': 'x'}, {'evil.exe': 'x'}, {'C:/evil.txt': 'x'}, {'cache/x': 'x'}])
def test_hostile_archives_are_rejected_and_write_nothing(home, entries):
    with pytest.raises(ValueError): backup.import_backup('bad.zip', make_zip(entries))
    assert not (home.parent / 'evil.txt').exists() and not (home / 'evil.exe').exists()


def test_not_a_backup_is_rejected(home):
    with pytest.raises(ValueError): backup.import_backup('x.zip', make_zip({'settings.json': '{}'}, manifest=False))
    with pytest.raises(ValueError): backup.import_backup('x.zip', b'this is not a zip')
    wrong = io.BytesIO()
    with zipfile.ZipFile(wrong, 'w') as z: z.writestr('backup.json', json.dumps(dict(app='Something Else')))
    with pytest.raises(ValueError): backup.import_backup('x.zip', wrong.getvalue())


def test_delete_only_inside_backups_folder(home):
    seed(home); name = backup.create_backup().name; (home / 'precious.zip').write_bytes(b'keep')
    backup.delete_backup('../precious.zip')                                           # only the file NAME is used: nothing outside backups/ can be removed
    assert (home / 'precious.zip').exists()
    backup.delete_backup(name); assert not any(b['name'] == name for b in backup.list_backups())


def test_api_actions_report_errors_cleanly(home):
    seed(home)
    assert api.ROUTES['backup_create']({})['ok']
    assert api.ROUTES['backup_restore']({'name': 'missing.zip'})['ok'] is False
    import base64
    bad = api.ROUTES['backup_import']({'filename': 'x.zip', 'data': base64.b64encode(b'nope').decode()}); assert bad['ok'] is False and 'zip' in bad['error']


def test_old_data_folder_is_renamed_on_first_start(tmp_path, monkeypatch):
    import sys
    from mathkit.ui import shell
    if sys.platform == 'darwin': pytest.skip('macOS keeps the folder under the user library')
    for k in ('ORBSIM_HOME', 'ORBIT_SIMULATOR_HOME'): monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv('APPDATA', str(tmp_path)); monkeypatch.setenv('XDG_DATA_HOME', str(tmp_path))
    old = tmp_path / shell.LEGACY_NAME; old.mkdir(); (old / 'settings.json').write_text('{"a": 1}', encoding='utf-8')
    home = shell.appdata_dir()
    assert home == tmp_path / 'OrbSim' and (home / 'settings.json').exists() and not old.exists()


def test_backups_made_under_the_old_name_still_restore(tmp_path, monkeypatch):
    from mathkit.ui import backup
    assert 'Orbit Simulator' in backup.APP_NAMES and 'OrbSim' in backup.APP_NAMES
