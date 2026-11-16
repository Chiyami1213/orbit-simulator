"""Orientation of the Milky Way / star sky maps (assets/textures/2k_stars*.jpg) in ICRF.

The maps are equirectangular in **galactic** coordinates: the galactic centre is the middle of the image, longitude l increases to the LEFT and
latitude b increases DOWNWARD (rows from the top). This was found by locating the eight brightest stars (Sirius, Arcturus, Canopus, Vega, Capella,
Procyon, Betelgeuse, Rigel): all of them sit on the brightest pixels of the map at exactly these positions (see tests).
    pixel x = (0.5 - l'/360) * W,   pixel y (from the top) = (0.5 + b/180) * H,   with l' = l wrapped to (-180, 180].
The viewer applies the same mapping, after rotating a direction from ICRF to galactic axes with the Hipparcos matrix below.
"""
from __future__ import annotations
import numpy as np

# ICRS -> galactic rotation (ESA 1997, Hipparcos vol. 1, eq. 1.5.11): rows are the galactic x, y, z axes expressed in ICRS
ICRS_TO_GAL = np.array([[-0.0548755604162154, -0.8734370902348850, -0.4838350155487132],
                        [+0.4941094278755837, -0.4448296299600112, +0.7469822444972189],
                        [-0.8676661490190047, -0.1980763734312015, +0.4559837761750669]])

STARS = {'Sirius': (101.2872, -16.7161), 'Arcturus': (213.9154, 19.1824), 'Canopus': (95.9880, -52.6957), 'Vega': (279.2347, 38.7837),
         'Capella': (79.1723, 45.9980), 'Procyon': (114.8255, 5.2250), 'Betelgeuse': (88.7929, 7.4071), 'Rigel': (78.6345, -8.2016), 'Polaris': (37.9546, 89.2641)}
GALACTIC_CENTER = (266.4051, -28.9362)       # RA, Dec (deg)
NORTH_GALACTIC_POLE = (192.8595, 27.1283)


def radec_to_vec(ra_deg: float, dec_deg: float) -> np.ndarray:
    ra, dec = np.radians(ra_deg), np.radians(dec_deg); return np.array([np.cos(dec) * np.cos(ra), np.cos(dec) * np.sin(ra), np.sin(dec)])


def vec_to_radec(v) -> tuple[float, float]:
    v = np.asarray(v, float) / np.linalg.norm(v); return float(np.degrees(np.arctan2(v[1], v[0])) % 360), float(np.degrees(np.arcsin(v[2])))


def to_galactic(v_icrs) -> tuple[float, float]:
    """(l, b) in degrees of an ICRS direction."""
    g = ICRS_TO_GAL @ (np.asarray(v_icrs, float) / np.linalg.norm(v_icrs)); return float(np.degrees(np.arctan2(g[1], g[0])) % 360), float(np.degrees(np.arcsin(g[2])))


def pixel(v_icrs, width: int, height: int) -> tuple[float, float]:
    """Pixel (x, y from the top) of an ICRS direction in the galactic sky maps."""
    l, b = to_galactic(v_icrs); lp = (l + 180) % 360 - 180
    return (0.5 - lp / 360.0) * width, (0.5 + b / 180.0) * height
