"""JPL DE-series SPK ephemeris through the optional ``jplephem`` package (MIT licence). Used for DE440s (1849-2150, about 32 MB)."""
from __future__ import annotations
import numpy as np

# NAIF chains from the solar-system barycentre (0) to each body
ALT = {'Mercury': [(0, 1)], 'Venus': [(0, 2)], 'Mars': [(0, 4)]}          # barycentre only (the planet's moons displace it by < 1 km)
CHAINS = {'Sun': [(0, 10)], 'Mercury': [(0, 1), (1, 199)], 'Venus': [(0, 2), (2, 299)], 'Earth': [(0, 3), (3, 399)], 'Moon': [(0, 3), (3, 301)],
          'Mars': [(0, 4), (4, 499)], 'Jupiter': [(0, 5)], 'Saturn': [(0, 6)], 'Uranus': [(0, 7)], 'Neptune': [(0, 8)], 'Pluto': [(0, 9)],
          'SSB': []}


class SPKEphemeris:
    def __init__(self, path: str):
        from jplephem.spk import SPK
        self.kernel = SPK.open(str(path)); self.path = str(path)
        have = {(int(s.center), int(s.target)) for s in self.kernel.segments}
        self.chains = {}
        for b, c in CHAINS.items():
            for cand in (c, ALT.get(b)):
                if cand is not None and all(pair in have for pair in cand): self.chains[b] = cand; break
        self.bodies = tuple(b for b in self.chains if b != 'SSB')
        tag = 'DE440s' if 'de440' in self.path.lower() else 'SPK kernel'
        self.name = f'{tag} (JPL, via jplephem)'; self.accuracy = 'metre-level for the planets; the JPL development ephemeris'
        first = self.kernel.segments[0]; self.valid = (first.start_jd, first.end_jd)

    def _barystate(self, body: str, jd: float):
        r = np.zeros(3); v = np.zeros(3)
        for pair in self.chains[body]:
            p, vv = self.kernel[pair].compute_and_differentiate(jd)
            r += p; v += vv / 86400.0
        return r, v

    def _barypos(self, body: str, jd: float):
        r = np.zeros(3)
        for pair in self.chains[body]: r += self.kernel[pair].compute(jd)
        return r

    def position(self, body: str, jd_tdb: float, center: str = 'SSB'):
        r = self._barypos(body, jd_tdb)
        return r if center == 'SSB' else r - self._barypos(center, jd_tdb)

    def state(self, body: str, jd_tdb: float, center: str = 'SSB'):
        r, v = self._barystate(body, jd_tdb)
        if center not in ('SSB',):
            rc, vc = self._barystate(center, jd_tdb); r = r - rc; v = v - vc
        return r, v
