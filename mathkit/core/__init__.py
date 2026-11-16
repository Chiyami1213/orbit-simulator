"""Verified core.

Convenience re-exports. NOTE: the functions ``lambert``, ``hyperbola`` and ``flyby`` share a name with their
submodules, so they are deliberately *not* re-exported here (it would shadow the submodule). Import them as
``from mathkit.core.lambert import lambert`` etc.
"""
from .constants import D2R, R2D, BODIES, EXAM, AU, wrap360, wrap180, ConstantSet
from .kepler import (E_from_th, th_from_E, H_from_th, th_from_H, kepler_E, kepler_H,
                     time_since_periapsis, propagate)
from .conic import conic_from_rv_polar, r_of, gamma_of, v_of, state_to_conic_2d
from .fg import fg_theta, fg_E
from .frames import dcm_313, vnc_frame
from .elements import rv_from_elements, elements_from_rv
from .maneuvers import impulse_planar, apply_dv_vnc, intersect_conics
from .transfers import hohmann, bielliptic, plane_change
from .patched import escape_dv, capture_dv
from .lambert import lambert_minE, lambert_velocities, two_vector_transfer
from .timeutil import julian_date

__all__ = [
    'D2R', 'R2D', 'BODIES', 'EXAM', 'AU', 'wrap360', 'wrap180', 'ConstantSet',
    'E_from_th', 'th_from_E', 'H_from_th', 'th_from_H', 'kepler_E', 'kepler_H', 'time_since_periapsis', 'propagate',
    'conic_from_rv_polar', 'r_of', 'gamma_of', 'v_of', 'state_to_conic_2d', 'fg_theta', 'fg_E',
    'dcm_313', 'vnc_frame', 'rv_from_elements', 'elements_from_rv',
    'impulse_planar', 'apply_dv_vnc', 'intersect_conics', 'hohmann', 'bielliptic', 'plane_change',
    'escape_dv', 'capture_dv', 'lambert_minE', 'lambert_velocities', 'two_vector_transfer', 'julian_date',
]
