"""
The EQ in Hz and dB: kaiDAW's four-band EQ takes normalised values, which mean
20 Hz to 20 kHz, -20 to +20 dB and Q 0.1 to 4, each spread linearly.
"""

from __future__ import annotations

import pytest

from pypulang.sounds import eq


def test_a_shelf_is_set_in_hz_and_db():
    device = eq(high=(2500, -7))
    assert device.identifier == "4bandEq"
    assert device.params["High-shelf freq"] == pytest.approx((2500 - 20) / 19980)
    assert device.params["High-shelf gain"] == pytest.approx(13 / 40)
    assert "High-shelf Q" not in device.params and "Low-shelf gain" not in device.params


def test_a_peak_can_give_its_q():
    device = eq(mid=(400, 3, 0.7))
    assert device.params["Mid Q 1"] == pytest.approx(0.6 / 3.9)


@pytest.mark.parametrize(
    ("band", "message"),
    [((50000, -3), "50000 Hz is outside 20 to 20000"), ((3000, -30), "-30 dB is outside")],
)
def test_out_of_range_is_named(band, message):
    with pytest.raises(ValueError, match=message):
        eq(high=band)
