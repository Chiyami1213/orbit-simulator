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


# ---------------- time systems (additions; GMAT-compatible) ----------------
# TAI - UTC in seconds, effective from the given UTC calendar date (IERS Bulletin C; the last leap second was 2016-12-31).
LEAP_SECONDS = [((1972, 1, 1), 10), ((1972, 7, 1), 11), ((1973, 1, 1), 12), ((1974, 1, 1), 13), ((1975, 1, 1), 14), ((1976, 1, 1), 15),
                ((1977, 1, 1), 16), ((1978, 1, 1), 17), ((1979, 1, 1), 18), ((1980, 1, 1), 19), ((1981, 7, 1), 20), ((1982, 7, 1), 21),
                ((1983, 7, 1), 22), ((1985, 7, 1), 23), ((1988, 1, 1), 24), ((1990, 1, 1), 25), ((1991, 1, 1), 26), ((1992, 7, 1), 27),
                ((1993, 7, 1), 28), ((1994, 7, 1), 29), ((1996, 1, 1), 30), ((1997, 7, 1), 31), ((1999, 1, 1), 32), ((2006, 1, 1), 33),
                ((2009, 1, 1), 34), ((2012, 7, 1), 35), ((2015, 7, 1), 36), ((2017, 1, 1), 37)]
TT_MINUS_TAI = 32.184                    # s
A1_MINUS_TAI = 0.0343817                 # s (GMAT)
GMAT_MJD_OFFSET = 2430000.0              # GMAT ModJulian = JD - 2430000.0 (epoch 05 Jan 1941 12:00)
JD_J2000 = 2451545.0


def tai_minus_utc(jd_utc: float) -> float:
    """TAI - UTC (s) for a UTC Julian date; 10 s before 1972 (no rubber-second model)."""
    n = 10.0
    for (Y, M, D), s in LEAP_SECONDS:
        if jd_utc >= julian_date(Y, M, D, 0.0): n = float(s)
    return n


def utc_to_tai(jd_utc: float) -> float: return jd_utc + tai_minus_utc(jd_utc) / 86400.0
def tai_to_tt(jd_tai: float) -> float: return jd_tai + TT_MINUS_TAI / 86400.0
def tai_to_a1(jd_tai: float) -> float: return jd_tai + A1_MINUS_TAI / 86400.0


def tt_to_tdb(jd_tt: float) -> float:
    """TDB = TT + 0.001657 s sin(g), g = 357.53 deg + 0.98560028 deg/day (d = days since J2000); good to about 30 microseconds."""
    g = np.radians(357.53 + 0.98560028 * (jd_tt - JD_J2000))
    return jd_tt + (0.001657 * np.sin(g) + 0.000014 * np.sin(2 * g)) / 86400.0


def utc_to_tdb(jd_utc: float) -> float: return tt_to_tdb(tai_to_tt(utc_to_tai(jd_utc)))
def tdb_minus_utc(jd_utc: float) -> float: return (utc_to_tdb(jd_utc) - jd_utc) * 86400.0
def jd_to_modjulian(jd: float) -> float: return jd - GMAT_MJD_OFFSET
def modjulian_to_jd(mjd: float) -> float: return mjd + GMAT_MJD_OFFSET


_MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']


def format_gregorian(jd_utc: float) -> str:
    """GMAT UTCGregorian string, e.g. '27 Sep 2024 00:00:00.000'."""
    Y, M, D, h, mi, s = jd_to_calendar(jd_utc + 0.5e-3 / 86400.0)           # round to the millisecond
    return f'{D:02d} {_MON[M - 1]} {Y:04d} {h:02d}:{mi:02d}:{min(s, 59.999):06.3f}'


def parse_gregorian(text: str) -> float:
    """Parse '27 Sep 2024 00:00:00.000' (quotes allowed) to a UTC Julian date."""
    t = text.strip().strip("'\"").split()
    D, mon, Y, hms = int(t[0]), _MON.index(t[1][:3].title()) + 1, int(t[2]), t[3] if len(t) > 3 else '0:0:0'
    h, mi, s = (hms.split(':') + ['0', '0'])[:3]
    return calendar_to_jd(Y, mon, D, int(h), int(mi), float(s))
