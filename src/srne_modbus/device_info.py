"""The 20-register serial-number block.

The block is declared at offset 0 and placed with ``base_offset``, because the
upstream plugin looks for it at two different addresses.
"""

from __future__ import annotations

from modbus_connection.model import string

from .model import SrneComponent

SERIAL_ADDRESS = 0x35
SERIAL_ADDRESS_FALLBACK = 0x300


class DeviceInformation(SrneComponent):
    """A serial-number block, placed at whichever address answers."""

    serial_number = string(0, 20)
