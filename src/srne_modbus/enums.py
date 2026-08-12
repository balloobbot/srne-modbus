"""Enumerated register codes.

Both maps are transcribed verbatim from the upstream plugin's ``scale`` dicts,
including their gaps: the charger-state map has no member for code 3. Upstream
renders an unlisted code as the string ``"Unknown"``; here it decodes to
``None``, which is how ``modbus_connection.model`` reports a code it cannot map.
"""

from __future__ import annotations

from enum import IntEnum


class ChargerState(IntEnum):
    """Charge-controller state (register 0x10B)."""

    CHARGER_OFF = 0
    QUICK_CHARGE = 1
    CONSTANT_VOLTAGE_CHARGE = 2
    FLOAT_CHARGE = 4
    RESERVED_1 = 5
    LITHIUM_BATTERY_ACTIVE = 6
    RESERVED_2 = 7


class RunMode(IntEnum):
    """Inverter run mode (register 0x210)."""

    POWER_UP_DELAY = 0
    WAITING_STATE = 1
    INITIALISATION = 2
    SOFT_START = 3
    MAINS_POWERED_OPERATION = 4
    INVERTER_POWERED_OPERATION = 5
    INVERTER_TO_MAINS = 6
    MAINS_TO_INVERTER = 7
    BATTERY_ACTIVE = 8
    SHUTDOWN_BY_USER = 9
    FAULT = 10
