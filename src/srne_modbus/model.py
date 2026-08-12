"""SRNE-specific presets over the ``modbus_connection.model`` framework.

Everything SRNE exposes lives in the holding-register space (FC03) and every
value is a single 16-bit word; the upstream plugin declares no 32-bit registers,
so its ``order32`` word order never applies here.

The upstream plugin's entity descriptions default to an *unsigned* 16-bit read
(``REGISTER_U16``), the opposite of ``modbus_connection.model``'s signed
default, so the helpers below spell ``signed`` out at every call site.
"""

from __future__ import annotations

from modbus_connection.model import Component, NumberField, gauge, integer

# The upstream plugin declares ``block_size=100``: it never asks the inverter
# for a window wider than 100 registers.
MAX_READ_SPAN = 100


class SrneComponent(Component):
    """An SRNE sub-system: holding registers, capped at the plugin's read width."""

    max_span = MAX_READ_SPAN


def voltage(address: int) -> NumberField[float]:
    """An unsigned 0.1-scaled voltage register (V)."""
    return gauge(address, 0.1, signed=False, unit="V")


def current(address: int, *, signed: bool = False) -> NumberField[float]:
    """A 0.1-scaled current register (A)."""
    return gauge(address, 0.1, signed=signed, unit="A")


def frequency(address: int) -> NumberField[float]:
    """An unsigned 0.01-scaled frequency register (Hz)."""
    return gauge(address, 0.01, signed=False, unit="Hz")


def temperature(address: int) -> NumberField[float]:
    """An unsigned 0.1-scaled temperature register (°C)."""
    return gauge(address, 0.1, signed=False, unit="°C")


def power(address: int, *, signed: bool = False) -> NumberField[int]:
    """An unscaled power register (W)."""
    return integer(address, signed=signed, unit="W")
