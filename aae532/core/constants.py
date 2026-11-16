"""Constants and angle helpers (course "Useful Constants" table, exam-rounded set, AU).

Ported verbatim from the verified orbitcore.py reference. Do not change formulas without a failing test.
"""
import numpy as np

D2R = np.pi / 180

R2D = 180 / np.pi

BODIES = {
    'Sun':     dict(mu=132712440017.99, R=695990,    a=None),
    'Moon':    dict(mu=4902.8005821478, R=1738.2,    a=384400,     e=0.0554),
    'Mercury': dict(mu=22032.080486418, R=2439.7,    a=57909101,   e=0.20563661),
    'Venus':   dict(mu=324858.59882646, R=6051.9,    a=108207284,  e=0.00676399),
    'Earth':   dict(mu=398600.4415,     R=6378.1363, a=149597898,  e=0.01673163),
    'Mars':    dict(mu=42828.314258067, R=3397,      a=227944135,  e=0.09336511),
    'Jupiter': dict(mu=126712767.8578,  R=71492,     a=778279959,  e=0.04853590),
    'Saturn':  dict(mu=37940626.061137, R=60268,     a=1427387908, e=0.05550825),
    'Uranus':  dict(mu=5794549.0070719, R=25559,     a=2870480873, e=0.04685740),
    'Neptune': dict(mu=6836534.0638793, R=25269,     a=4498337290, e=0.00895439),
    'Pluto':   dict(mu=981.600887707,   R=1162,      a=5907150229, e=0.24885238),
}

EXAM = {'Earth': dict(mu=4.0e5, R=6400), 'Moon': dict(mu=5000, R=2000 / 1), 'Mars': dict(mu=4.2e4, R=3400)}

AU = 149597870.7

def wrap360(x): return x % 360

def wrap180(x): return (x + 180) % 360 - 180


class ConstantSet:
    """Switchable constants: 'Course table' (BODIES) or 'Exam rounded' (EXAM overrides; Moon radius editable).

    Exam 1 uses R_moon = 2000 km, Exam 2 uses 1500 km. Bodies not in EXAM fall back to the course table.
    """

    def __init__(self, mode: str = 'Course table', moon_R: float = 2000.0):
        self.mode = mode; self.moon_R = moon_R

    @property
    def exam(self) -> bool:
        return self.mode == 'Exam rounded'

    def body(self, name: str) -> dict:
        b = dict(BODIES[name])
        if self.exam and name in EXAM:
            b.update(EXAM[name])
            if name == 'Moon':
                b['R'] = self.moon_R
        return b

    def mu(self, name: str) -> float: return self.body(name)['mu']
    def R(self, name: str) -> float: return self.body(name)['R']
