"""The AC side: grid, inverter output, load and temperatures (0x210-0x224)."""

from __future__ import annotations

from modbus_connection.model import enum

from .enums import RunMode
from .model import SrneComponent, current, frequency, temperature, voltage


class Inverter(SrneComponent):
    """Grid and inverter AC measurements, charge currents and temperatures."""

    run_mode = enum(0x210, RunMode)

    grid_voltage_meter_l1 = voltage(0x213)
    grid_current_l1 = current(0x214)
    grid_frequency_l1 = frequency(0x215)

    inverter_voltage_meter_l1 = voltage(0x216)
    inverter_current_l1 = current(0x217)
    inverter_frequency_l1 = frequency(0x218)

    load_current_l1 = current(0x219)

    battery_charge_mains = current(0x21E)
    """Battery charging current drawn from the mains."""

    dc_dc_temperature = temperature(0x220)
    dc_ac_temperature = temperature(0x221)
    translator_temperature = temperature(0x222)
    """Transformer temperature; the upstream name's spelling is kept for stability."""

    battery_charge_pv = current(0x224)
    """Battery charging current supplied by PV."""
