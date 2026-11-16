"""Calendar utilities.

Ported verbatim from the verified orbitcore.py reference. Do not change formulas without a failing test.
"""

def julian_date(Y, M, Dd, hr=12.0):
    if M <= 2: Y -= 1; M += 12
    A = Y // 100; B = 2 - A + A // 4
    return int(365.25 * (Y + 4716)) + int(30.6001 * (M + 1)) + Dd + B - 1524.5 + hr / 24


# ---------------- additions (not part of the verified orbitcore.py) ----------------
import datetime as _dt
import numpy as np


def calendar_to_jd(Y: int, M: int, D: int, hour: float = 0.0, minute: float = 0.0, second: float = 0.0) -> float:
    """Julian date of a UT calendar date/time (0h UT => JD ends in .5; noon => .0)."""
    return julian_date(Y, M, D, hour + minute / 60 + second / 3600)


def jd_to_calendar(jd: float) -> tuple[int, int, int, int, int, float]:
    """(Y, M, D, hour, minute, second) UT from a Julian date (Meeus, Astronomical Algorithms ch. 7; Gregorian after 1582-10-15)."""
    jd = jd + 0.5; Z = int(np.floor(jd)); F = jd - Z
    if Z < 2299161: A = Z
    else:
        al = int((Z - 1867216.25) / 36524.25); A = Z + 1 + al - al // 4
    B = A + 1524; C = int((B - 122.1) / 365.25); Dd = int(365.25 * C); E = int((B - Dd) / 30.6001)
    day = B - Dd - int(30.6001 * E); month = E - 1 if E < 14 else E - 13; year = C - 4716 if month > 2 else C - 4715
    secs = F * 86400.0; h = int(secs // 3600); mi = int((secs - 3600 * h) // 60); s = secs - 3600 * h - 60 * mi
    if s > 59.9995: s = 0.0; mi += 1
    if mi == 60: mi = 0; h += 1
    return year, month, day, h, mi, s


def weekday_name(Y: int, M: int, D: int) -> str:
    return ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'][_dt.date(Y, M, D).weekday()]


def _nth_sunday(Y: int, M: int, n: int) -> int:
    """Day of month of the n-th Sunday (n = -1 for the last)."""
    if n > 0:
        first = _dt.date(Y, M, 1); off = (6 - first.weekday()) % 7; return 1 + off + 7 * (n - 1)
    nxt = _dt.date(Y + (M == 12), M % 12 + 1, 1); last = nxt - _dt.timedelta(days=1)
    return last.day - ((last.weekday() - 6) % 7)


def us_eastern_offset_hours(Y: int, M: int, D: int, hour: float = 12.0) -> int:
    """UT - ET in hours (5 for EST, 4 for EDT) using US rules: 2007+ second Sunday of March to first Sunday of November (2 am local);
    1987-2006 first Sunday of April to last Sunday of October."""
    if Y >= 2007: start = _dt.datetime(Y, 3, _nth_sunday(Y, 3, 2), 2); end = _dt.datetime(Y, 11, _nth_sunday(Y, 11, 1), 2)
    elif Y >= 1987: start = _dt.datetime(Y, 4, _nth_sunday(Y, 4, 1), 2); end = _dt.datetime(Y, 10, _nth_sunday(Y, 10, -1), 2)
    else: return 5
    t = _dt.datetime(Y, M, D, int(hour), int((hour % 1) * 60))
    return 4 if start <= t < end else 5


def et_to_ut(Y: int, M: int, D: int, hour: int, minute: int = 0) -> tuple[int, int, int, int, int, int]:
    """Convert a US Eastern civil time to UT. Returns (Y, M, D, hour, minute, offset_hours)."""
    off = us_eastern_offset_hours(Y, M, D, hour + minute / 60)
    t = _dt.datetime(Y, M, D, hour, minute) + _dt.timedelta(hours=off)
    return t.year, t.month, t.day, t.hour, t.minute, off
