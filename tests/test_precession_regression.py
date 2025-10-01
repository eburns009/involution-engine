import numpy as np

import spiceypy as spice
# Import the module so we can monkeypatch its apply_precession_iau2006
import services.spice.main as mod
from services.spice.main import convert_to_ecliptic_of_date_spice

def wrapdiff(a, b):
    # minimal angular difference in degrees
    return abs(((a - b + 540) % 360) - 180)

def _sun_geocentric_pos_j2000(et):
    # Apparent geocentric Sun vector in J2000 (km)
    # targ Sun(10) as seen from Earth(399)
    pos, _ = spice.spkpos("10", et, "J2000", "LT+S", "399")
    return np.array(pos)

def test_precession_step_is_required_for_1962(client, monkeypatch):
    """
    If we skip the J2000->mean-of-date precession, 1962 tropical longitudes shift by ~0.5°.
    This guards against regressions where ecliptic-of-date rotation is applied to a J2000 vector.
    """
    # 1962-07-03T04:33:00Z (Fort Knox golden)
    et = spice.str2et("1962-07-03T04:33:00Z")
    r_j2000 = _sun_geocentric_pos_j2000(et)

    # Correct pipeline: precess J2000 -> mean-of-date, then rotate by obliquity(date)
    lam_true = convert_to_ecliptic_of_date_spice(r_j2000, et)["longitude"]

    # Simulate the bug: disable precession (identity), keep everything else the same
    def _identity_precession(v, T):  # noqa: N802 (match original signature)
        return v
    monkeypatch.setattr(mod, "apply_precession_iau2006", _identity_precession)

    lam_no_prec = convert_to_ecliptic_of_date_spice(r_j2000, et)["longitude"]
    delta = wrapdiff(lam_no_prec, lam_true)

    # Precession between 1962 and J2000 ~0.52°
    assert 0.48 <= delta <= 0.58, f"Expected ~0.52°, got {delta:.4f}° (regression: precession step missing)"