"""The DC side: battery and the two PV inputs (registers 0x100-0x111)."""

from __future__ import annotations

from modbus_connection.model import enum, integer

from .enums import ChargerState
from .model import SrneComponent, current, power, voltage


class ChargeController(SrneComponent):
    """Battery state and PV input measurements."""

    battery_capacity_charge = integer(0x100, signed=False, unit="%")
    """Battery state of charge."""

    battery_voltage = voltage(0x101)
    battery_current = current(0x102, signed=True)
    """Battery current; negative while discharging."""

    pv_voltage_1 = voltage(0x107)
    pv_current_1 = current(0x108)
    pv_power_1 = power(0x109)

    charger_state = enum(0x10B, ChargerState)

    battery_power = power(0x10E, signed=True)
    """Battery power; negative while discharging."""

    pv_voltage_2 = voltage(0x10F)
    pv_current_2 = current(0x110)
    pv_power_2 = power(0x111)
