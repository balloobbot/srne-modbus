"""Fixtures: an SrneInverter over modbus-connection's in-memory mock backend.

Everything on this device is a holding register; there are no coils, no input
registers and no 32-bit values.
"""

from __future__ import annotations

import pytest
from modbus_connection.mock import MockModbusUnit

from srne_modbus import SrneInverter


def ascii_registers(text: str) -> list[int]:
    """Pack ASCII into 16-bit registers, two characters per register (hi, lo)."""
    if len(text) % 2:
        text += "\0"
    return [(ord(text[i]) << 8) | ord(text[i + 1]) for i in range(0, len(text), 2)]


SERIAL = "MSRNE12345"

# Raw holding-register words keyed by address; the decoded view is inline.
HOLDING: dict[int, int | list[int]] = {
    0x35: ascii_registers(SERIAL),
    # -- charge controller --
    0x100: 87,  # battery capacity -> 87 %
    0x101: 532,  # battery voltage -> 53.2 V
    0x102: 0xFFCE,  # battery current -> -5.0 A (signed)
    0x107: 3210,  # pv voltage 1 -> 321.0 V
    0x108: 45,  # pv current 1 -> 4.5 A
    0x109: 1445,  # pv power 1 -> 1445 W
    0x10B: 2,  # charger state -> constant voltage charge
    0x10E: 0xFC18,  # battery power -> -1000 W (signed)
    0x10F: 2980,  # pv voltage 2 -> 298.0 V
    0x110: 33,  # pv current 2 -> 3.3 A
    0x111: 983,  # pv power 2 -> 983 W
    # -- inverter --
    0x210: 5,  # run mode -> inverter powered operation
    0x213: 2301,  # grid voltage L1 -> 230.1 V
    0x214: 27,  # grid current L1 -> 2.7 A
    0x215: 4998,  # grid frequency L1 -> 49.98 Hz
    0x216: 2299,  # inverter voltage L1 -> 229.9 V
    0x217: 41,  # inverter current L1 -> 4.1 A
    0x218: 5001,  # inverter frequency L1 -> 50.01 Hz
    0x219: 38,  # load current L1 -> 3.8 A
    0x21E: 120,  # battery charge from mains -> 12.0 A
    0x220: 415,  # DC-DC temperature -> 41.5 °C
    0x221: 388,  # DC-AC temperature -> 38.8 °C
    0x222: 502,  # translator temperature -> 50.2 °C
    0x224: 210,  # battery charge from PV -> 21.0 A
}


@pytest.fixture
def srne(mock_modbus_unit: MockModbusUnit) -> SrneInverter:
    """An SrneInverter over the mock unit, preloaded with device values."""
    mock_modbus_unit.holding.update(HOLDING)
    return SrneInverter(mock_modbus_unit)
